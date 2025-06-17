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
    def vector_store_name(self) -> str:
        return self._config["assistant"]["vector_store_name"]

    @property
    def valid_species(self):
        return self._config.get("species", {}).get("valid", [])
    
    @property
    def units(self):
        return self._config.get("units", {})
    
    def units_for(self, state: str, species: str) -> list[str]:
        return self.units.get(state, {}).get(species, [])
    
    @property
    def summary_prompt(self) -> str:
        return self._config["prompts"]["summary"]

    @property
    def unit_prompt(self) -> str:
        return self._config["prompts"]["unit"]
    
    def summary_prompt_for(self, state: str) -> str:
        return self._config.get("prompts_by_state", {}).get(state, {}).get("summary", self.summary_prompt)
    
    def sectional_queries_for(self, state: str) -> dict:
        """
        Return a dictionary of section name → query string for the given state.
        """
        return self._config.get("sectional_queries_by_state", {}).get(state, {})
    
    def summary_intro_for(self, state: str) -> str:
        return self._config.get("summary_prompt_by_state", {}).get(state, {}).get("general_intro", "")

    def summary_outro_for(self, state: str) -> str:
        return self._config.get("summary_prompt_by_state", {}).get(state, {}).get("general_outro", "")

    def section_templates_for(self, state: str) -> dict:
        return self._config.get("section_templates_by_state", {}).get(state, {})




