# Guia rápido das abas — WiFi Sensing

Visão geral do que cada aba do aplicativo faz.

---

## 📊 Dashboard
Visão geral em tempo real do ambiente Wi-Fi.
- **Cartões (KPIs):** nº de redes, banda dominante, alteração ambiental, estabilidade e sinal médio.
- **Tabela:** todas as redes detectadas (SSID, BSSID, RSSI colorido por qualidade, canal, frequência, banda).
- **Gráfico de RSSI:** intensidade das redes mais fortes ao longo do tempo (alinhado à direita = agora).
- **Ocupação de canais:** barras por banda mostrando os canais mais congestionados.
- **Controles:** Iniciar/Parar coleta, intervalo de amostragem, rede monitorada e exportar CSV.

## 🧍 Sensoriamento Ambiental
Nove métricas **reais** extraídas da variação do sinal (sem câmeras).
1. **Movimento** — intensidade do movimento (PCA multi-link).
2. **Presença / Atividade** — ambiente vazio, parado, movimento leve ou intenso.
3. **Eventos bruscos** — picos de variação (passagem de pessoa, porta).
4. **Periodicidade** — movimento rítmico detectado por FFT.
5. **Alteração ambiental** — probabilidade de mudança vs. linha de base.
6. **Estabilidade** — quão estável está o ambiente.
7. **Qualidade de sinal** — RSSI médio (mín/máx).
8. **Nº de redes** — contagem ao longo do tempo.
9. **Ocupação espectral** — distribuição por banda (2.4/5/6 GHz).

> Botão **🎯 Calibrar ambiente vazio:** com o local vazio, calibra os limiares ao seu espaço (mais preciso).

## 🗺️ Mapa de Calor
Dois mapas de calor (rede × tempo) da paisagem do sinal.
- **Intensidade (RSSI):** força de cada rede ao longo do tempo (cores quentes = sinal forte).
- **Movimento:** variação do sinal por rede (cores quentes = atividade física no ambiente).

## 🧠 Interpretação (IA)
Análise em linguagem natural dos resultados, gerada por um **LLM local** (Microsoft BitNet b1.58), 100% offline.
- Botão **Interpretar resultados:** resume o estado atual e gera um laudo técnico (congestionamento, interferência, qualidade, estabilidade e recomendações).
- A primeira geração demora alguns segundos (carrega o modelo); as seguintes são rápidas.

---

> **Privacidade:** todo o processamento — captura, análise e IA — roda localmente. Nenhum dado sai da máquina.
