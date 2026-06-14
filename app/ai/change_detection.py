"""Detecção de alterações no ambiente físico via sinais Wi-Fi.

A premissa é que mudanças no ambiente (movimentação, obstáculos, presença de
pessoas) alteram a propagação dos sinais. O detector mantém uma linha de base
estatística e calcula um índice probabilístico de alteração quando o
comportamento recente diverge dessa base.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque

import numpy as np


@dataclass
class ChangeResult:
    """Resultado de uma avaliação de mudança ambiental.

    Attributes:
        probability: Índice probabilístico de alteração [0, 1].
        is_alert: ``True`` se ultrapassou o limiar configurado.
        z_score: Magnitude do desvio em relação à linha de base.
    """

    probability: float
    is_alert: bool
    z_score: float


class ChangeDetector:
    """Detecta alterações ambientais a partir da série de RSSI.

    Usa uma janela de referência (linha de base) e uma janela recente. A
    divergência entre as duas é convertida em probabilidade via função
    logística sobre o z-score do RSSI médio recente.
    """

    def __init__(
        self,
        baseline_window: int = 60,
        recent_window: int = 10,
        threshold: float = 0.7,
        sensitivity: float = 1.0,
    ) -> None:
        """Inicializa o detector.

        Args:
            baseline_window: Nº de amostras que compõem a linha de base.
            recent_window: Nº de amostras recentes avaliadas.
            threshold: Limiar de probabilidade para disparo de alerta.
            sensitivity: Fator multiplicativo da resposta logística.
        """
        self.baseline_window = baseline_window
        self.recent_window = recent_window
        self.threshold = threshold
        self.sensitivity = sensitivity
        self._buffer: Deque[float] = deque(maxlen=baseline_window + recent_window)

    def reset(self) -> None:
        """Limpa o histórico acumulado."""
        self._buffer.clear()

    def update(self, rssi: float) -> ChangeResult:
        """Adiciona uma nova leitura e avalia a probabilidade de mudança.

        Args:
            rssi: Valor de RSSI mais recente.

        Returns:
            :class:`ChangeResult` com a probabilidade e o estado de alerta.
        """
        self._buffer.append(float(rssi))

        if len(self._buffer) < self.recent_window + 5:
            return ChangeResult(probability=0.0, is_alert=False, z_score=0.0)

        data = np.array(self._buffer, dtype=float)
        recent = data[-self.recent_window:]
        baseline = data[: -self.recent_window]

        base_mean = float(np.mean(baseline))
        base_std = float(np.std(baseline)) + 1e-6
        recent_mean = float(np.mean(recent))

        z = abs(recent_mean - base_mean) / base_std
        # Função logística centrada em z=2 (≈2 desvios -> ~0.5).
        probability = 1.0 / (1.0 + np.exp(-self.sensitivity * (z - 2.0)))
        return ChangeResult(
            probability=float(probability),
            is_alert=probability >= self.threshold,
            z_score=z,
        )

    def stability_index(self) -> float:
        """Retorna um índice de estabilidade do ambiente em [0, 1].

        Quanto mais próximo de 1, mais estável (menor variância recente).
        """
        if len(self._buffer) < 5:
            return 1.0
        std = float(np.std(np.array(self._buffer, dtype=float)))
        # Mapeia desvio padrão para [0, 1] de forma decrescente.
        return float(np.exp(-std / 5.0))
