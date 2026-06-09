"""Metrics collection and analysis."""

import time
import os
import csv
from collections import deque
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


# Cabeçalho legado (protótipo inicial) — mantido como padrão para garantir
# compatibilidade retroativa com os testes e CSVs já existentes.
LEGACY_HEADERS = [
    "segment_id",
    "timestamp",
    "quality",
    "bitrate_kbps",
    "throughput_kbps",
    "buffer_level_secs",
    "rebuffering_occurred",
    "quality_changed",
]

# Schema completo exigido pela especificação do projeto (14 campos).
# Cobre jitter, failover e play contínuo. Os nomes seguem o schema já usado
# pelo cliente real (main.py) e lido por graphs.py — em particular "vazao_kbps"
# é mantido sem acento para preservar a compatibilidade com esse pipeline.
SPEC_HEADERS = [
    "segment",            # número sequencial do segmento
    "timestamp",          # horário ISO 8601
    "server_id",          # id do servidor ("A" ou "B")
    "quality",            # qualidade selecionada pelo ABR
    "bitrate_kbps",       # bitrate nominal da representação
    "vazao_kbps",         # vazão medida neste segmento
    "download_time_s",    # tempo de download do segmento
    "jitter_network_ms",  # variação de latência entre chunks do mesmo segmento
    "jitter_ewma_ms",     # EWMA da variação entre segmentos consecutivos
    "buffer_level_s",     # nível estimado do buffer em segundos
    "buffer_can_play",    # 1 se buffer >= mínimo para play contínuo, 0 caso contrário
    "rebuffer_event",     # 1 se ocorreu rebuffering neste segmento
    "stall_duration_s",   # duração do stall em segundos (0 se não houve)
    "failover_total",     # número acumulado de failovers até este segmento
]


@dataclass
class ThroughputMeasurement:
    """Data class for a single throughput measurement."""

    bytes_downloaded: int
    time_elapsed: float
    throughput_kbps: float
    timestamp: datetime

    def __repr__(self) -> str:
        """Return string representation."""
        return f"ThroughputMeasurement(throughput={self.throughput_kbps:.2f} kbps, bytes={self.bytes_downloaded})"


class ThroughputMeter:
    """Measure throughput (bitrate) of segment downloads."""

    def __init__(self, history_size: int = 5):
        """
        Initialize throughput meter.

        Args:
            history_size: Number of recent measurements to keep in history (default: 5)
        """
        self.history_size = history_size
        self.history: deque = deque(maxlen=history_size)
        self.current_start_time: Optional[float] = None
        self.current_start_timestamp: Optional[datetime] = None

    def start_measurement(self) -> None:
        """
        Start timing a download.

        Should be called before downloading a segment.
        """
        self.current_start_time = time.time()
        self.current_start_timestamp = datetime.now()

    def stop_measurement(self, bytes_downloaded: int) -> ThroughputMeasurement:
        """
        Stop timing and calculate throughput.

        Args:
            bytes_downloaded: Number of bytes downloaded in this segment

        Returns:
            ThroughputMeasurement object with calculated metrics

        Raises:
            RuntimeError: If start_measurement() was not called first
            ValueError: If bytes_downloaded is negative
        """
        if self.current_start_time is None:
            raise RuntimeError("Measurement not started. Call start_measurement() first.")

        if bytes_downloaded < 0:
            raise ValueError("bytes_downloaded must be non-negative")

        # Calculate elapsed time
        elapsed_time = time.time() - self.current_start_time

        # Avoid division by zero
        if elapsed_time <= 0:
            elapsed_time = 0.001  # 1 millisecond minimum

        # Calculate throughput: (bytes * 8 bits) / time in seconds / 1000 bits per kbit
        throughput_kbps = (bytes_downloaded * 8) / elapsed_time / 1000

        # Create measurement
        measurement = ThroughputMeasurement(
            bytes_downloaded=bytes_downloaded,
            time_elapsed=elapsed_time,
            throughput_kbps=throughput_kbps,
            timestamp=self.current_start_timestamp,
        )

        # Add to history
        self.history.append(measurement)

        # Reset
        self.current_start_time = None
        self.current_start_timestamp = None

        return measurement

    def get_history(self) -> List[ThroughputMeasurement]:
        """
        Get all measurements in history.

        Returns:
            List of ThroughputMeasurement objects
        """
        return list(self.history)

    def get_average_throughput(self) -> float:
        """
        Calculate average throughput from history.

        Returns:
            Average throughput in kbps

        Raises:
            RuntimeError: If history is empty
        """
        if not self.history:
            raise RuntimeError("No measurements in history")

        total = sum(m.throughput_kbps for m in self.history)
        return total / len(self.history)

    def get_min_throughput(self) -> float:
        """
        Get minimum throughput from history.

        Returns:
            Minimum throughput in kbps

        Raises:
            RuntimeError: If history is empty
        """
        if not self.history:
            raise RuntimeError("No measurements in history")

        return min(m.throughput_kbps for m in self.history)

    def get_max_throughput(self) -> float:
        """
        Get maximum throughput from history.

        Returns:
            Maximum throughput in kbps

        Raises:
            RuntimeError: If history is empty
        """
        if not self.history:
            raise RuntimeError("No measurements in history")

        return max(m.throughput_kbps for m in self.history)

    def get_jitter(self) -> float:
        """
        Calculate jitter (variation) in throughput.

        Jitter is the standard deviation of throughput values.

        Returns:
            Standard deviation of throughput in kbps

        Raises:
            RuntimeError: If history has less than 2 measurements
        """
        if len(self.history) < 2:
            raise RuntimeError("Need at least 2 measurements to calculate jitter")

        # Calculate average
        avg = self.get_average_throughput()

        # Calculate variance
        variance = sum((m.throughput_kbps - avg) ** 2 for m in self.history) / len(self.history)

        # Calculate standard deviation
        jitter = variance ** 0.5

        return jitter

    def get_last_throughput(self) -> Optional[float]:
        """
        Get the most recent throughput measurement.

        Returns:
            Most recent throughput in kbps, or None if history is empty
        """
        if not self.history:
            return None

        return self.history[-1].throughput_kbps

    def get_throughput_trend(self) -> str:
        """
        Determine if throughput is increasing, decreasing, or stable.

        Returns:
            "increasing", "decreasing", or "stable"

        Raises:
            RuntimeError: If history has less than 2 measurements
        """
        if len(self.history) < 2:
            raise RuntimeError("Need at least 2 measurements to calculate trend")

        # Get first half and second half
        mid = len(self.history) // 2
        first_half = list(self.history)[: len(self.history) - mid]
        second_half = list(self.history)[len(self.history) - mid :]

        first_avg = sum(m.throughput_kbps for m in first_half) / len(first_half)
        second_avg = sum(m.throughput_kbps for m in second_half) / len(second_half)

        # Allow 35% tolerance for stability (to account for natural timing variations)
        threshold = first_avg * 0.35

        if second_avg > first_avg + threshold:
            return "increasing"
        elif second_avg < first_avg - threshold:
            return "decreasing"
        else:
            return "stable"

    def clear_history(self) -> None:
        """Clear all measurements from history."""
        self.history.clear()

    def __repr__(self) -> str:
        """Return string representation."""
        if not self.history:
            return "ThroughputMeter(empty)"

        return (
            f"ThroughputMeter(measurements={len(self.history)}, "
            f"avg={self.get_average_throughput():.2f} kbps)"
        )

class MetricsRecorder:
    """Gera a coleta de métricas de streaming e grava em arquivos CSV."""

    def __init__(
        self,
        output_dir: str = "logs",
        batch_size: int = 5,
        headers: Optional[List[str]] = None,
    ):
        """
        Inicializa o gravador de métricas.

        Args:
            output_dir: Diretório onde os arquivos de log serão salvos.
            batch_size: Quantidade de registros na memória antes de descarregar (flush) no CSV.
            headers: Lista de colunas do CSV. Se None, usa o cabeçalho legado
                (LEGACY_HEADERS) para manter compatibilidade com os testes
                existentes. O cliente real (main.py) passa SPEC_HEADERS.
        """
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.buffer_data: List[Dict[str, Any]] = []

        # Definição das colunas: usa o cabeçalho informado ou, na ausência dele,
        # o legado (backward compat com os CSVs do protótipo inicial).
        self.headers = list(headers) if headers is not None else list(LEGACY_HEADERS)

        # Cria a pasta de logs se ela não existir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        # Gera o nome do arquivo único com base no TIMESTAMP atual
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = os.path.join(self.output_dir, f"metrics_{timestamp_str}.csv")
        
        # Cria o arquivo inicialmente inserindo apenas o cabeçalho correto
        self._write_headers()

    def _write_headers(self) -> None:
        """Escreve o cabeçalho no arquivo CSV se ele estiver vazio."""
        with open(self.filepath, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)

    def record_segment(self, segment_data: Dict[str, Any]) -> None:
        """
        Guarda os dados do segmento em memória e escreve em lote se atingir o limite.

        Args:
            segment_data: Dicionário contendo as chaves correspondentes às colunas do CSV.
        """
        # Garante que o timestamp esteja no formato ISO se não for string
        if isinstance(segment_data.get("timestamp"), datetime):
            segment_data["timestamp"] = segment_data["timestamp"].isoformat()
        elif "timestamp" not in segment_data:
            segment_data["timestamp"] = datetime.now().isoformat()

        self.buffer_data.append(segment_data)

        # Se o tamanho do lote em memória atingir o batch_size, descarrega no arquivo
        if len(self.buffer_data) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """Descarrega os dados retidos na memória diretamente para o arquivo CSV."""
        if not self.buffer_data:
            return

        with open(self.filepath, mode='a', newline='', encoding='utf-8') as f:
            # DictWriter mapeia as chaves do dicionário perfeitamente com o cabeçalho
            writer = csv.DictWriter(f, fieldnames=self.headers, extrasaction='ignore')
            writer.writerows(self.buffer_data)
            
        # Limpa o buffer da memória após escrever
        self.buffer_data.clear()

    def close(self) -> None:
        """Garante que qualquer dado residual na memória seja salvo ao fechar o player."""
        self.flush()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()