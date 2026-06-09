"""Testes do schema CSV completo da spec no MetricsRecorder (Issue 13)."""

import csv

from metrics import MetricsRecorder, SPEC_HEADERS, LEGACY_HEADERS


EXPECTED_SPEC_HEADERS = [
    "segment", "timestamp", "server_id", "quality", "bitrate_kbps",
    "vazao_kbps", "download_time_s", "jitter_network_ms", "jitter_ewma_ms",
    "buffer_level_s", "buffer_can_play", "rebuffer_event",
    "stall_duration_s", "failover_total",
]


def test_spec_headers_has_14_fields():
    assert len(SPEC_HEADERS) == 14
    assert SPEC_HEADERS == EXPECTED_SPEC_HEADERS


def test_default_headers_are_legacy(tmp_path):
    """Sem o parâmetro headers, mantém o cabeçalho antigo (backward compat)."""
    recorder = MetricsRecorder(output_dir=str(tmp_path), batch_size=5)
    assert recorder.headers == LEGACY_HEADERS

    with open(recorder.filepath, encoding="utf-8") as f:
        header_row = next(csv.reader(f))
    assert header_row == LEGACY_HEADERS


def test_spec_headers_written_to_csv(tmp_path):
    """Passando SPEC_HEADERS, o CSV deve usar os 14 campos da spec."""
    recorder = MetricsRecorder(output_dir=str(tmp_path), batch_size=1, headers=SPEC_HEADERS)
    assert recorder.headers == SPEC_HEADERS

    with open(recorder.filepath, encoding="utf-8") as f:
        header_row = next(csv.reader(f))
    assert header_row == SPEC_HEADERS


def test_record_segment_with_spec_fields(tmp_path):
    """Um segmento gravado com as chaves da spec deve aparecer corretamente."""
    recorder = MetricsRecorder(output_dir=str(tmp_path), batch_size=1, headers=SPEC_HEADERS)
    segment = {
        "segment": 1,
        "timestamp": "2026-06-09T10:00:00",
        "server_id": "A",
        "quality": "720p",
        "bitrate_kbps": 1200,
        "vazao_kbps": 3500.0,
        "download_time_s": 0.42,
        "jitter_network_ms": 1.5,
        "jitter_ewma_ms": 0.8,
        "buffer_level_s": 6.0,
        "buffer_can_play": 1,
        "rebuffer_event": 0,
        "stall_duration_s": 0.0,
        "failover_total": 0,
    }
    recorder.record_segment(segment)
    recorder.close()

    with open(recorder.filepath, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["server_id"] == "A"
    assert rows[0]["quality"] == "720p"
    assert rows[0]["failover_total"] == "0"
    assert rows[0]["vazao_kbps"] == "3500.0"


def test_headers_is_copied_not_referenced(tmp_path):
    """Mutar SPEC_HEADERS depois não deve afetar o recorder."""
    custom = list(SPEC_HEADERS)
    recorder = MetricsRecorder(output_dir=str(tmp_path), headers=custom)
    custom.append("campo_extra")
    assert "campo_extra" not in recorder.headers
