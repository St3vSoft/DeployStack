from dataclasses import dataclass

@dataclass
class CinderBackupConfig:
    backup_driver: str
    compression_algorithm: str
    backup_file_size_in_bytes: int
    backup_sha_block_size_in_bytes: int
    backup_workers: int

@dataclass
class CinderConfig:
    enabled_backends: list
    nfs_snapshots_enabled: bool
    lvm_vg: str
    physical_volume: str
    lvm_image_size_in_gb: int
    enable_backup: bool
    cinder_backup_params: CinderBackupConfig

@dataclass
class ManilaConfig:
    lvm_vg: str
    lvm_physical_volume: str
    lvm_image_size_in_gb: int
    backend: str
    share_protocols: list
    dhss_auth_type: str

@dataclass
class NovaComputeConfig:
    nova_virt_type: str
    cpu_allocation_ratio: float
    ram_allocation_ratio: float
    disk_allocation_ratio: float
    allow_resize_to_same_host: bool

@dataclass
class OpenStackConfig:
    config_file_path: str
    install_horizon: bool
    install_cinder: bool
    install_manila: bool
    cinder: CinderConfig
    manila: ManilaConfig
    nova_compute: NovaComputeConfig
    neutron_driver: str
    os_mgmt_iface: str
    default_gateway: str
    os_mgmt_gateway: str
    os_release: str
