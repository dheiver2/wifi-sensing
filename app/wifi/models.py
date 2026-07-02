"""Modelos de dados compartilhados para amostras Wi-Fi."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class WifiSample:
    """Representa uma única medição de uma rede Wi-Fi.

    Attributes:
        ssid: Nome da rede.
        bssid: Endereço MAC do ponto de acesso.
        rssi: Intensidade do sinal em dBm.
        channel: Canal Wi-Fi.
        frequency_mhz: Frequência central em MHz.
        bandwidth_mhz: Largura de banda em MHz (quando disponível).
        timestamp: Momento da medição (UTC).
    """

    ssid: str
    bssid: str
    rssi: int
    channel: int
    frequency_mhz: float
    bandwidth_mhz: float | None = None
    timestamp: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Serializa a amostra em dicionário (timestamp em ISO 8601)."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @staticmethod
    def band(frequency_mhz: float) -> str:
        """Retorna a banda ('2.4 GHz', '5 GHz', '6 GHz') a partir da frequência."""
        if frequency_mhz < 3000:
            return "2.4 GHz"
        if frequency_mhz < 5925:
            return "5 GHz"
        return "6 GHz"
