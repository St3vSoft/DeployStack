from pathlib import Path
import tomllib

class Config:

    DEFAULT_PATH = Path("/etc/deploystack-loopback.conf")

    def __init__(self, path=None):
        self.path = Path(path or self.DEFAULT_PATH)

        with self.path.open("rb") as f:
            self.data = tomllib.load(f)

    def resource(self, name):
        return self.data[name]

    def backend(self, resource, name):
        try:
            return self.data[resource][name]
        except KeyError:
            raise KeyError(
                f"Backend not found: {resource}/{name}"
            )

    def backend_names(self, resource):
        return list(self.data[resource].keys())

    def resolve_backends(self, resource=None, backend=None):
        if resource is None and backend is not None:
            raise ValueError(
                "backend requires a resource"
            )

        if resource is None:
            resources = self.resource_names()
        else:
            resources = [resource]

        result = []

        for resource_name in resources:
            resource_config = self.data[resource_name]

            if backend is not None:
                if backend not in resource_config:
                    raise KeyError(
                        f"Backend not found: "
                        f"{resource_name}/{backend}"
                    )

                result.append(
                    (
                        resource_name,
                        backend,
                        resource_config[backend],
                    )
                )
                continue

            for backend_name, backend_config in resource_config.items():
                result.append(
                    (
                        resource_name,
                        backend_name,
                        backend_config,
                    )
                )

        return result

    def resource_names(self):
        return [
            name for name in self.data if name != "lvm"
        ]

    @property
    def lvm_config(self):
        return self.data["lvm"]["config"]