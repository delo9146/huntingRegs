import os
import toml

class ConfigManager:
    def __init__(self, config_path=None):
        # default path setup…
        self.config_path = config_path or os.path.join("config", "regulations.toml")
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        self._config = toml.load(self.config_path)

    @property
    def input_dir(self):
        return self._config["paths"]["input_dir"]

    @property
    def output_dir(self):
        return self._config["paths"]["output_dir"]

    @property
    def model_name(self):
        return self._config["openai"]["model_name"]

    @property
    def api_key_env(self):
        return self._config["openai"]["api_key_env"]

    @property
    def assistant_name(self) -> str:
        return self._config["assistant"]["name"]

    @property
    def vector_store_name(self) -> str:
        return self._config["assistant"]["vector_store_name"]

    @property
    def valid_species(self):
        return self._config.get("species", {}).get("valid", [])
