from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from brownie.network.account import LocalAccount
from ocean_lib.data_provider.data_service_provider import DataServiceProvider
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.web3_internal.utils import sign_with_key
from requests import PreparedRequest
from web3.main import Web3

from feltflow.ocean.data_service_provider import CustomDataServiceProvider
from feltflow.ocean.ocean_compute import CustomOceanCompute
from feltflow.order import get_valid_until_time, pay_for_compute_service
from feltflow.subgraph import get_access_details


class ComputeJob:
    """Class providing all functions for working with compute job."""

    def __init__(
        self,
        ocean: Ocean,
        dataset_dids: List[str],
        algorithm_did: str,
        algocustomdata: dict,
    ):
        self.ocean = ocean
        self.algocustomdata = algocustomdata
        self.did = dataset_dids[0]
        self.datasets = [ocean.assets.resolve(did) for did in dataset_dids]
        self.algorithm = ocean.assets.resolve(algorithm_did)

        assert (
            self.algorithm is not None
        ), f"Couldn't resolve algorithm: {algorithm_did}"
        for did, dataset in zip(dataset_dids, self.datasets):
            assert dataset is not None, f"Couldn't resolve dataset: {did}"

        self.ocean.compute = CustomOceanCompute(ocean.config)

        # TODO: Check service types and compatibility
        self.compute_service = self.datasets[0].services[0]
        self.algo_service = self.algorithm.services[0]

        self.chain_id = self.ocean.config_dict["chainId"]

        try:
            self.compute_env = ocean.compute.get_free_c2d_environment(
                self.compute_service.service_endpoint,
                self.chain_id,
            )
        except Exception:
            self.compute_env = ocean.compute.get_c2d_environments(
                self.compute_service.service_endpoint,
                self.chain_id,
            )[0]

        self.state = "init"

    def start(self, account: LocalAccount, nonce: Optional[str] = None) -> None:
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
            float(self.compute_env["maxJobDuration"]),
            float(self.compute_service.timeout),
            float(self.algo_service.timeout),
        )

        # TODO: Would be nice to batch all approve transactions into one
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

        self.job_info = self.ocean.compute.start(
            consumer_wallet=account,
            dataset=datasets[0],
            compute_environment=self.compute_env["id"],
            algorithm=algorithm,
            algorithm_algocustomdata=self.algocustomdata,
            additional_datasets=datasets[1:],
            nonce=nonce,
        )
        self.job_id = self.job_info["jobId"]

        self.state = "running"

        return self.job_info

    def check_status(self, account: LocalAccount) -> str:
        assert self.state != "init", f"Compute job must be started first."
        self.job_info = self.ocean.compute.status(
            self.datasets[0], self.compute_service, self.job_id, account
        )

        if not self.job_info["ok"]:
            self.state = "failed"

        elif self.job_info["status"] == 70:
            self.state = "finished"
            self.files = {
                file["filename"]: (i, file)
                for i, file in enumerate(self.job_info["results"])
            }

        return self.state

    def get_outputs(self) -> dict:
        assert self.state == "finished", "Job must finish first before getting outputs"
        return self.files

    def get_file_url(
        self, file_name: str, account: LocalAccount, nonce: Optional[str] = None
    ) -> str:
        assert self.state == "finished", "Job must finish first before getting outputs"

        index = self.files[file_name][0]

        nonce, signature = CustomDataServiceProvider.sign_message(
            account, f"{account.address}{self.job_id}{str(index)}", nonce
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

    def get_file(self, file_name: str, account: LocalAccount) -> Dict[str, Any]:
        assert self.state == "finished", "Job must finish first before getting outputs"
        index = self.files[file_name][0]
        return self.ocean.compute.result(
            self.datasets[0], self.compute_service, self.job_id, index, account
        )
