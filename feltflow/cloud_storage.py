import json
from typing import Any, List

import requests


class CloudStorage:
    """Class communicating with FELT backend server.
    Code is following the javascript API definition.
    """

    def __init__(self, api_base_url: str, launch_token: str):
        self.api_base_url = api_base_url
        self.headers = {"Content-Type": "application/json"}
        self.launch_token = launch_token

    def _stringify(self, data: dict) -> str:
        """Turn dictionary into JSON string."""
        return json.dumps(data, separators=(",", ":"))

    def _fetch(self, endpoint: str, method: str, data: str) -> requests.Response:
        """Send request to FELT API with appropriate headers."""
        response = requests.request(
            method, f"{self.api_base_url}{endpoint}", data=data, headers=self.headers
        )
        if not response.ok:
            raise Exception("Failed to store/update job in cloud storage.")

        return response

    def get_job(self) -> dict:
        res = requests.request(
            "GET",
            f"{self.api_base_url}/api/python-flow/jobs?launchToken={self.launch_token}",
        )
        return res.json()

    def create_job(self) -> requests.Response:
        """Store new job through API into the FELT Labs storage."""
        data = self._stringify({"launchToken": self.launch_token})
        return self._fetch("/api/python-flow/jobs", "POST", data)

    def add_aggregation(
        self,
        round: str,
        authToken: str,
        localTrainingsIds: List[str],
        computeJob: dict,
    ) -> requests.Response:
        """Store new local training through API into the FELT Labs storage."""
        data = self._stringify(
            {
                "launchToken": self.launch_token,
                "round": round,
                "authToken": authToken,
                "localTrainingsIds": localTrainingsIds,
                "computeJob": computeJob,
            }
        )
        return self._fetch("/api/python-flow/jobs/aggregation", "POST", data)

    def add_local_training(
        self,
        round: str,
        seed: int,
        authToken: str,
        dataDid: str,
        computeJob: dict,
    ) -> requests.Response:
        """Store new aggregation through API into the FELT Labs storage."""
        data = self._stringify(
            {
                "launchToken": self.launch_token,
                "round": round,
                "seed": seed,
                "authToken": authToken,
                "dataDid": dataDid,
                "computeJob": computeJob,
            }
        )
        return self._fetch("/api/python-flow/jobs/localTraining", "POST", data)
