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
    parser.add_argument("csv_path", help="Path to the metrics CSV file")
    parser.add_argument(
        "--output-dir",
        default="graphs",
        help="Directory where graph PNG files will be saved",
    )
    args = parser.parse_args()

    generated = generate_graphs(args.csv_path, args.output_dir)
    for path in generated.values():
        print(path)


if __name__ == "__main__":
    main()
