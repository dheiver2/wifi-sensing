"""Janela principal da aplicação WiFi Sensing.

Organizada em abas: um Dashboard em tempo real (tabela + gráficos) e uma aba de
interpretação por LLM open-source local. Inclui detecção de alteração ambiental
e indicador de estabilidade.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ai.bitnet import BitNetClient
from app.ai.change_detection import ChangeDetector, ChangeResult
from app.ai.human_sensing import HumanSensingEngine
from app.analytics.signal_processing import moving_average
from app.analytics.summary import build_summary
from app.database.repository import MeasurementRepository
from app.ui import theme
from app.ui.heatmap_panel import HeatmapPanel
from app.ui.human_panel import HumanSensingPanel
from app.ui.llm_panel import LLMPanel
from app.ui.scan_worker import ScanController
from app.utils.config import AppConfig
from app.utils.logging_config import get_logger
from app.wifi.models import WifiSample
from app.wifi.scanner import WifiScanner

logger = get_logger(__name__)

_BAND_COLOR = theme.BAND_COLOR
_SERIES_COLORS = theme.SERIES


class _Card(QFrame):
    """Cartão de KPI: título pequeno em cima, valor grande embaixo."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        self.value = QLabel("—")
        self.value.setObjectName("cardValue")
        self.sub = QLabel("")
        self.sub.setObjectName("muted")
        lay.addWidget(t)
        lay.addWidget(self.value)
        lay.addWidget(self.sub)

    def set(self, value: str, sub: str = "", color: str | None = None) -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        if color:
            self.value.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {color};")


class MainWindow(QMainWindow):
    """Janela principal com abas de Dashboard e Interpretação (IA)."""

    def __init__(
        self,
        scanner: WifiScanner,
        repository: MeasurementRepository,
        config: AppConfig,
        llm_client: BitNetClient | None = None,
    ) -> None:
        super().__init__()
        self._scanner = scanner
        self._repo = repository
        self._config = config

        self._history: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=config.history_points)
        )
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._ssid_by_bssid: dict[str, str] = {}
        self._last_samples: list[WifiSample] = []
        self._last_change: ChangeResult | None = None
        self._top_n = 8

        self._detector = ChangeDetector(threshold=config.change_threshold)
        self._human = HumanSensingEngine(
            sample_rate_hz=1.0 / max(config.scan_interval_s, 0.1)
        )
        self._controller = ScanController(scanner, config.scan_interval_s)
        self._llm = llm_client or BitNetClient()

        self._build_ui()
        self._connect_signals()
        self.setWindowTitle("WiFi Sensing — Análise de Sinais Wi-Fi")
        self.resize(1200, 760)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_dashboard_tab(), "📊 Dashboard")
        self.human_panel = HumanSensingPanel()
        self.tabs.addTab(self.human_panel, "🧍 Sensoriamento Ambiental")
        self.heatmap_panel = HeatmapPanel()
        self.tabs.addTab(self.heatmap_panel, "🗺️ Mapa de Calor")
        self.llm_panel = LLMPanel(self._llm)
        self.tabs.addTab(self.llm_panel, "🧠 Interpretação (IA)")
        self.setCentralWidget(self.tabs)
        self.setStatusBar(self.statusBar())
        self._build_status_widgets()

    def _build_dashboard_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)
        root.addLayout(self._build_toolbar())
        root.addLayout(self._build_kpis())

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._build_table(), stretch=2)
        body.addWidget(self._build_plots(), stretch=3)
        root.addLayout(body)
        return page

    def _build_kpis(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(14)
        self.kpi_nets = _Card("Redes detectadas")
        self.kpi_band = _Card("Banda dominante")
        self.kpi_change = _Card("Alteração ambiental")
        self.kpi_stab = _Card("Estabilidade")
        self.kpi_quality = _Card("Sinal médio")
        for c in (self.kpi_nets, self.kpi_band, self.kpi_change,
                  self.kpi_stab, self.kpi_quality):
            row.addWidget(c)
        return row

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        self.btn_start = QPushButton("▶ Iniciar")
        self.btn_start.setObjectName("primary")
        self.btn_stop = QPushButton("⏸ Parar")
        self.btn_export = QPushButton("⬇ Exportar CSV")
        self.btn_stop.setEnabled(False)
        bar.addWidget(self.btn_start)
        bar.addWidget(self.btn_stop)
        bar.addWidget(self.btn_export)

        bar.addSpacing(16)
        bar.addWidget(QLabel("Intervalo (s):"))
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.5, 60.0)
        self.spin_interval.setSingleStep(0.5)
        self.spin_interval.setValue(self._config.scan_interval_s)
        bar.addWidget(self.spin_interval)

        bar.addSpacing(16)
        bar.addWidget(QLabel("Rede monitorada:"))
        self.combo_focus = QComboBox()
        self.combo_focus.setMinimumWidth(220)
        self.combo_focus.addItem("(todas)")
        bar.addWidget(self.combo_focus)

        bar.addSpacing(16)
        bar.addWidget(QLabel("Mostrar top:"))
        self.spin_top = QSpinBox()
        self.spin_top.setRange(1, 20)
        self.spin_top.setValue(self._top_n)
        bar.addWidget(self.spin_top)

        bar.addStretch()
        return bar

    def _build_table(self) -> QWidget:
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["SSID", "BSSID", "RSSI", "Canal", "Freq (MHz)", "Banda"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        return self.table

    def _build_plots(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Série temporal de RSSI (apenas top-N para legibilidade).
        self.plot = pg.PlotWidget(title="Intensidade do sinal (RSSI) — redes mais fortes")
        self.plot.setLabel("left", "RSSI", units="dBm")
        self.plot.setLabel("bottom", "Amostras (mais recente à direita)")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setYRange(-100, -20)
        self.legend = self.plot.addLegend(offset=(-10, 10), labelTextSize="8pt")
        splitter.addWidget(self.plot)

        # Ocupação de canais (barras).
        self.chan_plot = pg.PlotWidget(title="Ocupação de canais (nº de redes)")
        self.chan_plot.setLabel("left", "Redes")
        self.chan_plot.setLabel("bottom", "Canal")
        self.chan_plot.showGrid(y=True, alpha=0.3)
        self._chan_bars: pg.BarGraphItem | None = None
        splitter.addWidget(self.chan_plot)

        splitter.setSizes([460, 240])
        return splitter

    def _build_status_widgets(self) -> None:
        sb = self.statusBar()
        self.lbl_status = QLabel("Pronto.")
        sb.addWidget(self.lbl_status, 1)

    def _connect_signals(self) -> None:
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_export.clicked.connect(self._on_export)
        self.spin_interval.valueChanged.connect(
            lambda v: self._controller.worker.set_interval(v)
        )
        self.spin_top.valueChanged.connect(self._on_top_changed)
        self._controller.worker.samples_ready.connect(self._on_samples)
        self._controller.worker.error.connect(self._on_error)
        self.llm_panel.summary_requested.connect(self._on_interpret)
        self.human_panel.calibrate_requested.connect(self._on_calibrate)

    @Slot()
    def _on_calibrate(self) -> None:
        """Coleta a linha de base do ambiente vazio por alguns segundos."""
        from PySide6.QtCore import QTimer

        self._human.start_calibration()
        self.human_panel.btn_calibrate.setEnabled(False)
        self.human_panel.btn_calibrate.setText("🎯 Calibrando… saia do ambiente")
        self.lbl_status.setText("Calibrando ambiente vazio (6s)…")

        def _finish() -> None:
            self._human.finish_calibration()
            self.human_panel.btn_calibrate.setEnabled(True)
            self.human_panel.btn_calibrate.setText("🎯 Recalibrar ambiente vazio")
            self.lbl_status.setText("Calibração concluída.")

        QTimer.singleShot(6000, _finish)

    # ------------------------------------------------------------- Handlers
    @Slot()
    def _on_start(self) -> None:
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("Coletando…")
        self._controller.start()

    @Slot()
    def _on_stop(self) -> None:
        self._controller.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Parado.")

    @Slot(int)
    def _on_top_changed(self, value: int) -> None:
        self._top_n = value
        if self._last_samples:
            self._update_plot(self._last_samples)

    @Slot(list)
    def _on_samples(self, samples: list[WifiSample]) -> None:
        if not samples:
            return
        self._last_samples = samples
        self._repo.add_samples(samples)
        self._update_table(samples)
        self._update_focus_combo(samples)
        self._update_plot(samples)
        self._update_channel_plot(samples)
        self._update_change_indicator(samples)
        self.human_panel.update_state(
            self._human.update(self._anchor_rssi(samples), samples)
        )
        self.heatmap_panel.update_frame(samples)
        self._update_kpis(samples)
        self.lbl_status.setText(
            f"Última coleta {datetime.now():%H:%M:%S}"
        )

    def _update_kpis(self, samples: list[WifiSample]) -> None:
        from collections import Counter

        self.kpi_nets.set(str(len(samples)))
        bands = Counter(WifiSample.band(s.frequency_mhz) for s in samples)
        if bands:
            band, n = bands.most_common(1)[0]
            self.kpi_band.set(band, f"{n} redes", _BAND_COLOR.get(band))
        rssis = [s.rssi for s in samples]
        if rssis:
            mean = sum(rssis) / len(rssis)
            self.kpi_quality.set(f"{mean:.0f} dBm", f"min {min(rssis)} / max {max(rssis)}")

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self.lbl_status.setText(f"Erro: {message}")

    @Slot()
    def _on_export(self) -> None:
        default = str(self._config.db_path.parent / "exports" / "medicoes.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar medições", default, "CSV (*.csv)"
        )
        if not path:
            return
        n = self._repo.export_csv(Path(path))
        QMessageBox.information(self, "Exportação", f"{n} medições exportadas.")

    @Slot()
    def _on_interpret(self) -> None:
        """Monta o resumo da análise e dispara a interpretação por LLM."""
        if not self._last_samples:
            QMessageBox.information(
                self, "Sem dados", "Inicie a coleta antes de interpretar."
            )
            return
        # Usa o último resultado já calculado na varredura; NÃO chama update()
        # aqui para não injetar uma amostra duplicada no detector.
        change_prob = self._last_change.probability if self._last_change else 0.0
        prompt = build_summary(
            self._last_samples,
            self._history,
            change_prob,
            self._detector.stability_index(),
            self.combo_focus.currentText(),
        )
        self.llm_panel.generate(prompt)

    # -------------------------------------------------------------- Updates
    def _update_table(self, samples: list[WifiSample]) -> None:
        self.table.setSortingEnabled(False)
        ordered = sorted(samples, key=lambda s: s.rssi, reverse=True)
        self.table.setRowCount(len(ordered))
        for row, s in enumerate(ordered):
            values = [
                s.ssid, s.bssid, str(s.rssi), str(s.channel),
                f"{s.frequency_mhz:.0f}", WifiSample.band(s.frequency_mhz),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 2:
                    item.setForeground(self._rssi_color(s.rssi))
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)

    @staticmethod
    def _rssi_color(rssi: int) -> QColor:
        if rssi >= -60:
            return QColor("#2ca02c")
        if rssi >= -75:
            return QColor("#E9A412")
        return QColor("#d62728")

    def _update_focus_combo(self, samples: list[WifiSample]) -> None:
        for s in samples:
            if s.bssid not in self._ssid_by_bssid:
                self._ssid_by_bssid[s.bssid] = s.ssid
                self.combo_focus.addItem(f"{s.ssid} ({s.bssid})", s.bssid)

    def _update_plot(self, samples: list[WifiSample]) -> None:
        for s in samples:
            self._history[s.bssid].append(float(s.rssi))

        focus = self.combo_focus.currentData()
        if focus:
            shown = [focus] if focus in self._history else []
        else:
            # Top-N pela última leitura de RSSI.
            latest = sorted(samples, key=lambda s: s.rssi, reverse=True)
            shown = [s.bssid for s in latest[: self._top_n]]

        shown_set = set(shown)
        maxlen = max((len(self._history[b]) for b in shown), default=0)

        # Esconde curvas que saíram do conjunto exibido.
        for bssid, curve in self._curves.items():
            if bssid not in shown_set:
                curve.setData([], [])

        for idx, bssid in enumerate(shown):
            series = np.array(self._history[bssid], dtype=float)
            smoothed = moving_average(series, self._config.moving_average_window)
            # Alinha a leitura mais recente à direita (eixo comum).
            x = np.arange(maxlen - smoothed.size, maxlen)
            if bssid not in self._curves:
                color = _SERIES_COLORS[idx % len(_SERIES_COLORS)]
                name = self._ssid_by_bssid.get(bssid, bssid)
                self._curves[bssid] = self.plot.plot(
                    pen=pg.mkPen(color, width=2), name=name
                )
            self._curves[bssid].setData(x, smoothed)

    def _update_channel_plot(self, samples: list[WifiSample]) -> None:
        counts = Counter(s.channel for s in samples)
        band_of = {s.channel: WifiSample.band(s.frequency_mhz) for s in samples}
        channels = sorted(counts)
        if not channels:
            return
        x = list(range(len(channels)))
        heights = [counts[c] for c in channels]
        brushes = [_BAND_COLOR.get(band_of[c], "#999999") for c in channels]

        if self._chan_bars is not None:
            self.chan_plot.removeItem(self._chan_bars)
        self._chan_bars = pg.BarGraphItem(
            x=x, height=heights, width=0.7, brushes=brushes
        )
        self.chan_plot.addItem(self._chan_bars)
        ax = self.chan_plot.getAxis("bottom")
        ax.setTicks([[(i, str(c)) for i, c in enumerate(channels)]])

    def _anchor_rssi(self, samples: list[WifiSample]) -> float:
        """Valor de RSSI estável para alimentar a detecção de mudança.

        Com uma rede monitorada, usa o RSSI dela; caso contrário, usa a mediana
        de todas as redes — métrica robusta que não depende da ordem do scan.
        """
        focus = self.combo_focus.currentData()
        if focus:
            target = next((s for s in samples if s.bssid == focus), None)
            if target is not None:
                return float(target.rssi)
        return float(np.median([s.rssi for s in samples]))

    def _update_change_indicator(self, samples: list[WifiSample]) -> None:
        result = self._detector.update(self._anchor_rssi(samples))
        self._last_change = result
        pct = int(result.probability * 100)
        color = theme.RED if result.is_alert else theme.GREEN
        self.kpi_change.set(
            f"{pct}%", "⚠ alteração!" if result.is_alert else "ambiente estável", color
        )
        stability = self._detector.stability_index()
        scol = theme.GREEN if stability > 0.6 else theme.YELLOW if stability > 0.3 else theme.RED
        self.kpi_stab.set(f"{stability * 100:.0f}%", color=scol)

    # ------------------------------------------------------------- Lifecycle
    def closeEvent(self, event) -> None:
        self._controller.stop()
        for obj in (self._scanner, self._llm):
            close = getattr(obj, "close", None)
            if callable(close):
                close()
        super().closeEvent(event)
