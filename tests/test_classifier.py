"""Testes do pipeline de classificação de padrões ambientais."""

from __future__ import annotations

import numpy as np
import pytest

from app.ai.classifier import EnvironmentClassifier


def _dataset(seed=0):
    rng = np.random.default_rng(seed)
    a = rng.normal(0, 1, size=(40, 5))
    b = rng.normal(6, 1, size=(40, 5))
    X = np.vstack([a, b])
    y = np.array([0] * 40 + [1] * 40)
    return X, y


def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        EnvironmentClassifier(mode="invalid")


def test_supervised_requires_labels():
    clf = EnvironmentClassifier(mode="supervised")
    with pytest.raises(ValueError):
        clf.train(np.zeros((10, 3)))


def test_predict_before_train_raises():
    clf = EnvironmentClassifier(mode="supervised")
    with pytest.raises(RuntimeError):
        clf.predict(np.zeros((1, 5)))


def test_supervised_learns_separable_classes():
    X, y = _dataset()
    clf = EnvironmentClassifier(mode="supervised")
    clf.train(X, y, feature_names=[f"f{i}" for i in range(5)])
    assert clf.is_trained
    preds = clf.predict(X)
    assert (preds == y).mean() > 0.9
    proba = clf.predict_proba(X)
    assert proba is not None and proba.shape == (80, 2)


def test_unsupervised_clusters_and_no_proba():
    X, _ = _dataset()
    clf = EnvironmentClassifier(mode="unsupervised", n_clusters=2)
    clf.train(X)
    labels = clf.predict(X)
    assert set(np.unique(labels)) <= {0, 1}
    assert clf.predict_proba(X) is None


def test_save_and_load_roundtrip(tmp_path):
    X, y = _dataset()
    clf = EnvironmentClassifier(mode="supervised")
    clf.train(X, y, feature_names=["a", "b", "c", "d", "e"])
    path = tmp_path / "model.joblib"
    clf.save(path)
    loaded = EnvironmentClassifier.load(path)
    assert loaded.is_trained
    assert loaded.feature_names == ["a", "b", "c", "d", "e"]
    np.testing.assert_array_equal(loaded.predict(X), clf.predict(X))
