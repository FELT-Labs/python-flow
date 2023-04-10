import logging
import os
import time

from feltflow.cloud_storage import CloudStorage

# Turn off info logging (must be before ocean_lib imports)
logging.basicConfig(level=logging.ERROR)

from brownie.network import accounts
from dotenv import load_dotenv

from feltflow.config import get_ocean
from feltflow.federated_training import FederatedTraining

load_dotenv()

# Use environment variables to set infura and private key
# os.environ["WEB3_INFURA_PROJECT_ID"] = ""
# os.environ["PRIVATE_KEY"] = ""


def main():
    # Create Ocean instance
    ocean = get_ocean(80001)
    storage = CloudStorage(
        "http://localhost:3000",
        os.getenv("SESSION"),  # TODO: Replace with call param
    )

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

    dids = [
        "did:op:3632e8584837f2eac04d85466c0cebd8b8cb2673b472a82a310175da9730042a",
        "did:op:cad4a81c9a8e1c1071ccf3e9dea6f8f42d58e100fa3ddf2950c8f0da9e0dda46",
    ]

    algo_config = {
        "id": "FELT",
        "name": "FELT Federated Training",
        "assets": {
            "training": "did:op:87e58362dfc60bbeaf83d5495e587a891a9ca697a6c5ec3585bfe1f8586f85fa",
            "aggregation": "did:op:dcefb784c302094251ae1bc19d898eb584bd7be20a623bab078d4df0283e6c79",
            "emptyDataset": "did:op:20bf68f480e17aff3e6947792e75b615908a46394ba33c8cfb94587a0a8d2c29",
        },
        "hasParameters": True,
    }

    federated_training = FederatedTraining(
        ocean, storage, dids, algo_config, algocustomdata
    )
    federated_training.run(account, iterations=1)

    ## TEST DIDs
    # data_did = "did:op:3632e8584837f2eac04d85466c0cebd8b8cb2673b472a82a310175da9730042a"
    # algo_did = "did:op:8d6f2b6689c1ae347aeeb4b2708c3db03bbb143e90671dfaa478c9b5b9a8af6a"

    # compute_job = ComputeJob(ocean, [data_did], algo_did, algocustomdata)
    # compute_job.start(account)
    # while compute_job.state == "running":
    #     compute_job.check_status(account)
    #     time.sleep(5)

    # print(compute_job.get_file_url("model", account))
