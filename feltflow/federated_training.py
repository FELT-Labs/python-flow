import json
import time
from typing import Dict, List

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

    def _local_jobs(self, algocustomdata: dict):
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

    def latest_model(self, account):
        """Get the latest model from aggregation or return initial model."""
        if self.iterations_data:
            data = self.iterations_data[-1]["aggregation"].get_file("model", account)
            return json.loads(data.decode("utf-8"))

        return self.algocustomdata

    def run(self, account: LocalAccount, iterations: int = 1):
        for i in range(iterations):
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
            while True:
                stats = [c.check_status(account) for c in trainings]
                print("stats", stats)
                if all(map(lambda x: x == "finished", stats)):
                    break

                if any(map(lambda x: x == "failed", stats)):
                    raise Exception("Some local training failed")

                time.sleep(5)

            # Aggregate with nonce trick
            nonce = CustomDataServiceProvider.get_nonce()
            url_nonce = str(nonce + 1000)
            urls = [c.get_file_url("model", account, url_nonce) for c in trainings]
            aggregation_data = {"model_urls": urls}
            # Aggregation job and start aggregation
            iteration["aggregation"] = ComputeJob(
                self.ocean,
                [self.algorithm_config["emptyDataset"]],
                self.algorithm_config["aggregation"],
                aggregation_data,
            )
            iteration["aggregation"].start(account, str(nonce))
            while iteration["aggregation"].check_status(account) != "finished":
                time.sleep(5)

            print("Finished with outputs:", iteration["aggregation"].get_outputs())
            print(iteration["aggregation"].get_file("model", account))
