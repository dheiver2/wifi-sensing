"""Aquisição de dados Wi-Fi multiplataforma (Windows, Linux e macOS).

A captura real depende de ferramentas do sistema operacional. Caso nenhuma
esteja disponível, um scanner simulado é usado para fins de pesquisa e testes.
"""

from __future__ import annotations

import abc
import platform
import random
import re
import subprocess
from typing import List

from app.utils.logging_config import get_logger
from app.wifi.models import WifiSample

logger = get_logger(__name__)


def channel_to_frequency(channel: int, band: str | None = None) -> float:
    """Converte um canal Wi-Fi em frequência central aproximada (MHz).

    Args:
        channel: Número do canal.
        band: Banda explícita ('2.4 GHz', '5 GHz', '6 GHz'). Quando informada,
            resolve a ambiguidade de canais que existem em mais de uma banda
            (ex.: canal 1 em 2.4 GHz e em 6 GHz).
    """
    if band == "6 GHz":
        return 5950.0 + channel * 5  # 6E: ch1 ≈ 5955 MHz
    if band == "2.4 GHz" or (band is None and 1 <= channel <= 14):
        return 2484.0 if channel == 14 else 2407.0 + channel * 5
    if band == "5 GHz" or (band is None and 32 <= channel <= 177):
        return 5000.0 + channel * 5
    return 0.0


class WifiScanner(abc.ABC):
    """Interface base para implementações de scanner Wi-Fi."""

    @abc.abstractmethod
    def scan(self) -> List[WifiSample]:
        """Executa uma varredura e retorna as amostras detectadas."""
        raise NotImplementedError


class LinuxScanner(WifiScanner):
    """Scanner baseado em ``nmcli`` (NetworkManager)."""

    _FIELDS = "SSID,BSSID,SIGNAL,CHAN,FREQ"

    def scan(self) -> List[WifiSample]:
        cmd = [
            "nmcli", "-t", "-f", self._FIELDS, "device", "wifi", "list", "--rescan", "yes",
        ]
        out = subprocess.check_output(cmd, text=True, timeout=30)
        samples: List[WifiSample] = []
        for line in out.strip().splitlines():
            # BSSID contém ':' escapados como '\:' no modo terse do nmcli.
            parts = re.split(r"(?<!\\):", line)
            if len(parts) < 5:
                continue
            ssid, bssid, signal, chan, freq = parts[:5]
            bssid = bssid.replace("\\:", ":")
            try:
                rssi = int(signal) // 2 - 100  # percentual -> dBm aproximado
                channel = int(chan)
                frequency = float(freq.split()[0])
            except (ValueError, IndexError):
                continue
            samples.append(
                WifiSample(
                    ssid=ssid or "<oculto>",
                    bssid=bssid,
                    rssi=rssi,
                    channel=channel,
                    frequency_mhz=frequency,
                )
            )
        return samples


class WindowsScanner(WifiScanner):
    """Scanner baseado em ``netsh wlan show networks mode=bssid``."""

    def scan(self) -> List[WifiSample]:
        out = subprocess.check_output(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            text=True, timeout=30, errors="ignore",
        )
        samples: List[WifiSample] = []
        ssid = ""
        bssid = ""
        rssi = 0
        channel = 0
        for raw in out.splitlines():
            line = raw.strip()
            if line.startswith("SSID ") and ":" in line:
                ssid = line.split(":", 1)[1].strip() or "<oculto>"
            elif line.startswith("BSSID"):
                bssid = line.split(":", 1)[1].strip()
            elif line.startswith("Signal"):
                pct = int(line.split(":", 1)[1].strip().rstrip("%"))
                rssi = pct // 2 - 100
            elif line.startswith("Channel"):
                channel = int(line.split(":", 1)[1].strip())
                samples.append(
                    WifiSample(
                        ssid=ssid,
                        bssid=bssid,
                        rssi=rssi,
                        channel=channel,
                        frequency_mhz=channel_to_frequency(channel),
                    )
                )
        return samples


class MacScanner(WifiScanner):
    """Scanner real para macOS via CoreWLAN (pyobjc).

    Substitui a antiga ferramenta ``airport``, removida a partir do macOS 14.4.
    Fornece RSSI, canal, banda e largura de banda **reais** do rádio.

    Limitação do sistema operacional: SSID e BSSID só são revelados quando o
    processo possui permissão de **Localização** (TCC). Em um interpretador de
    linha de comando isso não é concedido, então esses campos podem vir nulos —
    nesse caso é gerada uma identidade estável a partir de banda+canal+largura.
    Empacotando como ``.app`` com Localização autorizada, os nomes aparecem.
    """

    _WIDTH = {0: None, 1: 20.0, 2: 40.0, 3: 80.0, 4: 160.0}
    _BAND = {0: None, 1: "2.4 GHz", 2: "5 GHz", 3: "6 GHz"}

    def __init__(self, refresh_interval_s: float = 20.0) -> None:
        import CoreWLAN  # import tardio: só é necessário no macOS
        import threading

        self._client = CoreWLAN.CWWiFiClient.sharedWiFiClient()
        self._iface = self._client.interface()
        if self._iface is None:
            raise RuntimeError("Nenhuma interface Wi-Fi encontrada (CoreWLAN).")
        self._warned_redacted = False
        self._last_samples: List[WifiSample] = []
        self._refresh_interval = refresh_interval_s

        # Um scan ativo completo leva ~15-25s no macOS. Para um dashboard
        # responsivo, lê-se o cache do sistema (instantâneo) a cada chamada de
        # scan(), enquanto esta thread força scans ativos periódicos para manter
        # o cache fresco com RSSI atualizado.
        self._active_scan_once()  # prime inicial (bloqueante, uma vez)
        self._stop = threading.Event()
        self._refresher = threading.Thread(
            target=self._refresh_loop, name="wifi-refresh", daemon=True
        )
        self._refresher.start()

    def close(self) -> None:
        """Encerra a thread de atualização do cache."""
        self._stop.set()

    def _refresh_loop(self) -> None:
        while not self._stop.wait(self._refresh_interval):
            self._active_scan_once()

    def _active_scan_once(self) -> None:
        """Dispara um scan ativo (bloqueante) para atualizar o cache do sistema."""
        import time

        for attempt in range(5):
            _, error = self._iface.scanForNetworksWithName_error_(None, None)
            if error is None:
                return
            if error.code() == 16:  # Resource busy
                time.sleep(1.5 * (attempt + 1))
                continue
            logger.debug("Scan ativo falhou: %s", error)
            return

    def scan(self) -> List[WifiSample]:
        """Retorna as redes do cache do sistema (rápido, dados reais)."""
        networks = self._iface.cachedScanResults()
        if not networks:
            return self._last_samples

        # Agrupa por (banda, canal, largura) para gerar identidade estável quando
        # o BSSID não está disponível (rede sem permissão de Localização).
        raw = []
        for net in networks:
            ch_obj = net.wlanChannel()
            channel = ch_obj.channelNumber() if ch_obj else 0
            band = self._BAND.get(ch_obj.channelBand()) if ch_obj else None
            width = self._WIDTH.get(ch_obj.channelWidth()) if ch_obj else None
            raw.append(
                {
                    "ssid": net.ssid(),
                    "bssid": net.bssid(),
                    "rssi": int(net.rssiValue()),
                    "channel": int(channel),
                    "band": band,
                    "width": width,
                }
            )

        if not self._warned_redacted and all(r["bssid"] is None for r in raw):
            logger.warning(
                "SSID/BSSID indisponíveis (sem permissão de Localização). "
                "RSSI/canal/banda são reais; nomes exigem app empacotado com TCC."
            )
            self._warned_redacted = True

        # Ordena por RSSI desc. dentro de cada grupo para indexar de forma estável.
        from collections import defaultdict

        groups: dict[tuple, list[dict]] = defaultdict(list)
        for r in raw:
            groups[(r["band"], r["channel"], r["width"])].append(r)

        samples: List[WifiSample] = []
        for (band, channel, width), items in groups.items():
            items.sort(key=lambda x: x["rssi"], reverse=True)
            for rank, r in enumerate(items):
                bssid = r["bssid"]
                if bssid:
                    ssid = r["ssid"] or "<oculto>"
                    identity = bssid
                else:
                    # Identidade sintética estável (sem BSSID real disponível).
                    identity = f"{band or '?'}-ch{channel}-w{int(width or 0)}-#{rank}"
                    ssid = r["ssid"] or f"AP {identity}"
                samples.append(
                    WifiSample(
                        ssid=ssid,
                        bssid=identity,
                        rssi=r["rssi"],
                        channel=channel,
                        frequency_mhz=channel_to_frequency(channel, band),
                        bandwidth_mhz=width,
                    )
                )
        self._last_samples = samples
        return samples


class SimulatedScanner(WifiScanner):
    """Gera dados sintéticos realistas para testes e demonstração.

    Útil quando as ferramentas do sistema não estão disponíveis ou quando
    se deseja reproduzir cenários de interferência de forma controlada.
    """

    _NETWORKS = [
        ("LabNet-2G", "aa:bb:cc:00:00:01", 6, 2437.0),
        ("LabNet-5G", "aa:bb:cc:00:00:02", 36, 5180.0),
        ("Vizinho-2G", "dd:ee:ff:00:00:03", 11, 2462.0),
        ("IoT-Sensors", "11:22:33:00:00:04", 1, 2412.0),
    ]

    def __init__(self) -> None:
        self._t = 0

    def scan(self) -> List[WifiSample]:
        self._t += 1
        samples: List[WifiSample] = []
        for ssid, bssid, channel, freq in self._NETWORKS:
            base = -55 if freq < 3000 else -65
            # Variação senoidal + ruído gaussiano simulando o ambiente.
            jitter = random.gauss(0, 2.5)
            drift = 4 * __import__("math").sin(self._t / 8.0)
            rssi = int(base + drift + jitter)
            samples.append(
                WifiSample(
                    ssid=ssid,
                    bssid=bssid,
                    rssi=rssi,
                    channel=channel,
                    frequency_mhz=freq,
                    bandwidth_mhz=20.0 if freq < 3000 else 80.0,
                )
            )
        return samples


def create_scanner(force_simulated: bool = False) -> WifiScanner:
    """Cria o scanner adequado ao sistema operacional.

    Args:
        force_simulated: Se ``True``, retorna sempre o scanner simulado.

    Returns:
        Uma instância de :class:`WifiScanner`. Em caso de falha na detecção
        da plataforma real, recai para :class:`SimulatedScanner`.
    """
    if force_simulated:
        logger.info("Usando scanner simulado (forçado).")
        return SimulatedScanner()

    system = platform.system()
    if system == "Linux":
        candidate: WifiScanner = LinuxScanner()
    elif system == "Windows":
        candidate = WindowsScanner()
    elif system == "Darwin":
        candidate = MacScanner()
    else:
        raise RuntimeError(
            f"Plataforma '{system}' não suportada. Use --simulate para dados sintéticos."
        )

    # Valida a captura real. Sem fallback silencioso: se falhar, propaga o erro
    # (o usuário decide usar --simulate conscientemente).
    n = len(candidate.scan())
    logger.info("Scanner nativo (%s) inicializado: %d redes detectadas.", system, n)
    return candidate
