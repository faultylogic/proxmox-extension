import requests
import urllib3
from typing import Any, Dict, List, Optional


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

    # ------------------------------------------------------------------ Cluster
    def get_cluster_status(self) -> List[Dict]:
        return self._get("/cluster/status")

    def get_cluster_resources(self) -> List[Dict]:
        return self._get("/cluster/resources")

    def get_ha_status(self) -> List[Dict]:
        return self._get("/cluster/ha/status/current")

    def get_ha_resources(self) -> List[Dict]:
        return self._get("/cluster/ha/resources")

    def get_replication_jobs(self) -> List[Dict]:
        return self._get("/cluster/replication")

    def get_backup_jobs(self) -> List[Dict]:
        return self._get("/cluster/backup")

    def get_not_backed_up(self) -> List[Dict]:
        return self._get("/cluster/backup-info/not-backed-up")

    def get_ceph_status(self) -> Dict:
        return self._get("/cluster/ceph/status")

    def get_ceph_flags(self) -> List[Dict]:
        return self._get("/cluster/ceph/flags")

    # ------------------------------------------------------------------ Nodes
    def get_nodes(self) -> List[Dict]:
        return self._get("/nodes")

    def get_node_status(self, node: str) -> Dict:
        return self._get(f"/nodes/{node}/status")

    def get_node_services(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/services")

    def get_node_subscription(self, node: str) -> Dict:
        return self._get(f"/nodes/{node}/subscription")

    def get_node_apt_updates(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/apt/update")

    def get_node_tasks(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/tasks")

    def get_node_replication(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/replication")

    def get_node_netstat(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/netstat")

    # ------------------------------------------------------------------ Disks
    def get_node_disks(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/disks/list")

    def get_disk_smart(self, node: str, disk: str) -> Dict:
        return self._get(f"/nodes/{node}/disks/smart?disk={disk}")

    # ------------------------------------------------------------------ VMs
    def get_vms(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/qemu")

    def get_vm_status(self, node: str, vmid: int) -> Dict:
        return self._get(f"/nodes/{node}/qemu/{vmid}/status/current")

    def get_vm_snapshots(self, node: str, vmid: int) -> List[Dict]:
        return self._get(f"/nodes/{node}/qemu/{vmid}/snapshot")

    def get_vm_agent_fsinfo(self, node: str, vmid: int) -> List[Dict]:
        data = self._get(f"/nodes/{node}/qemu/{vmid}/agent/get-fsinfo")
        # returns {"result": [...]} or list depending on version
        if isinstance(data, dict):
            return data.get("result", [])
        return data or []

    def get_vm_agent_network(self, node: str, vmid: int) -> List[Dict]:
        data = self._get(f"/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces")
        if isinstance(data, dict):
            return data.get("result", [])
        return data or []

    # ------------------------------------------------------------------ LXC
    def get_containers(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/lxc")

    def get_container_status(self, node: str, vmid: int) -> Dict:
        return self._get(f"/nodes/{node}/lxc/{vmid}/status/current")

    def get_container_snapshots(self, node: str, vmid: int) -> List[Dict]:
        return self._get(f"/nodes/{node}/lxc/{vmid}/snapshot")

    # ------------------------------------------------------------------ Storage
    def get_storage(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/storage")

    def get_storage_status(self, node: str, storage: str) -> Dict:
        return self._get(f"/nodes/{node}/storage/{storage}/status")

    def get_storage_content(self, node: str, storage: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/storage/{storage}/content")

    # ------------------------------------------------------------------ Ceph (node-scoped)
    def get_ceph_osds(self, node: str) -> Dict:
        return self._get(f"/nodes/{node}/ceph/osd")

    def get_ceph_pools(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/ceph/pool")

    def get_ceph_mons(self, node: str) -> List[Dict]:
        return self._get(f"/nodes/{node}/ceph/mon")
