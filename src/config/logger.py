import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

_NOISY_LOGGERS: tuple[str, ...] = ("httpx", "openai", "anthropic", "httpcore","urllib3", "asyncio", "multipart",)

_lock              = threading.Lock()
_registry: dict[str, logging.Logger] = {}
_system_configured = False

def _build_formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt     = "%(asctime)s  %(levelname)-8s  %(name)-35s  %(message)s",
        datefmt = "%Y-%m-%d %H:%M:%S",
    )

def _configure_system(log_dir: Path, is_production: bool) -> None:
    global _system_configured
    if _system_configured:
        return

    root = logging.getLogger()
    root.setLevel(logging.INFO if is_production else logging.DEBUG)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    log_dir.mkdir(parents=True, exist_ok=True)
    _system_configured = True


def setup_logger(
    log_path: Path | None = None,
    name: str = "app",
    boss_name: str | None = None,
    his_name: str = "",
) -> logging.Logger:
    if boss_name is not None:
        name = his_name or boss_name
        from .settings import Settings
        clean_boss = boss_name.removesuffix(".txt").removesuffix(".log")
        log_path = Settings.LOG_DIR / f"{clean_boss}.log"
    elif log_path is None:
        from .settings import Settings
        log_path = Settings.LOG_DIR / f"{name}.log"

    if name in _registry:
        return _registry[name]

    with _lock:
        if name in _registry:
            return _registry[name]

        from .settings import Settings

        is_prod  : bool = Settings.is_production
        log_dir  : Path = Settings.LOG_DIR

        _configure_system(log_dir, is_prod)

        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        if logger.handlers:
            _registry[name] = logger
            return logger

        fmt = _build_formatter()

        # 1. Rotating file handler
        fh = RotatingFileHandler(
            log_path,
            maxBytes    = 5 * 1024 * 1024,
            backupCount = 3,
            encoding    = "utf-8",
        )
        fh.setLevel(logging.INFO if is_prod else logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # 2. Console handler
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.WARNING if is_prod else logging.DEBUG)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

        _registry[name] = logger
        return logger

def shutdown_logger() -> None:
    with _lock:
        for logger in _registry.values():
            for handler in logger.handlers[:]:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)
        _registry.clear()
    logging.shutdown()


# Backwards compatibility alias
shutdown = shutdown_logger