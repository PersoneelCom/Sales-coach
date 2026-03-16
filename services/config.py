import json
import os
from typing import Any, Optional

import streamlit as st
from dotenv import load_dotenv


load_dotenv()


def get_setting(name: str, default: Optional[Any] = None) -> Any:
    if name in st.secrets:
        return st.secrets[name]
    return os.getenv(name, default)


def get_json_setting(name: str) -> Optional[dict]:
    value = get_setting(name)
    if not value:
        return None
    if isinstance(value, dict):
        return value
    return json.loads(value)
