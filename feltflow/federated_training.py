import json
import time
from typing import Any, Dict, List

from brownie.network.account import LocalAccount
from ocean_lib.ocean.ocean import Ocean

from feltflow.comput_job import ComputeJob
from feltflow.ocean.data_service_provider import CustomDataServiceProvider


class FederatedTraining:
    """Class for running the federated algorithms."""

    def __init__(
        self,
        ocean: Ocean,
        dataset_dids: List[str],
        algorithm_config: Dict[str, str],
        algocustomdata: dict,
    ):
        self.ocean = ocean
        self.algocustomdata = algocustomdata
        self.dataset_dids = dataset_dids
        self.algorithm_config = algorithm_config
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
            data = self.iterations_data[-1]["aggregation"].get_file("model", account)
            return json.loads(data.decode("utf-8"))

        return self.algocustomdata

    def run_aggregation(
        self, local_trainings: List[ComputeJob], account: LocalAccount
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
            [self.algorithm_config["emptyDataset"]],
            self.algorithm_config["aggregation"],
            aggregation_data,
        )
        aggregation.start(account, str(nonce))

        return aggregation

    def run(self, account: LocalAccount, iterations: int = 1) -> None:
        """Run the federated training for specified number of iterations.

        Args:
            account: account used for starting the compute jobs
            iterations: number of iterations to be executed
        """
        for _ in range(iterations):
            # Get latest algocustomdata (model)
            trainings = self._local_jobs(self.latest_model(account))
            iteration = {
                "training": trainings,
                "aggregation": None,
            }
            self.iterations_data.append(iteration)

            # Start local training
            for compute in trainings:
                compute.start(account)

            # Wait for local training finish
            self._wait_for_compute(trainings, account)

            # Aggregation job and start aggregation
            iteration["aggregation"] = self.run_aggregation(trainings, account)

            # Wait for aggregation to finish
            self._wait_for_compute([iteration["aggregation"]], account)

            print("Finished with outputs:", iteration["aggregation"].get_outputs())
            print(iteration["aggregation"].get_file("model", account))

    def _local_jobs(self, algocustomdata: dict) -> List[ComputeJob]:
        """Initialize local training jobs for each dataset.

        Args:
            algocustomdata: model definition used for local training
        """
        return [
            ComputeJob(
                self.ocean,
                [did],
                self.algorithm_config["training"],
                algocustomdata,
            )
            for did in self.dataset_dids
        ]

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
