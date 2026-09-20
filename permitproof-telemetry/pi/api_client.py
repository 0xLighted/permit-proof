import os
from urllib.parse import urlparse
import httpx


class API:
    def __init__(self):
        self.device_id = os.getenv("PERMITPROOF_DEVICE_ID", "pi-001")
        token = os.getenv("PERMITPROOF_TOKEN", "")
        if len(token) < 24:
            raise RuntimeError("Missing local token. Run python -m scripts.setup_local")
        url = os.getenv("PERMITPROOF_API_URL", "http://127.0.0.1:8000")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
            raise ValueError("Use an HTTP(S) URL without embedded credentials")
        if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Plain HTTP allowed only over loopback; use HTTPS or an SSH tunnel remotely")
        self.path = f"/api/v1/devices/{self.device_id}"
        self.client = httpx.Client(base_url=url, timeout=3,
                                  headers={"Authorization": f"Bearer {token}"}, trust_env=False)

    def _request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def event(self, event):
        return self._request("POST", self.path + "/events", json=event)

    def desired(self):
        return self._request("GET", self.path + "/desired-state")

    def report(self, report):
        return self._request("POST", self.path + "/reported-state", json=report)

    def status(self):
        return self._request("GET", self.path + "/status")

    def close(self):
        self.client.close()
