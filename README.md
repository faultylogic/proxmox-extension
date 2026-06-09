# Dynatrace Extension 2.0 — Proxmox VE

A Python-based Dynatrace Extension 2.0 that monitors a Proxmox VE cluster via the REST API, backed by the [proxmoxer](https://github.com/proxmoxer/proxmoxer) library. Runs on an ActiveGate and collects metrics for nodes, VMs, LXC containers, storage, Ceph, HA, and replication — surfacing them as custom metrics with full topology in Dynatrace.

---

## Table of Contents

- [Metrics Collected](#metrics-collected)
- [Prerequisites](#prerequisites)
- [Proxmox Setup](#proxmox-setup)
- [Guest Agent Setup (optional)](#guest-agent-setup-optional)
- [Build](#build)
- [Deploy](#deploy)
- [Configuration](#configuration)
- [Dashboards](#dashboards)
- [Project Structure](#project-structure)

---

## Metrics Collected

### Cluster

| Metric Key | Unit | Source |
|---|---|---|
| `custom.proxmox.cluster.nodes.total` | Count | `/cluster/status` |
| `custom.proxmox.cluster.nodes.online` | Count | `/cluster/status` |
| `custom.proxmox.cluster.backup.unprotected_guests` | Count | `/cluster/backup-info/not-backed-up` |
| `custom.proxmox.cluster.ha.quorate` | Count (1=yes) | `/cluster/ha/status/current` |
| `custom.proxmox.cluster.ha.resource.running` | Count (1=started) | `/cluster/ha/resources` |
| `custom.proxmox.cluster.replication.fail_count` | Count | `/cluster/replication` |
| `custom.proxmox.cluster.replication.duration` | Second | `/cluster/replication` |
| `custom.proxmox.cluster.replication.error` | Count (1=error) | `/cluster/replication` |

### Node — live stats

| Metric Key | Unit | Source |
|---|---|---|
| `custom.proxmox.node.cpu.usage` | Percent | `/nodes/{node}/status` |
| `custom.proxmox.node.cpu.count` | Count | `/nodes/{node}/status` |
| `custom.proxmox.node.cpu.sockets` | Count | `/nodes/{node}/status` |
| `custom.proxmox.node.loadavg.1m` / `5m` / `15m` | Count | `/nodes/{node}/status` |
| `custom.proxmox.node.memory.used` / `total` / `free` | Byte | `/nodes/{node}/status` |
| `custom.proxmox.node.swap.used` / `total` / `free` | Byte | `/nodes/{node}/status` |
| `custom.proxmox.node.disk.used` / `total` / `avail` | Byte | `/nodes/{node}/status` (rootfs) |
| `custom.proxmox.node.network.in` / `out` | Bit/hr | `/nodes` list |
| `custom.proxmox.node.netstat.in` / `out` | Byte | `/nodes/{node}/netstat` (per-VM tap) |
| `custom.proxmox.node.uptime` | Second | `/nodes/{node}/status` |
| `custom.proxmox.node.ksm.shared` | Byte | `/nodes/{node}/status` |
| `custom.proxmox.node.service.status` | Count (1=active) | `/nodes/{node}/services` |
| `custom.proxmox.node.subscription.active` | Count (1=yes) | `/nodes/{node}/subscription` |
| `custom.proxmox.node.updates.pending` | Count | `/nodes/{node}/apt/update` |
| `custom.proxmox.node.updates.proxmox_pending` | Count | `/nodes/{node}/apt/update` |
| `custom.proxmox.node.tasks.running` | Count | `/nodes/{node}/tasks` |
| `custom.proxmox.node.tasks.errors` | Count | `/nodes/{node}/tasks` |

### Node — rrddata (historical averages)

| Metric Key | Unit | Notes |
|---|---|---|
| `custom.proxmox.node.cpu.iowait` | Percent | I/O wait — not in live status |
| `custom.proxmox.node.memory.available` | Byte | Usable memory incl. page cache |
| `custom.proxmox.node.zfs.arcsize` | Byte | ZFS ARC size (0 on non-ZFS hosts) |
| `custom.proxmox.node.pressure.cpu.some` | Percent | Linux PSI — CPU pressure (some) |
| `custom.proxmox.node.pressure.io.some` / `io.full` | Percent | Linux PSI — I/O pressure |
| `custom.proxmox.node.pressure.memory.some` / `memory.full` | Percent | Linux PSI — memory pressure |

### Physical Disks

| Metric Key | Unit |
|---|---|
| `custom.proxmox.node.disk.device.size` | Byte |
| `custom.proxmox.node.disk.device.smart` | Count (1=PASSED) |
| `custom.proxmox.node.disk.device.smart_attr` | Count (raw SMART attribute value) |

### VM (QEMU) — live stats

| Metric Key | Unit |
|---|---|
| `custom.proxmox.vm.status` | Count (1=running) |
| `custom.proxmox.vm.cpu.usage` | Percent |
| `custom.proxmox.vm.cpu.count` | Count |
| `custom.proxmox.vm.memory.used` / `total` | Byte |
| `custom.proxmox.vm.balloon.current` / `target` | Byte |
| `custom.proxmox.vm.disk.read` / `write` | Byte/hr |
| `custom.proxmox.vm.disk.size` | Byte (allocated) |
| `custom.proxmox.vm.network.in` / `out` | Bit/hr |
| `custom.proxmox.vm.uptime` | Second |
| `custom.proxmox.vm.snapshot.count` | Count |

### VM — rrddata

| Metric Key | Unit | Notes |
|---|---|---|
| `custom.proxmox.vm.disk.used` | Byte | Actual disk consumed (not allocated) |
| `custom.proxmox.vm.memory.host` | Byte | Host memory held by guest (balloon) |
| `custom.proxmox.vm.pressure.cpu.some` / `cpu.full` | Percent | Linux PSI |
| `custom.proxmox.vm.pressure.io.some` | Percent | Linux PSI |
| `custom.proxmox.vm.pressure.memory.some` / `memory.full` | Percent | Linux PSI |

### VM — config (configured limits)

| Metric Key | Unit | Notes |
|---|---|---|
| `custom.proxmox.vm.config.cores` | Count | Configured vCPU cores |
| `custom.proxmox.vm.config.sockets` | Count | Configured CPU sockets |
| `custom.proxmox.vm.config.memory_mib` | Count | Max memory in MiB |
| `custom.proxmox.vm.config.balloon_mib` | Count | Minimum balloon in MiB |
| `custom.proxmox.vm.config.cpulimit` | Count | CPU limit (0=unlimited) |
| `custom.proxmox.vm.config.cpuunits` | Count | CPU priority weight |
| `custom.proxmox.vm.config.onboot` | Count (1=yes) | Start on boot |

### VM — Guest Agent (requires `qemu-guest-agent`)

| Metric Key | Unit |
|---|---|
| `custom.proxmox.vm.agent.disk.used` / `total` | Byte (per mountpoint) |
| `custom.proxmox.vm.agent.net.rx_bytes` / `tx_bytes` | Byte (per NIC) |
| `custom.proxmox.vm.agent.net.rx_errors` / `tx_errors` | Count |
| `custom.proxmox.vm.agent.net.rx_dropped` / `tx_dropped` | Count |

### LXC Container — live stats

| Metric Key | Unit |
|---|---|
| `custom.proxmox.lxc.status` | Count (1=running) |
| `custom.proxmox.lxc.cpu.usage` | Percent |
| `custom.proxmox.lxc.cpu.count` | Count |
| `custom.proxmox.lxc.memory.used` / `total` | Byte |
| `custom.proxmox.lxc.swap.used` / `total` | Byte |
| `custom.proxmox.lxc.disk.read` / `write` | Byte/hr |
| `custom.proxmox.lxc.disk.size` | Byte (allocated) |
| `custom.proxmox.lxc.network.in` / `out` | Bit/hr |
| `custom.proxmox.lxc.snapshot.count` | Count |

### LXC — rrddata

| Metric Key | Unit | Notes |
|---|---|---|
| `custom.proxmox.lxc.disk.used` | Byte | Actual disk consumed |
| `custom.proxmox.lxc.memory.host` | Byte | Host memory used by container |
| `custom.proxmox.lxc.pressure.cpu.some` / `cpu.full` | Percent | Linux PSI |
| `custom.proxmox.lxc.pressure.io.some` | Percent | Linux PSI |
| `custom.proxmox.lxc.pressure.memory.some` / `memory.full` | Percent | Linux PSI |

### LXC — config (configured limits)

| Metric Key | Unit |
|---|---|
| `custom.proxmox.lxc.config.cores` | Count |
| `custom.proxmox.lxc.config.memory_mib` | Count |
| `custom.proxmox.lxc.config.swap_mib` | Count |
| `custom.proxmox.lxc.config.cpulimit` | Count |
| `custom.proxmox.lxc.config.cpuunits` | Count |
| `custom.proxmox.lxc.config.onboot` | Count (1=yes) |
| `custom.proxmox.lxc.config.unprivileged` | Count (1=yes) |

### Storage

| Metric Key | Unit |
|---|---|
| `custom.proxmox.storage.used` / `total` / `avail` | Byte |
| `custom.proxmox.storage.enabled` | Count (1=yes) |
| `custom.proxmox.storage.active` | Count (1=yes) |
| `custom.proxmox.storage.backup_count` | Count |

### Ceph

| Metric Key | Unit |
|---|---|
| `custom.proxmox.ceph.health` | Count (2=OK, 1=WARN, 0=ERR) |
| `custom.proxmox.ceph.osd.total` / `up` / `in` | Count |
| `custom.proxmox.ceph.pg.total` | Count |
| `custom.proxmox.ceph.bytes.used` / `avail` / `total` | Byte |
| `custom.proxmox.ceph.io.read_bps` / `write_bps` / `recovering_bps` | Byte/s |
| `custom.proxmox.ceph.mon.count` | Count |
| `custom.proxmox.ceph.flag` | Count (1=set) |

Topology entities created: `proxmox:cluster`, `proxmox:node`, `proxmox:vm`, `proxmox:lxc`, `proxmox:storage` — with relationships visible in Smartscape.

---

## Prerequisites

- Dynatrace SaaS or Managed tenant (v1.333+ / 3rd gen platform)
- ActiveGate with Extension Execution Controller enabled (v333+)
- Python 3.14 (local build only — ActiveGate runtime handles execution)
- Proxmox VE 7.x or 8.x

---

## Proxmox Setup

The extension only needs read access. Create a dedicated monitoring user and API token with the built-in `PVEAuditor` role.

### 1. Create the user

```bash
pveum user add monitoring@pve --comment "Dynatrace monitoring"
```

### 2. Create an API token

```bash
pveum user token add monitoring@pve dynatrace --privsep 0
```

> **Save the token value immediately** — it is only shown once.

Sample output:

```
┌──────────────┬──────────────────────────────────────┐
│ key          │ value                                │
╞══════════════╪══════════════════════════════════════╡
│ full-tokenid │ monitoring@pve!dynatrace             │
├──────────────┼──────────────────────────────────────┤
│ value        │ xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx │
└──────────────┴──────────────────────────────────────┘
```

### 3. Grant read-only access

```bash
pveum aclmod / --user monitoring@pve --role PVEAuditor
```

---

## Guest Agent Setup (optional)

The `qemu-guest-agent` provides in-guest metrics: per-filesystem disk usage and per-NIC byte/error counters. Without it, those tiles simply show no data.

### 1. Enable the agent in the VM config (on any Proxmox node)

```bash
qm set <vmid> --agent enabled=1
```

### 2. Install inside the VM (Ubuntu/Debian)

```bash
sudo apt-get install -y qemu-guest-agent
sudo systemctl enable --now qemu-guest-agent
```

### 3. Reboot the VM

A reboot is required for Proxmox to create the `virtio-serial` device that the agent communicates over.

```bash
qm reboot <vmid>
```

---

## Build

### 1. Clone the repo and create a virtual environment

```bash
git clone https://github.com/faultylogic/proxmox-extension.git
cd proxmox-extension
python3.14 -m venv .venv
```

### 2. Install dependencies

```bash
.venv/bin/pip3 install "dt-extensions-sdk[cli]" requests proxmoxer
```

### 3. Generate signing certificates (first time only)

```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/dt-sdk gencerts
```

> **Bug workaround — key/cert order in `developer.pem`**
> There is a known bug where signature validation fails if the certificate appears before the private key. After generating, fix the order:
>
> ```bash
> KEY=$(awk '/-----BEGIN/,/-----END/' ~/.dynatrace/certificates/developer.pem | \
>   awk 'BEGIN{found=0} /BEGIN.*KEY/{found=1} found{print} /END.*KEY/{found=0}')
> CERT=$(awk '/-----BEGIN/,/-----END/' ~/.dynatrace/certificates/developer.pem | \
>   awk 'BEGIN{found=0} /BEGIN CERTIFICATE/{found=1} found{print} /END CERTIFICATE/{found=0}')
> printf "%s\n%s\n" "$KEY" "$CERT" > ~/.dynatrace/certificates/developer.pem
> ```

### 4. Build and sign

```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/dt-sdk build \
  --extra-platform linux_x86_64 \
  --only-extra-platforms \
  --python-version 3.14
```

Output: `dist/custom_proxmox-<version>.zip`

> **Always use `--extra-platform linux_x86_64 --only-extra-platforms`** when building on macOS. Without these flags, `dt-sdk` bundles macOS wheels that fail to install on the Linux ActiveGate.

---

## Deploy

### 1. Install the developer certificate on the ActiveGate

```bash
scp ~/.dynatrace/certificates/developer.pem user@<activegate-host>:/tmp/developer.pem
```

On the ActiveGate:

```bash
sudo mkdir -p /var/lib/dynatrace/remotepluginmodule/agent/conf/certificates
sudo mv /tmp/developer.pem /var/lib/dynatrace/remotepluginmodule/agent/conf/certificates/developer.pem
sudo chown dtuserag:dtuserag /var/lib/dynatrace/remotepluginmodule/agent/conf/certificates/developer.pem
sudo systemctl restart dynatracegateway
```

> The certificate must be placed directly on the ActiveGate host. The Dynatrace 3rd gen platform does not have a certificate management UI.

### 2. Upload the extension

1. Go to **Settings → Extensions 2.0**
2. Click **Upload extension**
3. Select `dist/custom_proxmox-<version>.zip`

---

## Configuration

Once uploaded, activate the extension by adding a monitoring configuration.

| Field | Example Value | Notes |
|---|---|---|
| **Proxmox Host** | `192.168.1.100` | Hostname or IP of any cluster node |
| **Port** | `8006` | Default Proxmox API port |
| **Verify SSL Certificate** | `false` | Set `true` only if using a trusted cert |
| **Username** | `monitoring@pve` | The user created in Proxmox Setup |
| **API Token Name** | `dynatrace` | Short name only — not the full tokenid |
| **API Token Value** | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | The secret from token creation |
| **Collection Interval** | `1` | Minutes between API polls |

---

## Dashboards

Two pre-built dashboards are bundled and imported automatically when the extension is activated.

### Proxmox Overview (`proxmox_overview.json`)

Fleet-wide view across all nodes. Variables: `cluster_name` and `node_name` (multi-select).

| Section | What you see |
|---|---|
| **Cluster** | Nodes online/total, unprotected guests, HA quorate status |
| **Nodes** | Services, subscription, pending updates, task errors, CPU (incl. iowait), load average, memory (used/free/available), swap, ZFS ARC, KSM, root disk, network, PSI pressure |
| **Physical Disks** | SMART health, SMART attributes, disk sizes |
| **Virtual Machines** | Status, CPU %, memory, balloon+host-memory, disk I/O, actual disk used, network, PSI pressure, configured limits table, status snapshot table |
| **VM Guest Agent** | Per-filesystem used/total, NIC RX/TX bytes, errors/dropped |
| **LXC Containers** | Status, CPU %, memory+host-memory, swap, disk I/O, actual disk used, network, PSI pressure, configured limits table, status snapshot table |
| **Storage** | Used/available over time, utilization table with backup count |
| **HA & Replication** | HA resource state, replication fail counts, replication duration |
| **Ceph** | Health, OSD counts, PG count, capacity, I/O throughput, operational flags |

### Proxmox Guest Detail (`proxmox_guest_detail.json`)

Drill-down view for a single guest. Variables: `cluster_name` → `node_name` → `vm_name` / `lxc_name`.

| Section | What you see |
|---|---|
| **VM** | Status/uptime/vcpu/snapshot chips + configured limits chips (cores, memory, balloon, onboot) + CPU, memory, balloon, host-memory, disk I/O, actual disk used, network, PSI pressure charts |
| **VM Guest Agent** | Filesystem table+chart, NIC bytes chart, errors chart, NIC snapshot table |
| **LXC** | Status/snapshot/vcpu/disk-size chips + configured limits chips (cores, memory, swap, onboot) + CPU, memory, host-memory, swap, disk I/O, actual disk used, network, PSI pressure charts |

---

## Project Structure

```
proxmox-extension/
├── extension/
│   ├── extension.yaml              # EEC manifest: metrics, topology, dashboards
│   ├── activationSchema.json       # UI configuration form
│   └── dashboards/
│       ├── proxmox_overview.json   # Fleet overview dashboard
│       └── proxmox_guest_detail.json  # Single-guest drill-down dashboard
├── proxmox_extension/
│   ├── __init__.py
│   ├── extension.py                # Main collection logic
│   └── proxmox_client.py           # proxmoxer-backed API client
├── setup.py
├── .gitignore
└── README.md
```

---

## Notes

- The `.venv/`, `dist/`, and `extension/lib/` directories are excluded from git — regenerate locally with the build steps above.
- Signing certificates in `~/.dynatrace/certificates/` are machine-local. Back up `ca.pem` and `ca.key` to keep signing continuity across rebuilds.
- To release a new version: bump `version` in both `extension/extension.yaml` and `setup.py`, then rebuild.
- PSI pressure metrics require Linux kernel 4.20+. They will be silently absent on older kernels.
- rrddata metrics use `timeframe=hour, cf=AVERAGE` — the most recent non-null value is reported each collection cycle.
