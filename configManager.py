import os
import toml

class ConfigManager:
    def __init__(self, config_path=None):
        # default path setup…
        self.config_path = config_path or os.path.join("config", "regulations.toml")
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        self._config = toml.load(self.config_path)

    # ← Insert your new property methods here, at this indentation level
    @property
    def input_dir(self):
        return self._config["paths"]["input_dir"]

    @property
    def output_dir(self):
        return self._config["paths"]["output_dir"]

    @property
    def pdf_files(self):
        return self._config["pdf"]["files"]

    @property
    def model_name(self):
        return self._config["openai"]["model_name"]

    @property
    def api_key_env(self):
        return self._config["openai"]["api_key_env"]

    @property
    def summary_template(self):
        return self._config["prompt"]["summary_template"]
