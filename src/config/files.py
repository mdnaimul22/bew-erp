import os
import json
import pickle
import shutil
from pathlib import Path
import yaml
from typing import Any, Union

from .paths import PROJECT_ROOT, resolve_sandboxed

# Core protected directories that cannot be deleted or overwritten via files.py
_PROTECTED_DIRS = {PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT / ".git"}


def _abs(relative_path: str | Path) -> Path:
    return resolve_sandboxed(relative_path)


def read_text(relative_path: str | Path, encoding: str = "utf-8") -> str:
    return _abs(relative_path).read_text(encoding=encoding)


def write_text(relative_path: str | Path, content: str, encoding: str = "utf-8") -> None:
    path = _abs(relative_path)
    # Prevent modifying application source code
    if path == PROJECT_ROOT or (PROJECT_ROOT / "src") in path.parents or path == (PROJECT_ROOT / "src"):
        raise ValueError(f"Access denied: modifying source directory is forbidden: {relative_path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)


def read_json(relative_path: str | Path) -> Any:
    return json.loads(read_text(relative_path))


def write_json(relative_path: str | Path, data: Any, indent: int = 2) -> None:
    write_text(relative_path, json.dumps(data, indent=indent, ensure_ascii=False))


def read_yaml(relative_path: str | Path) -> Any:
    return yaml.safe_load(read_text(relative_path))


def write_yaml(relative_path: str | Path, data: Any) -> None:
    write_text(relative_path, yaml.safe_dump(data, sort_keys=False))


def read_pickle(path: str | Path) -> Any:
    with open(_abs(path), 'rb') as f:
        return pickle.load(f)


def write_pickle(data: Any, path: str | Path) -> None:
    p = _abs(path)
    # Prevent modifying application source code
    if p == PROJECT_ROOT or (PROJECT_ROOT / "src") in p.parents or p == (PROJECT_ROOT / "src"):
        raise ValueError(f"Access denied: modifying source directory is forbidden: {path}")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'wb') as f:
        pickle.dump(data, f)


def exists(relative_path: str | Path) -> bool:
    try:
        return _abs(relative_path).exists()
    except (ValueError, OSError):
        return False


def is_file(relative_path: str | Path) -> bool:
    try:
        return _abs(relative_path).is_file()
    except (ValueError, OSError):
        return False


def is_dir(relative_path: str | Path) -> bool:
    try:
        return _abs(relative_path).is_dir()
    except (ValueError, OSError):
        return False


def ensure_dir(relative_path: str | Path) -> Path:
    path = _abs(relative_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def delete(relative_path: str | Path) -> None:
    path = _abs(relative_path)
    # Self-destruction and critical directory guard
    if path in _PROTECTED_DIRS or (PROJECT_ROOT / "src") in path.parents or (PROJECT_ROOT / ".git") in path.parents:
        raise ValueError(f"Security violation: Cannot delete protected path: {relative_path}")
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def list_files(relative_path: str | Path, pattern: str = "*") -> list[Path]:
    return list(_abs(relative_path).glob(pattern))


def get_size(relative_path: str | Path) -> int:
    return os.path.getsize(_abs(relative_path))


def get_mtime(relative_path: str | Path) -> float:
    return os.path.getmtime(_abs(relative_path))


def read_from_pos(relative_path: str | Path, pos: int, encoding: str = "utf-8") -> str:
    with open(_abs(relative_path), "r", encoding=encoding, errors="ignore") as f:
        f.seek(pos)
        return f.read()


def get_abs_path(*parts: str | Path) -> str:
    if not parts:
        return str(PROJECT_ROOT)
    first = Path(parts[0]).expanduser()
    if first.is_absolute():
        p = Path(*parts).expanduser()
        return str(resolve_sandboxed(p))
    target = PROJECT_ROOT.joinpath(*parts)
    return str(resolve_sandboxed(target))


def get_rel_path(path: Union[str, Path], base: Union[str, Path, None] = None) -> str:
    if not path:
        return ""
    p_str = str(path).strip()
    base_dir = Path(base).resolve() if base else PROJECT_ROOT
    try:
        p = Path(p_str).expanduser()
        if p.is_absolute():
            return str(p.resolve().relative_to(base_dir))
    except (ValueError, OSError):
        pass
    return p_str


