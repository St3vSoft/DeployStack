import yaml
import re
import os
import configparser

pattern = re.compile(r"\$(\w+)")

def resolve_vars(obj, config=None):
    if config is None:
        config = obj

    if isinstance(obj, dict):
        return {k: resolve_vars(v, config) for k, v in obj.items()}

    if isinstance(obj, list):
        return [resolve_vars(v, config) for v in obj]

    if isinstance(obj, str):
        match = pattern.fullmatch(obj)
        if match:
            return config.get(match.group(1), obj)
        return obj

    return obj

def get_conf_option(conf_file, section, option, interpolation=True):
    config = configparser.ConfigParser(
        interpolation=None if not interpolation else configparser.BasicInterpolation()
    )

    config.optionxform = str  
    config.read(conf_file)

    if section in config and option in config[section]:
        return config[section][option]

    return None

def parse_config(file_path):
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Configuration file '{file_path}' does not exist.")

    with open(file_path, "r") as f:
        return yaml.safe_load(f) or {}

def set(config_dict, key, value):
    keys = key.split(".")
    d = config_dict

    for k in keys[:-1]:
        if k not in d or not isinstance(d[k], dict):
            d[k] = {}
        d = d[k]

    d[keys[-1]] = value
    return value

def get(config_dict, key, default=None, required=False):
    keys = key.split(".")
    value = config_dict

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            if required:
                raise KeyError(f"Required configuration key '{key}' not found.")
            return default

    return value

def to_bool(value):

    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ["yes", "true", "1"]