import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional, cast

# Turn off info logging (must be before ocean_lib imports)
logging.basicConfig(level=logging.ERROR)

from brownie.network import accounts
from dotenv import load_dotenv

from feltflow.cloud_storage import CloudStorage
from feltflow.config import get_ocean
from feltflow.federated_training import FederatedTraining

load_dotenv()

# Use environment variables to set infura and private key
# os.environ["WEB3_INFURA_PROJECT_ID"] = ""
# os.environ["PRIVATE_KEY"] = ""


@dataclass
class Config:
    launch_token: str
    api_endpoint: str
    algocustomdata: dict = field(default_factory=dict)


def _help_exit(parser, error_msg=None):
    """Print help of parser and quit the script."""
    parser.print_help()
    if error_msg:
        print(f"\nERROR: {error_msg}")
    sys.exit(2)


def _parse_training_args(args_str: Optional[List[str]] = None) -> Config:
    """Parse and partially validate arguments form command line.
    Arguments are parsed from string args_str or command line if args_str is None

    Args:
        args_str: list with string arguments or None if using command line

    Returns:
        Parsed args object
    """
    parser = argparse.ArgumentParser(
        prog="FELT Labs - Federated Learning",
        description="""
            Script for running federated learning with FELT Labs from command line.
        """,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--launch_token",
        type=str,
        required=True,
        help="Name used for identifying the training.",
    )
    parser.add_argument(
        "--algocustomdata",
        type=lambda s: json.loads(s),
        default={},
        help="Custom data which will be passed to algorithm during run (passed as string representing JSON).",
    )
    parser.add_argument(
        "--api_endpoint",
        type=str,
        default="https://app.feltlabs.ai",
        help="API endpoint URL for storing jobs data.",
    )

    args = parser.parse_args(args_str)
    return cast(Config, args)


def main(config: Optional[Config] = None, args_str: Optional[List[str]] = None) -> None:
    if config is None:
        config = _parse_training_args(args_str)

    storage = CloudStorage(config.api_endpoint, config.launch_token)
    job = storage.get_job()

    if job["jobId"] is not None:
        raise Exception(
            f"Job with launch token {config.launch_token} was already started."
        )

    ocean = get_ocean(job["chainId"])
    account = accounts.add(os.getenv("PRIVATE_KEY"))

    print("FELT Labs: Starting training")
    print(f"  Chain ID: {job['chainId']}")
    print(f"  Using account: {account.address}")
    print(f"    Account balance: {account.balance()}")

    federated_training = FederatedTraining(
        ocean,
        storage,
        job["name"],
        job["dataDIDs"],
        job["algoConfig"],
        job["algoCustomData"],
    )
    federated_training.run(account, iterations=1)

    print(f"Training finished! View the results at: {config.api_endpoint}/jobs")
