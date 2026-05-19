"""Tests for graph generation from CSV metrics."""

from pathlib import Path

from graphs import GRAPH_FILENAMES, generate_graphs, load_csv_data


def write_csv(path: Path, contents: str) -> Path:
    path.write_text(contents.strip() + "\n", encoding="utf-8")
    return path


def test_generate_graphs_creates_expected_png_files(tmp_path):
    csv_path = write_csv(
        tmp_path / "metrics.csv",
        """
time_s,throughput_kbps,selected_quality,buffer_level,rebuffer
0,500,240p,4,0
4,900,360p,6,0
8,1200,480p,0,1
12,700,360p,3,0
16,1600,720p,5,0
""",
    )

    generated = generate_graphs(csv_path, tmp_path / "graphs")

    assert set(generated) == set(GRAPH_FILENAMES)
    for output_path in generated.values():
        assert output_path.exists()
        assert output_path.stat().st_size > 0


def test_load_csv_data_supports_aliases_and_rebuffer_count(tmp_path):
    csv_path = write_csv(
        tmp_path / "metrics_aliases.csv",
        """
elapsed_time,throughput,quality,buffer,rebuffer_count
0,400,240p,2,0
2,800,360p,0,1
4,1000,480p,3,1
6,600,240p,0,2
""",
    )

    metrics = load_csv_data(csv_path)

    assert metrics.time_s == [0.0, 2.0, 4.0, 6.0]
    assert metrics.throughput_kbps == [400.0, 800.0, 1000.0, 600.0]
    assert metrics.qualities == ["240p", "360p", "480p", "240p"]
    assert metrics.buffer_level == [2.0, 0.0, 3.0, 0.0]
    assert metrics.rebuffer_events == [False, True, False, True]


def test_load_csv_data_uses_row_index_when_time_is_missing(tmp_path):
    csv_path = write_csv(
        tmp_path / "metrics_without_time.csv",
        """
throughput_kbps,selected_quality,buffer_level
300,240p,1
600,360p,4
900,480p,0
""",
    )

    metrics = load_csv_data(csv_path)

    assert metrics.time_s == [0.0, 1.0, 2.0]
    assert metrics.rebuffer_events == [False, False, True]
