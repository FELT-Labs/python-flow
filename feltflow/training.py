import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from brownie.network import accounts
from dotenv import load_dotenv
from ocean_lib.example_config import get_config_dict
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.web3_internal.utils import connect_to_network

from feltflow.helpers import get_valid_until_time, pay_for_compute_service
from feltflow.subgraph import get_access_details

load_dotenv()

# Fix timestamp in python3/site-packages/ocean_lib/data_provider/base.py
# nonce = str(datetime.now(timezone.utc).timestamp() * 1000)

# Use environment variables to set infura and private key
# os.environ["WEB3_INFURA_PROJECT_ID"] = ""
# os.environ["PRIVATE_KEY"] = ""


# TODO: Class compute
#   - init with dids
#   - run compute(given algo, algocustomdata)
#   - get results
#
# TODO: Class fed compute (sub from compute class)
#   - fed run
#   - run compute (local, algo def)
#   - run agg -> run compute (fed, output of locals)
#   - get results or repeat


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
    print("Account balance", account.balance())
    print("Ocean balance", ocean.OCEAN_token.balanceOf(account))

    data_ddo = ocean.assets.resolve(data_did)
    algo_ddo = ocean.assets.resolve(algo_did)

    # TODO: Check service types and compatibility
    compute_service = data_ddo.services[0]
    algo_service = algo_ddo.services[0]
    free_c2d_env = ocean.compute.get_free_c2d_environment(
        compute_service.service_endpoint
    )

    data_ddo.access_details = get_access_details(
        compute_service, config["NETWORK_NAME"], account.address
    )
    algo_ddo.access_details = get_access_details(
        algo_service, config["NETWORK_NAME"], account.address
    )

    algocustomdata = {
        "model_definition": {
            "model_name": "LinearRegression",
            "model_type": "sklearn",
        },
        "data_type": "csv",
        "target_column": -1,
    }

    DATA_compute_input = ComputeInput(
        data_ddo, compute_service, data_ddo.access_details.get("valid_order_tx", "")
    )

    ALGO_compute_input = ComputeInput(
        algo_ddo, algo_service, algo_ddo.access_details.get("valid_order_tx", "")
    )

    valid_unitl = get_valid_until_time(
        free_c2d_env["maxJobDuration"], compute_service.timeout, algo_service.timeout
    )

    # TODO: Or possible speed up by allowing all spend for fixed exchange first
    # TODO: Calculate valid_until properly
    # Pay for dataset and algo for 1 day
    datasets, algorithm = pay_for_compute_service(
        datasets=[DATA_compute_input],
        algorithm_data=ALGO_compute_input,
        consume_market_order_fee_address=account.address,
        tx_dict={"from": account},
        compute_environment=free_c2d_env["id"],
        valid_until=valid_unitl,
        consumer_address=free_c2d_env["consumerAddress"],
        ocean=ocean,
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

    status = {}
    succeeded = False
    for _ in range(0, 200):
        status = ocean.compute.status(data_ddo, compute_service, job_id, account)
        # print("Status", status)
        if status.get("dateFinished") and Decimal(status["dateFinished"]) > 0:
            succeeded = True
            break
        time.sleep(5)

    if succeeded:
        for i, file_info in enumerate(status["results"]):
            output = ocean.compute.result(data_ddo, compute_service, job_id, i, account)
            print(file_info["filename"])
            # print(output)
            print()
    else:
        print("FAILED")
