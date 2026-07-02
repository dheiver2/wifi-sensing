# Contribuindo com o WiFi Sensing

Obrigado pelo interesse em contribuir! Este guia cobre o essencial para rodar,
testar e propor mudanças no projeto.

## Configurando o ambiente

```bash
git clone https://github.com/dheiver2/wifi-sensing.git
cd wifi-sensing
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pre-commit install                 # opcional, mas recomendado
```

Requer Python 3.11+.

## Rodando os testes e checagens de qualidade

```bash
pytest              # testes unitários
ruff check app tests   # lint
mypy                 # checagem de tipos
```

O CI (`.github/workflows/ci.yml`) roda essas três checagens em toda `push` e
`pull request`, em Linux, macOS e Windows. PRs só são aceitos se todas
passarem.

## Padrões de código

- Type hints em todas as funções públicas (`from __future__ import annotations`).
- Docstrings em português, no estilo já usado no projeto.
- Sem `print()` solto — use o logger (`app.utils.logging_config.get_logger`).
- Sem `except Exception` genérico sem log/reemissão — siga o padrão de
  `app/ui/scan_worker.py`.
- Novas dependências devem ser adicionadas em `requirements.txt` (runtime) ou
  `requirements-dev.txt` (apenas desenvolvimento/testes), com versão travada.

## Enviando uma mudança

1. Abra uma *issue* descrevendo o problema ou a proposta antes de investir
   tempo em uma mudança grande — evita retrabalho.
2. Crie um fork e um branch descritivo (`fix/nome-do-bug`, `feat/nome-da-feature`).
3. Adicione testes para qualquer comportamento novo ou corrigido.
4. Garanta que `pytest`, `ruff check` e `mypy` passam localmente.
5. Abra o Pull Request descrevendo o que mudou e por quê.

## Áreas sensíveis

- **Scanners de Wi-Fi** (`app/wifi/`): mudanças aqui afetam captura real de
  rádio em três sistemas operacionais diferentes — teste manualmente no SO que
  você tiver disponível e descreva no PR quais plataformas foram validadas.
- **Uso ético**: este projeto só deve escanear redes e ambientes para os quais
  o usuário tenha autorização. Não aceitamos contribuições que facilitem
  vigilância não autorizada ou coleta de dados de terceiros sem consentimento.
