import logging

from ..kore import JinYamlKomponent, wrap
from ..krypt.krypt_functions import dekrypt_str

logger = logging.getLogger(__name__)


__all__ = [
    "Resource",
    "Deployment",
    "ConfigMap",
    "Ingress",
    "Egress",
]


class Resource(JinYamlKomponent):
    def aktivate(self):
        super().aktivate()
        self.add_metadata()

    def __str__(self):
        return f"<Resource {self.kind}.{self.shortname} {self.name}>"

    def get_filename(self):
        return f"resources/{self.kind}-{self.name}.yaml"

    def add_metadata(self):
        for key in self.strukture.get("annotations", {}):
            if "annotations" not in self.yaml.metadata:
                self.yaml.metadata.annotations = {}
            self.yaml.metadata.annotations[key] = self.strukture.annotations[key]
        for key in self.strukture.get("labels", {}):
            if "labels" not in self.yaml.metadata:
                self.yaml.metadata.labels = {}
            self.yaml.metadata.labels[key] = self.strukture.labels[key]

    def annotation(self, name: str, val: str) -> None:
        if "annotations" not in self.yaml.metadata:
            self.yaml.metadata["annotations"] = {}
        self.yaml.metadata.annotations[name] = val

    def label(self, name: str, val: str) -> None:
        if "labels" not in self.yaml.metadata:
            self.yaml.metadata["labels"] = {}
        self.yaml.metadata.labels[name] = val

    def load_file(self, filename: str) -> str:
        with open(f"{self.app.konfig.dir}/{filename}") as f:
            return f.read()


class Deployment(Resource):
    def aktivate(self):
        super().aktivate()
        self.add_container_items()
        self.remove_container_items()

    def add_container_items(self):
        additions = self.strukture.get("add_to_container", {})
        if additions:
            container = wrap(self.get_path("spec.template.spec.containers")[0])
            for path in additions:
                container._set_path(path, additions[path])

    def remove_container_items(self):
        additions = self.strukture.get("remove_from_container", {})
        if additions:
            container = wrap(self.get_path("spec.template.spec.containers")[0])
            for path in additions:
                container._del_path(path)

    def pod_annotation(self, name: str, val: str) -> None:
        self.set_path(f"spec.template.metadata.annotations.{name}", val)

    def pod_label(self, name: str, val: str) -> None:
        self.set_path(f"spec.template.metadata.labels.{name}", val)


class Egress(Resource):
    def cidr_list(self) -> list:
        r = self._field("cidr_list", "")
        if not r:
            r = self._field("cidr", "")
        return str(r).split(",") if r else []

    def port_list(self) -> list:
        r = self._field("port_list", "")
        if not r:
            r = self._field("port", "")
        return str(r).split(",") if r else []


class ConfigMap(Resource):
    def var(self, varname: str):
        value = self.strukture.vars[varname]
        if not isinstance(value, str):
            value = self.app.konfig.get_path(f"var.{varname}", None)
        if value is None:
            raise ValueError(f"var {varname} should not be None")
        return value

    def file_data(self, filename: str) -> str:
        location: str = self.app.konfig.yaml["file"][filename]
        return self.app.konfig.load_repo_file(location)


class Secret(Resource):
    def file_data(self, filename: str) -> str:
        location: str = self.app.konfig.yaml["file"][filename]
        return self.app.konfig.load_repo_file(location)

    def get_filename(self):
        return f"secrets/resources/{self.kind}-{self.name}.yaml"


class SecretBasicAuth(Secret):
    def users(self):
        result = []
        for usr in self.strukture.get("users", []):
            entry = dekrypt_str(self.app.konfig.get_path(f"secret.basic_auth.{usr}"))
            result.append(f"{usr}:{entry}")
        result.append("")  # for the final newline
        return "\n".join(result)


class Ingress(Resource):
    def nginx_annon(self, name: str, val: str) -> None:
        self.annotation("nginx.ingress.kubernetes.io/" + name, val)

    def sticky(self) -> None:
        self.nginx_annon("affinity", "cookie")

    def rewrite_url(self, url: str) -> None:
        self.nginx_annon("rewrite-target", url)

    def read_timeout(self, sec: int) -> None:
        self.nginx_annon("proxy-read-timeout", str(sec))

    def max_body_size(self, size: int) -> None:
        self.nginx_annon("proxy-body-size", str(size))

    def whitelist(self, whitelist: str) -> None:
        self.nginx_annon("whitelist-source-range", whitelist)

    def session_cookie_samesite(self) -> None:
        self.nginx_annon("session-cookie-samesite", "None")

    def basic_auth(self, secret: str = None) -> None:
        secret = secret or f"{self.app.appname}-basic-auth"
        self.nginx_annon("auth-type", "basic")
        self.nginx_annon("auth-secret", secret)
        self.nginx_annon("auth-realm", self.app.appname + "-realm")


class KubeconfigFile(JinYamlKomponent):
    def get_filename(self):
        if self.strukture.get("filename"):
            return self.strukture.get("filename")
        return "kubeconfig.yaml"
