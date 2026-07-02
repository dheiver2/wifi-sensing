"""Detecção de alterações no ambiente físico via sinais Wi-Fi.

A premissa é que mudanças no ambiente (movimentação, obstáculos, presença de
pessoas) alteram a propagação dos sinais. O detector mantém uma linha de base
estatística e calcula um índice probabilístico de alteração quando o
comportamento recente diverge dessa base.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

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
        stability_scale: float = 5.0,
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
        self.stability_scale = stability_scale
        self._buffer: deque[float] = deque(maxlen=baseline_window + recent_window)

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
        value = float(rssi)
        if not np.isfinite(value):
            # Leitura inválida (scanner perdeu o AP): reaproveita a última
            # amostra válida em vez de contaminar a estatística com NaN/inf.
            value = self._buffer[-1] if self._buffer else 0.0
        self._buffer.append(value)

        if len(self._buffer) < self.recent_window + 5:
            return ChangeResult(probability=0.0, is_alert=False, z_score=0.0)

        data = np.array(self._buffer, dtype=float)
        recent = data[-self.recent_window:]
        baseline = data[: -self.recent_window]

        # Linha de base robusta: mediana + MAD (resistente a outliers, ao
        # contrário de média/desvio, que são puxados por picos espúrios de RSSI).
        base_med = float(np.median(baseline))
        mad = float(np.median(np.abs(baseline - base_med)))
        base_scale = 1.4826 * mad + 1e-6  # MAD reescalado ≈ desvio-padrão
        recent_med = float(np.median(recent))

        # (1) Desvio de NÍVEL (deslocamento da mediana recente).
        z_level = abs(recent_med - base_med) / base_scale
        # (2) Desvio de DISPERSÃO (a variabilidade recente cresce quando há
        # movimento, mesmo sem mudar o nível médio) — razão de espalhamento.
        recent_scale = 1.4826 * float(np.median(np.abs(recent - recent_med)))
        z_spread = max(0.0, (recent_scale - base_scale) / base_scale)

        # Combina as duas evidências (norma euclidiana) num único z robusto.
        z = float(np.hypot(z_level, z_spread))
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
        data = np.array(self._buffer, dtype=float)
        # Dispersão robusta (MAD reescalado) — não colapsa por um único pico.
        med = float(np.median(data))
        scale = 1.4826 * float(np.median(np.abs(data - med)))
        # Mapeia dispersão para [0, 1] de forma decrescente.
        return float(np.exp(-scale / self.stability_scale))
