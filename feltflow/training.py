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
    name: str
    chain_id: int
    dids: List[str]
    algo_config: dict
    session: str
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
        "--name",
        type=str,
        required=True,
        help="Name used for identifying the training.",
    )
    parser.add_argument(
        "--chain_id",
        type=int,
        required=True,
        help="Blockchain id identifying correct blockchain",
    )
    parser.add_argument(
        "--dids",
        type=lambda s: s.split(","),
        required=True,
        help="List of data DIDs split by comma (,)",
    )
    parser.add_argument(
        "--algo_config",
        type=lambda s: json.loads(s),
        required=True,
        help="Algorithm config passed as string representing JSON.",
    )
    parser.add_argument(
        "--session",
        type=str,
        required=True,
        help="User session cookie used for storing jobs in cloud storage",
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

    ocean = get_ocean(config.chain_id)
    storage = CloudStorage(config.api_endpoint, config.session)

    print("FELT Labs: Starting training")
    account = accounts.add(os.getenv("PRIVATE_KEY"))
    print("Using account:", account.address)
    print("    Account balance:", account.balance())

    federated_training = FederatedTraining(
        ocean,
        storage,
        config.name,
        config.dids,
        config.algo_config,
        config.algocustomdata,
    )
    federated_training.run(account, iterations=1)
