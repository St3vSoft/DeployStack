from .backends.generic import run_setup_generic_backend
from .common import run_setup_common_manila
from .backends.lvm import run_setup_lvm_backend

from ...utils.config.parser import get

def run_setup_manila(config, env):
    driver = (get(config, "manila.BACKEND") or "generic").lower().strip()
    driver_fn = run_setup_lvm_backend if driver == "lvm" else run_setup_generic_backend
    return run_setup_common_manila(config, driver_fn, env)