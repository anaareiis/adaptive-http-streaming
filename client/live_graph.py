#!/usr/bin/env python3
"""Visualização ao vivo da dinâmica do player durante a simulação.

Uso:
    # Terminal 1 — inicia a simulação
    python3 client/main.py --segments 60 --policy hybrid

    # Terminal 2 — abre o gráfico ao vivo
    python3 client/live_graph.py --policy hybrid

    # Ou apontando direto para um CSV
    python3 client/live_graph.py --csv logs/hybrid/metrics_20260624_104044.csv
"""

import argparse
import glob
import os
import sys
from pathlib import Path

import matplotlib
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import pandas as pd

_QUALITY_NOMINAL_KBPS: dict[str, int] = {
    "240p": 200,
    "360p": 400,
    "480p": 600,
    "720p": 1000,
    "1080p": 1200,
}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _find_latest_csv(policy: str) -> Path | None:
    pattern = str(_PROJECT_ROOT / "logs" / policy / "metrics_*.csv")
    files = glob.glob(pattern)
    return Path(max(files, key=os.path.getmtime)) if files else None


def _read_csv(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(path)
        if df.empty or len(df) < 1:
            return None
        return df
    except Exception:
        return None


def _redraw(fig: plt.Figure, ax_buf: plt.Axes, ax_net: plt.Axes, df: pd.DataFrame) -> None:
    ax_buf.cla()
    ax_net.cla()

    t = list(range(1, len(df) + 1))
    buffer = df["buffer_level_s"].tolist()
    throughput = df["vazao_kbps"].tolist()
    qualities = df["quality"].fillna("240p").tolist()
    quality_kbps = [_QUALITY_NOMINAL_KBPS.get(str(q), 400) for q in qualities]

    # Buffer — eixo esquerdo
    ax_buf.fill_between(t, buffer, alpha=0.20, color="#9467bd")
    ax_buf.plot(t, buffer, color="#9467bd", linewidth=2.5, label="Nível do Buffer (s)")
    ax_buf.set_ylabel("Nível do Buffer (s)", color="#9467bd", fontsize=11)
    ax_buf.tick_params(axis="y", labelcolor="#9467bd")
    ax_buf.set_xlabel("Segmento", fontsize=11)
    ax_buf.grid(True, alpha=0.25)
    if t:
        ax_buf.set_xlim(0, max(t) + 1)

    # Throughput — eixo direito, pontilhado
    ax_net.plot(t, throughput, color="#1f77b4", linewidth=1.5,
                alpha=0.75, linestyle=":", label="Vazão Medida (kbps)")

    # Qualidade — degrau sólido verde
    ax_net.step(t, quality_kbps, where="post",
                color="#2ca02c", linewidth=2.5, label="Qualidade (kbps nominal)")

    present_kbps = sorted(set(quality_kbps))
    ax_net.set_yticks(present_kbps)
    ax_net.set_yticklabels([
        f"{next((q for q, k in _QUALITY_NOMINAL_KBPS.items() if k == b), str(b))} ({b} kbps)"
        for b in present_kbps
    ])
    ax_net.set_ylabel("Throughput / Qualidade (kbps)", color="#1f77b4", fontsize=11)
    ax_net.tick_params(axis="y", labelcolor="#1f77b4")

    # Rebuffering — linhas vermelhas
    rebuf_col = df.get("rebuffer_event", pd.Series([0] * len(df))).tolist()
    first_rebuf = True
    for i, r in enumerate(rebuf_col):
        if r:
            ax_buf.axvline(x=t[i], color="#d62728", linewidth=1.8, alpha=0.8,
                           label="Rebuffering" if first_rebuf else "")
            first_rebuf = False

    # Failover — linhas laranja tracejadas
    if "failover_total" in df.columns:
        fov = df["failover_total"].tolist()
        first_fov = True
        for i in range(1, len(fov)):
            if fov[i] > fov[i - 1]:
                ax_buf.axvline(x=t[i], color="#ff7f0e", linewidth=2.2,
                               linestyle="--", alpha=0.95,
                               label="Failover" if first_fov else "")
                first_fov = False

    # Legenda combinada
    lines_buf, labels_buf = ax_buf.get_legend_handles_labels()
    lines_net, labels_net = ax_net.get_legend_handles_labels()
    ax_buf.legend(lines_buf + lines_net, labels_buf + labels_net,
                  loc="upper left", fontsize=9)

    seg_atual = t[-1] if t else 0
    server = df["server_id"].iloc[-1] if "server_id" in df.columns else "?"
    qual_atual = qualities[-1] if qualities else "?"
    buf_atual = f"{buffer[-1]:.1f}" if buffer else "?"
    fig.suptitle(
        f"Dinâmica do Player — seg {seg_atual} | servidor: {server} | qualidade: {qual_atual} | buffer: {buf_atual} s",
        fontsize=12, fontweight="bold",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Gráfico ao vivo da simulação DASH")
    parser.add_argument(
        "--policy", default="hybrid",
        choices=["rate_based", "buffer_based", "hybrid"],
        help="Política a monitorar (busca o CSV mais recente em logs/<policy>/)",
    )
    parser.add_argument("--csv", help="Caminho direto para o CSV (opcional)")
    parser.add_argument(
        "--interval", type=int, default=1500,
        help="Intervalo de atualização em ms (padrão: 1500)",
    )
    args = parser.parse_args()

    csv_locked: Path | None = Path(args.csv) if args.csv else None

    fig, ax_buf = plt.subplots(figsize=(13, 6))
    ax_net = ax_buf.twinx()
    fig.suptitle("Aguardando dados da simulação...", fontsize=12, color="gray")
    plt.tight_layout()

    def animate(_frame: int) -> None:
        nonlocal csv_locked
        path = csv_locked or _find_latest_csv(args.policy)
        if path is None or not path.exists():
            return
        df = _read_csv(path)
        if df is None:
            return
        csv_locked = path
        _redraw(fig, ax_buf, ax_net, df)
        fig.tight_layout()

    _ani = animation.FuncAnimation(
        fig, animate, interval=args.interval, cache_frame_data=False
    )
    plt.show()


if __name__ == "__main__":
    main()
