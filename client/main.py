"""
Cliente de Streaming Adaptativo — Tarefa 1 (Baseline Rate-Based ABR)
Conecta ao servidor real, baixa segmentos, mede vazão, gerencia buffer e grava CSV.
"""

import os
import csv
import math
import time
import requests
from collections import deque
from datetime import datetime

from abr import RateBasedABR
from buffer_manager import BufferManager

# ── Configurações ─────────────────────────────────────────────────────────────
MANIFEST_URL    = "http://137.131.178.229:8080/manifest"
TOTAL_SEGMENTS  = 30       # quantos segmentos baixar
CHUNK_SIZE      = 4096     # bytes por chunk (para medir jitter intra-segmento)
JITTER_EWMA_ALPHA = 0.2    # suavização EWMA do jitter entre segmentos

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
GRAPHS_DIR = os.path.join(os.path.dirname(__file__), "..", "graphs")


# ── Funções auxiliares ────────────────────────────────────────────────────────
def fetch_manifest(url: str) -> dict:
    """Baixa o manifesto JSON com as qualidades, servidores e duração dos segmentos."""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def parse_representations(manifest: dict) -> list:
    """Converte 'representations' do manifest para o formato esperado pelo ABR."""
    return [
        {"name": r["quality"], "bitrate": r["bitrate_kbps"]}
        for r in manifest["representations"]
    ]


def get_url_for_quality(manifest: dict, quality: str, base_url: str) -> str:
    """Monta a URL do segmento correspondente à qualidade escolhida pelo ABR."""
    for r in manifest["representations"]:
        if r["quality"] == quality:
            return base_url.rstrip("/") + r["url_path"]
    raise ValueError(f"Qualidade '{quality}' não encontrada no manifest")


def download_segment(url: str, timeout: int = 30) -> tuple:
    """
    Baixa um segmento em chunks e retorna:
        (bytes_total, download_time_s, jitter_network_ms)

    jitter_network_ms = desvio padrão dos intervalos entre chegadas de chunks.
    """
    chunk_times = []
    total_bytes = 0
    t_start = time.perf_counter()
    t_last_chunk = t_start

    with requests.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            now = time.perf_counter()
            chunk_times.append((now - t_last_chunk) * 1000)  # ms
            t_last_chunk = now
            total_bytes += len(chunk)

    t_end = time.perf_counter()
    download_time_s = t_end - t_start

    # Jitter intra-segmento = desvio padrão dos intervalos entre chunks
    if len(chunk_times) >= 2:
        intervals = chunk_times[1:]  # ignora o primeiro (inclui tempo de conexão)
        mean = sum(intervals) / len(intervals)
        variance = sum((x - mean) ** 2 for x in intervals) / len(intervals)
        jitter_network_ms = math.sqrt(variance)
    else:
        jitter_network_ms = 0.0

    return total_bytes, download_time_s, jitter_network_ms


def calc_throughput_kbps(bytes_total: int, time_s: float) -> float:
    """Calcula a vazão em kbps a partir do total de bytes e do tempo de download."""
    if time_s <= 0:
        return 0.0
    return (bytes_total * 8) / time_s / 1000


def ewma(prev: float, new_value: float, alpha: float = JITTER_EWMA_ALPHA) -> float:
    """Suaviza uma métrica usando média móvel exponencial."""
    return alpha * new_value + (1 - alpha) * prev


# ── Player principal ──────────────────────────────────────────────────────────
def run_player():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(GRAPHS_DIR, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUTPUT_DIR, f"metrics_{ts}.csv")

    # Campos exigidos pela especificação.
    # Cada linha do CSV representa um segmento baixado e o estado do player naquele momento.
    fieldnames = [
        "segment", "timestamp", "server_id", "quality", "bitrate_kbps",
        "vazao_kbps", "download_time_s", "jitter_network_ms", "jitter_ewma_ms",
        "buffer_level_s", "buffer_can_play", "rebuffer_event",
        "stall_duration_s", "failover_total",
    ]

    print("─" * 65)
    print(" Cliente ABR — Tarefa 1 (Rate-Based Baseline)")
    print("─" * 65)

    # 1. Manifest.
    # O manifest funciona como o "mapa" do vídeo: informa servidores, qualidades,
    # bitrates e duração de cada segmento.
    print(f"[manifest] GET {MANIFEST_URL}")
    manifest = fetch_manifest(MANIFEST_URL)
    segment_duration = manifest["segment_duration_s"]
    qualities = parse_representations(manifest)

    # Servidor ativo.
    # Nesta tarefa usamos o servidor de maior prioridade, sem troca automática.
    servers = sorted(manifest["servers"], key=lambda s: s["priority"])
    active_server = servers[0]
    base_url = active_server["url"]
    server_id = active_server["id"]

    print(f"[server]   {server_id} → {base_url}")
    print(f"[segment]  {segment_duration}s | {len(qualities)} qualidades disponíveis")
    print(f"[csv]      {csv_path}\n")

    # 2. Componentes principais do cliente.
    # ABR decide a qualidade, BufferManager controla reprodução e history guarda
    # as últimas vazões para deixar a decisão menos sensível a uma única medição.
    abr     = RateBasedABR()
    buffer  = BufferManager(max_buffer=60.0)
    history = deque(maxlen=5)   # Histórico de throughput com janela de 5 segmentos.

    # Estado de jitter EWMA entre segmentos.
    # A EWMA suaviza variações bruscas e ajuda a observar tendência de instabilidade.
    jitter_ewma_ms = 0.0

    # Marca o fim do segmento anterior para estimar variação entre downloads.
    t_prev_segment_end = None

    failover_total = 0

    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for seg_num in range(1, TOTAL_SEGMENTS + 1):

            # ── Seleção de qualidade ──────────────────────────────────────────
            # No primeiro segmento ainda não existe histórico; por isso começamos
            # em 240p. Depois disso, o ABR usa a média das últimas vazões medidas.
            if history:
                avg_throughput = sum(history) / len(history)
                selected_quality = abr.select_quality(avg_throughput, qualities)
            else:
                selected_quality = "240p"   # Partida inicial conservadora.

            bitrate_kbps = next(
                q["bitrate"] for q in qualities if q["name"] == selected_quality
            )
            url = get_url_for_quality(manifest, selected_quality, base_url)

            # ── Download do segmento ──────────────────────────────────────────
            # O segmento é baixado em chunks para medir tanto o tempo total quanto
            # a irregularidade de chegada dos dados dentro do próprio segmento.
            t_download_start = time.perf_counter()
            timestamp_iso = datetime.now().isoformat()

            try:
                total_bytes, download_time_s, jitter_network_ms = download_segment(url)
            except requests.RequestException as exc:
                print(f"  [ERRO] segmento {seg_num}: {exc}")
                continue

            # ── Throughput medido ─────────────────────────────────────────────
            # Vazão = quantidade de bits baixados dividida pelo tempo real gasto.
            vazao_kbps = calc_throughput_kbps(total_bytes, download_time_s)
            history.append(vazao_kbps)

            # ── Jitter EWMA entre segmentos ───────────────────────────────────
            # Além do jitter interno do download, mantemos uma média suavizada da
            # variação temporal entre segmentos consecutivos.
            if t_prev_segment_end is not None:
                inter_seg_gap_ms = (t_download_start - t_prev_segment_end) * 1000
                jitter_ewma_ms = ewma(jitter_ewma_ms, abs(inter_seg_gap_ms - (download_time_s * 1000)))
            t_prev_segment_end = time.perf_counter()

            # ── Buffer ────────────────────────────────────────────────────────
            # Adiciona ao buffer a duração de vídeo que acabou de chegar.
            buffer.add_segment(segment_duration)
            # Consome o tempo real de download, simulando o player tocando enquanto
            # espera o próximo segmento chegar.
            buffer.consume(download_time_s)

            buffer_level_s   = round(buffer.get_buffer_level(), 3)
            buffer_can_play  = 1 if buffer.can_play() else 0
            rebuffer_event   = 1 if buffer.is_rebuffering() else 0

            # Stall: se houve rebuffering, estima quanto tempo faltaria até voltar
            # ao mínimo de 2s necessário para tocar com segurança.
            if rebuffer_event:
                stall_duration_s = round(
                    max(0.0, buffer.MIN_BUFFER_TO_PLAY - buffer_level_s), 3
                )
            else:
                stall_duration_s = 0.0

            # ── Log terminal ──────────────────────────────────────────────────
            # Linha compacta para acompanhar a demo em tempo real.
            rebuf_mark = " ⚠ REBUFFER" if rebuffer_event else ""
            print(
                f"  seg {seg_num:03d} | {selected_quality:<5} | "
                f"vazao={vazao_kbps:7.1f} kbps | "
                f"buf={buffer_level_s:5.2f}s | "
                f"dl={download_time_s:.3f}s | "
                f"jitter={jitter_network_ms:.1f}ms{rebuf_mark}"
            )

            # ── CSV ───────────────────────────────────────────────────────────
            # Persiste as mesmas métricas do terminal com campos extras para análise
            # posterior e geração de gráficos.
            writer.writerow({
                "segment":          seg_num,
                "timestamp":        timestamp_iso,
                "server_id":        server_id,
                "quality":          selected_quality,
                "bitrate_kbps":     bitrate_kbps,
                "vazao_kbps":       round(vazao_kbps, 2),
                "download_time_s":  round(download_time_s, 4),
                "jitter_network_ms": round(jitter_network_ms, 2),
                "jitter_ewma_ms":   round(jitter_ewma_ms, 2),
                "buffer_level_s":   buffer_level_s,
                "buffer_can_play":  buffer_can_play,
                "rebuffer_event":   rebuffer_event,
                "stall_duration_s": stall_duration_s,
                "failover_total":   failover_total,
            })
            csvfile.flush()   # Garante que os dados apareçam no CSV em tempo real.

    print(f"\n[ok] CSV salvo em: {csv_path}")

    # 3. Gráficos automáticos.
    # Ao fim da execução, o script de gráficos transforma o CSV em evidências visuais.
    print("[ok] Gerando gráficos...")
    try:
        import subprocess
        graphs_script = os.path.join(os.path.dirname(__file__), "graphs.py")
        subprocess.run(
            ["python3", graphs_script, csv_path, "--output-dir", GRAPHS_DIR],
            check=True
        )
        print(f"[ok] Gráficos em: {GRAPHS_DIR}/")
    except Exception as exc:
        print(f"[aviso] Gráficos não gerados: {exc}")

    print("─" * 65)
    print(" Sessão concluída.")
    print("─" * 65)
    return csv_path


if __name__ == "__main__":
    run_player()
