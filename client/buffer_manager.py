"""Gerenciamento do buffer de vídeo para streaming adaptativo."""

from typing import List, Dict, Optional
from datetime import datetime


class BufferManager:
    """Controla o nível do buffer e detecta eventos de rebuffering."""

    # Constantes de controle do buffer.
    # O player só é considerado apto a tocar quando tem pelo menos 2s acumulados.
    MIN_BUFFER_TO_PLAY = 2.0
    # Quando o buffer chega a 0s, consideramos que houve rebuffering/travamento.
    REBUFFER_THRESHOLD = 0.0

    def __init__(self, max_buffer: float = 60.0):
        """
        Inicializa o gerenciador com um tamanho máximo de buffer.

        Argumentos:
            max_buffer: Capacidade máxima do buffer em segundos. O padrão é 60s.
        """
        if max_buffer <= 0:
            raise ValueError("max_buffer must be positive")

        self.max_buffer = max_buffer
        self.current_buffer = 0.0
        self.rebuffer_count = 0
        self.rebuffer_history = []
        self.total_consumed = 0.0

    def add_segment(self, duration: float) -> None:
        """
        Adiciona um segmento baixado ao buffer.

        Cada segmento representa alguns segundos de vídeo pronto para reprodução.
        Por isso, quando o download termina, somamos essa duração ao buffer atual.

        Argumentos:
            duration: Duração do segmento em segundos.

        Erros:
            ValueError: Se a duração informada não for positiva.
        """
        if duration <= 0:
            raise ValueError("Segment duration must be positive")

        # Soma a duração do segmento, mas nunca deixa passar da capacidade máxima.
        old_buffer = self.current_buffer
        self.current_buffer = min(self.current_buffer + duration, self.max_buffer)

        # Se chegou no limite, apenas mantemos o buffer cheio; não há estouro real.
        if self.current_buffer == self.max_buffer and old_buffer < self.max_buffer:
            pass

    def consume(self, time_elapsed: float) -> None:
        """
        Consome buffer enquanto o player está reproduzindo/esperando.

        No cliente principal, esse tempo costuma ser o tempo real de download.
        Enquanto um novo segmento baixa, o vídeo que já estava no buffer continua
        sendo consumido.

        Argumentos:
            time_elapsed: Tempo decorrido em segundos.

        Erros:
            ValueError: Se o tempo informado não for positivo.
        """
        if time_elapsed <= 0:
            raise ValueError("time_elapsed must be positive")

        old_buffer = self.current_buffer
        self.current_buffer = max(0.0, self.current_buffer - time_elapsed)
        self.total_consumed += time_elapsed

        # Detecta rebuffering quando o buffer sai de um valor positivo e chega a 0.
        if old_buffer > self.REBUFFER_THRESHOLD and self.current_buffer <= self.REBUFFER_THRESHOLD:
            self._record_rebuffer()

    def can_play(self) -> bool:
        """
        Verifica se existe buffer suficiente para reprodução contínua.

        Retorna:
            True se o buffer tiver pelo menos MIN_BUFFER_TO_PLAY segundos.
        """
        return self.current_buffer >= self.MIN_BUFFER_TO_PLAY

    def get_buffer_level(self) -> float:
        """
        Retorna o nível atual do buffer em segundos.

        Retorna:
            Quantidade de vídeo já armazenada para reprodução.
        """
        return self.current_buffer

    def get_buffer_percentage(self) -> float:
        """
        Retorna o uso do buffer como porcentagem da capacidade máxima.

        Retorna:
            Porcentagem de ocupação do buffer, de 0 a 100.
        """
        if self.max_buffer == 0:
            return 0.0
        return (self.current_buffer / self.max_buffer) * 100

    def _record_rebuffer(self) -> None:
        """Registra um evento de rebuffering com timestamp e contador."""
        self.rebuffer_count += 1
        event = {
            "timestamp": datetime.now(),
            "buffer_level": self.current_buffer,
            "rebuffer_number": self.rebuffer_count,
        }
        self.rebuffer_history.append(event)

    def get_rebuffer_count(self) -> int:
        """
        Retorna o total de eventos de rebuffering.

        Retorna:
            Quantidade de vezes em que o buffer esvaziou.
        """
        return self.rebuffer_count

    def get_rebuffer_history(self) -> List[Dict]:
        """
        Retorna o histórico completo de rebuffering.

        Retorna:
            Lista de eventos com timestamp, nível de buffer e número do evento.
        """
        return self.rebuffer_history.copy()

    def get_last_rebuffer(self) -> Optional[Dict]:
        """
        Retorna o último evento de rebuffering.

        Retorna:
            Último evento registrado ou None se nunca houve rebuffering.
        """
        if self.rebuffer_history:
            return self.rebuffer_history[-1].copy()
        return None

    def is_rebuffering(self) -> bool:
        """
        Verifica se o player está em estado de rebuffering.

        A reprodução é considerada travada quando:
        - o buffer está esgotado;
        - e o player já tentou consumir algum conteúdo.

        Retorna:
            True se o estado atual representa rebuffering.
        """
        return (
            self.current_buffer <= self.REBUFFER_THRESHOLD
            and (self.rebuffer_count > 0 or self.total_consumed > 0)
        )

    def fill_buffer(self, duration: float) -> None:
        """
        Preenche o buffer rapidamente, útil em testes e simulações.

        Argumentos:
            duration: Duração total a adicionar em segundos.
        """
        if duration <= 0:
            raise ValueError("duration must be positive")

        self.current_buffer = min(self.current_buffer + duration, self.max_buffer)

    def drain_buffer(self, duration: float) -> None:
        """
        Esvazia parte do buffer, útil em testes e simulações.

        Argumentos:
            duration: Duração a remover do buffer, em segundos.
        """
        if duration <= 0:
            raise ValueError("duration must be positive")

        old_buffer = self.current_buffer
        self.current_buffer = max(0.0, self.current_buffer - duration)

        # Também verifica rebuffering quando o esvaziamento é feito manualmente.
        if old_buffer > self.REBUFFER_THRESHOLD and self.current_buffer <= self.REBUFFER_THRESHOLD:
            self._record_rebuffer()

    def reset(self) -> None:
        """Reinicia o buffer, contadores e histórico de rebuffering."""
        self.current_buffer = 0.0
        self.rebuffer_count = 0
        self.rebuffer_history = []
        self.total_consumed = 0.0

    def get_stats(self) -> Dict:
        """
        Retorna um resumo com as principais estatísticas do buffer.

        Retorna:
            Dicionário com nível atual, porcentagem, rebuffering e consumo total.
        """
        return {
            "current_buffer": self.current_buffer,
            "max_buffer": self.max_buffer,
            "buffer_percentage": self.get_buffer_percentage(),
            "can_play": self.can_play(),
            "is_rebuffering": self.is_rebuffering(),
            "rebuffer_count": self.rebuffer_count,
            "total_consumed": self.total_consumed,
        }

    def __repr__(self) -> str:
        """Retorna uma representação resumida do estado do buffer."""
        return (
            f"BufferManager(buffer={self.current_buffer:.1f}s/"
            f"{self.max_buffer:.1f}s, "
            f"rebuffers={self.rebuffer_count}, "
            f"can_play={self.can_play()})"
        )
