import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

from brownie.network.account import LocalAccount
from ocean_lib.ocean.ocean import Ocean

from feltflow.cloud_storage import CloudStorage
from feltflow.comput_job import ComputeJob
from feltflow.cryptography import encrypt_nacl
from feltflow.ocean.data_service_provider import CustomDataServiceProvider


class FederatedTraining:
    """Class for running the federated algorithms."""

    def __init__(
        self,
        ocean: Ocean,
        storage: CloudStorage,
        public_key: str,
        name: str,
        dataset_dids: List[str],
        algorithm_config: Dict[str, Any],
        algocustomdata: dict,
    ):
        assert len(dataset_dids) >= 1, "No datasets provided for training"

        self.ocean = ocean
        self.storage = storage
        self.public_key = public_key
        self.algocustomdata = algocustomdata
        self.dataset_dids = dataset_dids
        self.algorithm_config = algorithm_config
        self.name = name
        self.type = "solo" if len(dataset_dids) == 1 else "multi"
        self.nonce = None

        self.iterations_data = []
        # Run this just to test compatibility of data and algorithms:
        self._local_jobs(self.algocustomdata)

    def latest_model(self, account: LocalAccount) -> Dict[str, Any]:
        """Get the latest model from aggregation or return initial model.

        Args:
            account: account of user who started the training
        """
        if self.iterations_data:
            data = self.iterations_data[-1]["final_job"].get_file("model", account)
            model = json.loads(data.decode("utf-8"))
            if self.type == "multi":
                model["seeds"] = self.iterations_data[-1]["seeds"]
            return model

        return self.algocustomdata

    def run_aggregation(
        self, round: str, local_trainings: List[ComputeJob], account: LocalAccount
    ) -> ComputeJob:
        """Run aggregation of provided local trainings.

        Args:
            local_trainings: list of local trainings to be aggregated
            account: account used for aggregation

        Returns:
            new compute job of the aggregation
        """
        # Nonce trick - urls have higher nonce that compute job start
        nonce = CustomDataServiceProvider.get_nonce()
        url_nonce = str(nonce + 1000)

        urls = [c.get_file_url("model", account, url_nonce) for c in local_trainings]
        aggregation_data = {"model_urls": urls}

        # Create aggregation job and start aggregation
        aggregation = ComputeJob(
            self.ocean,
            [self.algorithm_config["assets"]["emptyDataset"]],
            self.algorithm_config["assets"]["aggregation"],
            aggregation_data,
        )
        job_info, auth_token = aggregation.start(account, str(nonce))

        # Store job in FELT cloud
        self.storage.add_aggregation(
            round,
            encrypt_nacl(auth_token, self.public_key),
            [c.did for c in local_trainings],
            job_info,
        )

        return aggregation

    def run(self, account: LocalAccount, iterations: int = 1) -> None:
        """Run the federated training for specified number of iterations.

        Args:
            account: account used for starting the compute jobs
            iterations: number of iterations to be executed
        """
        # Init job in FELT storage
        self.storage.create_job()

        for iter in range(iterations):
            # Get latest algocustomdata (model)
            trainings, seeds = self._local_jobs(self.latest_model(account))
            iteration = {
                "training": trainings,
                "seeds": seeds,
                "aggregation": None,
                "final_job": None,
            }
            self.iterations_data.append(iteration)

            # Start local training
            for compute, seed in zip(trainings, seeds):
                job_info, auth_token = compute.start(account)
                # Store job in FELT cloud
                self.storage.add_local_training(
                    str(iter),
                    seed,
                    encrypt_nacl(auth_token, self.public_key),
                    compute.did,
                    job_info,
                )

            # Wait for local training finish
            self._wait_for_compute(trainings, account)

            if self.type == "multi":
                # Aggregation job and start aggregation
                iteration["aggregation"] = self.run_aggregation(
                    str(iter), trainings, account
                )
                # Wait for aggregation to finish
                self._wait_for_compute([iteration["aggregation"]], account)
                iteration["final_job"] = iteration["aggregation"]
            else:
                iteration["final_job"] = iteration["training"][0]

            print("Finished with outputs:")
            print(iteration["final_job"].get_outputs())
            print("Model data:\n", self.latest_model(account))

    def _local_jobs(self, algocustomdata: dict) -> Tuple[List[ComputeJob], List[int]]:
        """Initialize local training jobs for each dataset.

        Args:
            algocustomdata: model definition used for local training
        """
        seeds = [self._get_seed() for _ in self.dataset_dids]
        jobs = []
        for did, seed in zip(self.dataset_dids, seeds):
            algocustomdata["seed"] = seed
            jobs.append(
                ComputeJob(
                    self.ocean,
                    [did],
                    self.algorithm_config["assets"]["training"],
                    algocustomdata,
                )
            )
        return jobs, seeds

    def _wait_for_compute(self, compute_jobs: List[ComputeJob], account: LocalAccount):
        """Wait for all compute jobs to finish."""
        while True:
            stats = [c.check_status(account) for c in compute_jobs]
            print("Stats", stats)

            if any(map(lambda x: x == "failed", stats)):
                raise Exception(f"Some compute job failed: {stats}")

            if all(map(lambda x: x == "finished", stats)):
                break

            time.sleep(5)

    def _timestamp(self):
        return int(datetime.now().timestamp() * 1000)

    def _get_seed(self) -> int:
        return int.from_bytes(os.urandom(1), "big") if self.type == "multi" else 0
