"""Configuração de logging estruturado para a aplicação."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> logging.Logger:
    """Configura o logger raiz da aplicação.

    Args:
        level: Nível mínimo de log (ex.: ``logging.INFO``).
        log_file: Caminho opcional para gravação dos logs em arquivo.

    Returns:
        O logger raiz configurado.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Evita handlers duplicados em reconfigurações.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    return root


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger nomeado para o módulo informado."""
    return logging.getLogger(name)
