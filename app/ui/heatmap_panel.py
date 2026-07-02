"""Aba de mapas de calor do ambiente Wi-Fi.

Dois mapas reais, construídos a partir do RSSI medido:

* Intensidade (RSSI) por rede × tempo — a "paisagem" do sinal.
* Movimento (variação do RSSI) por rede × tempo — revela quando há atividade
  física perturbando cada caminho de propagação. É o análogo possível, com
  RSSI de uma antena, à detecção de movimento por Wi-Fi.

Observação honesta: a imagem espacial 2D "através de paredes" do artigo do MIT
(RF-Capture/WiTrack) exige radar FMCW, arranjos de antenas e CSI — não é
reproduzível apenas com RSSI. Aqui o "espaço" é (rede × tempo), não (x × y).
"""

from __future__ import annotations

from collections import deque

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget

from app.ui import theme
from app.wifi.models import WifiSample

_MAX_ROWS = 22
_MAX_COLS = 120


class _HeatmapView(QWidget):
    """Um mapa de calor (ImageItem) com barra de cor e rótulos de rede."""

    def __init__(self, title: str, cmap_name: str, levels: tuple[float, float],
                 unit: str) -> None:
        super().__init__()
        self._levels = levels
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        header = QLabel(
            f"{title} <span style='color:{theme.GREEN};font-weight:bold'>[REAL]</span>"
            f" <span style='color:{theme.MUTED}'>— {unit}</span>"
        )
        header.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(header)

        self.plot = pg.PlotWidget()
        self.plot.setMenuEnabled(False)
        self.plot.setLabel("bottom", "Tempo (amostras →)")
        self.plot.getAxis("left").setWidth(150)
        self.img = pg.ImageItem()
        self.plot.addItem(self.img)
        cmap = pg.colormap.get(cmap_name)
        self.img.setColorMap(cmap)
        bar = pg.ColorBarItem(values=levels, colorMap=cmap)
        bar.setImageItem(self.img, insert_in=self.plot.getPlotItem())
        lay.addWidget(self.plot)

    def set_matrix(self, mat: np.ndarray, ylabels: list[str]) -> None:
        self.img.setImage(mat, levels=self._levels, autoLevels=False)
        ticks = [(i + 0.5, name) for i, name in enumerate(ylabels)]
        self.plot.getAxis("left").setTicks([ticks])
        self.plot.setYRange(0, max(len(ylabels), 1))


class HeatmapPanel(QWidget):
    """Aba com os mapas de calor de intensidade e de movimento."""

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        note = QLabel(
            "Mapas de calor reais do RSSI medido. O mapa de <b>movimento</b> "
            "destaca atividade física no ambiente (cores quentes = maior variação "
            "do sinal). <i>Imagem espacial através de paredes (RF-Capture/MIT) "
            "exigiria radar e CSI — não reproduzível só com RSSI.</i>"
        )
        note.setTextFormat(Qt.TextFormat.RichText)
        note.setWordWrap(True)
        root.addWidget(note)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.hm_rssi = _HeatmapView(
            "Intensidade do sinal (RSSI) por rede", "inferno", (-95, -30), "dBm"
        )
        self.hm_motion = _HeatmapView(
            "Movimento / atividade (variação do RSSI) por rede", "viridis", (0, 10), "Δ dBm"
        )
        splitter.addWidget(self.hm_rssi)
        splitter.addWidget(self.hm_motion)
        splitter.setSizes([360, 360])
        root.addWidget(splitter)

        self._frames: deque[dict[str, float]] = deque(maxlen=_MAX_COLS)
        self._ssid: dict[str, str] = {}

    def update_frame(self, samples: list[WifiSample]) -> None:
        """Adiciona a varredura atual e redesenha os mapas de calor."""
        if not samples:
            return
        for s in samples:
            self._ssid.setdefault(s.bssid, s.ssid)
        self._frames.append({s.bssid: float(s.rssi) for s in samples})

        # Linhas = redes mais fortes (média de RSSI ao longo do histórico).
        means: dict[str, list] = {}
        for frame in self._frames:
            for b, r in frame.items():
                means.setdefault(b, []).append(r)
        order = sorted(means, key=lambda b: np.mean(means[b]), reverse=True)[:_MAX_ROWS]
        if not order:
            return

        # Matriz redes × tempo (NaN onde a rede não apareceu naquele instante).
        n_t = len(self._frames)
        mat = np.full((len(order), n_t), np.nan)
        for c, frame in enumerate(self._frames):
            for r, b in enumerate(order):
                if b in frame:
                    mat[r, c] = frame[b]

        rssi_mat = np.where(np.isnan(mat), -95.0, mat)
        # Movimento = variação absoluta entre instantes consecutivos.
        motion = np.abs(np.diff(mat, axis=1)) if n_t > 1 else np.zeros((len(order), 1))
        motion = np.nan_to_num(motion, nan=0.0)
        if motion.shape[1] >= 1:  # alinha largura com o mapa de RSSI
            motion = np.hstack([motion[:, :1], motion])

        ylabels = [self._ssid.get(b, b)[:22] for b in order]
        self.hm_rssi.set_matrix(rssi_mat, ylabels)
        self.hm_motion.set_matrix(motion, ylabels)
