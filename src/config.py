import os
import re
from pathlib import Path

import yaml


def load_config(path: Path) -> dict:
    """Load YAML config with ${ENV_VAR} interpolation."""
    text = Path(path).read_text()

    def replace_env(match):
        var = match.group(1)
        val = os.environ.get(var)
        if val is None:
            raise ValueError(f"Environment variable not set: {var}")
        return val

    text = re.sub(r"\$\{(\w+)\}", replace_env, text)
    return yaml.safe_load(text)
