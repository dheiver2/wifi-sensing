"""Configuração centralizada da aplicação."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Diretório base do projeto (raiz do repositório).
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = DATA_DIR / "models"
EXPORT_DIR = DATA_DIR / "exports"
LOG_DIR = DATA_DIR / "logs"


@dataclass
class AppConfig:
    """Parâmetros configuráveis da aplicação.

    Attributes:
        scan_interval_s: Intervalo entre varreduras Wi-Fi, em segundos.
        db_path: Caminho do banco SQLite.
        moving_average_window: Janela da média móvel para suavização do RSSI.
        change_threshold: Limiar do índice probabilístico para disparo de alerta.
        history_points: Quantidade máxima de pontos exibidos nos gráficos.
    """

    scan_interval_s: float = 3.0
    db_path: Path = field(default_factory=lambda: DATA_DIR / "wifi_sensing.db")
    moving_average_window: int = 5
    change_threshold: float = 0.7
    history_points: int = 300

    def ensure_dirs(self) -> None:
        """Garante a existência dos diretórios de dados."""
        for directory in (DATA_DIR, MODELS_DIR, EXPORT_DIR, LOG_DIR):
            directory.mkdir(parents=True, exist_ok=True)
