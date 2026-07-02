"""Técnicas de processamento de sinais aplicadas às séries de RSSI.

Inclui filtragem de ruído, média móvel, FFT, análise estatística e extração
de características utilizadas pelos modelos de IA.
"""

from __future__ import annotations

import numpy as np
from scipy import signal as sp_signal
from scipy import stats


def sanitize_series(series: np.ndarray) -> np.ndarray:
    """Converte para vetor 1D de float e neutraliza valores não-finitos.

    Garantia de robustez para todo o pipeline: ``NaN``/``inf`` (comuns quando o
    scanner perde uma leitura) são interpolados a partir dos vizinhos finitos;
    se não houver nenhum valor finito, retorna zeros. Isso evita que um único
    valor inválido contamine médias, FFTs e covariâncias rio abaixo.

    Args:
        series: Sequência de valores (qualquer dtype convertível para float).

    Returns:
        Vetor 1D ``float`` finito, com o mesmo comprimento da entrada.
    """
    arr = np.asarray(series, dtype=float).ravel()
    if arr.size == 0:
        return arr
    finite = np.isfinite(arr)
    if finite.all():
        return arr
    if not finite.any():
        return np.zeros_like(arr)
    idx = np.arange(arr.size)
    arr = arr.copy()
    arr[~finite] = np.interp(idx[~finite], idx[finite], arr[finite])
    return arr


def moving_average(series: np.ndarray, window: int = 5) -> np.ndarray:
    """Aplica média móvel simples para suavizar a série.

    Args:
        series: Vetor 1D de valores (ex.: RSSI ao longo do tempo).
        window: Tamanho da janela. Valores <= 1 retornam a série original.

    Returns:
        Série suavizada com o mesmo comprimento da entrada.
    """
    series = sanitize_series(series)
    if window <= 1 or series.size < window:
        return series
    kernel = np.ones(window) / window
    return np.convolve(series, kernel, mode="same")


def hampel_filter(series: np.ndarray, window: int = 7, n_sigmas: float = 3.0) -> np.ndarray:
    """Remove outliers (spikes) preservando as bordas de movimento.

    Para cada ponto, compara-o à mediana de uma janela local; se desviar mais
    que ``n_sigmas`` do desvio absoluto mediano (MAD), substitui pela mediana.
    Mais robusto que a média móvel contra picos espúrios de RSSI.

    Args:
        series: Vetor 1D de valores.
        window: Tamanho (raio efetivo) da janela local.
        n_sigmas: Limiar de desvio em múltiplos do MAD.

    Returns:
        Série com outliers corrigidos (mesmo comprimento).
    """
    series = sanitize_series(series)
    n = series.size
    if n < 3:
        return series.copy()
    out = series.copy()
    k = 1.4826  # fator que torna o MAD comparável ao desvio-padrão
    half = max(1, window // 2)
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        local = series[lo:hi]
        med = np.median(local)
        mad = k * np.median(np.abs(local - med))
        # Com MAD>0, regra clássica n-sigmas; com vizinhança constante (MAD=0),
        # qualquer divergência da mediana é um spike.
        is_outlier = abs(series[i] - med) > n_sigmas * mad if mad > 0 else series[i] != med
        if is_outlier:
            out[i] = med
    return out


def kalman_smooth(series: np.ndarray, q: float = 0.05, r: float = 4.0) -> np.ndarray:
    """Suaviza a série com um filtro de Kalman 1D (modelo de passeio aleatório).

    Acompanha mudanças reais de nível do sinal melhor que a média móvel, com
    menos atraso, ajustando a confiança via ruído de processo ``q`` e de medição
    ``r``.

    Args:
        series: Vetor 1D de valores (ex.: RSSI).
        q: Variância do ruído de processo (quanto o estado pode variar).
        r: Variância do ruído de medição (quão ruidosa é a leitura).

    Returns:
        Série filtrada (mesmo comprimento).
    """
    series = sanitize_series(series)
    if series.size == 0:
        return series
    x = series[0]      # estimativa de estado
    p = 1.0            # covariância da estimativa
    out = np.empty_like(series)
    for i, z in enumerate(series):
        # Predição.
        p += q
        # Atualização.
        k = p / (p + r)
        x = x + k * (z - x)
        p = (1 - k) * p
        out[i] = x
    return out


def denoise(series: np.ndarray, window: int = 7, polyorder: int = 2) -> np.ndarray:
    """Remove ruído de alta frequência com o filtro de Savitzky-Golay.

    Args:
        series: Vetor 1D de valores.
        window: Comprimento da janela (será ajustado para ímpar).
        polyorder: Ordem do polinômio de ajuste.

    Returns:
        Série filtrada.
    """
    series = sanitize_series(series)
    if series.size < 5:
        return series
    win = min(window, series.size)
    if win % 2 == 0:
        win -= 1
    win = max(win, polyorder + 1 + (polyorder % 2 == 0))
    if win % 2 == 0:
        win += 1
    if win > series.size:
        return series
    return sp_signal.savgol_filter(series, win, polyorder)


def compute_fft(
    series: np.ndarray, sample_rate: float = 1.0, window: bool = True
) -> tuple[np.ndarray, np.ndarray]:
    """Calcula a Transformada Rápida de Fourier (espectro de magnitude).

    Aplica remoção de DC e, por padrão, uma janela de Hann antes da FFT para
    reduzir o vazamento espectral (*spectral leakage*) — essencial quando a
    série é curta e o sinal periódico não completa um número inteiro de ciclos.
    A magnitude é corrigida pelo ganho coerente da janela para manter a escala.

    Args:
        series: Vetor 1D de valores.
        sample_rate: Taxa de amostragem em Hz (1 / intervalo de varredura).
        window: Se ``True`` (padrão), aplica janela de Hann.

    Returns:
        Tupla ``(frequências, magnitudes)`` contendo apenas o lado positivo.
    """
    series = sanitize_series(series)
    series = series - np.mean(series)
    n = series.size
    if n < 2:
        return np.array([]), np.array([])
    if window:
        w = np.hanning(n)
        coherent_gain = float(np.mean(w)) or 1.0
        series = series * w
        mags = np.abs(np.fft.rfft(series)) / (n * coherent_gain)
    else:
        mags = np.abs(np.fft.rfft(series)) / n
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
    return freqs, mags


def statistical_summary(series: np.ndarray) -> dict[str, float]:
    """Calcula estatísticas descritivas de uma série."""
    series = sanitize_series(series)
    if series.size == 0:
        return {k: 0.0 for k in ("mean", "std", "min", "max", "skew", "kurtosis", "rms")}
    return {
        "mean": float(np.mean(series)),
        "std": float(np.std(series)),
        "min": float(np.min(series)),
        "max": float(np.max(series)),
        "skew": float(stats.skew(series)) if series.size > 2 else 0.0,
        "kurtosis": float(stats.kurtosis(series)) if series.size > 3 else 0.0,
        "rms": float(np.sqrt(np.mean(series**2))),
    }


def extract_features(series: np.ndarray, sample_rate: float = 1.0) -> dict[str, float]:
    """Extrai um vetor de características de uma série temporal de RSSI.

    Combina estatísticas no domínio do tempo e da frequência, úteis para
    classificação de padrões ambientais e detecção de alterações.

    Returns:
        Dicionário ordenado de características.
    """
    series = sanitize_series(series)
    feats = statistical_summary(series)

    # Variação temporal.
    diffs = np.diff(series) if series.size > 1 else np.array([0.0])
    feats["mean_abs_diff"] = float(np.mean(np.abs(diffs)))
    feats["max_abs_diff"] = float(np.max(np.abs(diffs)))
    feats["range"] = feats["max"] - feats["min"]

    # Domínio da frequência.
    freqs, mags = compute_fft(series, sample_rate)
    if mags.size > 1:
        spectral_energy = float(np.sum(mags**2))
        dominant = float(freqs[int(np.argmax(mags[1:]) + 1)]) if mags.size > 1 else 0.0
        # Entropia espectral (medida de "desordem" do espectro).
        p = mags / (np.sum(mags) + 1e-12)
        spectral_entropy = float(-np.sum(p * np.log2(p + 1e-12)))
    else:
        spectral_energy = dominant = spectral_entropy = 0.0

    feats["spectral_energy"] = spectral_energy
    feats["dominant_freq"] = dominant
    feats["spectral_entropy"] = spectral_entropy
    return feats
