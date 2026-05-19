import configparser

def set_conf_option(conf_file, section, option, value):

    config = configparser.ConfigParser()
    config.optionxform = str  # mantiene maiuscole/minuscole
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