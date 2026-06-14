"""Motor de sensoriamento ambiental a partir de RSSI — métricas 100% reais.

Todas as métricas aqui são **de fato derivadas** da série temporal de RSSI
medida (sem simulação). São as inferências fisicamente possíveis com RSSI a
baixa taxa de amostragem: presença, movimento, atividade grosseira, eventos
bruscos, periodicidade, alteração ambiental, estabilidade e qualidade espectral.

Métricas que exigiriam CSI (batimento cardíaco, posição, gestos, contagem exata
de pessoas) foram deliberadamente removidas por não serem mensuráveis com este
hardware — ver classe :class:`CSIBackend` como ponto de extensão futuro.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Deque, Sequence

import numpy as np

from app.analytics.signal_processing import hampel_filter, kalman_smooth
from app.wifi.models import WifiSample

_ACTIVITIES = ["Ambiente vazio/estático", "Parado / sentado", "Movimento leve", "Movimento intenso"]


@dataclass
class SensingState:
    """Métricas reais de sensoriamento ambiental em um instante."""

    motion_index: float            # movimento (RSSI filtrado por Kalman+Hampel)
    coherence: float               # fração de APs movendo-se juntos [0..1]
    calibrated: bool               # limiar adaptado a ambiente vazio?
    presence: bool                 # movimento acima do limiar
    activity: str                  # faixa de atividade
    jerk: float                    # variação brusca instantânea (dBm)
    event: bool                    # evento brusco detectado
    periodicity_period_s: float    # período dominante (s); 0 se sem ritmo
    has_rhythm: bool
    change_prob: float             # alteração ambiental [0..1]
    stability: float               # estabilidade [0..1]
    mean_rssi: float
    min_rssi: float
    max_rssi: float
    net_count: int
    band_counts: dict[str, int]
    busiest_channel: tuple[int, int]  # (canal, nº de redes)


class HumanSensingEngine:
    """Calcula métricas reais de sensoriamento a partir do RSSI."""

    def __init__(self, sample_rate_hz: float = 0.33, window: int = 48) -> None:
        """Inicializa o motor.

        Args:
            sample_rate_hz: Taxa de amostragem efetiva (1/intervalo de scan).
            window: Nº de amostras retidas para análise temporal.
        """
        self.sample_rate_hz = sample_rate_hz
        self._window = max(window, 32)
        self._buffer: Deque[float] = deque(maxlen=self._window)
        self._ap_hist: dict[str, Deque[float]] = {}
        self._motion_threshold = 1.5  # dBm de desvio ~ movimento perceptível
        # Calibração de ambiente vazio (limiar adaptativo).
        self._calibrated = False
        self._calib_threshold = self._motion_threshold
        self._calib_buffer: list[float] = []
        self._calibrating = False

    def start_calibration(self) -> None:
        """Inicia a coleta da linha de base do ambiente vazio."""
        self._calibrating = True
        self._calib_buffer = []

    def finish_calibration(self) -> None:
        """Conclui a calibração e define o limiar adaptativo de presença."""
        self._calibrating = False
        if len(self._calib_buffer) >= 4:
            arr = np.array(self._calib_buffer)
            # Limiar = média + 3σ do ruído do ambiente vazio (mín. 0.8 dBm).
            self._calib_threshold = max(0.8, float(arr.mean() + 3 * arr.std()))
            self._calibrated = True

    def update(self, anchor_rssi: float, samples: Sequence[WifiSample]) -> SensingState:
        """Atualiza o motor com a leitura mais recente.

        Args:
            anchor_rssi: RSSI de referência (mediana do ambiente ou rede focada).
            samples: Todas as amostras da varredura atual.

        Returns:
            O :class:`SensingState` resultante (todas as métricas reais).
        """
        self._buffer.append(float(anchor_rssi))
        raw = np.array(self._buffer, dtype=float)
        # Cadeia de filtragem: Hampel (remove spikes) -> Kalman (suaviza nível).
        arr = kalman_smooth(hampel_filter(raw)) if raw.size >= 3 else raw

        # --- Movimento (sinal filtrado) e fusão multi-AP ---
        recent = arr[-8:]
        motion_anchor = float(np.std(recent)) if recent.size >= 3 else 0.0
        motion_fused, coherence = self._fuse_multi_ap(samples, motion_anchor)
        motion = motion_fused

        threshold = self._calib_threshold if self._calibrated else self._motion_threshold
        present = motion > threshold

        if self._calibrating:
            self._calib_buffer.append(motion)

        jerk = float(abs(arr[-1] - arr[-2])) if arr.size >= 2 else 0.0
        event = jerk > 6.0

        if not present:
            activity = _ACTIVITIES[1] if arr.size > 4 else _ACTIVITIES[0]
        elif jerk > 6 or motion > 2 * threshold:
            activity = _ACTIVITIES[3]
        else:
            activity = _ACTIVITIES[2]

        # --- Periodicidade (movimento rítmico: ventilador, balanço, passos) ---
        period, has_rhythm = self._periodicity(arr)

        # --- Alteração ambiental (z-score recente vs linha de base) ---
        change_prob = self._change_probability(arr)

        # --- Estabilidade ---
        stability = float(np.exp(-float(np.std(arr)) / 5.0)) if arr.size >= 5 else 1.0

        # --- Qualidade espectral (toda a varredura) ---
        rssis = np.array([s.rssi for s in samples], dtype=float)
        bands = Counter(WifiSample.band(s.frequency_mhz) for s in samples)
        channels = Counter(s.channel for s in samples)
        busiest = channels.most_common(1)[0] if channels else (0, 0)

        return SensingState(
            motion_index=motion,
            coherence=coherence,
            calibrated=self._calibrated,
            presence=present,
            activity=activity,
            jerk=jerk,
            event=event,
            periodicity_period_s=period,
            has_rhythm=has_rhythm,
            change_prob=change_prob,
            stability=stability,
            mean_rssi=float(np.mean(rssis)) if rssis.size else 0.0,
            min_rssi=float(np.min(rssis)) if rssis.size else 0.0,
            max_rssi=float(np.max(rssis)) if rssis.size else 0.0,
            net_count=len(samples),
            band_counts=dict(bands),
            busiest_channel=busiest,
        )

    def _fuse_multi_ap(self, samples, motion_anchor: float) -> tuple[float, float]:
        """Funde a variação de múltiplos APs em um índice de movimento robusto.

        Mantém uma curta janela de RSSI por AP. O movimento do ambiente é a
        mediana dos desvios por AP (robusta a ruído de um único AP). A coerência
        é a fração de APs ativos que variaram juntos no último instante — alta
        coerência indica um evento físico global (alguém andando) e não ruído
        local de um único ponto de acesso.

        Returns:
            (movimento_fundido, coerência) — coerência em [0, 1].
        """
        for s in samples:
            hist = self._ap_hist.setdefault(s.bssid, deque(maxlen=10))
            hist.append(float(s.rssi))
        # Remove APs que sumiram (mantém só os vistos recentemente).
        seen = {s.bssid for s in samples}
        for b in [b for b in self._ap_hist if b not in seen]:
            if len(self._ap_hist[b]) <= 1:
                self._ap_hist.pop(b, None)

        stds, deltas = [], []
        for hist in self._ap_hist.values():
            if len(hist) >= 4:
                a = np.array(hist, dtype=float)
                stds.append(float(np.std(a[-6:])))
                deltas.append(float(a[-1] - a[-2]))
        if len(stds) < 3:
            return motion_anchor, 0.0

        motion = float(np.median(stds))
        deltas_arr = np.array(deltas)
        movers = np.abs(deltas_arr) > 1.0
        coherence = float(np.mean(movers)) if deltas_arr.size else 0.0
        return motion, coherence

    def _periodicity(self, arr: np.ndarray) -> tuple[float, bool]:
        """Detecta periodicidade dominante na série de RSSI (FFT)."""
        if arr.size < 16:
            return 0.0, False
        detr = arr - np.mean(arr)
        freqs = np.fft.rfftfreq(detr.size, d=1.0 / self.sample_rate_hz)
        mags = np.abs(np.fft.rfft(detr))
        if mags.size <= 1:
            return 0.0, False
        mags[0] = 0.0  # remove componente DC
        idx = int(np.argmax(mags))
        peak, mean_mag = mags[idx], float(np.mean(mags[1:]) + 1e-9)
        if freqs[idx] <= 0:
            return 0.0, False
        has_rhythm = peak > 3.0 * mean_mag  # pico destacado do ruído
        return float(1.0 / freqs[idx]), has_rhythm

    def _change_probability(self, arr: np.ndarray) -> float:
        """Probabilidade de alteração ambiental via z-score logístico."""
        if arr.size < 15:
            return 0.0
        recent = arr[-10:]
        baseline = arr[:-10]
        base_mean = float(np.mean(baseline))
        base_std = float(np.std(baseline)) + 1e-6
        z = abs(float(np.mean(recent)) - base_mean) / base_std
        return float(1.0 / (1.0 + np.exp(-(z - 2.0))))


class CSIBackend:
    """Ponto de extensão para hardware de CSI real (não implementado).

    Implemente esta interface para um dispositivo CSI (ESP32-CSI, Nexmon,
    Intel 5300) e habilite métricas hoje impossíveis com RSSI: contagem de
    pessoas, posição, direção, velocidade, marcha, respiração de alta precisão,
    batimento cardíaco e gestos.
    """

    def read_csi(self):  # pragma: no cover - contrato de extensão
        raise NotImplementedError(
            "Conecte um dispositivo CSI e implemente a leitura de subportadoras."
        )
