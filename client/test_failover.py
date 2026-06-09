"""Testes para o FailoverManager (Issue 12)."""

from unittest.mock import patch

import pytest
import requests

from failover import FailoverManager


# ── Fixtures / helpers ──────────────────────────────────────────────────────
SERVERS = [
    {"id": "B", "url": "http://137.131.178.229:8081", "priority": 2},
    {"id": "A", "url": "http://137.131.178.229:8080", "priority": 1},
]


class FakeResponse:
    """Resposta HTTP falsa para simular o endpoint /health."""

    def __init__(self, status_code=200, json_data=None, raise_json=False):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {"status": "ok"}
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("No JSON")
        return self._json_data


def make_manager(**kwargs):
    return FailoverManager(SERVERS, **kwargs)


# ── __init__ / current_server ───────────────────────────────────────────────
def test_init_sorts_by_priority():
    """O servidor de prioridade 1 (A) deve ficar ativo no início."""
    fm = make_manager()
    assert fm.current_server["id"] == "A"
    assert [s["id"] for s in fm.servers] == ["A", "B"]
    assert fm.total_failovers == 0
    assert fm.failover_events == []


def test_init_does_not_mutate_input():
    """A lista original do manifest não deve ser alterada."""
    original = list(SERVERS)
    make_manager()
    assert SERVERS == original


def test_init_empty_raises():
    with pytest.raises(ValueError):
        FailoverManager([])


# ── health_check ────────────────────────────────────────────────────────────
def test_health_check_ok():
    fm = make_manager()
    with patch("failover.requests.get", return_value=FakeResponse(200, {"status": "ok", "instance": "A"})):
        assert fm.health_check(fm.current_server) is True


def test_health_check_non_200():
    fm = make_manager()
    with patch("failover.requests.get", return_value=FakeResponse(503)):
        assert fm.health_check(fm.current_server) is False


def test_health_check_status_not_ok():
    fm = make_manager()
    with patch("failover.requests.get", return_value=FakeResponse(200, {"status": "degraded"})):
        assert fm.health_check(fm.current_server) is False


def test_health_check_200_without_json_is_available():
    fm = make_manager()
    with patch("failover.requests.get", return_value=FakeResponse(200, raise_json=True)):
        assert fm.health_check(fm.current_server) is True


def test_health_check_connection_error():
    fm = make_manager()
    with patch("failover.requests.get", side_effect=requests.ConnectionError("recusada")):
        assert fm.health_check(fm.current_server) is False


def test_health_check_timeout():
    fm = make_manager()
    with patch("failover.requests.get", side_effect=requests.Timeout("timeout")):
        assert fm.health_check(fm.current_server) is False


def test_health_check_builds_health_url():
    fm = make_manager()
    with patch("failover.requests.get", return_value=FakeResponse()) as mock_get:
        fm.health_check({"id": "A", "url": "http://host:8080/"})
        called_url = mock_get.call_args[0][0]
        assert called_url == "http://host:8080/health"


# ── try_failover ────────────────────────────────────────────────────────────
def test_try_failover_migrates_to_next_available():
    fm = make_manager()
    with patch.object(fm, "health_check", return_value=True):
        migrated = fm.try_failover(segment=7)

    assert migrated is True
    assert fm.current_server["id"] == "B"
    assert fm.total_failovers == 1
    assert len(fm.failover_events) == 1

    event = fm.failover_events[0]
    assert event["segment"] == 7
    assert event["from_server"] == "A"
    assert event["to_server"] == "B"
    assert "timestamp" in event


def test_try_failover_no_server_available():
    fm = make_manager()
    with patch.object(fm, "health_check", return_value=False):
        migrated = fm.try_failover(segment=3)

    assert migrated is False
    assert fm.current_server["id"] == "A"  # permanece no servidor original
    assert fm.total_failovers == 0
    assert fm.failover_events == []


def test_try_failover_on_last_server_returns_false():
    fm = make_manager()
    # Migra A -> B; agora não há próximo servidor.
    with patch.object(fm, "health_check", return_value=True):
        assert fm.try_failover(1) is True
        assert fm.try_failover(2) is False
    assert fm.current_server["id"] == "B"
    assert fm.total_failovers == 1


def test_try_failover_skips_unavailable_and_picks_next():
    """Com 3 servidores, pula o B indisponível e migra direto para C."""
    servers = [
        {"id": "A", "url": "http://a", "priority": 1},
        {"id": "B", "url": "http://b", "priority": 2},
        {"id": "C", "url": "http://c", "priority": 3},
    ]
    fm = FailoverManager(servers)

    def fake_health(server):
        return server["id"] == "C"  # apenas C está saudável

    with patch.object(fm, "health_check", side_effect=fake_health):
        migrated = fm.try_failover(segment=5)

    assert migrated is True
    assert fm.current_server["id"] == "C"
    assert fm.failover_events[0]["from_server"] == "A"
    assert fm.failover_events[0]["to_server"] == "C"


def test_reset_returns_to_primary():
    fm = make_manager()
    with patch.object(fm, "health_check", return_value=True):
        fm.try_failover(1)
    assert fm.current_server["id"] == "B"

    fm.reset()
    assert fm.current_server["id"] == "A"
    # O histórico de failovers é preservado.
    assert fm.total_failovers == 1
    assert len(fm.failover_events) == 1
