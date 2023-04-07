from typing import Any, Dict

from ocean_lib.models.datatoken1 import Datatoken1
from ocean_lib.ocean.ocean import Ocean


class Approve:
    """Class handling all approve calls during dataset order.

    Right now it adds amounts together if there are multiple approve calls for one spender
    In future this should batch approves together to minimize transaction calls.
    """

    def __init__(self) -> None:
        self.approve = {}

    def add_approve(self, token_address: str, spender: str, amount: int) -> None:
        """Add approve transaction.

        Args:
            token_address: address of ERC20 token which should call approve
            spender: spender argument of approve call
            amount: amount to be approved
        """
        if not self.approve.get(token_address):
            self.approve[token_address] = {spender: amount}

        self.approve[token_address][spender] = (
            self.approve[token_address].get(spender, 0) + amount
        )

    def get_amount(self, token_address: str, spender: str) -> int:
        """Get approve amount for give token and spender pair.

        Args:
            token_address: address of ERC20 token which should call approve
            spender: spender argument of approve call

        Returns:
            approve amount or 0 if such approve doesn't exist.
        """
        return self.approve.get(token_address, {}).get(spender, 0)

    def appprove_all(self, ocean: Ocean, tx_dict: Dict[str, Any]) -> None:
        """Approve all stored transactions.

        Args:
            ocean: ocean class with all configs
            tx_dict: transaction config, must contain key {"from": account}
        """
        for token_address, transactions in self.approve.items():
            token = Datatoken1(ocean.config, token_address)
            for spender, amount in transactions.items():
                if amount == 0:
                    continue

                token_balance = token.balanceOf(tx_dict["from"])
                if token_balance < amount:
                    raise ValueError(
                        f"Your token balance {token_balance} {token.symbol()} is not  "
                        f"sufficient to execute the requested service. This service "
                        f"requires {amount} {token.symbol()}."
                    )

                token.approve(spender, amount, tx_dict)
