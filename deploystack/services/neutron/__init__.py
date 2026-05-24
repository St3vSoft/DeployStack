from .ovs import run_setup_ovs_neutron
from .ovn import run_setup_ovn_neutron
from .common import run_setup_neutron_common

def run_setup_neutron(config, env):
    driver = config.get("neutron", {}).get("DRIVER", "ovs").lower()
    driver_fn = run_setup_ovn_neutron if driver == "ovn" else run_setup_ovs_neutron
    return run_setup_neutron_common(config, driver_fn, env)

   