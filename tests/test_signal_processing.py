"""Testes das técnicas de processamento de sinais e suas validações."""

from __future__ import annotations

import numpy as np
import pytest

from app.analytics import signal_processing as sp


# --------------------------------------------------------------- sanitize_series
def test_sanitize_replaces_nan_and_inf_by_interpolation():
    series = [0.0, np.nan, 2.0, np.inf, 4.0]
    out = sp.sanitize_series(series)
    assert np.all(np.isfinite(out))
    assert out.tolist() == pytest.approx([0.0, 1.0, 2.0, 3.0, 4.0])


def test_sanitize_all_invalid_returns_zeros():
    out = sp.sanitize_series([np.nan, np.inf, -np.inf])
    assert np.all(out == 0.0)


def test_sanitize_empty():
    assert sp.sanitize_series([]).size == 0


@pytest.mark.parametrize(
    "func", [sp.moving_average, sp.hampel_filter, sp.kalman_smooth, sp.denoise]
)
def test_filters_never_emit_non_finite(func):
    """Toda a cadeia deve ser imune a NaN/inf na entrada (validação)."""
    series = np.array([10.0, np.nan, -50.0, np.inf, -48.0, -47.0, -90.0, -49.0])
    out = func(series)
    assert np.all(np.isfinite(out))
    assert out.shape[0] == series.shape[0]


# --------------------------------------------------------------- moving_average
def test_moving_average_preserves_length_and_smooths():
    series = np.array([1.0, 9.0, 1.0, 9.0, 1.0, 9.0, 1.0])
    out = sp.moving_average(series, window=3)
    assert out.shape == series.shape
    assert np.std(out) < np.std(series)


# --------------------------------------------------------------- hampel_filter
def test_hampel_removes_isolated_spike():
    series = np.full(21, -60.0)
    series[10] = 20.0  # spike grosseiro
    out = sp.hampel_filter(series, window=7, n_sigmas=3.0)
    assert abs(out[10] - (-60.0)) < 1.0
    # vizinhos intocados
    assert out[0] == pytest.approx(-60.0)


def test_hampel_keeps_genuine_step():
    series = np.concatenate([np.full(10, -60.0), np.full(10, -40.0)])
    out = sp.hampel_filter(series, window=5)
    # um degrau real não deve ser apagado
    assert out[-1] == pytest.approx(-40.0, abs=1.0)


# --------------------------------------------------------------- kalman_smooth
def test_kalman_tracks_level_with_less_variance():
    rng = np.random.default_rng(0)
    truth = -55.0
    noisy = truth + rng.normal(0, 4, size=200)
    out = sp.kalman_smooth(noisy)
    assert np.std(out) < np.std(noisy)
    assert out[-1] == pytest.approx(truth, abs=2.0)


# --------------------------------------------------------------- compute_fft
def test_fft_recovers_dominant_frequency():
    fs = 4.0
    t = np.arange(0, 32, 1 / fs)
    f0 = 0.5
    sig = np.sin(2 * np.pi * f0 * t)
    freqs, mags = sp.compute_fft(sig, sample_rate=fs)
    assert freqs[int(np.argmax(mags))] == pytest.approx(f0, abs=0.1)


def test_fft_window_reduces_leakage():
    """A janela de Hann deve concentrar mais energia no pico (menos vazamento)."""
    fs = 4.0
    t = np.arange(0, 17.3, 1 / fs)  # número não-inteiro de ciclos -> vazamento
    sig = np.sin(2 * np.pi * 0.7 * t)
    _, mags_win = sp.compute_fft(sig, sample_rate=fs, window=True)
    _, mags_raw = sp.compute_fft(sig, sample_rate=fs, window=False)
    conc_win = mags_win.max() / (mags_win.sum() + 1e-12)
    conc_raw = mags_raw.max() / (mags_raw.sum() + 1e-12)
    assert conc_win > conc_raw


# --------------------------------------------------------------- extract_features
def test_extract_features_keys_and_finite():
    rng = np.random.default_rng(1)
    series = -60 + rng.normal(0, 3, size=64)
    feats = sp.extract_features(series, sample_rate=1.0)
    for key in ("mean", "std", "spectral_entropy", "dominant_freq", "range"):
        assert key in feats
    assert all(np.isfinite(v) for v in feats.values())


def test_extract_features_handles_short_series():
    feats = sp.extract_features([-60.0], sample_rate=1.0)
    assert all(np.isfinite(v) for v in feats.values())
