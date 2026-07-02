"""Aba de interpretação por LLM local nativo (BitNet b1.58 via bitnet.cpp)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ai.bitnet import SYSTEM_PROMPT, BitNetClient
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class _LLMWorker(QObject):
    """Executa a chamada ao LLM fora da thread da UI."""

    done = Signal(str)
    failed = Signal(str)

    def __init__(self, client: BitNetClient, prompt: str) -> None:
        super().__init__()
        self._client = client
        self._prompt = prompt

    @Slot()
    def run(self) -> None:
        try:
            text = self._client.generate(self._prompt, system=SYSTEM_PROMPT)
            self.done.emit(text or "(resposta vazia)")
        except Exception as exc:
            logger.exception("Falha na geração do LLM.")
            self.failed.emit(str(exc))


class LLMPanel(QWidget):
    """Painel que gera e exibe a interpretação dos resultados via LLM local."""

    # Solicita ao MainWindow o resumo textual da análise corrente.
    summary_requested = Signal()

    def __init__(self, client: BitNetClient) -> None:
        super().__init__()
        self._client = client
        self._thread: QThread | None = None
        self._worker: _LLMWorker | None = None
        self._build_ui()
        self._refresh_models()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.btn_generate = QPushButton("🧠 Interpretar resultados")
        top.addWidget(self.btn_generate)
        top.addWidget(QLabel("Modelo:"))
        self.combo_model = QComboBox()
        top.addWidget(self.combo_model)
        self.lbl_status = QLabel()
        top.addWidget(self.lbl_status)
        top.addStretch()
        root.addLayout(top)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(
            "Clique em 'Interpretar resultados' para gerar uma análise em "
            "linguagem natural dos sinais Wi-Fi usando o LLM local BitNet b1.58 2B4T (nativo)."
        )
        root.addWidget(self.output)

        self.btn_generate.clicked.connect(self.summary_requested.emit)
        self.combo_model.currentTextChanged.connect(self._on_model_changed)

    def _refresh_models(self) -> None:
        if not self._client.is_available():
            self.lbl_status.setText("⚠ BitNet não instalado (ver README).")
            self.btn_generate.setEnabled(False)
            return
        try:
            models = self._client.list_models()
        except Exception:
            models = []
        self.combo_model.clear()
        self.combo_model.addItems(models or [self._client.model])
        if self._client.model in models:
            self.combo_model.setCurrentText(self._client.model)
        self.lbl_status.setText("✓ BitNet pronto (modelo carrega na 1ª geração).")

    def _on_model_changed(self, name: str) -> None:
        if name:
            self._client.model = name

    def generate(self, prompt: str) -> None:
        """Inicia a geração da interpretação a partir do resumo informado."""
        if self._thread is not None:
            return  # já há uma geração em andamento
        self.output.setPlainText("Gerando interpretação… (pode levar alguns segundos)")
        self.btn_generate.setEnabled(False)
        self.lbl_status.setText("⏳ Processando…")

        self._thread = QThread()
        self._worker = _LLMWorker(self._client, prompt)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    @Slot(str)
    def _on_done(self, text: str) -> None:
        self.output.setPlainText(text)
        self.lbl_status.setText("✓ Concluído.")
        self._cleanup()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.output.setPlainText(f"Erro ao gerar interpretação:\n{message}")
        self.lbl_status.setText("⚠ Erro.")
        self._cleanup()

    def _cleanup(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
        self._thread = None
        self._worker = None
        self.btn_generate.setEnabled(True)
