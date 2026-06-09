"""Failover entre servidores com health check automático.

Permite ao cliente suportar dois (ou mais) servidores com troca automática
quando o servidor principal falha. A lista de servidores e suas prioridades
vem do manifest.

Comportamento:
- Ao iniciar usa o servidor de prioridade 1 (Servidor A).
- Ao detectar falha (timeout, erro HTTP, conexão recusada), faz GET /health no
  próximo servidor da lista; se disponível, migra e registra o evento; caso
  contrário tenta o próximo (se houver).
"""

import requests
from datetime import datetime
from typing import Any, Dict, List, Optional


class FailoverManager:
    """Gerencia a troca automática de servidores via health check."""

    # Caminho do endpoint de saúde: GET /health → {"status": "ok", "instance": ...}
    HEALTH_PATH = "/health"
    # Tempo máximo de espera (em segundos) ao consultar /health.
    DEFAULT_HEALTH_TIMEOUT = 5.0

    def __init__(
        self,
        servers: List[Dict[str, Any]],
        health_timeout: float = DEFAULT_HEALTH_TIMEOUT,
    ):
        """
        Inicializa o gerenciador de failover.

        Args:
            servers: Lista de dicts do manifest, cada um com ao menos as chaves
                'id', 'url' e 'priority'.
            health_timeout: Timeout em segundos para o health check.

        Raises:
            ValueError: Se a lista de servidores estiver vazia.
        """
        if not servers:
            raise ValueError("É necessário ao menos um servidor para o failover")

        # Ordena por prioridade (1 = principal). Usamos cópia da lista para não
        # mutar a estrutura original do manifest.
        self.servers: List[Dict[str, Any]] = sorted(
            servers, key=lambda s: s.get("priority", float("inf"))
        )
        self.health_timeout = health_timeout

        # Índice, dentro de self.servers, do servidor atualmente ativo.
        self.current_index = 0

        # Métricas de failover exigidas pela especificação.
        self.total_failovers = 0
        self.failover_events: List[Dict[str, Any]] = []

    @property
    def current_server(self) -> Dict[str, Any]:
        """Retorna o dict do servidor atualmente ativo."""
        return self.servers[self.current_index]

    def health_check(self, server: Dict[str, Any]) -> bool:
        """
        Consulta GET /health do servidor informado.

        Args:
            server: Dict do servidor com a chave 'url'.

        Returns:
            True se o servidor respondeu de forma saudável (HTTP 200 e, quando há
            corpo JSON, status == "ok"); False em caso de erro, timeout ou
            conexão recusada.
        """
        url = server["url"].rstrip("/") + self.HEALTH_PATH
        try:
            resp = requests.get(url, timeout=self.health_timeout)
        except requests.RequestException:
            return False

        if resp.status_code != 200:
            return False

        # O endpoint responde {"status": "ok", "instance": "A"/"B", ...}.
        # Se não houver corpo JSON, mas a resposta foi 200, consideramos disponível.
        try:
            data = resp.json()
        except ValueError:
            return True

        return data.get("status") == "ok"

    def try_failover(self, segment: Optional[int] = None) -> bool:
        """
        Tenta migrar para o próximo servidor disponível da lista.

        Percorre os servidores de prioridade inferior à do atual e, no primeiro
        que passar no health check, migra para ele, registra o evento e
        incrementa o contador de failovers.

        Args:
            segment: Número do segmento em que a falha ocorreu (apenas registro).

        Returns:
            True se migrou para outro servidor; False se nenhum dos próximos
            servidores estava disponível.
        """
        origem = self.current_server

        for next_index in range(self.current_index + 1, len(self.servers)):
            candidate = self.servers[next_index]
            if self.health_check(candidate):
                self.current_index = next_index
                self.total_failovers += 1
                self.failover_events.append(
                    {
                        "segment": segment,
                        "from_server": origem.get("id"),
                        "to_server": candidate.get("id"),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                return True

        # Nenhum servidor de menor prioridade respondeu ao health check.
        return False

    def reset(self) -> None:
        """Volta ao servidor de maior prioridade, preservando o histórico."""
        self.current_index = 0

    def __repr__(self) -> str:
        """Retorna uma representação resumida do estado do failover."""
        s = self.current_server
        return (
            f"FailoverManager(active={s.get('id')}, "
            f"servers={len(self.servers)}, "
            f"failovers={self.total_failovers})"
        )
