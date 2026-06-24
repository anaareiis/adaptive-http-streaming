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
    "buffer_seconds",
    "buffer_s",
    "buffer",
    "current_buffer",
    "buffer_level_secs",
    "buffer_level_s",
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


@dataclass
class StreamingMetrics:
    """Normalized streaming metrics loaded from CSV."""

    time_s: List[float]
    throughput_kbps: List[float]
    qualities: List[str]
    buffer_level: List[float]
    rebuffer_events: List[bool]


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

    time_s = _parse_time_values(rows, columns, time_col)
    throughput = _parse_float_column(rows, columns, throughput_col, "throughput")
    qualities = [_read_value(row, columns, quality_col).strip() for row in rows]
    buffer_level = _parse_float_column(rows, columns, buffer_col, "buffer level")
    rebuffer_events = _parse_rebuffer_events(rows, columns, buffer_level)

    if not all(qualities):
        raise ValueError("Quality column contains empty values")

    return StreamingMetrics(
        time_s=time_s,
        throughput_kbps=throughput,
        qualities=qualities,
        buffer_level=buffer_level,
        rebuffer_events=rebuffer_events,
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
    }

    _plot_throughput_timeline(metrics, paths["throughput_timeline"])
    _plot_quality_timeline(metrics, paths["quality_timeline"])
    _plot_buffer_level(metrics, paths["buffer_level"])
    _plot_quality_distribution(metrics, paths["quality_distribution"])
    _plot_throughput_histogram(metrics, paths["throughput_histogram"])

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
        nargs=2,
        metavar=("CSV1", "CSV2"),
        help="Gera gráficos comparativos sobrepostos entre duas sessões (ex: Política 1 vs Política 2)",
    )
    parser.add_argument(
        "--labels",
        nargs=2,
        metavar=("LABEL1", "LABEL2"),
        default=["Política 1", "Política 2"],
        help="Rótulos das duas sessões usados no modo --compare",
    )
    args = parser.parse_args()

    if args.compare:
        generate_comparison_graphs(args.compare[0], args.compare[1], args.labels, args.output_dir)
        for name in ("comparison_throughput", "comparison_quality_timeline", "comparison_buffer_level", "comparison_jitter"):
            print(os.path.join(args.output_dir, f"{name}.png"))
        return

    if not args.csv_path:
        parser.error("csv_path é obrigatório quando --compare não é usado")

    generated = generate_graphs(args.csv_path, args.output_dir)
    for path in generated.values():
        print(path)

def generate_comparison_graphs(csv1, csv2, labels, output_dir="logs/graphs"):
    """
    Gera gráficos comparativos sobrepostos mapeando as colunas dinamicamente.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Carregar os dados
    df1 = pd.read_csv(csv1)
    df2 = pd.read_csv(csv2)
    
    # Mapeamento Dinâmico de Colunas para evitar KeyError
    def get_col(df, options):
        for opt in options:
            if opt in df.columns:
                return opt
        raise KeyError(f"Nenhuma das colunas {options} foi encontrada no CSV. Colunas disponíveis: {list(df.columns)}")

    # Mapeamento exato baseado no cabeçalho real detectado
    col_seg = get_col(df1, ['segment', 'segmento'])
    col_vazao = get_col(df1, ['vazao', 'vazao_kbps', 'throughput_kbps'])
    col_quality = get_col(df1, ['quality', 'qualidade'])
    col_buffer = get_col(df1, ['buffer level', 'buffer_level_s', 'buffer_level'])
    col_jitter = get_col(df1, ['jitter_ewma', 'jitter_ewma_ms'])
    col_stall = get_col(df1, ['rebuffer_event', 'stall_event'])
    col_failover = get_col(df1, ['failover_total', 'failovers'])

    # Identificar segmento de failover (onde o contador de failover total é maior que zero)
    failover_seg_1 = df1[df1[col_failover] > 0][col_seg].min()
    failover_seg_2 = df2[df2[col_failover] > 0][col_seg].min()
    
    # Define o primeiro que aconteceu para traçar a linha vertical de failover
    if not pd.isna(failover_seg_1) and not pd.isna(failover_seg_2):
        failover_seg = min(failover_seg_1, failover_seg_2)
    else:
        failover_seg = failover_seg_1 if not pd.isna(failover_seg_1) else failover_seg_2

    colors = ['#1f77b4', '#ff7f0e'] 

    # ─── GRÁFICO 1: VAZÃO MEDIDA ───────────────────────────────────────────
    plt.figure(figsize=(10, 5))
    plt.plot(df1[col_seg], df1[col_vazao], label=labels[0], color=colors[0], marker='o')
    plt.plot(df2[col_seg], df2[col_vazao], label=labels[1], color=colors[1], marker='s')
    if not pd.isna(failover_seg):
        plt.axvline(x=failover_seg, color='red', linestyle='--', label='Failover Server')
    plt.title('Comparativo de Vazão Medida por Segmento')
    plt.xlabel('Segmento')
    plt.ylabel('Vazão (kbps)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_throughput.png'), dpi=150)
    plt.close()

    # ─── GRÁFICO 2: QUALIDADE SELECIONADA (STEP CHART) ─────────────────────
    plt.figure(figsize=(10, 5))
    def get_numeric_quality(q_str):
        try:
            return int(''.join(filter(str.isdigit, str(q_str))))
        except ValueError:
            return 0

    all_qualities = sorted(list(set(df1[col_quality].unique()).union(set(df2[col_quality].unique()))), key=get_numeric_quality)
    q_map = {name: i for i, name in enumerate(all_qualities)}
    
    y1 = df1[col_quality].map(q_map)
    y2 = df2[col_quality].map(q_map)

    plt.step(df1[col_seg], y1, where='mid', label=labels[0], color=colors[0], linewidth=2)
    plt.step(df2[col_seg], y2, where='mid', label=labels[1], color=colors[1], linewidth=2)
    
    if not pd.isna(failover_seg):
        plt.axvline(x=failover_seg, color='red', linestyle='--', label='Failover')
        
    plt.yticks(range(len(all_qualities)), all_qualities)
    plt.title('Comparativo de Qualidade Selecionada ao Longo do Tempo')
    plt.xlabel('Segmento')
    plt.ylabel('Qualidade')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_quality_timeline.png'), dpi=150)
    plt.close()

    # ─── GRÁFICO 3: NÍVEL DO BUFFER E REBUFFERING ──────────────────────────
    plt.figure(figsize=(10, 5))
    plt.plot(df1[col_seg], df1[col_buffer], label=f'Buffer {labels[0]}', color=colors[0])
    plt.plot(df2[col_seg], df2[col_buffer], label=f'Buffer {labels[1]}', color=colors[1])
    
    stalls1 = df1[df1[col_stall] == 1]
    stalls2 = df2[df2[col_stall] == 1]
    
    if not stalls1.empty:
        plt.scatter(stalls1[col_seg], stalls1[col_buffer], color='red', marker='X', s=100, zorder=5, label=f'Stall {labels[0]}')
    if not stalls2.empty:
        plt.scatter(stalls2[col_seg], stalls2[col_buffer], color='darkred', marker='X', s=100, zorder=5, label=f'Stall {labels[1]}')

    if not pd.isna(failover_seg):
        plt.axvline(x=failover_seg, color='red', linestyle='--', label='Failover')
        
    plt.title('Comparativo do Nível do Buffer e Travamentos')
    plt.xlabel('Segmento')
    plt.ylabel('Buffer (s)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_buffer_level.png'), dpi=150)
    plt.close()

    # ─── GRÁFICO 4: JITTER EWMA ────────────────────────────────────────────
    plt.figure(figsize=(10, 5))
    plt.plot(df1[col_seg], df1[col_jitter], label=labels[0], color=colors[0])
    plt.plot(df2[col_seg], df2[col_jitter], label=labels[1], color=colors[1])
    if not pd.isna(failover_seg):
        plt.axvline(x=failover_seg, color='red', linestyle='--', label='Failover')
    plt.title('Comparativo de Jitter EWMA ao Longo dos Segmentos')
    plt.xlabel('Segmento')
    plt.ylabel('Jitter EWMA (ms)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparison_jitter.png'), dpi=150)
    plt.close()

if __name__ == "__main__":
    main()
