"""Worker de aquisição Wi-Fi executado em thread separada da UI."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from app.utils.logging_config import get_logger
from app.wifi.models import WifiSample
from app.wifi.scanner import WifiScanner

logger = get_logger(__name__)


class ScanWorker(QObject):
    """Executa varreduras periódicas sem bloquear a interface.

    Signals:
        samples_ready: Emitido a cada varredura com a lista de amostras.
        error: Emitido em caso de falha na captura.
    """

    samples_ready = Signal(list)
    error = Signal(str)

    def __init__(self, scanner: WifiScanner, interval_s: float) -> None:
        super().__init__()
        self._scanner = scanner
        self._interval_ms = int(interval_s * 1000)
        self._timer: QTimer | None = None
        self._running = False

    @Slot()
    def start(self) -> None:
        """Inicia o laço de varredura (chamado dentro da thread)."""
        self._running = True
        self._timer = QTimer()
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._do_scan)
        self._timer.start()
        self._do_scan()  # primeira varredura imediata
        logger.info("ScanWorker iniciado (intervalo=%dms).", self._interval_ms)

    @Slot()
    def stop(self) -> None:
        """Interrompe o laço de varredura."""
        self._running = False
        if self._timer is not None:
            self._timer.stop()
        logger.info("ScanWorker parado.")

    def set_interval(self, interval_s: float) -> None:
        """Atualiza o intervalo de amostragem em tempo de execução."""
        self._interval_ms = int(interval_s * 1000)
        if self._timer is not None:
            self._timer.setInterval(self._interval_ms)

    @Slot()
    def _do_scan(self) -> None:
        if not self._running:
            return
        try:
            samples: list[WifiSample] = self._scanner.scan()
            self.samples_ready.emit(samples)
        except Exception as exc:
            logger.exception("Falha na varredura.")
            self.error.emit(str(exc))


class ScanController:
    """Gerencia o ciclo de vida da thread de varredura."""

    def __init__(self, scanner: WifiScanner, interval_s: float) -> None:
        self.thread = QThread()
        self.worker = ScanWorker(scanner, interval_s)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start)

    def start(self) -> None:
        """Inicia a thread de varredura."""
        self.thread.start()

    def stop(self) -> None:
        """Para o worker e encerra a thread com segurança."""
        self.worker.stop()
        self.thread.quit()
        self.thread.wait(2000)
