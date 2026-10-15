import configparser

def toml_string(value):
    return f'"{value}"'

def set_samba_option(conf_file, section, option, value):
    with open(conf_file) as f:
        lines = f.readlines()

    out = []
    in_section = False
    option_found = False

    for line in lines:
        stripped = line.strip()

        if stripped.lower() == f"[{section.lower()}]":
            in_section = True

        elif stripped.startswith("[") and stripped.endswith("]"):
            if in_section and not option_found:
                out.append(f"\t{option} = {value}\n")
                option_found = True
            in_section = False

        if in_section and stripped.lower().startswith(option.lower() + " ="):
            out.append(f"\t{option} = {value}\n")
            option_found = True
        else:
            out.append(line)

    if in_section and not option_found:
        out.append(f"\t{option} = {value}\n")

    with open(conf_file, "w") as f:
        f.writelines(out)

def remove_conf_option(conf_file, section, option, interpolation=True):
    
    config = configparser.ConfigParser(
        interpolation=None if not interpolation else configparser.BasicInterpolation()
    )
    config.optionxform = str
    config.read(conf_file)

    if section in config:
        config.remove_option(section, option)

        if not config.options(section):
            config.remove_section(section)

        with open(conf_file, "w") as f:
            config.write(f)

def set_conf_option(conf_file, section, option, value, interpolation = True):

    config = configparser.ConfigParser(
        interpolation=None if not interpolation else configparser.BasicInterpolation()
    )
    
    config.optionxform = str
    config.read(conf_file)

    if section not in config:
        config[section] = {}

    config[section][option] = value

    with open(conf_file, "w") as f:
        config.write(f)

def set_service_option(service_file, section, option, value):
    lines = []
    current_section = None
    option_set = False

    with open(service_file, 'r') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1]
            if current_section == section and stripped.startswith(option + "="):
                line = f"{option}={value}\n"
                option_set = True
            lines.append(line)

    if not option_set:

        new_lines = []
        current_section = None
        for line in lines:
            new_lines.append(line)
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1]
            if current_section == section and not option_set:
                new_lines.append(f"{option}={value}\n")
                option_set = True
        lines = new_lines

    with open(service_file, 'w') as f:
        f.writelines(lines)