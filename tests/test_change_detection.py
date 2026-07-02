"""Testes do detector de alteração ambiental (estatística robusta)."""

from __future__ import annotations

import numpy as np

from app.ai.change_detection import ChangeDetector


def _feed(detector, values):
    result = None
    for v in values:
        result = detector.update(v)
    return result


def test_stable_environment_low_probability():
    det = ChangeDetector(baseline_window=60, recent_window=10)
    rng = np.random.default_rng(0)
    res = _feed(det, -60 + rng.normal(0, 1, size=70))
    assert res.probability < 0.5
    assert not res.is_alert


def test_level_shift_triggers_alert():
    det = ChangeDetector(baseline_window=60, recent_window=10, threshold=0.7)
    rng = np.random.default_rng(1)
    _feed(det, -60 + rng.normal(0, 1, size=60))
    res = _feed(det, -45 + rng.normal(0, 1, size=10))  # mudança de nível clara
    assert res.probability >= 0.7
    assert res.is_alert


def test_variance_burst_detected_without_level_change():
    """Movimento aumenta a dispersão mesmo sem mover a média: deve detectar."""
    det = ChangeDetector(baseline_window=60, recent_window=10, threshold=0.6)
    rng = np.random.default_rng(2)
    _feed(det, -60 + rng.normal(0, 0.5, size=60))
    res = _feed(det, -60 + rng.normal(0, 8, size=10))  # mesma média, +variância
    assert res.probability > 0.5


def test_single_outlier_does_not_false_alarm():
    """Estatística robusta (mediana/MAD) ignora um pico isolado."""
    det = ChangeDetector(baseline_window=60, recent_window=10, threshold=0.7)
    rng = np.random.default_rng(3)
    _feed(det, -60 + rng.normal(0, 1, size=69))
    res = det.update(30.0)  # único spike grosseiro
    assert not res.is_alert


def test_stability_index_bounds_and_monotonicity():
    calm = ChangeDetector()
    noisy = ChangeDetector()
    rng = np.random.default_rng(4)
    _feed(calm, -60 + rng.normal(0, 0.3, size=40))
    _feed(noisy, -60 + rng.normal(0, 10, size=40))
    si_calm, si_noisy = calm.stability_index(), noisy.stability_index()
    assert 0.0 <= si_noisy <= si_calm <= 1.0
    assert si_calm > si_noisy


def test_nan_input_is_handled():
    det = ChangeDetector()
    res = _feed(det, [-60.0] * 20 + [float("nan")])
    assert np.isfinite(res.probability)
