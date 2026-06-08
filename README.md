# Dynatrace Extension 2.0 — Proxmox VE

A Python-based Dynatrace Extension 2.0 that monitors a Proxmox VE cluster via the REST API. Runs on an ActiveGate and collects metrics for nodes, VMs, LXC containers, and storage — surfacing them as custom metrics with full topology in Dynatrace.

---

## Table of Contents

- [Metrics Collected](#metrics-collected)
- [Prerequisites](#prerequisites)
- [Proxmox Setup](#proxmox-setup)
- [Build](#build)
- [Deploy](#deploy)
- [Configuration](#configuration)
- [Dashboard](#dashboard)
- [Project Structure](#project-structure)

---

## Metrics Collected

| Group | Metric Key | Unit |
|-------|-----------|------|
| **Cluster** | `custom.proxmox.cluster.nodes.total` | Count |
| | `custom.proxmox.cluster.nodes.online` | Count |
| **Node** | `custom.proxmox.node.cpu.usage` | Percent |
| | `custom.proxmox.node.memory.used` | Byte |
| | `custom.proxmox.node.memory.total` | Byte |
| | `custom.proxmox.node.disk.used` | Byte |
| | `custom.proxmox.node.disk.total` | Byte |
| | `custom.proxmox.node.network.in` | Bit/hr |
| | `custom.proxmox.node.network.out` | Bit/hr |
| | `custom.proxmox.node.uptime` | Second |
| **VM (QEMU)** | `custom.proxmox.vm.cpu.usage` | Percent |
| | `custom.proxmox.vm.memory.used` | Byte |
| | `custom.proxmox.vm.memory.total` | Byte |
| | `custom.proxmox.vm.disk.read` | Byte/hr |
| | `custom.proxmox.vm.disk.write` | Byte/hr |
| | `custom.proxmox.vm.network.in` | Bit/hr |
| | `custom.proxmox.vm.network.out` | Bit/hr |
| | `custom.proxmox.vm.uptime` | Second |
| **LXC Container** | `custom.proxmox.lxc.cpu.usage` | Percent |
| | `custom.proxmox.lxc.memory.used` | Byte |
| | `custom.proxmox.lxc.memory.total` | Byte |
| | `custom.proxmox.lxc.disk.read` | Byte/hr |
| | `custom.proxmox.lxc.disk.write` | Byte/hr |
| | `custom.proxmox.lxc.network.in` | Bit/hr |
| | `custom.proxmox.lxc.network.out` | Bit/hr |
| **Storage** | `custom.proxmox.storage.used` | Byte |
| | `custom.proxmox.storage.total` | Byte |

Topology entities created: `proxmox:cluster`, `proxmox:node`, `proxmox:vm`, `proxmox:lxc`, `proxmox:storage` — with relationships visible in Smartscape.

---

## Prerequisites

- Dynatrace SaaS or Managed tenant (v1.333+)
- ActiveGate with Extension Execution Controller enabled (v333+)
- Python 3.14 (used for local build only — the ActiveGate runtime handles execution)
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
│ info         │ {"privsep":"0"}                      │
├──────────────┼──────────────────────────────────────┤
│ value        │ xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx │
└──────────────┴──────────────────────────────────────┘
```

### 3. Grant read-only access

```bash
pveum aclmod / --user monitoring@pve --role PVEAuditor
```

The `PVEAuditor` role provides:

| Permission | Purpose |
|---|---|
| `VM.Audit` | Read VM and LXC status |
| `Sys.Audit` | Read node and cluster status |
| `Datastore.Audit` | Read storage utilization |

---

## Build

### 1. Clone the repo and create a virtual environment

```bash
git clone <repo-url>
cd proxmox-extension
python3.14 -m venv .venv
```

### 2. Install dependencies

```bash
.venv/bin/pip3 install "dt-extensions-sdk[cli]" requests
```

### 3. Generate signing certificates (first time only)

```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/dt-sdk gencerts
```

This writes a CA and developer certificate to `~/.dynatrace/certificates/`.

### 4. Build and sign

```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/dt-sdk build
```

Output: `dist/custom_proxmox-1.0.0.zip`

---

## Deploy

### 1. Upload the CA certificate to Dynatrace

Before uploading the extension, Dynatrace needs to trust your signing certificate.

1. In your Dynatrace tenant go to **Settings → Extensions → Extension certificates**
2. Upload `~/.dynatrace/certificates/ca.pem`

### 2. Upload the extension

1. Go to **Settings → Extensions 2.0**
2. Click **Upload extension**
3. Select `dist/custom_proxmox-1.0.0.zip`

---

## Configuration

Once uploaded, activate the extension by adding a monitoring configuration.

| Field | Example Value | Notes |
|---|---|---|
| **Proxmox Host** | `192.168.1.100` | Hostname or IP of any cluster node |
| **Port** | `8006` | Default Proxmox API port |
| **Verify SSL Certificate** | `false` | Set `true` only if using a trusted cert |
| **Username** | `monitoring@pve` | The user created in Proxmox Setup |
| **API Token Name** | `dynatrace` | The token ID (not the full-tokenid) |
| **API Token Value** | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | The secret from token creation |
| **Collection Interval** | `1` | Minutes between API polls |

> The **API Token Name** is just the short name (`dynatrace`), not the full token ID (`monitoring@pve!dynatrace`).

---

## Dashboard

A pre-built dashboard is bundled with the extension at `extension/dashboards/proxmox_overview.json`. It is automatically imported when the extension is activated and includes:

- **Cluster** — nodes online vs total
- **Nodes** — CPU, memory, disk, and network per node
- **VMs** — CPU, memory, disk I/O, and network per VM
- **LXC Containers** — CPU, memory, disk I/O, and network per container
- **Storage** — used vs total and utilization % per storage pool

Dashboard variables allow filtering by cluster and node.

---

## Project Structure

```
proxmox-extension/
├── extension/
│   ├── extension.yaml              # EEC manifest: metrics, topology, relationships
│   ├── activationSchema.json       # UI configuration form
│   └── dashboards/
│       └── proxmox_overview.json   # Pre-built overview dashboard
├── proxmox_extension/
│   ├── __init__.py
│   ├── extension.py                # Main extension logic
│   └── proxmox_client.py           # Proxmox REST API client
├── setup.py
├── .gitignore
└── README.md
```

---

## Notes

- The `.venv/`, `dist/`, and `extension/lib/` directories are excluded from git — regenerate them locally with the build steps above.
- Signing certificates in `~/.dynatrace/certificates/` are machine-local and not committed. Back up `ca.pem` and `ca.key` if you plan to release future versions signed with the same CA.
- To release a new version, bump `version` in both `extension/extension.yaml` and `setup.py`, then rebuild.
