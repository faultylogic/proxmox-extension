import logging
from dynatrace_extension import Extension, Status, StatusValue
from .proxmox_client import ProxmoxClient

logger = logging.getLogger(__name__)


class ProxmoxExtension(Extension):

    def initialize(self):
        self.client = None

    def query(self):
        config = self.activation_config
        try:
            client = ProxmoxClient(
                host=config["host"],
                port=int(config.get("port", 8006)),
                username=config["username"],
                token_name=config["token_name"],
                token_value=config["token_value"],
                verify_ssl=bool(config.get("verify_ssl", False)),
            )
            self._collect_cluster(client)
            self._collect_nodes(client)
            self.report_status(Status(StatusValue.OK, "Proxmox metrics collected"))
        except Exception as e:
            logger.exception("Failed to collect Proxmox metrics")
            self.report_status(Status(StatusValue.GENERIC_ERROR, str(e)))

    def _collect_cluster(self, client: ProxmoxClient):
        cluster_status = client.get_cluster_status()
        cluster_name = "proxmox"
        nodes_total = 0
        nodes_online = 0

        for item in cluster_status:
            if item.get("type") == "cluster":
                cluster_name = item.get("name", "proxmox")
            elif item.get("type") == "node":
                nodes_total += 1
                if item.get("online", 0):
                    nodes_online += 1

        dims = {"cluster_name": cluster_name}
        self.report_metric("custom.proxmox.cluster.nodes.total", nodes_total, dims)
        self.report_metric("custom.proxmox.cluster.nodes.online", nodes_online, dims)

    def _collect_nodes(self, client: ProxmoxClient):
        cluster_status = client.get_cluster_status()
        cluster_name = next(
            (i.get("name", "proxmox") for i in cluster_status if i.get("type") == "cluster"),
            "proxmox",
        )

        for node_summary in client.get_nodes():
            node = node_summary.get("node")
            if not node:
                continue
            try:
                status = client.get_node_status(node)
                dims = {"node_name": node, "cluster_name": cluster_name}

                cpu = status.get("cpu", 0)
                self.report_metric("custom.proxmox.node.cpu.usage", cpu * 100, dims)

                mem = status.get("memory", {})
                self.report_metric("custom.proxmox.node.memory.used", mem.get("used", 0), dims)
                self.report_metric("custom.proxmox.node.memory.total", mem.get("total", 0), dims)

                disk = status.get("rootfs", {})
                self.report_metric("custom.proxmox.node.disk.used", disk.get("used", 0), dims)
                self.report_metric("custom.proxmox.node.disk.total", disk.get("total", 0), dims)

                net = status.get("ksm", {})  # network totals are in node summary
                self.report_metric("custom.proxmox.node.network.in", node_summary.get("netin", 0), dims)
                self.report_metric("custom.proxmox.node.network.out", node_summary.get("netout", 0), dims)
                self.report_metric("custom.proxmox.node.uptime", status.get("uptime", 0), dims)

                self._collect_vms(client, node, cluster_name)
                self._collect_containers(client, node, cluster_name)
                self._collect_storage(client, node, cluster_name)
            except Exception:
                logger.exception("Error collecting metrics for node %s", node)

    def _collect_vms(self, client: ProxmoxClient, node: str, cluster_name: str):
        for vm in client.get_vms(node):
            vmid = vm.get("vmid")
            name = vm.get("name", str(vmid))
            if not vmid:
                continue
            try:
                status = client.get_vm_status(node, vmid)
                dims = {"vmid": str(vmid), "vm_name": name, "node_name": node, "cluster_name": cluster_name}

                self.report_metric("custom.proxmox.vm.cpu.usage", status.get("cpu", 0) * 100, dims)
                self.report_metric("custom.proxmox.vm.memory.used", status.get("mem", 0), dims)
                self.report_metric("custom.proxmox.vm.memory.total", status.get("maxmem", 0), dims)
                self.report_metric("custom.proxmox.vm.disk.read", status.get("diskread", 0), dims)
                self.report_metric("custom.proxmox.vm.disk.write", status.get("diskwrite", 0), dims)
                self.report_metric("custom.proxmox.vm.network.in", status.get("netin", 0), dims)
                self.report_metric("custom.proxmox.vm.network.out", status.get("netout", 0), dims)
                self.report_metric("custom.proxmox.vm.uptime", status.get("uptime", 0), dims)
            except Exception:
                logger.exception("Error collecting metrics for VM %s on %s", vmid, node)

    def _collect_containers(self, client: ProxmoxClient, node: str, cluster_name: str):
        for ct in client.get_containers(node):
            vmid = ct.get("vmid")
            name = ct.get("name", str(vmid))
            if not vmid:
                continue
            try:
                status = client.get_container_status(node, vmid)
                dims = {"vmid": str(vmid), "lxc_name": name, "node_name": node, "cluster_name": cluster_name}

                self.report_metric("custom.proxmox.lxc.cpu.usage", status.get("cpu", 0) * 100, dims)
                self.report_metric("custom.proxmox.lxc.memory.used", status.get("mem", 0), dims)
                self.report_metric("custom.proxmox.lxc.memory.total", status.get("maxmem", 0), dims)
                self.report_metric("custom.proxmox.lxc.disk.read", status.get("diskread", 0), dims)
                self.report_metric("custom.proxmox.lxc.disk.write", status.get("diskwrite", 0), dims)
                self.report_metric("custom.proxmox.lxc.network.in", status.get("netin", 0), dims)
                self.report_metric("custom.proxmox.lxc.network.out", status.get("netout", 0), dims)
            except Exception:
                logger.exception("Error collecting metrics for LXC %s on %s", vmid, node)

    def _collect_storage(self, client: ProxmoxClient, node: str, cluster_name: str):
        for storage in client.get_storage(node):
            name = storage.get("storage")
            if not name:
                continue
            dims = {"storage_name": name, "node_name": node, "cluster_name": cluster_name}
            self.report_metric("custom.proxmox.storage.used", storage.get("used", 0), dims)
            self.report_metric("custom.proxmox.storage.total", storage.get("total", 0), dims)
