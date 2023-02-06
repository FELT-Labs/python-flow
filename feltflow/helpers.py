from typing import List

from ocean_lib.data_provider.data_service_provider import DataServiceProvider
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.models.datatoken import TokenFeeInfo
from ocean_lib.models.datatoken_enterprise import DatatokenEnterprise
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.ocean.util import to_wei


def start_or_reuse_order_based_on_initialize_response(
    asset_compute_input: ComputeInput,
    item: dict,
    consume_market_fees: TokenFeeInfo,
    tx_dict: dict,
    consumer_address: str,
    ocean: Ocean,
):
    provider_fees = item.get("providerFee")
    valid_order = item.get("validOrder")

    if valid_order and not provider_fees:
        asset_compute_input.transfer_tx_id = valid_order
        return

    service = asset_compute_input.service
    dt = DatatokenEnterprise(ocean.config_dict, service.datatoken)

    if valid_order and provider_fees:
        asset_compute_input.transfer_tx_id = dt.reuse_order(
            valid_order, provider_fees=provider_fees, tx_dict=tx_dict
        ).txid
        return

    # TODO: Add some requirements on extended DDO with access_details
    if asset_compute_input.ddo.access_details["type"] == "fixed":
        asset_compute_input.transfer_tx_id = dt.buy_DT_and_order(
            consumer=consumer_address,
            service_index=asset_compute_input.ddo.get_index_of_service(service),
            provider_fees=provider_fees,
            exchange=dt.get_exchanges()[0],
            max_base_token_amount=to_wei(1000),  # TODO: add proper value
            consume_market_swap_fee_amount=consume_market_fees.amount,
            consume_market_swap_fee_address=consume_market_fees.address,
            tx_dict=tx_dict,
        ).txid
    elif asset_compute_input.ddo.access_details["type"] == "free":
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
):
    data_provider = DataServiceProvider
    wallet_address = tx_dict["from"]

    if not consumer_address:
        consumer_address = wallet_address

    initialize_response = data_provider.initialize_compute(
        [x.as_dictionary() for x in datasets],
        algorithm_data.as_dictionary(),
        datasets[0].service.service_endpoint,
        consumer_address,
        compute_environment,
        valid_until,
    )

    result = initialize_response.json()
    for i, item in enumerate(result["datasets"]):
        start_or_reuse_order_based_on_initialize_response(
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
        start_or_reuse_order_based_on_initialize_response(
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
