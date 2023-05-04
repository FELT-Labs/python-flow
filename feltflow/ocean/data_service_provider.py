import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from enforce_typing import enforce_types
from ocean_lib.agreements.service_types import ServiceTypes
from ocean_lib.data_provider.base import DataServiceProviderBase, urljoin
from ocean_lib.data_provider.data_service_provider import DataServiceProvider
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.structures.algorithm_metadata import AlgorithmMetadata
from ocean_lib.web3_internal.utils import sign_with_key
from web3.main import Web3

logger = logging.getLogger("ocean")


class CustomDataServiceProvider(DataServiceProvider):
    """Customization of original DataServiceProvider from ocean.py adding custom nonce."""

    @staticmethod
    def get_nonce() -> float:
        return datetime.now().timestamp() * 1000

    @staticmethod
    @enforce_types
    def sign_message(wallet, msg: str, nonce: Optional[str] = None) -> Tuple[str, str]:
        if not nonce:
            nonce = str(CustomDataServiceProvider.get_nonce())
        message_hash = Web3.solidityKeccak(
            ["bytes"],
            [Web3.toBytes(text=f"{msg}{nonce}")],
        )
        signed = sign_with_key(message_hash, wallet.private_key)

        return nonce, str(signed)

    @staticmethod
    def get_auth_token(wallet, provider_uri: str) -> str:
        message = f"{wallet.address}"
        nonce, signature = CustomDataServiceProvider.sign_message(wallet, message)
        expiration = int(float(nonce) / 1000 + 3600 * 24 * 5000)  # Valid for 5000 days

        payload = {
            "address": wallet.address,
            "expiration": str(expiration),
            "signature": signature,
            "nonce": nonce,
        }

        provider_uri = DataServiceProviderBase.get_root_uri(provider_uri)
        auth_endpoint = urljoin(provider_uri, "/api/services/createAuthToken")

        response = DataServiceProvider._http_method(
            "get",
            auth_endpoint,
            data=json.dumps(payload),
            headers={"content-type": "application/json"},
        )

        return response.json()["token"]

    @staticmethod
    # @enforce_types omitted due to subscripted generics error
    def start_compute_job(
        dataset_compute_service: Any,  # Can not add Service typing due to enforce_type errors.
        consumer,
        dataset: ComputeInput,
        compute_environment: str,
        algorithm: Optional[ComputeInput] = None,
        algorithm_meta: Optional[AlgorithmMetadata] = None,
        algorithm_custom_data: Optional[dict] = None,
        input_datasets: Optional[List[ComputeInput]] = None,
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a compute job.

        Either algorithm or algorithm_meta must be defined.

        :param dataset_compute_service:
        :param consumer: hex str the ethereum address of the consumer executing the compute job
        :param dataset: ComputeInput dataset with a compute service
        :param compute_environment: str compute environment id
        :param algorithm: ComputeInput algorithm witha download service.
        :param algorithm_meta: AlgorithmMetadata algorithm metadata
        :param algorithm_custom_data: dict customizable algo parameters (ie. no of iterations, etc)
        :param input_datasets: List[ComputeInput] additional input datasets
        :return job_info dict and auth_token string
        """
        assert (
            algorithm or algorithm_meta
        ), "either an algorithm did or an algorithm meta must be provided."

        assert (
            hasattr(dataset_compute_service, "type")
            and dataset_compute_service.type == ServiceTypes.CLOUD_COMPUTE
        ), "invalid compute service"

        auth_token = CustomDataServiceProvider.get_auth_token(
            consumer, dataset_compute_service.service_endpoint
        )
        payload = CustomDataServiceProvider._prepare_compute_payload(
            consumer=consumer,
            dataset=dataset,
            compute_environment=compute_environment,
            algorithm=algorithm,
            algorithm_meta=algorithm_meta,
            algorithm_custom_data=algorithm_custom_data,
            input_datasets=input_datasets,
            nonce=nonce,
        )

        logger.info(f"invoke start compute endpoint with this url: {payload}")
        _, compute_endpoint = DataServiceProvider.build_compute_endpoint(
            dataset_compute_service.service_endpoint
        )
        print("Payload", payload)
        response = DataServiceProvider._http_method(
            "post",
            compute_endpoint,
            data=json.dumps(payload),
            headers={
                "content-type": "application/json",
                "AuthToken": auth_token,
            },
        )

        logger.debug(
            f"got DataProvider execute response: {response.content} with status-code {response.status_code} "
        )

        DataServiceProviderBase.check_response(
            response, "computeStartEndpoint", compute_endpoint, payload, [200, 201]
        )

        try:
            job_info = json.loads(response.content.decode("utf-8"))
            job = job_info[0] if isinstance(job_info, list) else job_info
            return job, auth_token

        except KeyError as err:
            logger.error(f"Failed to extract jobId from response: {err}")
            raise KeyError(f"Failed to extract jobId from response: {err}")
        except json.JSONDecodeError as err:
            logger.error(f"Failed to parse response json: {err}")
            raise

    @staticmethod
    # @enforce_types omitted due to subscripted generics error
    def _prepare_compute_payload(
        consumer,
        dataset: ComputeInput,
        compute_environment: str,
        algorithm: Optional[ComputeInput] = None,
        algorithm_meta: Optional[AlgorithmMetadata] = None,
        algorithm_custom_data: Optional[dict] = None,
        input_datasets: Optional[List[ComputeInput]] = None,
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        assert (
            algorithm or algorithm_meta
        ), "either an algorithm did or an algorithm meta must be provided."

        if algorithm_meta:
            assert isinstance(algorithm_meta, AlgorithmMetadata), (
                f"expecting a AlgorithmMetadata type "
                f"for `algorithm_meta`, got {type(algorithm_meta)}"
            )

        _input_datasets = []
        if input_datasets:
            for _input in input_datasets:
                assert _input.did, "The received dataset does not have a did."
                assert (
                    _input.transfer_tx_id
                ), "The received dataset does not have a transaction id."
                assert (
                    _input.service_id
                ), "The received dataset does not have a specified service id."
                if _input.did != dataset.did:
                    _input_datasets.append(_input.as_dictionary())

        payload = {
            "dataset": {
                "documentId": dataset.did,
                "serviceId": dataset.service_id,
                "transferTxId": dataset.transfer_tx_id,
            },
            "environment": compute_environment,
            "algorithm": {},
            "nonce": nonce if nonce else CustomDataServiceProvider.get_nonce(),
            "consumerAddress": consumer.address,
            "additionalInputs": _input_datasets or [],
        }

        if dataset.userdata:
            payload["dataset"]["userdata"] = dataset.userdata

        if algorithm:
            payload.update(
                {
                    "algorithm": {
                        "documentId": algorithm.did,
                        "serviceId": algorithm.service_id,
                        "transferTxId": algorithm.transfer_tx_id,
                    }
                }
            )
            if algorithm.userdata:
                payload["algorithm"]["userdata"] = algorithm.userdata
            if algorithm_custom_data:
                payload["algorithm"]["algocustomdata"] = algorithm_custom_data
        else:
            payload["algorithm"] = algorithm_meta.as_dictionary()

        return payload


# Fix the invalid signature (leave this until merged PR: https://github.com/oceanprotocol/ocean.py/pull/1307)
DataServiceProvider.sign_message = CustomDataServiceProvider.sign_message
