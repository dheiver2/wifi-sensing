"""Pipeline de classificação de padrões ambientais (Scikit-Learn).

Suporta aprendizado supervisionado (RandomForest) e não supervisionado
(KMeans) sobre os vetores de características extraídos dos sinais Wi-Fi.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class EnvironmentClassifier:
    """Classificador de padrões ambientais a partir de características de sinal.

    Pode operar em dois modos:
        * ``supervised``: requer rótulos; usa RandomForest.
        * ``unsupervised``: agrupa estados ambientais com KMeans.
    """

    def __init__(self, mode: str = "supervised", n_clusters: int = 3) -> None:
        """Inicializa o pipeline.

        Args:
            mode: ``"supervised"`` ou ``"unsupervised"``.
            n_clusters: Número de grupos para o modo não supervisionado.
        """
        if mode not in ("supervised", "unsupervised"):
            raise ValueError(f"Modo inválido: {mode!r}")
        self.mode = mode
        self.n_clusters = n_clusters
        self.feature_names: list[str] = []
        self._trained = False

        if mode == "supervised":
            self.pipeline = Pipeline(
                steps=[
                    ("scaler", StandardScaler()),
                    ("clf", RandomForestClassifier(n_estimators=200, random_state=42)),
                ]
            )
        else:
            self.pipeline = Pipeline(
                steps=[
                    ("scaler", StandardScaler()),
                    ("clf", KMeans(n_clusters=n_clusters, n_init=10, random_state=42)),
                ]
            )

    @property
    def is_trained(self) -> bool:
        """Indica se o modelo já foi treinado."""
        return self._trained

    def train(
        self,
        X: np.ndarray,
        y: Sequence | None = None,
        feature_names: Sequence[str] | None = None,
    ) -> None:
        """Treina o modelo.

        Args:
            X: Matriz de características ``(n_amostras, n_features)``.
            y: Rótulos (obrigatório no modo supervisionado).
            feature_names: Nomes das colunas de ``X`` (opcional).
        """
        X = np.asarray(X, dtype=float)
        if feature_names is not None:
            self.feature_names = list(feature_names)
        if self.mode == "supervised":
            if y is None:
                raise ValueError("Modo supervisionado requer rótulos 'y'.")
            self.pipeline.fit(X, y)
        else:
            self.pipeline.fit(X)
        self._trained = True
        logger.info("Modelo (%s) treinado com %d amostras.", self.mode, X.shape[0])

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Prediz rótulos/grupos para novas amostras."""
        if not self._trained:
            raise RuntimeError("Modelo não treinado.")
        return self.pipeline.predict(np.asarray(X, dtype=float))

    def predict_proba(self, X: np.ndarray) -> np.ndarray | None:
        """Retorna probabilidades (apenas modo supervisionado)."""
        if self.mode != "supervised" or not self._trained:
            return None
        return self.pipeline.predict_proba(np.asarray(X, dtype=float))

    def save(self, path: Path) -> None:
        """Salva o modelo treinado em disco (joblib)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "mode": self.mode,
                "n_clusters": self.n_clusters,
                "feature_names": self.feature_names,
                "pipeline": self.pipeline,
                "trained": self._trained,
            },
            path,
        )
        logger.info("Modelo salvo em %s", path)

    @classmethod
    def load(cls, path: Path) -> EnvironmentClassifier:
        """Carrega um modelo previamente salvo."""
        data = joblib.load(path)
        obj = cls(mode=data["mode"], n_clusters=data.get("n_clusters", 3))
        obj.pipeline = data["pipeline"]
        obj.feature_names = data.get("feature_names", [])
        obj._trained = data.get("trained", True)
        logger.info("Modelo carregado de %s", path)
        return obj
