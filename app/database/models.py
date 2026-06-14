"""Modelos ORM (SQLAlchemy) para persistência das medições."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Classe base declarativa do SQLAlchemy."""


class Measurement(Base):
    """Registro de uma medição de sinal Wi-Fi persistida."""

    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ssid: Mapped[str] = mapped_column(String(64), index=True)
    bssid: Mapped[str] = mapped_column(String(17), index=True)
    rssi: Mapped[int] = mapped_column(Integer)
    channel: Mapped[int] = mapped_column(Integer)
    frequency_mhz: Mapped[float] = mapped_column(Float)
    bandwidth_mhz: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)

    def __repr__(self) -> str:  # pragma: no cover - representação auxiliar
        return (
            f"<Measurement {self.ssid} ({self.bssid}) "
            f"rssi={self.rssi} ch={self.channel}>"
        )
