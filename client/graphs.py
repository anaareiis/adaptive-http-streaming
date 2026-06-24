"""Generate graphs from adaptive streaming CSV metrics."""

import argparse
import csv
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Union

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import os
import pandas as pd


GRAPH_FILENAMES = {
    "throughput_timeline": "throughput_timeline.png",
    "quality_timeline": "quality_timeline.png",
    "buffer_level": "buffer_level.png",
    "quality_distribution": "quality_distribution.png",
    "throughput_histogram": "throughput_histogram.png",
    "jitter_ewma": "jitter_ewma.png",
    "player_dynamics": "player_dynamics.png",
}

TIME_ALIASES = (
    "time_s",
    "time",
    "elapsed_time",
    "elapsed_time_s",
    "timestamp",
    "datetime",
)
THROUGHPUT_ALIASES = (
    "throughput_kbps",
    "throughput",
    "vazao_kbps",
    "vazao",
    "bandwidth_kbps",
)
QUALITY_ALIASES = (
    "selected_quality",
    "quality",
    "qualidade",
    "quality_name",
    "representation",
)

BUFFER_ALIASES = (
    "buffer_level",
    "buffer_level_s",
    "buffer_seconds",
    "buffer_s",
    "buffer",
    "current_buffer",
    "buffer_level_secs",
)
FAILOVER_ALIASES = (
    "failover_total",
    "failover_count",
    "failovers",
)
REBUFFER_ALIASES = (
    "rebuffer",
    "is_rebuffering",
    "rebuffering",
    "rebuffer_event",
    "stall",
    "stalled",
    "rebuffering_occurred",
)
REBUFFER_COUNT_ALIASES = (
    "rebuffer_count",
    "rebuffers",
    "rebuffer_number",
)
JITTER_INSTANT_ALIASES = (
    'jitter_network_ms', 
    'jitter_instant', 
    'jitter_raw',
)
JITTER_EWMA_ALIASES = (
    'jitter_ewma_ms', 
    'jitter', 
    'jitter_filtered',
)

@dataclass
class StreamingMetrics:
    """Normalized streaming metrics loaded from CSV."""

    time_s: List[float]
    throughput_kbps: List[float]
    qualities: List[str]
    buffer_level: List[float]
    rebuffer_events: List[bool]
    jitter_network_ms: Optional[List[float]] = None
    jitter_ewma_ms: Optional[List[float]] = None
    failover_times: Optional[List[float]] = None


def load_csv_data(csv_path: Union[str, Path]) -> StreamingMetrics:
    """
    Load and normalize streaming metrics from a CSV file.

    The loader accepts common aliases for time, throughput, quality, buffer,
    and rebuffer columns. If no time column exists, row indexes are used.
    """
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV file has no data rows: {path}")

    columns = _normalized_columns(rows[0].keys())
    throughput_col = _find_column(columns, THROUGHPUT_ALIASES, "throughput")
    quality_col = _find_column(columns, QUALITY_ALIASES, "quality")
    buffer_col = _find_column(columns, BUFFER_ALIASES, "buffer level")
    time_col = _find_optional_column(columns, TIME_ALIASES)
    jitter_instant_col = _find_optional_column(columns, JITTER_INSTANT_ALIASES)
    jitter_ewma_col = _find_optional_column(columns, JITTER_EWMA_ALIASES)
    failover_col = _find_optional_column(columns, FAILOVER_ALIASES)

    time_s = _parse_time_values(rows, columns, time_col)
    throughput = _parse_float_column(rows, columns, throughput_col, "throughput")
    qualities = [_read_value(row, columns, quality_col).strip() for row in rows]
    buffer_level = _parse_float_column(rows, columns, buffer_col, "buffer level")
    rebuffer_events = _parse_rebuffer_events(rows, columns, buffer_level)

    jitter_network_ms = (
        _parse_float_column(rows, columns, jitter_instant_col, "jitter_network")
        if jitter_instant_col else None
    )
    jitter_ewma_ms = (
        _parse_float_column(rows, columns, jitter_ewma_col, "jitter_ewma")
        if jitter_ewma_col else None
    )

    failover_times = None
    if failover_col:
        failover_totals = _parse_float_column(rows, columns, failover_col, "failover")
        prev = failover_totals[0]
        times = [time_s[0]] if prev > 0 else []
        for i, val in enumerate(failover_totals[1:], start=1):
            if val > prev:
                times.append(time_s[i])
            prev = val
        failover_times = times or None

    if not all(qualities):
        raise ValueError("Quality column contains empty values")

    return StreamingMetrics(
        time_s=time_s,
        throughput_kbps=throughput,
        qualities=qualities,
        buffer_level=buffer_level,
        rebuffer_events=rebuffer_events,
        jitter_network_ms=jitter_network_ms,
        jitter_ewma_ms=jitter_ewma_ms,
        failover_times=failover_times,
    )


def generate_graphs(
    csv_path: Union[str, Path],
    output_dir: Union[str, Path] = "graphs",
) -> Dict[str, Path]:
    """Generate all streaming metric graphs and return their output paths."""
    metrics = load_csv_data(csv_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    paths = {
        "throughput_timeline": output_path / GRAPH_FILENAMES["throughput_timeline"],
        "quality_timeline": output_path / GRAPH_FILENAMES["quality_timeline"],
        "buffer_level": output_path / GRAPH_FILENAMES["buffer_level"],
        "quality_distribution": output_path / GRAPH_FILENAMES["quality_distribution"],
        "throughput_histogram": output_path / GRAPH_FILENAMES["throughput_histogram"],
        "jitter_ewma": output_path / GRAPH_FILENAMES["jitter_ewma"],
        "player_dynamics": output_path / GRAPH_FILENAMES["player_dynamics"],
    }

    _plot_throughput_timeline(metrics, paths["throughput_timeline"])
    _plot_quality_timeline(metrics, paths["quality_timeline"])
    _plot_buffer_level(metrics, paths["buffer_level"])
    _plot_quality_distribution(metrics, paths["quality_distribution"])
    _plot_throughput_histogram(metrics, paths["throughput_histogram"])
    _plot_jitter_ewma(metrics, paths["jitter_ewma"])
    _plot_player_dynamics(metrics, paths["player_dynamics"])

    return paths


def _plot_throughput_timeline(metrics: StreamingMetrics, output_path: Path) -> None:
    quality_map = _quality_rank_map(metrics.qualities)
    quality_values = [quality_map[quality] for quality in metrics.qualities]
    bar_width = _bar_width(metrics.time_s)

    fig, ax_throughput = plt.subplots(figsize=(10, 5))
    ax_quality = ax_throughput.twinx()

    ax_quality.bar(
        metrics.time_s,
        quality_values,
        width=bar_width,
        color="#9ecae1",
        alpha=0.45,
        label="Selected quality",
    )
    ax_throughput.plot(
        metrics.time_s,
        metrics.throughput_kbps,
        color="#1f77b4",
        marker="o",
        linewidth=2,
        label="Throughput",
    )

    _format_time_axis(ax_throughput)
    _format_quality_axis(ax_quality, quality_map)
    _highlight_rebuffers(ax_throughput, metrics)
    _highlight_failover(ax_throughput, metrics)
    ax_throughput.set_ylabel("Throughput (kbps)")
    ax_quality.set_ylabel("Quality")
    ax_throughput.set_title("Throughput vs Selected Quality")
    _combine_legends(ax_throughput, ax_quality)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_quality_timeline(metrics: StreamingMetrics, output_path: Path) -> None:
    quality_map = _quality_rank_map(metrics.qualities)
    quality_values = [quality_map[quality] for quality in metrics.qualities]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.step(
        metrics.time_s,
        quality_values,
        where="post",
        color="#2ca02c",
        linewidth=2,
        label="Selected quality",
    )
    ax.scatter(metrics.time_s, quality_values, color="#2ca02c", s=24)

    _format_time_axis(ax)
    _format_quality_axis(ax, quality_map)
    _highlight_rebuffers(ax, metrics)
    _highlight_failover(ax, metrics)
    ax.set_ylabel("Quality")
    ax.set_title("Quality Timeline")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_buffer_level(metrics: StreamingMetrics, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(
        metrics.time_s,
        metrics.buffer_level,
        color="#9467bd",
        marker="o",
        linewidth=2,
        label="Buffer level",
    )
    ax.axhline(0, color="#444444", linewidth=1, alpha=0.5)

    _format_time_axis(ax)
    _highlight_rebuffers(ax, metrics)
    _highlight_failover(ax, metrics)
    ax.set_ylabel("Buffer (s)")
    ax.set_title("Buffer Level")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_quality_distribution(metrics: StreamingMetrics, output_path: Path) -> None:
    durations = _quality_durations(metrics.time_s, metrics.qualities)
    quality_map = _quality_rank_map(durations.keys())
    qualities = sorted(durations, key=lambda quality: quality_map[quality])
    values = [durations[quality] for quality in qualities]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(qualities, values, color="#74c476")
    ax.set_xlabel("Quality")
    ax.set_ylabel("Time at quality (s)")
    ax.set_title("Quality Distribution")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_throughput_histogram(metrics: StreamingMetrics, output_path: Path) -> None:
    bins = min(10, max(3, math.ceil(math.sqrt(len(metrics.throughput_kbps)))))

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(metrics.throughput_kbps, bins=bins, color="#fdae6b", edgecolor="#8c510a")
    ax.set_xlabel("Throughput (kbps)")
    ax.set_ylabel("Frequency")
    ax.set_title("Throughput Histogram")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


_QUALITY_NOMINAL_KBPS: Dict[str, int] = {
    "240p": 200, "360p": 400, "480p": 600, "720p": 1000, "1080p": 1200,
}


def _plot_player_dynamics(metrics: StreamingMetrics, output_path: Path) -> None:
    """Buffer + throughput + quality (bitrate nominal) num único painel — gráfico de apresentação."""
    quality_kbps = [
        _QUALITY_NOMINAL_KBPS.get(q, 400) for q in metrics.qualities
    ]

    fig, ax_buf = plt.subplots(figsize=(12, 6))
    ax_net = ax_buf.twinx()

    # Buffer — eixo esquerdo (área preenchida + linha)
    ax_buf.fill_between(metrics.time_s, metrics.buffer_level,
                        alpha=0.20, color="#9467bd")
    ax_buf.plot(metrics.time_s, metrics.buffer_level,
                color="#9467bd", linewidth=2.5, label="Nível do Buffer (s)")

    # Throughput — eixo direito (pontilhado)
    ax_net.plot(metrics.time_s, metrics.throughput_kbps,
                color="#1f77b4", linewidth=1.5, alpha=0.75,
                linestyle=":", label="Vazão Medida (kbps)")

    # Qualidade como bitrate nominal — eixo direito (degrau sólido)
    ax_net.step(metrics.time_s, quality_kbps, where="post",
                color="#2ca02c", linewidth=2.5, label="Qualidade Selecionada (kbps nominal)")

    # Marcadores de rebuffering e failover
    _highlight_rebuffers(ax_buf, metrics)
    _highlight_failover(ax_buf, metrics)

    # Ticks do eixo direito nas resoluções conhecidas
    present_kbps = sorted(set(quality_kbps))
    ax_net.set_yticks(present_kbps)
    ax_net.set_yticklabels([
        f"{next((q for q, k in _QUALITY_NOMINAL_KBPS.items() if k == b), str(b))} ({b} kbps)"
        for b in present_kbps
    ])

    ax_buf.set_xlabel("Número de Segmento", fontsize=11)
    ax_buf.set_ylabel("Nível do Buffer (s)", color="#9467bd", fontsize=11)
    ax_net.set_ylabel("Throughput / Qualidade (kbps)", color="#1f77b4", fontsize=11)
    ax_buf.tick_params(axis="y", labelcolor="#9467bd")
    ax_net.tick_params(axis="y", labelcolor="#1f77b4")
    ax_buf.set_title(
        "Dinâmica do Player: Adaptação de Mídia e Instabilidade da Rede",
        fontsize=13, fontweight="bold",
    )
    ax_buf.grid(True, alpha=0.25)

    # Legenda combinada
    lines_buf, labels_buf = ax_buf.get_legend_handles_labels()
    lines_net, labels_net = ax_net.get_legend_handles_labels()
    ax_buf.legend(lines_buf + lines_net, labels_buf + labels_net,
                  loc="upper left", fontsize=9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_jitter_ewma(metrics: StreamingMetrics, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    if metrics.jitter_network_ms:
        ax.plot(
            metrics.time_s, metrics.jitter_network_ms,
            color="#fdae6b", linewidth=1.5, linestyle="--", alpha=0.7,
            label="Jitter instantâneo (rede)",
        )
    if metrics.jitter_ewma_ms:
        ax.plot(
            metrics.time_s, metrics.jitter_ewma_ms,
            color="#d62728", linewidth=2,
            label="Jitter EWMA",
        )
    _format_time_axis(ax)
    _highlight_rebuffers(ax, metrics)
    _highlight_failover(ax, metrics)
    ax.set_ylabel("Jitter (ms)")
    ax.set_title("Variação de Atraso (Jitter) — Instantâneo e EWMA")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _normalized_columns(columns: Iterable[str]) -> Dict[str, str]:
    return {_normalize_column(column): column for column in columns}


def _normalize_column(column: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", column.strip().lower()).strip("_")


def _find_column(
    columns: Dict[str, str],
    aliases: Sequence[str],
    label: str,
) -> str:
    column = _find_optional_column(columns, aliases)
    if column is None:
        available = ", ".join(sorted(columns.values()))
        raise ValueError(f"Missing {label} column. Available columns: {available}")
    return column


def _find_optional_column(columns: Dict[str, str], aliases: Sequence[str]) -> Optional[str]:
    for alias in aliases:
        normalized_alias = _normalize_column(alias)
        if normalized_alias in columns:
            return columns[normalized_alias]
    return None


def _read_value(row: Dict[str, str], columns: Dict[str, str], column: str) -> str:
    return row.get(column, "")


def _parse_float_column(
    rows: Sequence[Dict[str, str]],
    columns: Dict[str, str],
    column: str,
    label: str,
) -> List[float]:
    values = []
    for index, row in enumerate(rows, start=1):
        raw_value = _read_value(row, columns, column).strip()
        try:
            values.append(float(raw_value))
        except ValueError as exc:
            raise ValueError(
                f"Invalid {label} value at row {index}: {raw_value!r}"
            ) from exc
    return values


def _parse_time_values(
    rows: Sequence[Dict[str, str]],
    columns: Dict[str, str],
    time_col: Optional[str],
) -> List[float]:
    if time_col is None:
        return [float(index) for index in range(len(rows))]

    raw_values = [_read_value(row, columns, time_col).strip() for row in rows]

    try:
        return [float(value) for value in raw_values]
    except ValueError:
        pass

    timestamps = [_parse_datetime(value) for value in raw_values]
    start = timestamps[0]
    return [(timestamp - start).total_seconds() for timestamp in timestamps]


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp value: {value!r}") from exc


def _parse_rebuffer_events(
    rows: Sequence[Dict[str, str]],
    columns: Dict[str, str],
    buffer_level: Sequence[float],
) -> List[bool]:
    rebuffer_col = _find_optional_column(columns, REBUFFER_ALIASES)
    if rebuffer_col is not None:
        return [
            _parse_bool(_read_value(row, columns, rebuffer_col))
            for row in rows
        ]

    rebuffer_count_col = _find_optional_column(columns, REBUFFER_COUNT_ALIASES)
    if rebuffer_count_col is not None:
        counts = _parse_float_column(rows, columns, rebuffer_count_col, "rebuffer count")
        previous = counts[0]
        events = [previous > 0]
        for count in counts[1:]:
            events.append(count > previous)
            previous = count
        return events

    events = [False]
    for previous_buffer, current_buffer in zip(buffer_level, buffer_level[1:]):
        events.append(previous_buffer > 0 and current_buffer <= 0)
    return events


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "sim", "s"}:
        return True
    if normalized in {"0", "false", "no", "n", "nao", ""}:
        return False
    try:
        return float(normalized) != 0
    except ValueError as exc:
        raise ValueError(f"Invalid boolean value: {value!r}") from exc


def _quality_rank_map(qualities: Iterable[str]) -> Dict[str, int]:
    unique_qualities = list(dict.fromkeys(qualities))
    sorted_qualities = sorted(unique_qualities, key=_quality_sort_key)
    return {quality: index + 1 for index, quality in enumerate(sorted_qualities)}


def _quality_sort_key(quality: str) -> tuple:
    match = re.search(r"\d+", quality)
    if match:
        return (0, int(match.group()), quality)
    return (1, quality)


def _format_quality_axis(ax, quality_map: Dict[str, int]) -> None:
    labels = [quality for quality, _ in sorted(quality_map.items(), key=lambda item: item[1])]
    ticks = [quality_map[quality] for quality in labels]
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels)
    if ticks:
        ax.set_ylim(min(ticks) - 0.5, max(ticks) + 0.5)


def _format_time_axis(ax) -> None:
    ax.set_xlabel("Time (s)")
    ax.grid(True, alpha=0.25)


def _highlight_rebuffers(ax, metrics: StreamingMetrics) -> None:
    added_label = False
    for time_value, is_rebuffering in zip(metrics.time_s, metrics.rebuffer_events):
        if not is_rebuffering:
            continue
        label = "Rebuffering" if not added_label else None
        ax.axvline(time_value, color="#d62728", alpha=0.35, linewidth=2, label=label)
        added_label = True


def _highlight_failover(ax, metrics: StreamingMetrics) -> None:
    if not metrics.failover_times:
        return
    added_label = False
    for t in metrics.failover_times:
        label = "Failover" if not added_label else None
        ax.axvline(t, color="#ff7f0e", linestyle="--", linewidth=2, alpha=0.8, label=label)
        added_label = True


def _combine_legends(*axes) -> None:
    handles = []
    labels = []
    for ax in axes:
        axis_handles, axis_labels = ax.get_legend_handles_labels()
        handles.extend(axis_handles)
        labels.extend(axis_labels)
    if handles:
        axes[0].legend(handles, labels, loc="best")


def _bar_width(time_s: Sequence[float]) -> float:
    if len(time_s) < 2:
        return 0.8

    deltas = [
        current - previous
        for previous, current in zip(time_s, time_s[1:])
        if current > previous
    ]
    if not deltas:
        return 0.8
    return min(deltas) * 0.8


def _quality_durations(time_s: Sequence[float], qualities: Sequence[str]) -> Dict[str, float]:
    durations: Dict[str, float] = {}
    deltas = [
        current - previous
        for previous, current in zip(time_s, time_s[1:])
        if current > previous
    ]
    default_duration = _median(deltas) if deltas else 1.0

    for index, quality in enumerate(qualities):
        if index < len(time_s) - 1 and time_s[index + 1] > time_s[index]:
            duration = time_s[index + 1] - time_s[index]
        else:
            duration = default_duration
        durations[quality] = durations.get(quality, 0.0) + duration

    return durations


def _median(values: Sequence[float]) -> float:
    sorted_values = sorted(values)
    middle = len(sorted_values) // 2
    if len(sorted_values) % 2 == 1:
        return sorted_values[middle]
    return (sorted_values[middle - 1] + sorted_values[middle]) / 2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate graphs from adaptive streaming CSV metrics."
    )
    parser.add_argument("csv_path", nargs="?", help="Path to the metrics CSV file")
    parser.add_argument(
        "--output-dir",
        default="graphs",
        help="Directory where graph PNG files will be saved",
    )
    parser.add_argument(
        "--compare",
        nargs="+",
        metavar="CSV",
        help="Gera gráficos comparativos sobrepostos entre N sessões (ex: csv1.csv csv2.csv csv3.csv)",
    )
    parser.add_argument(
        "--labels",
        nargs="+",
        metavar="LABEL",
        help="Rótulos das sessões usados no modo --compare (padrão: Política 1, 2, ...)",
    )
    args = parser.parse_args()

    if args.compare:
        labels = args.labels or [f"Política {i+1}" for i in range(len(args.compare))]
        generate_comparison_graphs(args.compare, labels, args.output_dir)
        for name in ("comparison_throughput", "comparison_quality_timeline", "comparison_buffer_level", "comparison_jitter"):
            print(os.path.join(args.output_dir, f"{name}.png"))
        return

    if not args.csv_path:
        parser.error("csv_path é obrigatório quando --compare não é usado")

    generated = generate_graphs(args.csv_path, args.output_dir)
    for path in generated.values():
        print(path)

def generate_comparison_graphs(csv_paths: List[str], labels: List[str], output_dir: str):
    """
    Gera gráficos comparativos sobrepostos aceitando N políticas/sessões (Issue 17).
    """
    if len(csv_paths) != len(labels):
        raise ValueError("A quantidade de arquivos CSV deve ser igual à de labels.")

    import pandas as pd
    import matplotlib.pyplot as plt
    import os

    # Carregar os DataFrames e mapear colunas usando os aliases existentes
    dataframes = []
    for path in csv_paths:
        df = pd.read_csv(path)
        
        # Identificar colunas cruciais de forma flexível e normalizar seus nomes
        df.rename(columns={
            col: 'segment' for col in df.columns if col in ('segment', 'segment_id', 'chunk_id')
        }, inplace=True)
        df.rename(columns={
            col: 'quality' for col in df.columns if col in QUALITY_ALIASES
        }, inplace=True)
        df.rename(columns={
            col: 'buffer' for col in df.columns if col in BUFFER_ALIASES
        }, inplace=True)
        df.rename(columns={
            col: 'vazao' for col in df.columns if col in THROUGHPUT_ALIASES
        }, inplace=True)
        df.rename(columns={
            col: 'jitter_instant' for col in df.columns if col in JITTER_INSTANT_ALIASES
        }, inplace=True)
        df.rename(columns={
            col: 'jitter_ewma' for col in df.columns if col in JITTER_EWMA_ALIASES
        }, inplace=True)
        df.rename(columns={
            col: 'stall' for col in df.columns if col in REBUFFER_ALIASES or col in ('rebuffer_event', 'rebuffering_occurred')
        }, inplace=True)
        
        # Validação de segurança pós-rename para garantir que a coluna essencial de buffer foi mapeada
        if 'buffer' not in df.columns:
            raise KeyError(f"Não foi encontrada nenhuma coluna de buffer reconhecida no arquivo: {path}. "
                           f"Colunas disponíveis: {list(df.columns)}")
            
        dataframes.append(df)

    os.makedirs(output_dir, exist_ok=True)
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'] # Azul, Laranja, Verde...
    
    # Encontrar se houve algum evento de failover global para marcar com linha vertical
    failover_seg = None
    for df in dataframes:
        if 'failover_total' in df.columns:
            changed = df[df['failover_total'] > 0]
            if not changed.empty:
                failover_seg = changed['segment'].iloc[0]
                break

    # ─── GRÁFICO 1: VAZÃO MEDIDA ───────────────────────────────────────────
    plt.figure(figsize=(10, 5))
    for i, df in enumerate(dataframes):
        if 'vazao' in df.columns:
            plt.plot(df['segment'], df['vazao'], label=labels[i], color=colors[i], alpha=0.8)
    if failover_seg:
        plt.axvline(x=failover_seg, color='red', linestyle='--', label='Failover detectado')
    plt.title('Comparativo de Vazão da Rede (Mesmo Cenário)')
    plt.xlabel('Segmento')
    plt.ylabel('Vazão Medida (kbps)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_throughput.png'), dpi=150)
    plt.close()

    # ─── GRÁFICO 2: EVOLUÇÃO DA QUALIDADE (RESOLUÇÃO DO MATPLOTLIB) ───────────
    plt.figure(figsize=(10, 5))

    # Constrói mapa de qualidade dinamicamente a partir de todos os dados
    all_qualities = sorted(
        {q for df in dataframes if 'quality' in df.columns for q in df['quality'].dropna().unique()},
        key=_quality_sort_key,
    )
    quality_map = {q: i for i, q in enumerate(all_qualities)}

    for i, df in enumerate(dataframes):
        if df is None or df.empty:
            continue

        current_label = labels[i] if i < len(labels) else f"Política {i+1}"
        current_color = colors[i % len(colors)]
        col_seg = 'segment' if 'segment' in df.columns else df.columns[0]

        if 'quality' in df.columns:
            y_values = df['quality'].map(quality_map)
            plt.plot(
                df[col_seg],
                y_values,
                label=current_label,
                color=current_color,
                marker='o',
                alpha=0.7,
                linewidth=2,
            )

    if failover_seg:
        plt.axvline(x=failover_seg, color='red', linestyle='--', label='Failover')

    plt.title('Comparativo de Tomada de Decisão de Qualidade (ABR)')
    plt.xlabel('Segmento')
    plt.ylabel('Resolução / Qualidade')
    plt.yticks(ticks=list(quality_map.values()), labels=list(quality_map.keys()))
    n = len(all_qualities)
    plt.ylim(-0.3, n - 0.7)
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.legend(loc='upper right')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_quality_timeline.png'), dpi=150)
    plt.close()

    # ─── GRÁFICO 3: NÍVEL DO BUFFER E TRAVAMENTOS (STALLS) ─────────────────
    plt.figure(figsize=(10, 5))
    for i, df in enumerate(dataframes):
        # Como o rename unificou tudo para 'buffer', usamos diretamente aqui:
        plt.plot(df['segment'], df['buffer'], label=f'Buffer {labels[i]}', color=colors[i])
        
        # Marcar Stalls específicos de cada política (considera 1 ou True como travamento)
        if 'stall' in df.columns:
            stalls = df[(df['stall'] == 1) | (df['stall'] == True)]
            if not stalls.empty:
                plt.scatter(stalls['segment'], stalls['buffer'], color='red', marker='X', s=120, zorder=5, label=f'Stall ({labels[i]})')
    if failover_seg:
        plt.axvline(x=failover_seg, color='red', linestyle='--', label='Failover')
    plt.title('Comparativo da Dinâmica do Buffer e Travamentos')
    plt.xlabel('Segmento')
    plt.ylabel('Segundos em Buffer (s)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_buffer_level.png'), dpi=150)
    plt.close()

   # ─── GRÁFICO 4: JITTER INSTANTÂNEO VS EWMA (3 POLÍTICAS) ─────────────────
    plt.figure(figsize=(10, 5))
    
    # Cores master para as 3 políticas
    colors_three = ['#1f77b4', '#ff7f0e', '#2ca02c'] # Azul (Rate), Laranja (Buffer), Verde (Hybrid)

    for i, df in enumerate(dataframes):
        if df is None or df.empty:
            continue
            
        current_label = labels[i] if i < len(labels) else f"Política {i+1}"
        current_color = colors_three[i] if i < len(colors_three) else colors[i]
        col_seg = 'segment' if 'segment' in df.columns else df.columns[0]
        
        # 1. Plot do Jitter Instantâneo (Pontilhado, fino e mais claro/transparente)
        if 'jitter_instant' in df.columns:
            plt.plot(
                df[col_seg], 
                df['jitter_instant'], 
                label=f'{current_label} (Instantâneo)', 
                color=current_color, 
                alpha=0.55,          # Linha bem mais clara
                linestyle=':',       # Estilo pontilhado
                linewidth=1.5
            )
            
        # 2. Plot do Jitter EWMA (Sólido, nítido e destacado)
        if 'jitter_ewma' in df.columns:
            plt.plot(
                df[col_seg], 
                df['jitter_ewma'], 
                label=f'{current_label} (EWMA)', 
                color=current_color, 
                linewidth=2.2,       # Linha mais grossa para destaque
                alpha=0.9,
                zorder=3             # Garante que o EWMA fique visualmente acima do pontilhado
            )

    plt.title('Comparativo de Instabilidade do Canal (Jitter Bruto vs EWMA)')
    plt.xlabel('Segmento')
    plt.ylabel('Jitter (ms)')
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Organiza a legenda em duas colunas para ficar limpo
    plt.legend(loc='upper right', ncol=2, fontsize='small')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_jitter.png'), dpi=150)
    plt.close()

    print(f"✨ Todos os 4 gráficos comparativos triplos gerados com sucesso em: {output_dir}")

if __name__ == "__main__":
    main()
