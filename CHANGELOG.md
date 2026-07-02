# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
- `LICENSE` (MIT).
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.
- Templates de issue e pull request (`.github/`).
- `pre-commit` config (ruff + mypy antes do commit).
- Cobertura de testes (`pytest-cov`) e badge de coverage.
- CI multiplataforma (Linux, macOS, Windows) e multi-versão (Python 3.11/3.12).

### Alterado
- Dependências travadas com faixa compatível (`~=`) em vez de piso aberto (`>=`).

## [0.1.0] - 2026-06-14

### Adicionado
- Dashboard em tempo real (PySide6) com tabela de redes e gráficos de RSSI.
- Aquisição multiplataforma: `nmcli` (Linux), `netsh` (Windows), CoreWLAN (macOS),
  com fallback simulado.
- Persistência em SQLite (SQLAlchemy) e exportação CSV.
- Processamento de sinais: média móvel, Savitzky-Golay, FFT, extração de características.
- Classificador supervisionado/não supervisionado (Scikit-Learn).
- Detecção de alterações ambientais via fusão multi-link por PCA e SVR/LVR.
- Aba de interpretação por LLM local (Microsoft BitNet b1.58 2B4T via bitnet.cpp).
- Página de apresentação via GitHub Pages.
- Ícone próprio do aplicativo.
