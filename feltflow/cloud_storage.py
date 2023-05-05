import json
from typing import Any

import requests


class CloudStorage:
    """Class communicating with FELT backend server.
    Code is following the javascript API definition.
    """

    def __init__(self, api_base_url: str, launch_token: str):
        self.endpoint = f"{api_base_url}/api/python-flow/jobs"
        self.headers = {"Content-Type": "application/json"}
        self.launch_token = launch_token

    def _stringify(self, data: dict) -> str:
        """Turn dictionary into JSON string."""
        return json.dumps(data, separators=(",", ":"))

    def _fetch(self, method: str, data: str) -> requests.Response:
        """Send request to FELT API with appropriate headers."""
        response = requests.request(
            method, self.endpoint, data=data, headers=self.headers
        )
        if not response.ok:
            raise Exception("Failed to store/update job in cloud storage.")

        return response

    def get_job(self) -> dict:
        res = requests.request(
            "GET", f"{self.endpoint}?launchToken={self.launch_token}"
        )
        return res.json()

    def create_job(self, job: dict) -> requests.Response:
        """Store new job through API into the FELT Labs storage."""
        data = self._stringify({"launchToken": self.launch_token, "job": job})
        return self._fetch("POST", data)

    def update_job(self, update_field: str, update_value: Any) -> requests.Response:
        """Update job from FELT Labs storage through API."""
        data = self._stringify(
            {
                "launchToken": self.launch_token,
                "updateField": update_field,
                "updateValue": update_value,
            }
        )
        return self._fetch("PATCH", data)
