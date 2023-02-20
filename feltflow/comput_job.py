from decimal import Decimal

from brownie.network.account import LocalAccount
from ocean_lib.data_provider.data_service_provider import DataServiceProvider
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.ocean.ocean import Ocean
from requests import PreparedRequest

from feltflow.helpers import get_valid_until_time, pay_for_compute_service
from feltflow.subgraph import get_access_details


class ComputeJob:
    """Class providing all functions for working with compute job."""

    def __init__(
        self,
        ocean: Ocean,
        dataset_dids: list[str],
        algorithm_did: str,
        algocustomdata: dict,
    ):
        self.ocean = ocean
        self.algocustomdata = algocustomdata
        self.datasets = [ocean.assets.resolve(did) for did in dataset_dids]
        self.algorithm = ocean.assets.resolve(algorithm_did)

        # TODO: Check service types and compatibility
        self.compute_service = self.datasets[0].services[0]
        self.algo_service = self.algorithm.services[0]

        # TODO: Add better selection of compute environment
        self.compute_env = ocean.compute.get_c2d_environments(
            self.compute_service.service_endpoint
        )[0]

        self.state = "init"

    def start(self, account: LocalAccount):
        assert self.state == "init", f"Compute job already in state {self.state}"

        # Add access details to dataset and algo DDOs
        for dataset in self.datasets:
            dataset.access_details = get_access_details(
                self.compute_service, self.ocean.config["NETWORK_NAME"], account.address
            )

        self.algorithm.access_details = get_access_details(
            self.algo_service, self.ocean.config["NETWORK_NAME"], account.address
        )

        data_input = [
            ComputeInput(
                ddo, self.compute_service, ddo.access_details.get("valid_order_tx", "")
            )
            for ddo in self.datasets
        ]
        algo_input = ComputeInput(
            self.algorithm,
            self.algo_service,
            self.algorithm.access_details.get("valid_order_tx", ""),
        )

        valid_unitl = get_valid_until_time(
            self.compute_env["maxJobDuration"],
            self.compute_service.timeout,
            self.algo_service.timeout,
        )

        # TODO: Possible speed up by allowing all spend for fixed exchange first
        datasets, algorithm = pay_for_compute_service(
            datasets=data_input,
            algorithm_data=algo_input,
            consume_market_order_fee_address=account.address,
            tx_dict={"from": account},
            compute_environment=self.compute_env["id"],
            valid_until=valid_unitl,
            consumer_address=self.compute_env["consumerAddress"],
            ocean=self.ocean,
        )

        self.job_id = self.ocean.compute.start(
            consumer_wallet=account,
            dataset=datasets[0],
            compute_environment=self.compute_env["id"],
            algorithm=algorithm,
            algorithm_algocustomdata=self.algocustomdata,
            additional_datasets=datasets[1:],
        )

        self.state = "running"

    def check_status(self, account: LocalAccount) -> str:
        assert self.state != "init", f"Compute job must be started first."
        status = self.ocean.compute.status(
            self.datasets[0], self.compute_service, self.job_id, account
        )

        if not status["ok"]:
            self.state = "failed"

        elif status["status"] == 70:
            self.state = "finished"
            self.files = {
                file["filename"]: (i, file) for i, file in enumerate(status["results"])
            }

        return self.state

    def get_outputs(self) -> dict:
        assert self.state == "finished", "Job must finish first before getting outputs"
        return self.files

    def get_file_url(self, file_name: str, account: LocalAccount) -> str:
        assert self.state == "finished", "Job must finish first before getting outputs"

        index = self.files[file_name][0]

        # TODO: Probably will need function for custom nonce
        nonce, signature = DataServiceProvider.sign_message(
            account, f"{account.address}{self.job_id}{str(index)}"
        )

        req = PreparedRequest()
        params = {
            "signature": signature,
            "nonce": nonce,
            "jobId": self.job_id,
            "index": index,
            "consumerAddress": account.address,
        }

        (
            _,
            compute_job_result_endpoint,
        ) = DataServiceProvider.build_compute_result_file_endpoint(
            self.compute_service.service_endpoint
        )
        req.prepare_url(compute_job_result_endpoint, params)
        return req.url

    def get_file(self, file_name: str, account: LocalAccount):
        assert self.state == "finished", "Job must finish first before getting outputs"
        index = self.files[file_name][0]
        return self.ocean.compute.result(
            self.datasets[0], self.compute_service, self.job_id, index, account
        )
