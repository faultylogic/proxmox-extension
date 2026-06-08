import logging
from dynatrace_extension import Extension
from .proxmox_client import ProxmoxClient

logger = logging.getLogger(__name__)


class ProxmoxExtension(Extension):

    def initialize(self):
        self.client = None

    def query(self):
        config = self.activation_config
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

                # CPU
                cpu = status.get("cpu", 0)
                self.report_metric("custom.proxmox.node.cpu.usage", cpu * 100, dims)
                cpuinfo = status.get("cpuinfo", {})
                self.report_metric("custom.proxmox.node.cpu.count", cpuinfo.get("cpus", 0), dims)
                self.report_metric("custom.proxmox.node.cpu.sockets", cpuinfo.get("sockets", 0), dims)

                # Load average
                loadavg = status.get("loadavg", [0, 0, 0])
                self.report_metric("custom.proxmox.node.loadavg.1m", float(loadavg[0]) if len(loadavg) > 0 else 0, dims)
                self.report_metric("custom.proxmox.node.loadavg.5m", float(loadavg[1]) if len(loadavg) > 1 else 0, dims)
                self.report_metric("custom.proxmox.node.loadavg.15m", float(loadavg[2]) if len(loadavg) > 2 else 0, dims)

                # Memory
                mem = status.get("memory", {})
                self.report_metric("custom.proxmox.node.memory.used", mem.get("used", 0), dims)
                self.report_metric("custom.proxmox.node.memory.total", mem.get("total", 0), dims)
                self.report_metric("custom.proxmox.node.memory.free", mem.get("free", 0), dims)

                # Swap
                swap = status.get("swap", {})
                self.report_metric("custom.proxmox.node.swap.used", swap.get("used", 0), dims)
                self.report_metric("custom.proxmox.node.swap.total", swap.get("total", 0), dims)
                self.report_metric("custom.proxmox.node.swap.free", swap.get("free", 0), dims)

                # Disk (root filesystem)
                disk = status.get("rootfs", {})
                self.report_metric("custom.proxmox.node.disk.used", disk.get("used", 0), dims)
                self.report_metric("custom.proxmox.node.disk.total", disk.get("total", 0), dims)
                self.report_metric("custom.proxmox.node.disk.avail", disk.get("avail", 0), dims)

                # Network (from node list summary)
                self.report_metric("custom.proxmox.node.network.in", node_summary.get("netin", 0), dims)
                self.report_metric("custom.proxmox.node.network.out", node_summary.get("netout", 0), dims)

                # Uptime
                self.report_metric("custom.proxmox.node.uptime", status.get("uptime", 0), dims)

                # KSM (Kernel Same-page Merging) deduplication
                ksm = status.get("ksm", {})
                if ksm:
                    self.report_metric("custom.proxmox.node.ksm.shared", ksm.get("shared", 0), dims)

                self._collect_vms(client, node, cluster_name)
                self._collect_containers(client, node, cluster_name)
                self._collect_storage(client, node, cluster_name)
                self._collect_disks(client, node, cluster_name)
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

                # Status: 1=running, 0=stopped/other
                vm_status = 1 if status.get("status") == "running" else 0
                self.report_metric("custom.proxmox.vm.status", vm_status, dims)

                # CPU
                self.report_metric("custom.proxmox.vm.cpu.usage", status.get("cpu", 0) * 100, dims)
                self.report_metric("custom.proxmox.vm.cpu.count", status.get("cpus", 0), dims)

                # Memory
                self.report_metric("custom.proxmox.vm.memory.used", status.get("mem", 0), dims)
                self.report_metric("custom.proxmox.vm.memory.total", status.get("maxmem", 0), dims)

                # Balloon memory (if enabled)
                balloon = status.get("ballooninfo", {})
                if balloon:
                    self.report_metric("custom.proxmox.vm.balloon.current", balloon.get("current_allocated", 0), dims)
                    self.report_metric("custom.proxmox.vm.balloon.target", balloon.get("target_allocated", 0), dims)

                # Disk I/O
                self.report_metric("custom.proxmox.vm.disk.read", status.get("diskread", 0), dims)
                self.report_metric("custom.proxmox.vm.disk.write", status.get("diskwrite", 0), dims)
                self.report_metric("custom.proxmox.vm.disk.size", status.get("maxdisk", 0), dims)

                # Network
                self.report_metric("custom.proxmox.vm.network.in", status.get("netin", 0), dims)
                self.report_metric("custom.proxmox.vm.network.out", status.get("netout", 0), dims)

                # Uptime
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

                # Status: 1=running, 0=stopped/other
                ct_status = 1 if status.get("status") == "running" else 0
                self.report_metric("custom.proxmox.lxc.status", ct_status, dims)

                # CPU
                self.report_metric("custom.proxmox.lxc.cpu.usage", status.get("cpu", 0) * 100, dims)
                self.report_metric("custom.proxmox.lxc.cpu.count", status.get("cpus", 0), dims)

                # Memory
                self.report_metric("custom.proxmox.lxc.memory.used", status.get("mem", 0), dims)
                self.report_metric("custom.proxmox.lxc.memory.total", status.get("maxmem", 0), dims)

                # Swap
                self.report_metric("custom.proxmox.lxc.swap.used", status.get("swap", 0), dims)
                self.report_metric("custom.proxmox.lxc.swap.total", status.get("maxswap", 0), dims)

                # Disk I/O
                self.report_metric("custom.proxmox.lxc.disk.read", status.get("diskread", 0), dims)
                self.report_metric("custom.proxmox.lxc.disk.write", status.get("diskwrite", 0), dims)
                self.report_metric("custom.proxmox.lxc.disk.size", status.get("maxdisk", 0), dims)

                # Network
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

            # Basic stats from list endpoint
            self.report_metric("custom.proxmox.storage.used", storage.get("used", 0), dims)
            self.report_metric("custom.proxmox.storage.total", storage.get("total", 0), dims)
            self.report_metric("custom.proxmox.storage.avail", storage.get("avail", 0), dims)

            # Enabled / active flags as gauges (1=true, 0=false)
            self.report_metric("custom.proxmox.storage.enabled", 1 if storage.get("enabled", 1) else 0, dims)
            self.report_metric("custom.proxmox.storage.active", 1 if storage.get("active", 0) else 0, dims)

    def _collect_disks(self, client: ProxmoxClient, node: str, cluster_name: str):
        try:
            disks = client.get_node_disks(node)
            for disk in disks:
                dev = disk.get("devpath", disk.get("dev", ""))
                if not dev:
                    continue
                # Normalise device name for use as a dimension value
                disk_name = dev.replace("/dev/", "")
                dims = {"disk_dev": disk_name, "node_name": node, "cluster_name": cluster_name}

                self.report_metric("custom.proxmox.node.disk.device.size", disk.get("size", 0), dims)
                health = disk.get("health", "")
                # SMART health: PASSED=1, FAILED=0, unknown=-1
                if health.upper() == "PASSED":
                    smart = 1
                elif health.upper() == "FAILED":
                    smart = 0
                else:
                    smart = -1
                self.report_metric("custom.proxmox.node.disk.device.smart", smart, dims)
        except Exception:
            logger.exception("Error collecting disk metrics for node %s", node)
