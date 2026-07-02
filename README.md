# WiFi Sensing — Análise de Sinais Wi-Fi

[![CI](https://github.com/dheiver2/wifi-sensing/actions/workflows/ci.yml/badge.svg)](https://github.com/dheiver2/wifi-sensing/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

🌐 **Página de apresentação:** https://dheiver2.github.io/wifi-sensing/

Aplicação desktop em Python para **pesquisa e experimentação em sensoriamento
sem fio**. Escaneia redes Wi-Fi, constrói séries temporais da variação dos
sinais, aplica processamento de sinais e técnicas de IA para identificar
padrões de interferência e **detectar alterações no ambiente físico**
(movimentação, presença de obstáculos) a partir da propagação dos sinais.

> ⚠️ Projeto de finalidade científica/educacional. Use apenas em redes e
> ambientes para os quais você tenha autorização.

## Funcionalidades

- **Dashboard em tempo real** (PySide6) com tabela de redes e gráficos dinâmicos de RSSI.
- **Aquisição multiplataforma** (Linux `nmcli`, Windows `netsh`, macOS CoreWLAN) com fallback simulado.
- Coleta de **SSID, BSSID, RSSI, canal, frequência, largura de banda e timestamp**.
- **Persistência** em SQLite (via SQLAlchemy) e exportação **CSV**.
- **Processamento de sinais**: média móvel, filtragem de ruído (Savitzky-Golay), FFT, estatísticas e extração de características.
- **IA** (Scikit-Learn): classificação supervisionada (RandomForest) e não supervisionada (KMeans), com salvar/carregar modelos.
- **Interpretação por LLM local nativo**: aba que usa o **Microsoft BitNet b1.58 2B4T** (modelo ternário 1.58-bit) via **bitnet.cpp**, rodando 100% offline na máquina.
- **Detecção de alterações ambientais** com índice probabilístico e alertas visuais.
- **Indicador de estabilidade** do ambiente.

## Arquitetura

```
app/
├── ui/          # Interface PySide6 (janela principal, worker de varredura)
├── wifi/        # Aquisição de dados (scanners por SO + modelo de amostra)
├── ai/          # Classificador e detecção de mudanças ambientais
├── database/    # Persistência SQLite (SQLAlchemy) e exportação CSV
├── analytics/   # Processamento de sinais e extração de características
├── utils/       # Configuração e logging estruturado
└── main.py      # Ponto de entrada
```

## Instalação

Requer **Python 3.11+** (testado em CI nas versões 3.11 e 3.12, em Linux,
macOS e Windows).

```bash
git clone https://github.com/dheiver2/wifi-sensing.git
cd wifi-sensing
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Para desenvolver (testes, lint, type-check, pre-commit), veja o
[CONTRIBUTING.md](CONTRIBUTING.md).

### Pré-requisitos por sistema operacional

| SO | Requisito | Observação |
|---|---|---|
| Linux | NetworkManager (`nmcli`) instalado e ativo | maioria das distros já traz por padrão |
| Windows | Nenhum extra | usa `netsh wlan`, já incluso no Windows |
| macOS | Nenhum extra para RSSI/canal | nomes de rede (SSID/BSSID) exigem empacotar como `.app`, veja abaixo |

## Uso

A partir da raiz do projeto:

```bash
# Execução normal (tenta captura nativa do SO)
python -m app.main

# Modo simulado (dados sintéticos — não requer Wi-Fi real)
python -m app.main --simulate

# Intervalo de amostragem customizado e logs detalhados
python -m app.main --interval 2 --debug
```

Na interface: **▶ Iniciar** começa a coleta, **⏸ Parar** interrompe e
**⬇ Exportar CSV** salva o histórico. Selecione uma rede em *"Rede monitorada"*
para focar a detecção de alteração ambiental nela.

### Notas por sistema operacional

- **Linux**: requer NetworkManager (`nmcli`). Pode pedir permissão para `--rescan`.
- **Windows**: usa `netsh wlan` (disponível por padrão).
- **macOS**: usa **CoreWLAN** (pyobjc). A ferramenta `airport` foi removida no macOS 14.4+.

#### macOS — obtendo SSID/BSSID reais (importante)

No macOS, RSSI/canal/banda/largura são lidos diretamente do rádio, mas o
sistema **só revela SSID e BSSID a aplicações com permissão de Localização**.
Rodando via `python -m app.main` (linha de comando) os nomes vêm ocultos — o
app funciona, mas identifica as redes por banda+canal.

Para obter **nomes e MACs reais**, empacote como `.app` e autorize a Localização:

```bash
# Build em modo alias (rápido; usa a venv atual)
python setup.py py2app -A

# Abrir o app — na primeira execução, autorize "Localização"
open "dist/WiFi Sensing.app"
```

O scanner usa o cache do sistema (leitura instantânea) e uma thread em segundo
plano que dispara scans ativos a cada ~20 s para manter o RSSI atualizado — um
scan ativo completo leva ~15–25 s no macOS, então o cache garante um dashboard
fluido.

> Para começar com um banco limpo (sem dados de testes anteriores), apague a
> pasta `data/`.

## Privacidade e dados coletados

Todos os dados capturados (SSID, BSSID, RSSI, canal, frequência, timestamp)
são gravados **apenas localmente** no SQLite em `data/wifi_sensing.db` — o
projeto **não envia nada para nenhum servidor remoto**. A aba de interpretação
por LLM também roda 100% offline (BitNet local, sem chamadas de rede).
`data/` já está no `.gitignore`, então esses dados nunca são versionados.

## Solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| `FileNotFoundError: nmcli` (Linux) | NetworkManager não instalado/ativo | `sudo apt install network-manager` e garanta que o serviço está rodando |
| Nomes de rede aparecem como `<oculto>`/sintéticos no macOS | Sem permissão de Localização (CLI não recebe TCC) | Empacote como `.app` (`python setup.py py2app -A`) e autorize Localização na primeira execução |
| Dashboard sem nenhuma rede | Wi-Fi desligado ou sem redes próximas | Use `--simulate` para validar a interface com dados sintéticos |
| Erro ao carregar a aba de IA (BitNet) | Binário/modelo do bitnet.cpp não compilados/baixados | Siga a seção [LLM local nativo](#llm-local-nativo--bitnet-b158-2b4t) |
| `pip install` falha em `pyobjc-framework-CoreWLAN` fora do macOS | Pacote é exclusivo do macOS | Ignore — o marcador `sys_platform == "darwin"` já evita a instalação em Linux/Windows |

## LLM local nativo — BitNet b1.58 2B4T

A aba **Interpretação (IA)** usa o modelo ternário da Microsoft executado
nativamente via [bitnet.cpp](https://github.com/microsoft/BitNet) (back-end
Metal no macOS), sem nuvem. Instalação (uma vez), a partir da raiz do projeto:

```bash
# 1) Ferramentas de build (cmake) e clone do bitnet.cpp
pip install cmake huggingface_hub
git clone --recursive https://github.com/microsoft/BitNet.git bitnet

# 2) Compila o binário nativo (gera bitnet/build/bin/llama-server)
cd bitnet && PATH="$(python -c 'import cmake,os;print(os.path.dirname(cmake.__file__)+"/data/bin")'):$PATH" \
    python setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T -q i2_s ; cd ..
# (a conversão HF→GGUF pode falhar — é esperado; o binário ainda é compilado)

# 3) Baixa o GGUF pronto da Microsoft
python -c "from huggingface_hub import hf_hub_download as d; \
d(repo_id='microsoft/bitnet-b1.58-2B-4T-gguf', filename='ggml-model-i2_s.gguf', \
local_dir='bitnet/models/BitNet-b1.58-2B-4T')"
```

O app inicia o servidor BitNet sob demanda (na primeira interpretação) e o
encerra ao fechar. Caminhos esperados: binário em
`bitnet/build/bin/llama-server` e modelo em
`bitnet/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf`.

> Nota: o BitNet 2B é compacto e veloz (~60 tokens/s no Apple Silicon), porém
> tem qualidade limitada em português. Para análises mais ricas, troque o
> `MODEL_NAME`/GGUF em `app/ai/bitnet.py` por um modelo maior compatível.

## Treinamento de modelos (exemplo programático)

```python
import numpy as np
from app.ai.classifier import EnvironmentClassifier
from app.utils.config import MODELS_DIR

X = np.random.rand(100, 8)          # vetores de características
y = np.random.randint(0, 3, 100)    # rótulos dos estados ambientais

clf = EnvironmentClassifier(mode="supervised")
clf.train(X, y)
clf.save(MODELS_DIR / "ambiente.joblib")

# Mais tarde:
clf = EnvironmentClassifier.load(MODELS_DIR / "ambiente.joblib")
print(clf.predict(X[:5]))
```

## Métodos e referências

A detecção de movimento/presença implementa técnicas consolidadas de
sensoriamento Wi-Fi *device-free* (sem dispositivo no corpo), aplicadas ao RSSI
de múltiplos APs:

- **Filtragem Hampel + Kalman** do RSSI — remove outliers (spikes) e suaviza o
  nível do sinal com baixo atraso (melhor que média móvel).
- **Fusão multi-link por PCA** — o movimento humano induz variação
  *correlacionada* entre enlaces, que se concentra na 1ª componente principal,
  enquanto o ruído de multipath se espalha. A amplitude (√maior autovalor) mede
  o movimento; a **coerência** (participation ratio do autovetor) distingue um
  evento físico global (muitos APs juntos) de ruído de um único AP.
  Baseado em *PCA-Kalman* (Zhou et al., 2018).
- **SVR / LVR** (Short/Long-term Averaged Variance Ratio) — razões do
  coeficiente de variação do RSSI (janela curta vs. anterior / vs. linha de
  base), detecção robusta e *calibration-free*. Baseado em Gong et al. (2015).
- **Calibração de ambiente vazio** — limiares adaptativos (regra 3σ) medidos no
  local, em vez de limiar fixo.

Referências:
- Zhou et al., *PCA-Kalman: device-free indoor human behavior detection with
  commodity Wi-Fi*, EURASIP J. Wireless Comm. Netw., 2018.
- Gong et al., *WiFi-Based Real-Time Calibration-Free Passive Human Motion
  Detection*, Sensors, 2015 (PMC4721815).

## Boas práticas adotadas

Código orientado a objetos, type hints, docstrings, logging estruturado,
tratamento de exceções, separação modular e fallback resiliente de aquisição.

## Contribuindo

Contribuições são bem-vindas! Veja o [CONTRIBUTING.md](CONTRIBUTING.md) para
configurar o ambiente de desenvolvimento e o [Código de Conduta](CODE_OF_CONDUCT.md).
Mudanças notáveis ficam registradas no [CHANGELOG.md](CHANGELOG.md).

## Licença

Distribuído sob a licença [MIT](LICENSE). Uso livre, inclusive acadêmico e
comercial — respeitando o aviso de uso ético no topo deste documento.
