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

    motion_index: float            # movimento via PCA multi-link (amplitude dBm)
    coherence: float               # variância explicada pela 1ª componente [0..1]
    svr: float                     # short-term averaged variance ratio (~1 = estático)
    lvr: float                     # long-term averaged variance ratio
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
        # Calibração de ambiente vazio (limiares adaptativos).
        self._calibrated = False
        self._calib_threshold = self._motion_threshold
        self._svr_threshold = 1.25
        self._baseline_cv = 1e-3
        self._calib_buffer: list[float] = []
        self._calib_svr: list[float] = []
        self._calib_cv: list[float] = []
        self._calibrating = False

    def start_calibration(self) -> None:
        """Inicia a coleta da linha de base do ambiente vazio."""
        self._calibrating = True
        self._calib_buffer = []
        self._calib_svr = []
        self._calib_cv = []

    def finish_calibration(self) -> None:
        """Conclui a calibração e define os limiares adaptativos (motion e SVR)."""
        self._calibrating = False
        if len(self._calib_buffer) >= 4:
            arr = np.array(self._calib_buffer)
            # Limiar = média + 3σ do ruído do ambiente vazio (regra clássica 3σ).
            self._calib_threshold = max(0.8, float(arr.mean() + 3 * arr.std()))
            if self._calib_svr:
                s = np.array(self._calib_svr)
                self._svr_threshold = max(1.15, float(s.mean() + 3 * s.std()))
            if self._calib_cv:
                self._baseline_cv = max(1e-3, float(np.mean(self._calib_cv)))
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
        self._track_aps(samples)
        # PCA multi-link: amplitude da componente de movimento correlacionada.
        motion_pca, coherence = self._pca_motion(window=8)
        motion = motion_pca if motion_pca > 0 else motion_anchor
        # SVR/LVR (razões de coeficiente de variação) — detecção calibration-free.
        svr = self._svr(short=6)
        lvr = self._lvr(short=6)

        if self._calibrating:
            self._calib_buffer.append(motion)
            self._calib_svr.append(svr)
            self._calib_cv.append(self._mean_cv(6))

        m_thr = self._calib_threshold if self._calibrated else self._motion_threshold
        s_thr = self._svr_threshold
        # Decisão: amplitude da componente PCA acima do limiar E coerência alta
        # (muitos APs juntos), o que rejeita ruído de um único enlace.
        present = motion > m_thr and coherence > 0.3

        jerk = float(abs(arr[-1] - arr[-2])) if arr.size >= 2 else 0.0
        event = jerk > 6.0

        if not present:
            activity = _ACTIVITIES[1] if arr.size > 4 else _ACTIVITIES[0]
        elif jerk > 6 or motion > 2 * m_thr or svr > 1.8 * s_thr:
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
            svr=svr,
            lvr=lvr,
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

    def _track_aps(self, samples) -> None:
        """Atualiza o histórico curto de RSSI por AP (para fusão multi-link)."""
        for s in samples:
            self._ap_hist.setdefault(s.bssid, deque(maxlen=12)).append(float(s.rssi))
        seen = {s.bssid for s in samples}
        for b in [b for b in self._ap_hist if b not in seen]:
            if len(self._ap_hist[b]) <= 1:
                self._ap_hist.pop(b, None)

    def _link_matrix(self, window: int) -> np.ndarray | None:
        """Matriz (links × janela) dos APs com histórico suficiente."""
        rows = [list(h)[-window:] for h in self._ap_hist.values() if len(h) >= window]
        return np.array(rows, dtype=float) if len(rows) >= 3 else None

    def _pca_motion(self, window: int = 8) -> tuple[float, float]:
        """Extrai a componente de movimento via PCA sobre múltiplos links.

        Baseado em PCA-Kalman (Zhou et al., 2018): o movimento humano induz
        variação *correlacionada* entre os enlaces, que se concentra na primeira
        componente principal, enquanto o ruído de multipath se espalha pelas
        demais. Retorna a amplitude (raiz do maior autovalor) e a variância
        explicada pela 1ª componente (coerência).
        """
        M = self._link_matrix(window)
        if M is None:
            return 0.0, 0.0
        Xc = M - M.mean(axis=1, keepdims=True)   # centra cada link no tempo
        # Covariância entre links (linhas = links = variáveis; colunas = tempo).
        cov = np.cov(Xc)
        if np.ndim(cov) < 2 or cov.shape[0] < 2:
            return 0.0, 0.0
        vals, vecs = np.linalg.eigh(cov)
        top = float(max(vals[-1], 0.0))
        amplitude = float(np.sqrt(top))
        # Coerência = espalhamento da 1ª componente entre links (participation
        # ratio normalizado): ~1 se muitos APs contribuem (evento físico global),
        # ~0 se a variação vem de um único AP (ruído local) — robustez multi-link.
        w = vecs[:, -1] ** 2
        pr = 1.0 / float(np.sum(w ** 2) + 1e-12)   # 1..n_links
        n = len(w)
        coherence = (pr - 1.0) / (n - 1.0) if n > 1 else 0.0
        return amplitude, float(np.clip(coherence, 0.0, 1.0))

    def _mean_cv(self, window: int) -> float:
        """Coeficiente de variação médio entre links na janela recente."""
        cvs = []
        for h in self._ap_hist.values():
            if len(h) >= window:
                a = np.array(list(h)[-window:], dtype=float)
                cvs.append(float(np.std(a) / (abs(np.mean(a)) + 1e-6)))
        return float(np.mean(cvs)) if cvs else 0.0

    def _svr(self, short: int = 6) -> float:
        """Short-term Averaged Variance Ratio (Gong et al., 2015).

        Razão do CV da janela curta atual pela janela curta anterior, média entre
        links. ~1.0 em ambiente estático; cresce no início do movimento.
        """
        ratios = []
        for h in self._ap_hist.values():
            if len(h) >= 2 * short:
                a = np.array(list(h), dtype=float)
                cur, prev = a[-short:], a[-2 * short:-short]
                cv_cur = np.std(cur) / (abs(np.mean(cur)) + 1e-6)
                cv_prev = np.std(prev) / (abs(np.mean(prev)) + 1e-6)
                ratios.append(cv_cur / (cv_prev + 1e-6))
        return float(np.mean(ratios)) if ratios else 1.0

    def _lvr(self, short: int = 6) -> float:
        """Long-term Averaged Variance Ratio: CV atual vs linha de base vazia."""
        return float(self._mean_cv(short) / (self._baseline_cv + 1e-6))

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
