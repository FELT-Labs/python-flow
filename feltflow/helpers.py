from datetime import datetime, timedelta, timezone
from typing import List, Union

from ocean_lib.data_provider.data_service_provider import DataServiceProvider
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.models.datatoken import Datatoken, TokenFeeInfo
from ocean_lib.models.datatoken_enterprise import DatatokenEnterprise
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.ocean.util import get_address_of_type, to_wei


def get_valid_until_time(
    max_job_duration: float, dataset_timeout: float, algorithm_timeout: float
) -> int:
    """Compute valid until time."""
    # Min time should be in minutes
    min_time = min(
        filter(
            lambda x: x != 0,
            map(float, [max_job_duration, dataset_timeout, algorithm_timeout]),
        )
    )
    return int((datetime.now(timezone.utc) + timedelta(minutes=min_time)).timestamp())


def get_typed_datatoken(
    ocean: Ocean, token_address: str
) -> Union[Datatoken, DatatokenEnterprise]:
    """Get datatoken class depending on datatoken id.

    Datatoken id:
        1 - Datatoken
        2 - DatatokneEnterprise
    """
    dt = Datatoken(ocean.config, token_address)
    if dt.getId() == 2:
        return DatatokenEnterprise(ocean.config, token_address)
    return dt


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
    dt = get_typed_datatoken(ocean, service.datatoken)

    if valid_order and provider_fees:
        asset_compute_input.transfer_tx_id = dt.reuse_order(
            valid_order, provider_fees=provider_fees, tx_dict=tx_dict
        ).txid
        return

    # TODO: Add some requirements on extended DDO with access_details
    if asset_compute_input.ddo.access_details["type"] == "fixed":
        exchange = dt.get_exchanges()[0]

        amt_needed = exchange.BT_needed(to_wei(1), consume_market_fees.amount)
        base_token = Datatoken(exchange._FRE.config_dict, exchange.details.base_token)

        base_token_balance = base_token.balanceOf(tx_dict["from"])
        if base_token_balance < amt_needed:
            raise ValueError(
                f"Your token balance {base_token_balance} {base_token.symbol()} is not sufficient "
                f"to execute the requested service. This service "
                f"requires {amt_needed} {base_token.symbol()}."
            )

        # Run purchase depending on datatoken type
        if dt.getId() == 2:
            if provider_fees:
                if base_token.address != provider_fees["providerFeeToken"]:
                    token = get_typed_datatoken(
                        ocean, provider_fees["providerFeeToken"]
                    )
                    token.approve(
                        dt.address,
                        int(provider_fees["providerFeeAmount"]),
                        tx_dict,
                    )
                else:
                    amt_needed += int(provider_fees["providerFeeAmount"])

            # Approve base token for buying data token
            base_token.approve(
                dt.address,
                amt_needed,
                tx_dict,
            )

            asset_compute_input.transfer_tx_id = dt.buy_DT_and_order(
                consumer=consumer_address,
                service_index=asset_compute_input.ddo.get_index_of_service(service),
                provider_fees=provider_fees,
                exchange=exchange,
                max_base_token_amount=amt_needed,
                consume_market_swap_fee_amount=consume_market_fees.amount,
                consume_market_swap_fee_address=consume_market_fees.address,
                tx_dict=tx_dict,
            ).txid
        else:
            # Approve base token for buying data token
            base_token.approve(
                exchange.address,
                amt_needed,
                tx_dict,
            )

            asset_compute_input.transfer_tx_id = dt.buy_DT_and_order(
                consumer=consumer_address,
                service_index=asset_compute_input.ddo.get_index_of_service(service),
                provider_fees=provider_fees,
                exchange=exchange,
                tx_dict=tx_dict,
            ).txid

    elif asset_compute_input.ddo.access_details["type"] == "free":
        # TODO: For different types + approve fees to datatoken
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
