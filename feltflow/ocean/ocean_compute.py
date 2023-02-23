import logging
from typing import Any, Dict, List, Optional, Type

from enforce_typing import enforce_types
from ocean_lib.agreements.consumable import AssetNotConsumable, ConsumableCodes
from ocean_lib.agreements.service_types import ServiceTypes
from ocean_lib.aquarius import Aquarius
from ocean_lib.assets.asset_downloader import is_consumable
from ocean_lib.assets.ddo import DDO
from ocean_lib.data_provider.data_service_provider import DataServiceProvider
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.ocean.ocean_compute import OceanCompute
from ocean_lib.services.service import Service
from ocean_lib.structures.algorithm_metadata import AlgorithmMetadata

from feltflow.ocean.data_service_provider import CustomDataServiceProvider

logger = logging.getLogger("ocean")


class CustomOceanCompute(OceanCompute):
    """Customized version of ocean.py OceanCompute allowing setting nonce."""

    @enforce_types
    def __init__(self, config_dict: dict) -> None:
        """Initialises OceanCompute class."""
        self._config_dict = config_dict
        self._data_provider = CustomDataServiceProvider

    @enforce_types
    def start(
        self,
        consumer_wallet,
        dataset: ComputeInput,
        compute_environment: str,
        algorithm: Optional[ComputeInput] = None,
        algorithm_meta: Optional[AlgorithmMetadata] = None,
        algorithm_algocustomdata: Optional[dict] = None,
        additional_datasets: List[ComputeInput] = [],
        nonce: Optional[str] = None,
    ) -> str:
        metadata_cache_uri = self._config_dict.get("METADATA_CACHE_URI")
        ddo = Aquarius.get_instance(metadata_cache_uri).get_ddo(dataset.did)
        service = ddo.get_service_by_id(dataset.service_id)
        assert (
            ServiceTypes.CLOUD_COMPUTE == service.type
        ), "service at serviceId is not of type compute service."

        consumable_result = is_consumable(
            ddo,
            service,
            {"type": "address", "value": consumer_wallet.address},
            with_connectivity_check=True,
        )
        if consumable_result != ConsumableCodes.OK:
            raise AssetNotConsumable(consumable_result)

        # Start compute job
        job_info = self._data_provider.start_compute_job(
            dataset_compute_service=service,
            consumer=consumer_wallet,
            dataset=dataset,
            compute_environment=compute_environment,
            algorithm=algorithm,
            algorithm_meta=algorithm_meta,
            algorithm_custom_data=algorithm_algocustomdata,
            input_datasets=additional_datasets,
            nonce=nonce,
        )
        return job_info["jobId"]
