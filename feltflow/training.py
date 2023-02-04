import os
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from brownie.network import accounts
from dotenv import load_dotenv
from ocean_lib.data_provider.data_service_provider import DataServiceProvider
from ocean_lib.example_config import get_config_dict
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.models.datatoken import Datatoken, TokenFeeInfo
from ocean_lib.models.datatoken_enterprise import DatatokenEnterprise
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.ocean.util import to_wei
from ocean_lib.web3_internal.utils import connect_to_network

load_dotenv()

# Fix timestamp in python3/site-packages/ocean_lib/data_provider/base.py
# nonce = str(datetime.now(timezone.utc).timestamp() * 1000)


# Use environment variables to set infura and private key
# os.environ["WEB3_INFURA_PROJECT_ID"] = ""
# os.environ["PRIVATE_KEY"] = ""
def main():
    # TEST DIDs
    data_did = "did:op:3632e8584837f2eac04d85466c0cebd8b8cb2673b472a82a310175da9730042a"
    algo_did = "did:op:8d6f2b6689c1ae347aeeb4b2708c3db03bbb143e90671dfaa478c9b5b9a8af6a"

    # Create Ocean instance
    connect_to_network("polygon-test")  # mumbai is "polygon-test"
    config = get_config_dict("polygon-test")
    ocean = Ocean(config)

    # Create Alice's wallet
    account = accounts.add(os.getenv("PRIVATE_KEY"))
    print(account.balance())
    print(ocean.OCEAN_token.balanceOf(account))

    data_ddo = ocean.assets.resolve(data_did)
    algo_ddo = ocean.assets.resolve(algo_did)

    # TODO: Check which service is compute
    compute_service = data_ddo.services[0]
    algo_service = algo_ddo.services[0]
    free_c2d_env = ocean.compute.get_free_c2d_environment(
        compute_service.service_endpoint
    )

    # TODO: Get TransferTxId
    # TODO: Query subgraph for proper pricing and last transaction
    algocustomdata = {
        "model_definition": {
            "model_name": "LinearRegression",
            "model_type": "sklearn",
        },
        "data_type": "csv",
        "target_column": -1,
    }

    DATA_compute_input = ComputeInput(data_ddo, compute_service)
    ALGO_compute_input = ComputeInput(algo_ddo, algo_service)
    # TODO: Add algocustomdata to algo compute input
    # TODO: Compute correct valid_until

    def start_or_reuse_order_based_on_initialize_response(
        asset_compute_input: ComputeInput,
        item: dict,
        consume_market_fees: TokenFeeInfo,
        tx_dict: dict,
        consumer_address: str,
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

        # TODO: Decide based on pricing mechanism
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

    def pay_for_compute_service(
        datasets: List[ComputeInput],
        algorithm_data: ComputeInput,
        compute_environment: str,
        valid_until: int,
        consume_market_order_fee_address: str,
        tx_dict: dict,
        consumer_address: Optional[str] = None,
    ):
        data_provider = DataServiceProvider
        wallet_address = tx_dict["from"]

        if not consumer_address:
            consumer_address = wallet_address

        print("algo data", algorithm_data.as_dictionary())

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
            )

            return datasets, algorithm_data

        return datasets, None

    # Pay for dataset and algo for 1 day
    datasets, algorithm = pay_for_compute_service(
        datasets=[DATA_compute_input],
        algorithm_data=ALGO_compute_input,
        consume_market_order_fee_address=account.address,
        tx_dict={"from": account},
        compute_environment=free_c2d_env["id"],
        valid_until=int(
            (datetime.now(timezone.utc) + timedelta(minutes=60)).timestamp()
        ),
        consumer_address=free_c2d_env["consumerAddress"],
    )
    print(datasets, algorithm.as_dictionary())

    # Start compute job
    job_id = ocean.compute.start(
        consumer_wallet=account,
        dataset=datasets[0],
        compute_environment=free_c2d_env["id"],
        algorithm=algorithm,
        algorithm_algocustomdata=algocustomdata,
    )
    print(f"Started compute job with id: {job_id}")

    from decimal import Decimal

    status = {}
    for _ in range(0, 200):
        status = ocean.compute.status(data_ddo, compute_service, job_id, account)
        print("Status", status)
        if status.get("dateFinished") and Decimal(status["dateFinished"]) > 0:
            succeeded = True
            break
        time.sleep(5)

    for i, file_info in enumerate(status["results"]):
        output = ocean.compute.result(data_ddo, compute_service, job_id, i, account)
        print(file_info["filename"])
        print(output)
        print()

    print("Results", output)
