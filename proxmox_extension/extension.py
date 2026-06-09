import logging
from typing import Any, Dict, List, Optional
from dynatrace_extension import Extension
from .proxmox_client import ProxmoxClient

logger = logging.getLogger(__name__)

# PVE services we care about monitoring
MONITORED_SERVICES = {
    "pve-cluster", "pvedaemon", "pveproxy", "pvestatd",
    "pvescheduler", "corosync", "pve-firewall",
}


def _latest(rrddata: List[Dict], field: str) -> Optional[float]:
    """Return the most recent non-null value for a field from rrddata."""
    for entry in reversed(rrddata):
        val = entry.get(field)
        if val is not None:
            return float(val)
    return None


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
        cluster_name = self._collect_cluster(client)
        self._collect_ha(client, cluster_name)
        self._collect_replication(client, cluster_name)
        self._collect_backups(client, cluster_name)
        self._collect_ceph(client, cluster_name)
        self._collect_nodes(client, cluster_name)

    # ------------------------------------------------------------------ Cluster

    def _collect_cluster(self, client: ProxmoxClient) -> str:
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
        return cluster_name

    # ------------------------------------------------------------------ HA

    def _collect_ha(self, client: ProxmoxClient, cluster_name: str):
        try:
            dims = {"cluster_name": cluster_name}
            quorate = 0
            for item in client.get_ha_status():
                if item.get("type") == "quorum":
                    quorate = 1 if item.get("quorate", 0) else 0
            self.report_metric("custom.proxmox.cluster.ha.quorate", quorate, dims)

            for resource in client.get_ha_resources():
                sid = resource.get("sid", "unknown")
                state = resource.get("state", "")
                rdims = {"ha_resource": sid, "cluster_name": cluster_name}
                self.report_metric(
                    "custom.proxmox.cluster.ha.resource.running",
                    1 if state == "started" else 0,
                    rdims,
                )
        except Exception:
            logger.exception("Error collecting HA metrics")

    # ------------------------------------------------------------------ Replication

    def _collect_replication(self, client: ProxmoxClient, cluster_name: str):
        try:
            for job in client.get_replication_jobs():
                job_id = job.get("id", "unknown")
                rdims = {"replication_job": job_id, "cluster_name": cluster_name}
                self.report_metric("custom.proxmox.cluster.replication.fail_count", job.get("fail_count", 0), rdims)
                duration = job.get("duration", 0)
                if duration:
                    self.report_metric("custom.proxmox.cluster.replication.duration", duration, rdims)
                self.report_metric("custom.proxmox.cluster.replication.error", 1 if job.get("error") else 0, rdims)
        except Exception:
            logger.exception("Error collecting replication metrics")

    # ------------------------------------------------------------------ Backups

    def _collect_backups(self, client: ProxmoxClient, cluster_name: str):
        try:
            dims = {"cluster_name": cluster_name}
            self.report_metric(
                "custom.proxmox.cluster.backup.unprotected_guests",
                len(client.get_not_backed_up()),
                dims,
            )
        except Exception:
            logger.exception("Error collecting backup metrics")

    # ------------------------------------------------------------------ Ceph

    def _collect_ceph(self, client: ProxmoxClient, cluster_name: str):
        try:
            status = client.get_ceph_status()
            dims = {"cluster_name": cluster_name}

            health_str = status.get("health", {}).get("status", "HEALTH_UNKNOWN")
            health_val = {"HEALTH_OK": 2, "HEALTH_WARN": 1, "HEALTH_ERR": 0}.get(health_str, -1)
            self.report_metric("custom.proxmox.ceph.health", health_val, dims)

            osdmap = status.get("osdmap", {})
            self.report_metric("custom.proxmox.ceph.osd.total", osdmap.get("num_osds", 0), dims)
            self.report_metric("custom.proxmox.ceph.osd.up", osdmap.get("num_up_osds", 0), dims)
            self.report_metric("custom.proxmox.ceph.osd.in", osdmap.get("num_in_osds", 0), dims)

            pgmap = status.get("pgmap", {})
            self.report_metric("custom.proxmox.ceph.pg.total", pgmap.get("num_pgs", 0), dims)
            self.report_metric("custom.proxmox.ceph.bytes.used", pgmap.get("bytes_used", 0), dims)
            self.report_metric("custom.proxmox.ceph.bytes.avail", pgmap.get("bytes_avail", 0), dims)
            self.report_metric("custom.proxmox.ceph.bytes.total", pgmap.get("bytes_total", 0), dims)
            self.report_metric("custom.proxmox.ceph.io.read_bps", pgmap.get("read_bytes_sec", 0), dims)
            self.report_metric("custom.proxmox.ceph.io.write_bps", pgmap.get("write_bytes_sec", 0), dims)
            self.report_metric("custom.proxmox.ceph.io.recovering_bps", pgmap.get("recovering_bytes_per_sec", 0), dims)

            monmap = status.get("monmap", {})
            self.report_metric("custom.proxmox.ceph.mon.count", monmap.get("num_mons", 0), dims)

            try:
                for flag in client.get_ceph_flags():
                    name = flag.get("name", "")
                    if name in ("noout", "noin", "nodown", "pause", "full", "nearfull"):
                        fdims = {"ceph_flag": name, "cluster_name": cluster_name}
                        self.report_metric("custom.proxmox.ceph.flag", 1 if flag.get("value") else 0, fdims)
            except Exception:
                logger.debug("Ceph flags not available")

        except Exception:
            logger.debug("Ceph not configured or not accessible — skipping")

    # ------------------------------------------------------------------ Nodes

    def _collect_nodes(self, client: ProxmoxClient, cluster_name: str):
        for node_summary in client.get_nodes():
            node = node_summary.get("node")
            if not node:
                continue
            try:
                status = client.get_node_status(node)
                dims = {"node_name": node, "cluster_name": cluster_name}

                # CPU
                self.report_metric("custom.proxmox.node.cpu.usage", status.get("cpu", 0) * 100, dims)
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

                # Root filesystem
                disk = status.get("rootfs", {})
                self.report_metric("custom.proxmox.node.disk.used", disk.get("used", 0), dims)
                self.report_metric("custom.proxmox.node.disk.total", disk.get("total", 0), dims)
                self.report_metric("custom.proxmox.node.disk.avail", disk.get("avail", 0), dims)

                # Network (aggregate)
                self.report_metric("custom.proxmox.node.network.in", node_summary.get("netin", 0), dims)
                self.report_metric("custom.proxmox.node.network.out", node_summary.get("netout", 0), dims)

                # Uptime / KSM
                self.report_metric("custom.proxmox.node.uptime", status.get("uptime", 0), dims)
                ksm = status.get("ksm", {})
                if ksm:
                    self.report_metric("custom.proxmox.node.ksm.shared", ksm.get("shared", 0), dims)

                # RRD — metrics only available here
                self._collect_node_rrddata(client, node, cluster_name)

                # Services / subscription / updates / tasks / netstat
                self._collect_node_services(client, node, cluster_name)
                self._collect_node_subscription(client, node, cluster_name)
                self._collect_node_updates(client, node, cluster_name)
                self._collect_node_netstat(client, node, cluster_name)
                self._collect_node_tasks(client, node, cluster_name)

                # Physical disks + SMART
                self._collect_disks(client, node, cluster_name)

                # VMs / LXC / Storage
                self._collect_vms(client, node, cluster_name)
                self._collect_containers(client, node, cluster_name)
                self._collect_storage(client, node, cluster_name)

            except Exception:
                logger.exception("Error collecting metrics for node %s", node)

    def _collect_node_rrddata(self, client: ProxmoxClient, node: str, cluster_name: str):
        try:
            rrd = client.get_node_rrddata(node)
            if not rrd:
                return
            dims = {"node_name": node, "cluster_name": cluster_name}

            # iowait — not available from /nodes/{node}/status
            iowait = _latest(rrd, "iowait")
            if iowait is not None:
                self.report_metric("custom.proxmox.node.cpu.iowait", iowait * 100, dims)

            # Memory available (different from free — accounts for cache)
            memavail = _latest(rrd, "memavailable")
            if memavail is not None:
                self.report_metric("custom.proxmox.node.memory.available", memavail, dims)

            # ZFS ARC size
            arcsize = _latest(rrd, "arcsize")
            if arcsize is not None:
                self.report_metric("custom.proxmox.node.zfs.arcsize", arcsize, dims)

            # Linux PSI (Pressure Stall Information) — kernel 4.20+
            for field, key in (
                ("pressurecpusome",    "custom.proxmox.node.pressure.cpu.some"),
                ("pressureiosome",     "custom.proxmox.node.pressure.io.some"),
                ("pressureiofull",     "custom.proxmox.node.pressure.io.full"),
                ("pressurememorysome", "custom.proxmox.node.pressure.memory.some"),
                ("pressurememoryfull", "custom.proxmox.node.pressure.memory.full"),
            ):
                val = _latest(rrd, field)
                if val is not None:
                    self.report_metric(key, val * 100, dims)
        except Exception:
            logger.debug("Could not collect rrddata for node %s", node)

    def _collect_node_services(self, client: ProxmoxClient, node: str, cluster_name: str):
        try:
            for svc in client.get_node_services(node):
                name = svc.get("service", svc.get("name", ""))
                if name not in MONITORED_SERVICES:
                    continue
                active = 1 if svc.get("active-state", svc.get("state", "")) == "active" else 0
                sdims = {"service_name": name, "node_name": node, "cluster_name": cluster_name}
                self.report_metric("custom.proxmox.node.service.status", active, sdims)
        except Exception:
            logger.exception("Error collecting service metrics for node %s", node)

    def _collect_node_subscription(self, client: ProxmoxClient, node: str, cluster_name: str):
        try:
            sub = client.get_node_subscription(node)
            active = 1 if sub.get("status", "notfound") == "active" else 0
            dims = {"node_name": node, "cluster_name": cluster_name}
            self.report_metric("custom.proxmox.node.subscription.active", active, dims)
        except Exception:
            logger.debug("Could not collect subscription for node %s", node)

    def _collect_node_updates(self, client: ProxmoxClient, node: str, cluster_name: str):
        try:
            updates = client.get_node_apt_updates(node)
            proxmox_updates = sum(1 for u in updates if "proxmox" in u.get("Origin", "").lower())
            dims = {"node_name": node, "cluster_name": cluster_name}
            self.report_metric("custom.proxmox.node.updates.pending", len(updates), dims)
            self.report_metric("custom.proxmox.node.updates.proxmox_pending", proxmox_updates, dims)
        except Exception:
            logger.debug("Could not collect apt updates for node %s", node)

    def _collect_node_netstat(self, client: ProxmoxClient, node: str, cluster_name: str):
        try:
            for iface in client.get_node_netstat(node):
                vmid = str(iface.get("vmid", ""))
                dev = iface.get("dev", "")
                if not vmid or not dev:
                    continue
                idims = {"vmid": vmid, "iface": dev, "node_name": node, "cluster_name": cluster_name}
                self.report_metric("custom.proxmox.node.netstat.in", iface.get("in", 0), idims)
                self.report_metric("custom.proxmox.node.netstat.out", iface.get("out", 0), idims)
        except Exception:
            logger.debug("Could not collect netstat for node %s", node)

    def _collect_node_tasks(self, client: ProxmoxClient, node: str, cluster_name: str):
        try:
            tasks = client.get_node_tasks(node)
            error_count = sum(1 for t in tasks if t.get("status", "").startswith("FAILED"))
            running_count = sum(1 for t in tasks if not t.get("endtime"))
            dims = {"node_name": node, "cluster_name": cluster_name}
            self.report_metric("custom.proxmox.node.tasks.errors", error_count, dims)
            self.report_metric("custom.proxmox.node.tasks.running", running_count, dims)
        except Exception:
            logger.debug("Could not collect tasks for node %s", node)

    # ------------------------------------------------------------------ Physical Disks

    def _collect_disks(self, client: ProxmoxClient, node: str, cluster_name: str):
        try:
            for disk in client.get_node_disks(node):
                dev = disk.get("devpath", disk.get("dev", ""))
                if not dev:
                    continue
                disk_name = dev.replace("/dev/", "")
                dims = {"disk_dev": disk_name, "node_name": node, "cluster_name": cluster_name}
                self.report_metric("custom.proxmox.node.disk.device.size", disk.get("size", 0), dims)
                health = disk.get("health", "")
                health_val = 1 if health.upper() == "PASSED" else (0 if health.upper() == "FAILED" else -1)
                self.report_metric("custom.proxmox.node.disk.device.smart", health_val, dims)
                self._collect_disk_smart(client, node, dev, disk_name, cluster_name)
        except Exception:
            logger.exception("Error collecting disk list for node %s", node)

    def _collect_disk_smart(self, client: ProxmoxClient, node: str, dev: str, disk_name: str, cluster_name: str):
        try:
            smart = client.get_disk_smart(node, dev)
            dims = {"disk_dev": disk_name, "node_name": node, "cluster_name": cluster_name}
            SMART_IDS = {
                5:   "reallocated_sectors",
                9:   "power_on_hours",
                187: "uncorrectable_errors",
                188: "command_timeout",
                197: "pending_sectors",
                198: "uncorrectable_sector_count",
                199: "udma_crc_errors",
            }
            for attr in smart.get("attributes", []):
                attr_id = attr.get("id")
                if attr_id in SMART_IDS:
                    adims = {**dims, "smart_attr": SMART_IDS[attr_id]}
                    raw = attr.get("raw", {})
                    raw_val = raw.get("value", 0) if isinstance(raw, dict) else int(raw or 0)
                    self.report_metric("custom.proxmox.node.disk.device.smart_attr", raw_val, adims)
        except Exception:
            logger.debug("SMART data not available for %s on %s", dev, node)

    # ------------------------------------------------------------------ VMs

    def _collect_vms(self, client: ProxmoxClient, node: str, cluster_name: str):
        for vm in client.get_vms(node):
            vmid = vm.get("vmid")
            name = vm.get("name", str(vmid))
            if not vmid:
                continue
            try:
                status = client.get_vm_status(node, vmid)
                dims = {"vmid": str(vmid), "vm_name": name, "node_name": node, "cluster_name": cluster_name}

                vm_running = 1 if status.get("status") == "running" else 0
                self.report_metric("custom.proxmox.vm.status", vm_running, dims)

                # CPU (live)
                self.report_metric("custom.proxmox.vm.cpu.usage", status.get("cpu", 0) * 100, dims)
                self.report_metric("custom.proxmox.vm.cpu.count", status.get("cpus", 0), dims)

                # Memory (live)
                self.report_metric("custom.proxmox.vm.memory.used", status.get("mem", 0), dims)
                self.report_metric("custom.proxmox.vm.memory.total", status.get("maxmem", 0), dims)

                # Balloon (live)
                balloon = status.get("ballooninfo", {})
                if balloon:
                    self.report_metric("custom.proxmox.vm.balloon.current", balloon.get("current_allocated", 0), dims)
                    self.report_metric("custom.proxmox.vm.balloon.target", balloon.get("target_allocated", 0), dims)

                # Disk I/O (live)
                self.report_metric("custom.proxmox.vm.disk.read", status.get("diskread", 0), dims)
                self.report_metric("custom.proxmox.vm.disk.write", status.get("diskwrite", 0), dims)
                self.report_metric("custom.proxmox.vm.disk.size", status.get("maxdisk", 0), dims)

                # Network (live)
                self.report_metric("custom.proxmox.vm.network.in", status.get("netin", 0), dims)
                self.report_metric("custom.proxmox.vm.network.out", status.get("netout", 0), dims)

                self.report_metric("custom.proxmox.vm.uptime", status.get("uptime", 0), dims)

                # Config — configured limits (not live usage)
                self._collect_vm_config(client, node, vmid, name, cluster_name)

                # RRD — disk usage + pressure metrics
                if vm_running:
                    self._collect_vm_rrddata(client, node, vmid, name, cluster_name)

                # Snapshots
                self._collect_vm_snapshots(client, node, vmid, name, cluster_name)

                # Guest agent
                if vm_running and status.get("agent", 0):
                    self._collect_vm_agent(client, node, vmid, name, cluster_name)

            except Exception:
                logger.exception("Error collecting metrics for VM %s on %s", vmid, node)

    def _collect_vm_config(self, client: ProxmoxClient, node: str, vmid: int, vm_name: str, cluster_name: str):
        try:
            cfg = client.get_vm_config(node, vmid)
            dims = {"vmid": str(vmid), "vm_name": vm_name, "node_name": node, "cluster_name": cluster_name}

            self.report_metric("custom.proxmox.vm.config.cores", cfg.get("cores", 1), dims)
            self.report_metric("custom.proxmox.vm.config.sockets", cfg.get("sockets", 1), dims)
            self.report_metric("custom.proxmox.vm.config.memory_mib", cfg.get("memory", 0), dims)
            self.report_metric("custom.proxmox.vm.config.balloon_mib", cfg.get("balloon", 0), dims)
            self.report_metric("custom.proxmox.vm.config.cpulimit", cfg.get("cpulimit", 0), dims)
            self.report_metric("custom.proxmox.vm.config.cpuunits", cfg.get("cpuunits", 1024), dims)
            self.report_metric("custom.proxmox.vm.config.onboot", 1 if cfg.get("onboot", 0) else 0, dims)
        except Exception:
            logger.debug("Could not collect config for VM %s on %s", vmid, node)

    def _collect_vm_rrddata(self, client: ProxmoxClient, node: str, vmid: int, vm_name: str, cluster_name: str):
        try:
            rrd = client.get_vm_rrddata(node, vmid)
            if not rrd:
                return
            dims = {"vmid": str(vmid), "vm_name": vm_name, "node_name": node, "cluster_name": cluster_name}

            # Actual disk usage — not available from status/current
            disk_used = _latest(rrd, "disk")
            if disk_used is not None:
                self.report_metric("custom.proxmox.vm.disk.used", disk_used, dims)

            # Host memory used by guest (balloon perspective)
            memhost = _latest(rrd, "memhost")
            if memhost is not None:
                self.report_metric("custom.proxmox.vm.memory.host", memhost, dims)

            # PSI pressure metrics
            for field, key in (
                ("pressurecpusome",    "custom.proxmox.vm.pressure.cpu.some"),
                ("pressurecpufull",    "custom.proxmox.vm.pressure.cpu.full"),
                ("pressureiosome",     "custom.proxmox.vm.pressure.io.some"),
                ("pressurememorysome", "custom.proxmox.vm.pressure.memory.some"),
                ("pressurememoryfull", "custom.proxmox.vm.pressure.memory.full"),
            ):
                val = _latest(rrd, field)
                if val is not None:
                    self.report_metric(key, val * 100, dims)
        except Exception:
            logger.debug("Could not collect rrddata for VM %s on %s", vmid, node)

    def _collect_vm_snapshots(self, client: ProxmoxClient, node: str, vmid: int, vm_name: str, cluster_name: str):
        try:
            snaps = client.get_vm_snapshots(node, vmid)
            real_snaps = [s for s in snaps if s.get("name") != "current"]
            dims = {"vmid": str(vmid), "vm_name": vm_name, "node_name": node, "cluster_name": cluster_name}
            self.report_metric("custom.proxmox.vm.snapshot.count", len(real_snaps), dims)
        except Exception:
            logger.debug("Could not collect snapshots for VM %s on %s", vmid, node)

    def _collect_vm_agent(self, client: ProxmoxClient, node: str, vmid: int, vm_name: str, cluster_name: str):
        try:
            for fs in client.get_vm_agent_fsinfo(node, vmid):
                mp = fs.get("mountpoint", "")
                if not mp:
                    continue
                fdims = {"vmid": str(vmid), "vm_name": vm_name, "mountpoint": mp, "node_name": node, "cluster_name": cluster_name}
                self.report_metric("custom.proxmox.vm.agent.disk.used", fs.get("used-bytes", 0), fdims)
                self.report_metric("custom.proxmox.vm.agent.disk.total", fs.get("total-bytes", 0), fdims)
        except Exception:
            logger.debug("Guest agent fsinfo not available for VM %s", vmid)

        try:
            for iface in client.get_vm_agent_network(node, vmid):
                iface_name = iface.get("name", "")
                if not iface_name or iface_name == "lo":
                    continue
                stats = iface.get("statistics", {})
                if not stats:
                    continue
                idims = {"vmid": str(vmid), "vm_name": vm_name, "iface": iface_name, "node_name": node, "cluster_name": cluster_name}
                self.report_metric("custom.proxmox.vm.agent.net.rx_bytes", stats.get("rx-bytes", 0), idims)
                self.report_metric("custom.proxmox.vm.agent.net.tx_bytes", stats.get("tx-bytes", 0), idims)
                self.report_metric("custom.proxmox.vm.agent.net.rx_errors", stats.get("rx-errs", 0), idims)
                self.report_metric("custom.proxmox.vm.agent.net.tx_errors", stats.get("tx-errs", 0), idims)
                self.report_metric("custom.proxmox.vm.agent.net.rx_dropped", stats.get("rx-dropped", 0), idims)
                self.report_metric("custom.proxmox.vm.agent.net.tx_dropped", stats.get("tx-dropped", 0), idims)
        except Exception:
            logger.debug("Guest agent network info not available for VM %s", vmid)

    # ------------------------------------------------------------------ LXC

    def _collect_containers(self, client: ProxmoxClient, node: str, cluster_name: str):
        for ct in client.get_containers(node):
            vmid = ct.get("vmid")
            name = ct.get("name", str(vmid))
            if not vmid:
                continue
            try:
                status = client.get_container_status(node, vmid)
                dims = {"vmid": str(vmid), "lxc_name": name, "node_name": node, "cluster_name": cluster_name}

                ct_running = 1 if status.get("status") == "running" else 0
                self.report_metric("custom.proxmox.lxc.status", ct_running, dims)

                # CPU (live)
                self.report_metric("custom.proxmox.lxc.cpu.usage", status.get("cpu", 0) * 100, dims)
                self.report_metric("custom.proxmox.lxc.cpu.count", status.get("cpus", 0), dims)

                # Memory (live)
                self.report_metric("custom.proxmox.lxc.memory.used", status.get("mem", 0), dims)
                self.report_metric("custom.proxmox.lxc.memory.total", status.get("maxmem", 0), dims)

                # Swap (live)
                self.report_metric("custom.proxmox.lxc.swap.used", status.get("swap", 0), dims)
                self.report_metric("custom.proxmox.lxc.swap.total", status.get("maxswap", 0), dims)

                # Disk I/O (live)
                self.report_metric("custom.proxmox.lxc.disk.read", status.get("diskread", 0), dims)
                self.report_metric("custom.proxmox.lxc.disk.write", status.get("diskwrite", 0), dims)
                self.report_metric("custom.proxmox.lxc.disk.size", status.get("maxdisk", 0), dims)

                # Network (live)
                self.report_metric("custom.proxmox.lxc.network.in", status.get("netin", 0), dims)
                self.report_metric("custom.proxmox.lxc.network.out", status.get("netout", 0), dims)

                # Config — configured limits
                self._collect_ct_config(client, node, vmid, name, cluster_name)

                # RRD — disk usage + pressure
                if ct_running:
                    self._collect_ct_rrddata(client, node, vmid, name, cluster_name)

                # Snapshots
                self._collect_ct_snapshots(client, node, vmid, name, cluster_name)

            except Exception:
                logger.exception("Error collecting metrics for LXC %s on %s", vmid, node)

    def _collect_ct_config(self, client: ProxmoxClient, node: str, vmid: int, lxc_name: str, cluster_name: str):
        try:
            cfg = client.get_container_config(node, vmid)
            dims = {"vmid": str(vmid), "lxc_name": lxc_name, "node_name": node, "cluster_name": cluster_name}

            self.report_metric("custom.proxmox.lxc.config.cores", cfg.get("cores", 1), dims)
            self.report_metric("custom.proxmox.lxc.config.memory_mib", cfg.get("memory", 0), dims)
            self.report_metric("custom.proxmox.lxc.config.swap_mib", cfg.get("swap", 0), dims)
            self.report_metric("custom.proxmox.lxc.config.cpulimit", cfg.get("cpulimit", 0), dims)
            self.report_metric("custom.proxmox.lxc.config.cpuunits", cfg.get("cpuunits", 1024), dims)
            self.report_metric("custom.proxmox.lxc.config.onboot", 1 if cfg.get("onboot", 0) else 0, dims)
            self.report_metric("custom.proxmox.lxc.config.unprivileged", 1 if cfg.get("unprivileged", 0) else 0, dims)
        except Exception:
            logger.debug("Could not collect config for LXC %s on %s", vmid, node)

    def _collect_ct_rrddata(self, client: ProxmoxClient, node: str, vmid: int, lxc_name: str, cluster_name: str):
        try:
            rrd = client.get_container_rrddata(node, vmid)
            if not rrd:
                return
            dims = {"vmid": str(vmid), "lxc_name": lxc_name, "node_name": node, "cluster_name": cluster_name}

            disk_used = _latest(rrd, "disk")
            if disk_used is not None:
                self.report_metric("custom.proxmox.lxc.disk.used", disk_used, dims)

            memhost = _latest(rrd, "memhost")
            if memhost is not None:
                self.report_metric("custom.proxmox.lxc.memory.host", memhost, dims)

            for field, key in (
                ("pressurecpusome",    "custom.proxmox.lxc.pressure.cpu.some"),
                ("pressurecpufull",    "custom.proxmox.lxc.pressure.cpu.full"),
                ("pressureiosome",     "custom.proxmox.lxc.pressure.io.some"),
                ("pressurememorysome", "custom.proxmox.lxc.pressure.memory.some"),
                ("pressurememoryfull", "custom.proxmox.lxc.pressure.memory.full"),
            ):
                val = _latest(rrd, field)
                if val is not None:
                    self.report_metric(key, val * 100, dims)
        except Exception:
            logger.debug("Could not collect rrddata for LXC %s on %s", vmid, node)

    def _collect_ct_snapshots(self, client: ProxmoxClient, node: str, vmid: int, lxc_name: str, cluster_name: str):
        try:
            snaps = client.get_container_snapshots(node, vmid)
            real_snaps = [s for s in snaps if s.get("name") != "current"]
            dims = {"vmid": str(vmid), "lxc_name": lxc_name, "node_name": node, "cluster_name": cluster_name}
            self.report_metric("custom.proxmox.lxc.snapshot.count", len(real_snaps), dims)
        except Exception:
            logger.debug("Could not collect snapshots for LXC %s on %s", vmid, node)

    # ------------------------------------------------------------------ Storage

    def _collect_storage(self, client: ProxmoxClient, node: str, cluster_name: str):
        for storage in client.get_storage(node):
            name = storage.get("storage")
            if not name:
                continue
            dims = {"storage_name": name, "node_name": node, "cluster_name": cluster_name}

            self.report_metric("custom.proxmox.storage.used", storage.get("used", 0), dims)
            self.report_metric("custom.proxmox.storage.total", storage.get("total", 0), dims)
            self.report_metric("custom.proxmox.storage.avail", storage.get("avail", 0), dims)
            self.report_metric("custom.proxmox.storage.enabled", 1 if storage.get("enabled", 1) else 0, dims)
            self.report_metric("custom.proxmox.storage.active", 1 if storage.get("active", 0) else 0, dims)

            self._collect_storage_backups(client, node, name, cluster_name)

    def _collect_storage_backups(self, client: ProxmoxClient, node: str, storage: str, cluster_name: str):
        try:
            content = client.get_storage_content(node, storage)
            backup_count = sum(1 for c in content if "backup" in str(c.get("volid", "")) or c.get("content") == "backup")
            dims = {"storage_name": storage, "node_name": node, "cluster_name": cluster_name}
            self.report_metric("custom.proxmox.storage.backup_count", backup_count, dims)
        except Exception:
            logger.debug("Could not collect content for storage %s on %s", storage, node)
