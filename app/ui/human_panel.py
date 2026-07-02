"""Aba de sensoriamento ambiental: 9 métricas reais derivadas do RSSI.

Todos os painéis usam dados de fato medidos (sem simulação). Métricas que
exigiriam CSI não são exibidas aqui propositalmente.
"""

from __future__ import annotations

from collections import deque

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ai.human_sensing import SensingState

_GREEN = "#2ca02c"
_BLUE = "#1f77b4"
_ORANGE = "#E94A12"
_BAND_COLOR = {"2.4 GHz": "#E94A12", "5 GHz": "#1f77b4", "6 GHz": "#2ca02c"}
_MAXLEN = 120


def _header(title: str) -> QLabel:
    lbl = QLabel(
        f"{title} <span style='color:{_GREEN};font-weight:bold'>[REAL]</span>"
    )
    lbl.setTextFormat(Qt.TextFormat.RichText)
    return lbl


class _TimePanel(QGroupBox):
    """Gráfico de série temporal com valor atual em destaque."""

    def __init__(self, title: str, unit: str, color: str = _BLUE, y_range=None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(_header(title))
        top.addStretch()
        self.value_lbl = QLabel("—")
        self.value_lbl.setStyleSheet("font-size: 19px; font-weight: bold;")
        top.addWidget(self.value_lbl)
        layout.addLayout(top)

        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=False, y=True, alpha=0.3)
        self.plot.setMenuEnabled(False)
        self.plot.hideAxis("bottom")
        if y_range:
            self.plot.setYRange(*y_range)
        self.curve = self.plot.plot(pen=pg.mkPen(color, width=2))
        layout.addWidget(self.plot)
        self._buf: deque[float] = deque(maxlen=_MAXLEN)
        self._unit = unit

    def push(self, value: float, label: str | None = None) -> None:
        self._buf.append(float(value))
        self.curve.setData(np.array(self._buf))
        self.value_lbl.setText(label or f"{value:.1f} {self._unit}")


class _StatePanel(QGroupBox):
    """Indicador categórico grande (atividade)."""

    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(_header(title))
        self.value_lbl = QLabel("—")
        self.value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_lbl.setWordWrap(True)
        self.value_lbl.setStyleSheet("font-size: 22px; font-weight: bold; padding: 14px;")
        layout.addWidget(self.value_lbl, stretch=1)

    def set_value(self, text: str, color: str = "#e6e8eb") -> None:
        self.value_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: bold; padding: 14px; color: {color};"
        )
        self.value_lbl.setText(text)


class _BandPanel(QGroupBox):
    """Barras de ocupação espectral por banda."""

    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(_header(title))
        top.addStretch()
        self.value_lbl = QLabel("—")
        self.value_lbl.setStyleSheet("font-size: 13px;")
        top.addWidget(self.value_lbl)
        layout.addLayout(top)

        self.plot = pg.PlotWidget()
        self.plot.setMenuEnabled(False)
        self.plot.showGrid(y=True, alpha=0.3)
        self._bars = None
        layout.addWidget(self.plot)
        self._bands = ["2.4 GHz", "5 GHz", "6 GHz"]
        ax = self.plot.getAxis("bottom")
        ax.setTicks([[(i, b) for i, b in enumerate(self._bands)]])

    def update_bands(self, counts: dict[str, int], busiest: tuple[int, int]) -> None:
        heights = [counts.get(b, 0) for b in self._bands]
        brushes = [_BAND_COLOR[b] for b in self._bands]
        if self._bars is not None:
            self.plot.removeItem(self._bars)
        self._bars = pg.BarGraphItem(
            x=list(range(len(self._bands))), height=heights, width=0.6, brushes=brushes
        )
        self.plot.addItem(self._bars)
        self.value_lbl.setText(f"Canal mais ocupado: {busiest[0]} ({busiest[1]} redes)")


class HumanSensingPanel(QWidget):
    """Aba com nove painéis de sensoriamento ambiental — todos reais."""

    calibrate_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        legend = QLabel(
            f"<span style='color:{_GREEN};font-weight:bold'>[REAL]</span> "
            "Métricas derivadas do RSSI medido, com filtro Kalman+Hampel e fusão "
            "multi-AP. (Posição, batimento, gestos e contagem exata exigiriam CSI.)"
        )
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend.setWordWrap(True)
        bar.addWidget(legend, 1)
        self.btn_calibrate = QPushButton("🎯 Calibrar ambiente vazio")
        self.btn_calibrate.clicked.connect(self.calibrate_requested.emit)
        bar.addWidget(self.btn_calibrate)
        self.lbl_calib = QLabel("limiar: fixo")
        self.lbl_calib.setObjectName("muted")
        bar.addWidget(self.lbl_calib)
        root.addLayout(bar)

        grid = QGridLayout()
        root.addLayout(grid)

        self.p_motion = _TimePanel("1. Movimento (PCA multi-link)", "dBm", _ORANGE, (0, 12))
        self.p_activity = _StatePanel("2. Presença / Atividade")
        self.p_event = _TimePanel("3. Eventos bruscos (passagem/porta)", "dBm", _ORANGE, (0, 15))
        self.p_rhythm = _TimePanel("4. Periodicidade (movimento rítmico)", "s", _BLUE)
        self.p_change = _TimePanel("5. Alteração ambiental", "%", _ORANGE, (0, 100))
        self.p_stability = _TimePanel("6. Estabilidade do ambiente", "%", _GREEN, (0, 100))
        self.p_quality = _TimePanel("7. Qualidade de sinal (RSSI médio)", "dBm", _BLUE, (-100, -20))
        self.p_count = _TimePanel("8. Nº de redes detectadas", "", _BLUE)
        self.p_band = _BandPanel("9. Ocupação espectral por banda")

        for i, p in enumerate([
            self.p_motion, self.p_activity, self.p_event,
            self.p_rhythm, self.p_change, self.p_stability,
            self.p_quality, self.p_count, self.p_band,
        ]):
            grid.addWidget(p, i // 3, i % 3)

    def update_state(self, st: SensingState) -> None:
        """Atualiza todos os painéis com um novo estado real."""
        self.p_motion.push(
            st.motion_index,
            f"{st.motion_index:.1f} dBm  {'● movimento' if st.presence else '○ estático'}"
            f"  · coer. {st.coherence * 100:.0f}%  · SVR {st.svr:.2f}  · LVR {st.lvr:.1f}",
        )
        self.lbl_calib.setText("limiar: calibrado ✓" if st.calibrated else "limiar: fixo")
        color = {
            "Movimento intenso": _ORANGE,
            "Movimento leve": "#E9A412",
        }.get(st.activity, _GREEN)
        self.p_activity.set_value(
            ("⚠ " if st.event else "") + st.activity, color
        )
        self.p_event.push(st.jerk, f"{st.jerk:.1f} dBm" + ("  ⚠ EVENTO" if st.event else ""))
        self.p_rhythm.push(
            st.periodicity_period_s if st.has_rhythm else 0.0,
            f"T = {st.periodicity_period_s:.1f}s" if st.has_rhythm else "sem ritmo",
        )
        self.p_change.push(st.change_prob * 100, f"{st.change_prob * 100:.0f}%")
        self.p_stability.push(st.stability * 100, f"{st.stability * 100:.0f}%")
        self.p_quality.push(
            st.mean_rssi,
            f"{st.mean_rssi:.0f} dBm  ({st.min_rssi:.0f}…{st.max_rssi:.0f})",
        )
        self.p_count.push(st.net_count, f"{st.net_count}")
        self.p_band.update_bands(st.band_counts, st.busiest_channel)
