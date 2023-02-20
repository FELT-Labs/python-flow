import os
import time
from decimal import Decimal

from brownie.network import accounts
from dotenv import load_dotenv
from ocean_lib.example_config import get_config_dict
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.web3_internal.utils import connect_to_network

from feltflow.comput_job import ComputeJob

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

    algocustomdata = {
        "model_definition": {
            "model_name": "LinearRegression",
            "model_type": "sklearn",
        },
        "data_type": "csv",
        "target_column": -1,
    }

    compute_job = ComputeJob(ocean, [data_did], algo_did, algocustomdata)
    compute_job.start(account)
    while compute_job.state == "running":
        compute_job.check_status(account)
        time.sleep(5)

    print(compute_job.get_file_url("model", account))
