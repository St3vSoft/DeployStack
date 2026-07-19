from .backends.generic import run_setup_generic_backend
from .common import run_setup_common_manila
from .backends.lvm import run_setup_lvm_backend

def run_setup_manila(config, env):
    driver = config.get("manila", {}).get("BACKEND", "generic").lower()
    driver_fn = run_setup_generic_backend if driver == "generic" else run_setup_lvm_backend
    return run_setup_common_manila(config, driver_fn, env)