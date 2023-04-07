from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Union

from ocean_lib.data_provider.data_service_provider import DataServiceProvider
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.models.datatoken_base import DatatokenBase, TokenFeeInfo
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.ocean.util import to_wei

from feltflow.approve import Approve


def get_valid_until_time(
    max_job_duration: float, dataset_timeout: float, algorithm_timeout: float
) -> int:
    """Compute valid until time."""
    # Min time should be in minutes
    min_time = min(
        filter(
            lambda x: x != 0,
            [max_job_duration, dataset_timeout, algorithm_timeout],
        )
    )
    return int((datetime.now(timezone.utc) + timedelta(minutes=min_time)).timestamp())


def _start_or_reuse_order_based_on_initialize_response(
    asset_compute_input: ComputeInput,
    item: dict,
    consume_market_fees: TokenFeeInfo,
    tx_dict: dict,
    consumer_address: str,
    ocean: Ocean,
) -> None:
    provider_fees = item.get("providerFee")
    valid_order = item.get("validOrder")

    approvals = Approve()

    # TODO: Here it depends on when was the order, if it is still valid we don't need to reuse order
    # if valid_order and (not provider_fees or provider_fees["providerFeeAmount"] == "0"):
    if valid_order and not provider_fees:
        asset_compute_input.transfer_tx_id = valid_order
        return

    service = asset_compute_input.service
    dt = DatatokenBase.get_typed(ocean.config, service.datatoken)

    if provider_fees:
        approvals.add_approve(
            provider_fees["providerFeeToken"],
            dt.address,
            int(provider_fees["providerFeeAmount"]),
        )

    if valid_order and provider_fees:
        approvals.appprove_all(ocean, tx_dict)
        asset_compute_input.transfer_tx_id = dt.reuse_order(
            valid_order, provider_fees=provider_fees, tx_dict=tx_dict
        ).txid
        return

    # TODO: Add some requirements on extended DDO with access_details
    if asset_compute_input.ddo.access_details["type"] == "fixed":
        exchange = dt.get_exchanges()[0]
        amount_needed = exchange.BT_needed(to_wei(1), consume_market_fees.amount)

        # Run purchase depending on datatoken type
        if dt.getId() == 2:
            # Approve base token for buying data token
            approvals.add_approve(
                exchange.details.base_token,
                dt.address,
                amount_needed,
            )
            approvals.appprove_all(ocean, tx_dict)
            total_amount = approvals.get_amount(exchange.details.base_token, dt.address)

            asset_compute_input.transfer_tx_id = dt.buy_DT_and_order(
                consumer=consumer_address,
                service_index=asset_compute_input.ddo.get_index_of_service(service),
                provider_fees=provider_fees,
                exchange=exchange,
                max_base_token_amount=total_amount,
                consume_market_swap_fee_amount=consume_market_fees.amount,
                consume_market_swap_fee_address=consume_market_fees.address,
                tx_dict=tx_dict,
            ).txid
        else:
            # Approve base token for buying data token
            approvals.add_approve(
                exchange.details.base_token,
                exchange.address,
                amount_needed,
            )
            approvals.appprove_all(ocean, tx_dict)

            asset_compute_input.transfer_tx_id = dt.buy_DT_and_order(
                consumer=consumer_address,
                service_index=asset_compute_input.ddo.get_index_of_service(service),
                provider_fees=provider_fees,
                exchange=exchange,
                tx_dict=tx_dict,
            ).txid

    elif asset_compute_input.ddo.access_details["type"] == "free":
        approvals.appprove_all(ocean, tx_dict)

        asset_compute_input.transfer_tx_id = dt.dispense_and_order(
            consumer=consumer_address,
            service_index=asset_compute_input.ddo.get_index_of_service(service),
            provider_fees=provider_fees,
            tx_dict=tx_dict,
        ).txid
    else:
        raise Exception("Unsupported asset access details.")


def pay_for_compute_service(
    datasets: List[ComputeInput],
    algorithm_data: ComputeInput,
    compute_environment: str,
    valid_until: int,
    consume_market_order_fee_address: str,
    tx_dict: dict,
    consumer_address: str,
    ocean: Ocean,
) -> Tuple[List[ComputeInput], Optional[ComputeInput]]:
    wallet_address = tx_dict["from"]

    if not consumer_address:
        consumer_address = wallet_address

    initialize_response = DataServiceProvider.initialize_compute(
        [x.as_dictionary() for x in datasets],
        algorithm_data.as_dictionary(),
        datasets[0].service.service_endpoint,
        consumer_address,
        compute_environment,
        valid_until,
    )

    result = initialize_response.json()
    for i, item in enumerate(result["datasets"]):
        _start_or_reuse_order_based_on_initialize_response(
            datasets[i],
            item,
            TokenFeeInfo(
                consume_market_order_fee_address,
                datasets[i].consume_market_order_fee_token,
                datasets[i].consume_market_order_fee_amount,
            ),
            tx_dict,
            consumer_address,
            ocean,
        )

    if "algorithm" in result:
        _start_or_reuse_order_based_on_initialize_response(
            algorithm_data,
            result["algorithm"],
            TokenFeeInfo(
                address=consume_market_order_fee_address,
                token=algorithm_data.consume_market_order_fee_token,
                amount=algorithm_data.consume_market_order_fee_amount,
            ),
            tx_dict,
            consumer_address,
            ocean,
        )

        return datasets, algorithm_data

    return datasets, None
