"""Ponto de entrada da aplicação WiFi Sensing."""

from __future__ import annotations

import argparse
import logging
import platform
import sys

from PySide6.QtWidgets import QApplication

from app.database.repository import MeasurementRepository
from app.ui.main_window import MainWindow
from app.utils.config import LOG_DIR, AppConfig
from app.utils.logging_config import setup_logging
from app.wifi.scanner import create_scanner


def parse_args() -> argparse.Namespace:
    """Interpreta os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(description="WiFi Sensing - análise de sinais Wi-Fi.")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Força o uso do scanner simulado (dados sintéticos).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Intervalo de amostragem em segundos (padrão: 3.0).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Habilita logs em nível DEBUG.",
    )
    return parser.parse_args()


def main() -> int:
    """Inicializa e executa a aplicação."""
    args = parse_args()

    config = AppConfig(scan_interval_s=args.interval)
    config.ensure_dirs()
    setup_logging(
        level=logging.DEBUG if args.debug else logging.INFO,
        log_file=LOG_DIR / "wifi_sensing.log",
    )

    # No macOS, solicita Localização para revelar SSID/BSSID (requer bundle .app).
    if not args.simulate and platform.system() == "Darwin":
        from app.wifi.location import request_location_authorization

        request_location_authorization()

    scanner = create_scanner(force_simulated=args.simulate)
    repository = MeasurementRepository(config.db_path)

    from app.ai.bitnet import BitNetClient

    llm_client = BitNetClient()

    app = QApplication(sys.argv)
    from app.ui.theme import apply_theme

    apply_theme(app)
    window = MainWindow(scanner, repository, config, llm_client=llm_client)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
