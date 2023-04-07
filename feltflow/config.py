from ocean_lib.example_config import get_config_dict
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.web3_internal.utils import connect_to_network

# Dictonary mapping chainId to network name
NETWORKS = {80001: "polygon-test"}


def get_ocean(chain_id: int):
    """Create Ocean object extend config object with extra fields.

    Extra fields added to ocean config:
        chainId (int): chain id used with the ocean

    Args:
        chainId: id of chain to connect to
    """
    network_name = NETWORKS[chain_id]

    connect_to_network(network_name)  # mumbai is "polygon-test"
    config = get_config_dict(network_name)
    config["chainId"] = chain_id

    return Ocean(config)
