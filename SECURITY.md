# Política de Segurança

## Versões suportadas

Este é um projeto de pesquisa/educacional em estágio inicial (v0.x). Apenas a
versão mais recente da branch `main` recebe correções de segurança.

## Reportando uma vulnerabilidade

Se você encontrar uma vulnerabilidade de segurança (por exemplo, execução de
comando arbitrário via entrada não sanitizada, exposição de dados coletados,
ou uso indevido dos scanners de Wi-Fi), por favor **não abra uma issue pública**.

Em vez disso, reporte de forma privada por e-mail para **dheiver.santos@gmail.com**
com:

- Descrição do problema e impacto potencial.
- Passos para reproduzir (se aplicável).
- Versão/commit afetado.

Você pode esperar uma resposta inicial em até 7 dias. Após a correção, o
crédito pelo reporte será dado (a menos que você prefira anonimato).

## Escopo

O WiFi Sensing captura metadados de rádio (SSID, BSSID, RSSI, canal) de redes
ao alcance do dispositivo. Todos os dados são armazenados **apenas localmente**
em SQLite — o projeto não envia dados a nenhum servidor remoto. Vulnerabilidades
relacionadas a esse escopo (ex.: escalonamento de privilégios via subprocess,
injeção via saída de `nmcli`/`netsh`) são bem-vindas como reporte.

Uso indevido do software para escanear redes sem autorização é uma questão de
**uso**, não de segurança do código, e está fora do escopo deste documento —
veja o aviso de uso ético no [README](README.md).
