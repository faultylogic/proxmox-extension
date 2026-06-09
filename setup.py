from setuptools import setup, find_packages

setup(
    name="proxmox_extension",
    version="1.1.1",
    description="Dynatrace Extension 2.0 for Proxmox VE",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "dt-extensions-sdk",
        "requests",
        "proxmoxer",
    ],
    entry_points={
        "dynatrace.extension": ["extension = proxmox_extension:ProxmoxExtension"],
    },
)
