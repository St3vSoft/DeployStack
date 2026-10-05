from .drivers.ovs import run_setup_ovs_neutron
from .drivers.ovn import run_setup_ovn_neutron
from .controller import run_setup_controller_neutron

def run_setup_neutron(config, env):
    driver = config.get("neutron", {}).get("DRIVER", "ovs").lower()
    driver_fn = run_setup_ovn_neutron if driver == "ovn" else run_setup_ovs_neutron
    return run_setup_controller_neutron(config, driver_fn, env)

   