"""Repositório de medições: gravação, consulta e exportação CSV."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Base, Measurement
from app.utils.logging_config import get_logger
from app.wifi.models import WifiSample

logger = get_logger(__name__)


class MeasurementRepository:
    """Encapsula o acesso ao banco SQLite de medições."""

    def __init__(self, db_path: Path) -> None:
        """Inicializa o engine e cria as tabelas se necessário.

        Args:
            db_path: Caminho do arquivo SQLite.
        """
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(self._engine)
        self._Session: sessionmaker[Session] = sessionmaker(
            bind=self._engine, future=True
        )
        logger.info("Banco inicializado em %s", db_path)

    def add_samples(self, samples: Iterable[WifiSample]) -> int:
        """Persiste um lote de amostras.

        Returns:
            Quantidade de registros inseridos.
        """
        rows = [
            Measurement(
                ssid=s.ssid,
                bssid=s.bssid,
                rssi=s.rssi,
                channel=s.channel,
                frequency_mhz=s.frequency_mhz,
                bandwidth_mhz=s.bandwidth_mhz,
                timestamp=s.timestamp,
            )
            for s in samples
        ]
        with self._Session() as session:
            session.add_all(rows)
            session.commit()
        logger.debug("Inseridas %d medições", len(rows))
        return len(rows)

    def fetch_series(
        self,
        bssid: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Measurement]:
        """Retorna medições filtradas por BSSID e/ou intervalo temporal."""
        stmt = select(Measurement).order_by(Measurement.timestamp)
        if bssid:
            stmt = stmt.where(Measurement.bssid == bssid)
        if since:
            stmt = stmt.where(Measurement.timestamp >= since)
        if limit:
            stmt = stmt.limit(limit)
        with self._Session() as session:
            return list(session.scalars(stmt))

    def to_records(self, bssid: str | None = None) -> list[dict]:
        """Carrega medições como lista de dicionários (timestamp em ISO 8601)."""
        return [
            {
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                "ssid": r.ssid,
                "bssid": r.bssid,
                "rssi": r.rssi,
                "channel": r.channel,
                "frequency_mhz": r.frequency_mhz,
                "bandwidth_mhz": r.bandwidth_mhz,
            }
            for r in self.fetch_series(bssid=bssid)
        ]

    def export_csv(self, path: Path, samples: Sequence[WifiSample] | None = None) -> int:
        """Exporta medições para CSV.

        Se ``samples`` for fornecido, exporta apenas esse lote; caso contrário,
        exporta todo o histórico do banco.

        Returns:
            Número de linhas escritas.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "timestamp", "ssid", "bssid", "rssi",
            "channel", "frequency_mhz", "bandwidth_mhz",
        ]
        records = [s.to_dict() for s in samples] if samples is not None else self.to_records()

        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for rec in records:
                writer.writerow({k: rec.get(k) for k in fields})
        logger.info("Exportadas %d linhas para %s", len(records), path)
        return len(records)
