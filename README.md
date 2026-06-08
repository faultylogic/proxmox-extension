# Dynatrace Extension 2.0 — Proxmox VE

Monitors a Proxmox VE cluster via the REST API, collecting metrics for nodes, VMs, LXC containers, and storage.

## Metrics collected

| Group | Metrics |
|-------|---------|
| Cluster | nodes total, nodes online |
| Node | CPU %, memory used/total, disk used/total, network in/out, uptime |
| VM (QEMU) | CPU %, memory used/total, disk read/write, network in/out, uptime |
| LXC | CPU %, memory used/total, disk read/write, network in/out |
| Storage | used bytes, total bytes |

## Prerequisites

- Dynatrace ActiveGate with Extension Execution Controller enabled
- Proxmox VE 7.x or 8.x
- Proxmox API token with `PVEAuditor` role (read-only is sufficient)

### Creating a Proxmox API token

```bash
# On the Proxmox host
pveum user add monitoring@pve
pveum aclmod / -user monitoring@pve -role PVEAuditor
pveum user token add monitoring@pve dynatrace
```

Copy the token secret shown — it is only displayed once.

## Build and deploy

```bash
# Install the dt-extensions-sdk CLI
pip install dt-extensions-sdk

# Build the extension zip
dt-sdk build

# Sign and upload via Dynatrace API or UI
dt-sdk sign --target dist/custom_proxmox-1.0.0.zip
```

## Activate

In Dynatrace → Hub → My extensions → Proxmox VE, add a monitoring configuration pointing at your Proxmox host with the API token credentials.
