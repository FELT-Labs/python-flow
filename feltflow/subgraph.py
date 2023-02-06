import time
from typing import Any, Dict

import requests
from ocean_lib.services.service import Service

query = """
 query TokenPriceQuery($datatokenId: ID!, $account: String) {
    token(id: $datatokenId) {
      id
      symbol
      name
      templateId
      publishMarketFeeAddress
      publishMarketFeeToken
      publishMarketFeeAmount
      orders(
        where: { payer: $account }
        orderBy: createdTimestamp
        orderDirection: desc
      ) {
        tx
        serviceIndex
        createdTimestamp
        reuses(orderBy: createdTimestamp, orderDirection: desc) {
          id
          caller
          createdTimestamp
          tx
          block
        }
      }
      dispensers {
        id
        active
        isMinter
        maxBalance
        token {
          id
          name
          symbol
        }
      }
      fixedRateExchanges {
        id
        exchangeId
        price
        publishMarketSwapFee
        baseToken {
          symbol
          name
          address
          decimals
        }
        datatoken {
          symbol
          name
          address
        }
        active
      }
    }
  }
"""

SUBGRAPH_URLS = {"polygon-test": "https://v4.subgraph.mumbai.oceanprotocol.com"}


def _access_details_from_token_price(
    token_price: Dict[str, Any], timeout: float = 0
) -> Dict[str, Any]:
    access_details = {}

    if not token_price.get("dispensers", []) and not token_price.get(
        "fixedRateExchanges", []
    ):
        access_details["type"] = "NOT_SUPPORTED"
        return access_details

    access_details.update(
        {
            "template_id": token_price["templateId"],
            "publisher_market_order_fee": token_price.get(
                "publishMarketFeeAmount", None
            ),
        }
    )

    if len(token_price.get("orders", [])) > 0:
        order = token_price["orders"][0]
        reused_order = order["reuses"][0] if len(order.get("reuses", [])) > 0 else None
        access_details.update(
            {
                "is_owned": timeout == 0
                or time.time() - order.get("createdTimestamp", 0) < timeout,
                "valid_order_tx": reused_order["tx"] if reused_order else order["tx"],
            }
        )

    if len(token_price.get("dispensers", [])) > 0:
        dispenser = token_price["dispensers"][0]
        access_details.update(
            {
                "type": "free",
                "address_or_id": dispenser["token"]["id"],
                "price": "0",
                "is_purchasable": dispenser["active"],
                "datatoken": {
                    "address": dispenser["token"]["id"],
                    "name": dispenser["token"]["name"],
                    "symbol": dispenser["token"]["symbol"],
                },
            }
        )
    elif len(token_price.get("fixedRateExchanges", [])) > 0:
        fixed = token_price["fixedRateExchanges"][0]
        access_details.update(
            {
                "type": "fixed",
                "address_or_id": fixed["exchangeId"],
                "price": fixed["price"],
                "is_purchasable": fixed["active"],
                "base_token": {
                    "address": fixed["baseToken"]["address"],
                    "name": fixed["baseToken"]["name"],
                    "symbol": fixed["baseToken"]["symbol"],
                    "decimals": fixed["baseToken"]["decimals"],
                },
                "datatoken": {
                    "address": fixed["datatoken"]["address"],
                    "name": fixed["datatoken"]["name"],
                    "symbol": fixed["datatoken"]["symbol"],
                },
            }
        )

    return access_details


def get_access_details(
    service: Service,
    chain_id: str,
    account: str,
):
    datatoken_id = service.datatoken
    res = requests.post(
        f"{SUBGRAPH_URLS[chain_id]}/subgraphs/name/oceanprotocol/ocean-subgraph",
        "",
        json={
            "query": query,
            "variables": {
                "account": account.lower(),
                "datatokenId": datatoken_id.lower(),
            },
        },
    )

    if res.status_code != 200:
        raise Exception(f"Unable to collect access details (error: {res.status_code}")

    token_price_data = res.json()["data"]["token"]
    return _access_details_from_token_price(token_price_data, service.timeout)
