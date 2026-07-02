"""Geração de resumos textuais do estado da análise para o LLM.

Converte as amostras e métricas em um texto estruturado e compacto, adequado
como prompt para o modelo de linguagem interpretar.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

import numpy as np

from app.analytics.signal_processing import statistical_summary
from app.wifi.models import WifiSample


def build_summary(
    samples: Sequence[WifiSample],
    histories: Mapping[str, Iterable[float]],
    change_probability: float,
    stability: float,
    focus_label: str = "(todas)",
) -> str:
    """Monta um resumo textual do estado atual da varredura.

    Args:
        samples: Amostras da última varredura.
        histories: Mapa BSSID -> série temporal de RSSI acumulada.
        change_probability: Índice probabilístico de alteração ambiental [0, 1].
        stability: Índice de estabilidade [0, 1].
        focus_label: Rótulo da rede monitorada.

    Returns:
        Texto pronto para ser enviado ao LLM.
    """
    if not samples:
        return "Nenhuma rede detectada na última varredura."

    rssis = np.array([s.rssi for s in samples], dtype=float)
    bands = Counter(WifiSample.band(s.frequency_mhz) for s in samples)
    channels = Counter(s.channel for s in samples)
    top = sorted(samples, key=lambda s: s.rssi, reverse=True)[:8]

    lines: list[str] = []
    lines.append(f"Total de redes detectadas: {len(samples)}.")
    lines.append(
        "Distribuição por banda: "
        + ", ".join(f"{b}: {n}" for b, n in bands.most_common())
        + "."
    )

    congested = [f"canal {ch} ({n} redes)" for ch, n in channels.most_common(5) if n > 1]
    if congested:
        lines.append("Canais mais ocupados: " + ", ".join(congested) + ".")
    else:
        lines.append("Não há canais com sobreposição relevante.")

    stats = statistical_summary(rssis)
    lines.append(
        f"RSSI (dBm): médio {stats['mean']:.0f}, mínimo {stats['min']:.0f}, "
        f"máximo {stats['max']:.0f}, desvio {stats['std']:.1f}."
    )

    lines.append("Redes mais fortes:")
    for s in top:
        band = WifiSample.band(s.frequency_mhz)
        bw = f"{s.bandwidth_mhz:.0f}MHz" if s.bandwidth_mhz else "?"
        lines.append(
            f"  - {s.ssid}: {s.rssi} dBm, canal {s.channel} ({band}, {bw})"
        )

    # Variação temporal das redes com histórico suficiente.
    volatil = []
    for bssid, series in histories.items():
        arr = np.asarray(list(series), dtype=float)
        if arr.size >= 5:
            volatil.append((bssid, float(np.std(arr))))
    if volatil:
        volatil.sort(key=lambda x: x[1], reverse=True)
        worst = volatil[0]
        lines.append(
            f"Maior variabilidade temporal de RSSI: desvio padrão de "
            f"{worst[1]:.1f} dBm (rede {worst[0]})."
        )

    lines.append(
        f"Rede monitorada: {focus_label}. "
        f"Índice de alteração ambiental: {change_probability * 100:.0f}%. "
        f"Índice de estabilidade: {stability * 100:.0f}%."
    )
    return "\n".join(lines)
