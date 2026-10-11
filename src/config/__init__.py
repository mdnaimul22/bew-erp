"""
Config module entry point.
Auto-loads environment variables and exports all 22 canonical configuration utilities.
"""

from .files import (
    read_text, write_text, read_json, write_json,
    read_yaml, write_yaml,
    read_pickle, write_pickle,
    exists, is_file, is_dir, ensure_dir, delete, list_files, get_abs_path, get_rel_path,
    get_size, get_mtime, read_from_pos,
)
from .dotenv import load_dotenv, set_value, get_value, remove_value
from .settings import Settings, ClientConfig
from .logger import setup_logger, shutdown_logger, shutdown

# Auto-load environment variables on import
load_dotenv()

__all__ = [
    # File I/O
    "read_text",
    "write_text",
    "read_json",
    "write_json",
    "read_yaml",
    "write_yaml",
    "read_pickle",
    "write_pickle",
    "read_from_pos",
    "get_size",
    "get_mtime",
    # Path & Directory Management
    "exists",
    "is_file",
    "is_dir",
    "ensure_dir",
    "delete",
    "list_files",
    "get_abs_path",
    "get_rel_path",
    # Environment Variables
    "load_dotenv",
    "set_value",
    "get_value",
    "remove_value",
    # Settings & Logging
    "Settings",
    "ClientConfig",
    "setup_logger",
    "shutdown_logger",
    "shutdown",
]