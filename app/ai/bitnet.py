"""Cliente nativo para o LLM Microsoft BitNet b1.58 2B4T via bitnet.cpp.

Executa o modelo ternário (1.58-bit) inteiramente na máquina, sem nuvem, usando
o servidor ``llama-server`` compilado do bitnet.cpp (back-end Metal no macOS).

O cliente gerencia o ciclo de vida do servidor: inicia-o sob demanda na primeira
geração e o encerra ao fechar a aplicação. Expõe a mesma interface usada pelo
painel de IA (``is_available``, ``list_models``, ``generate``, ``model``).
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request

from app.utils.config import BASE_DIR
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

_BITNET_DIR = BASE_DIR / "bitnet"
_SERVER_BIN = _BITNET_DIR / "build" / "bin" / "llama-server"
_MODEL_PATH = (
    _BITNET_DIR / "models" / "BitNet-b1.58-2B-4T" / "ggml-model-i2_s.gguf"
)
MODEL_NAME = "BitNet-b1.58-2B-4T"

SYSTEM_PROMPT = (
    "Você é um especialista em redes Wi-Fi e processamento de sinais. "
    "Analise os dados de varredura e escreva uma interpretação técnica clara em "
    "português do Brasil. Seja objetivo e use no máximo 6 parágrafos curtos. "
    "Aborde: (1) congestionamento de canais e sobreposição, (2) qualidade dos "
    "sinais (RSSI), (3) possível interferência, (4) avaliação da estabilidade e "
    "de alterações no ambiente físico, (5) recomendações práticas. "
    "Não invente dados além dos fornecidos."
)


class BitNetClient:
    """Cliente HTTP para o ``llama-server`` do bitnet.cpp (modelo BitNet)."""

    def __init__(self, host: str = "http://localhost", port: int = 8081,
                 threads: int = 4, ctx: int = 2048, timeout_s: float = 180.0) -> None:
        self.host = host
        self.port = port
        self.threads = threads
        self.ctx = ctx
        self.timeout_s = timeout_s
        self.model = MODEL_NAME
        self._proc: subprocess.Popen | None = None

    @property
    def base_url(self) -> str:
        return f"{self.host}:{self.port}"

    def is_available(self) -> bool:
        """Verifica se o binário e o modelo BitNet estão instalados."""
        return _SERVER_BIN.exists() and _MODEL_PATH.exists()

    def list_models(self) -> list[str]:
        """Retorna o modelo disponível (BitNet é dedicado a um modelo)."""
        return [MODEL_NAME] if self.is_available() else []

    # ------------------------------------------------------------- servidor
    def _server_healthy(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as r:
                return r.status == 200
        except Exception:  # noqa: BLE001
            return False

    def ensure_server(self) -> None:
        """Inicia o ``llama-server`` se ainda não estiver no ar."""
        if self._server_healthy():
            return
        if not self.is_available():
            raise RuntimeError(
                "BitNet não instalado. Compile o bitnet.cpp e baixe o GGUF "
                "(ggml-model-i2_s.gguf) em bitnet/models/BitNet-b1.58-2B-4T/."
            )
        logger.info("Iniciando servidor BitNet (%s)…", _SERVER_BIN)
        self._proc = subprocess.Popen(
            [
                str(_SERVER_BIN), "-m", str(_MODEL_PATH),
                "-c", str(self.ctx), "-t", str(self.threads),
                "--port", str(self.port),
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # Aguarda o modelo carregar (~poucos segundos).
        deadline = time.time() + 60
        while time.time() < deadline:
            if self._server_healthy():
                logger.info("Servidor BitNet pronto na porta %d.", self.port)
                return
            if self._proc.poll() is not None:
                raise RuntimeError("O servidor BitNet encerrou inesperadamente.")
            time.sleep(1.0)
        raise RuntimeError("Tempo esgotado ao iniciar o servidor BitNet.")

    def close(self) -> None:
        """Encerra o servidor BitNet, se iniciado por este cliente."""
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    # ------------------------------------------------------------- geração
    def generate(self, prompt: str, system: str | None = None) -> str:
        """Gera texto a partir do prompt usando o modelo BitNet local.

        Args:
            prompt: Entrada do usuário (resumo da análise).
            system: Instrução de sistema (papel do modelo).

        Returns:
            O texto gerado pelo modelo.

        Raises:
            RuntimeError: Se o servidor não puder ser iniciado/contatado.
        """
        self.ensure_server()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = json.dumps(
            {"messages": messages, "max_tokens": 512, "temperature": 0.3}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions", data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read())
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Falha ao contatar o BitNet: {exc}") from exc
        return data["choices"][0]["message"]["content"].strip()
