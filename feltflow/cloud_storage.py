import json
from typing import Any

import requests


class CloudStorage:
    """Class communicating with FELT backend server.
    Code is following the javascript API definition.
    """

    def __init__(self, api_base_url: str, user_token: str):
        self.endpoint = f"{api_base_url}/api/jobs"
        self.token = user_token
        self.headers = {"Content-Type": "application/json"}
        self.cookies = {"next-auth.session-token": user_token}

    def _stringify(self, data: dict) -> str:
        return json.dumps(data, separators=(",", ":"))

    def _fetch(self, method: str, data: str) -> requests.Response:
        return requests.request(
            method, self.endpoint, data=data, headers=self.headers, cookies=self.cookies
        )

    def create_user_job(self, job: dict) -> requests.Response:
        data = self._stringify({"job": job})
        return self._fetch("PUT", data)

    def update_user_job(
        self, job_id: str, update_field: str, update_value: Any
    ) -> requests.Response:
        data = self._stringify(
            {
                "jobId": job_id,
                "updateField": update_field,
                "updateValue": update_value,
            }
        )
        return self._fetch("PATCH", data)
