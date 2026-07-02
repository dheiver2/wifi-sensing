"""Testes do repositório de medições (persistência e exportação CSV)."""

from __future__ import annotations

import csv

from app.database.repository import MeasurementRepository
from app.wifi.models import WifiSample


def _samples():
    return [
        WifiSample("RedeA", "aa:bb:cc:00:00:01", -55, 36, 5180.0, 80.0),
        WifiSample("RedeB", "aa:bb:cc:00:00:02", -70, 6, 2437.0, 20.0),
    ]


def test_add_and_fetch(tmp_path):
    repo = MeasurementRepository(tmp_path / "db.sqlite")
    n = repo.add_samples(_samples())
    assert n == 2
    rows = repo.fetch_series()
    assert len(rows) == 2
    assert {r.ssid for r in rows} == {"RedeA", "RedeB"}


def test_export_csv_from_db_without_pandas(tmp_path):
    """Exportação a partir do banco usa stdlib (csv), sem pandas."""
    repo = MeasurementRepository(tmp_path / "db.sqlite")
    repo.add_samples(_samples())
    out = tmp_path / "export.csv"
    written = repo.export_csv(out)
    assert written == 2
    with out.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert rows[0]["ssid"] in {"RedeA", "RedeB"}
    assert "timestamp" in rows[0]


def test_export_csv_from_samples(tmp_path):
    repo = MeasurementRepository(tmp_path / "db.sqlite")
    out = tmp_path / "batch.csv"
    written = repo.export_csv(out, samples=_samples())
    assert written == 2
    with out.open(encoding="utf-8") as fh:
        assert sum(1 for _ in csv.DictReader(fh)) == 2


def test_to_records_shape(tmp_path):
    repo = MeasurementRepository(tmp_path / "db.sqlite")
    repo.add_samples(_samples())
    records = repo.to_records()
    assert len(records) == 2
    assert set(records[0]) == {
        "timestamp", "ssid", "bssid", "rssi",
        "channel", "frequency_mhz", "bandwidth_mhz",
    }
