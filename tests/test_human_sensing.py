"""Testes do motor de sensoriamento ambiental (PCA multi-link, periodicidade)."""

from __future__ import annotations

import numpy as np

from app.ai.human_sensing import HumanSensingEngine
from app.wifi.models import WifiSample


def _samples(rssis, base_freq=5180.0):
    return [
        WifiSample(
            ssid=f"AP{i}", bssid=f"00:11:22:33:44:{i:02x}",
            rssi=int(r), channel=36, frequency_mhz=base_freq,
        )
        for i, r in enumerate(rssis)
    ]


def _run(engine, frames):
    state = None
    for frame in frames:
        anchor = float(np.median([s.rssi for s in frame]))
        state = engine.update(anchor, frame)
    return state


def test_static_environment_no_presence():
    eng = HumanSensingEngine(sample_rate_hz=1.0)
    rng = np.random.default_rng(0)
    frames = [_samples(-60 + rng.normal(0, 0.4, size=5)) for _ in range(40)]
    state = _run(eng, frames)
    assert not state.presence
    assert state.motion_index < 2.0


def test_correlated_motion_detected():
    """Flutuação correlacionada entre vários APs deve elevar a coerência."""
    eng = HumanSensingEngine(sample_rate_hz=1.0)
    rng = np.random.default_rng(1)
    frames = []
    for t in range(40):
        common = 6.0 * np.sin(2 * np.pi * 0.1 * t)  # movimento global
        rssis = [-60 + common + rng.normal(0, 0.3) for _ in range(6)]
        frames.append(_samples(rssis))
    state = _run(eng, frames)
    assert state.coherence > 0.3
    assert state.motion_index > 1.0


def test_correlated_motion_more_coherent_than_single_noisy_ap():
    """Movimento global (correlacionado) deve gerar coerência maior que o
    ruído concentrado em um único enlace — discriminação multi-link robusta."""
    rng = np.random.default_rng(2)

    eng_single = HumanSensingEngine(sample_rate_hz=1.0)
    single_frames = []
    for _ in range(40):
        rssis = [-60 + rng.normal(0, 0.3) for _ in range(5)]
        rssis[0] = -60 + rng.normal(0, 12)  # único enlace muito ruidoso
        single_frames.append(_samples(rssis))
    coh_single = _run(eng_single, single_frames).coherence

    eng_global = HumanSensingEngine(sample_rate_hz=1.0)
    global_frames = []
    for t in range(40):
        common = 6.0 * np.sin(2 * np.pi * 0.1 * t)
        rssis = [-60 + common + rng.normal(0, 0.3) for _ in range(5)]
        global_frames.append(_samples(rssis))
    coh_global = _run(eng_global, global_frames).coherence

    assert coh_global > coh_single


def test_periodicity_detects_rhythm():
    eng = HumanSensingEngine(sample_rate_hz=2.0)
    frames = []
    for t in range(60):
        val = -55 + 5 * np.sin(2 * np.pi * 0.25 * t / 2.0)
        frames.append(_samples([val] * 4))
    state = _run(eng, frames)
    assert state.has_rhythm
    assert state.periodicity_period_s > 0


def test_slow_drift_is_not_rhythm():
    """Deriva lenta (menos de ~2 ciclos) não deve virar 'ritmo'."""
    eng = HumanSensingEngine(sample_rate_hz=1.0)
    frames = [_samples([-60 + 0.1 * t] * 4) for t in range(48)]
    state = _run(eng, frames)
    assert not state.has_rhythm


def test_state_fields_always_finite():
    eng = HumanSensingEngine(sample_rate_hz=1.0)
    rng = np.random.default_rng(5)
    frames = [_samples(-60 + rng.normal(0, 2, size=5)) for _ in range(30)]
    state = _run(eng, frames)
    for val in (state.motion_index, state.coherence, state.svr, state.lvr,
                state.change_prob, state.stability):
        assert np.isfinite(val)
    assert 0.0 <= state.stability <= 1.0
    assert 0.0 <= state.change_prob <= 1.0
