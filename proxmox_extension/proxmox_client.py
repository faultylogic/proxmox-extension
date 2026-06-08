import requests
import urllib3
from typing import Any


class ProxmoxClient:
    """Thin wrapper around the Proxmox VE REST API using API token auth."""

    def __init__(self, host: str, port: int, username: str, token_name: str, token_value: str, verify_ssl: bool = False):
        self.base_url = f"https://{host}:{port}/api2/json"
        self.headers = {
            "Authorization": f"PVEAPIToken={username}!{token_name}={token_value}"
        }
        self.verify_ssl = verify_ssl
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _get(self, path: str) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = requests.get(url, headers=self.headers, verify=self.verify_ssl, timeout=10)
        response.raise_for_status()
        return response.json().get("data", {})

    def get_cluster_status(self) -> list[dict]:
        return self._get("/cluster/status")

    def get_nodes(self) -> list[dict]:
        return self._get("/nodes")

    def get_node_status(self, node: str) -> dict:
        return self._get(f"/nodes/{node}/status")

    def get_vms(self, node: str) -> list[dict]:
        return self._get(f"/nodes/{node}/qemu")

    def get_vm_status(self, node: str, vmid: int) -> dict:
        return self._get(f"/nodes/{node}/qemu/{vmid}/status/current")

    def get_containers(self, node: str) -> list[dict]:
        return self._get(f"/nodes/{node}/lxc")

    def get_container_status(self, node: str, vmid: int) -> dict:
        return self._get(f"/nodes/{node}/lxc/{vmid}/status/current")

    def get_storage(self, node: str) -> list[dict]:
        return self._get(f"/nodes/{node}/storage")
