"""
Cliente de Streaming Adaptativo — Tarefa 1 (Issue 14 Compliant)
Conecta ao servidor real, baixa segmentos, mede vazão com timing por chunk,
calcula jitter (Network e EWMA), gerencia buffer e executa failover automático.
"""

import os
import math
import sys
import time
import argparse
import requests
from datetime import datetime

from abr import RateBasedABR, BufferBasedABR, HybridABR
from buffer_manager import BufferManager
from failover import FailoverManager
from metrics import MetricsRecorder, SPEC_HEADERS

# Parâmetros de rede e streaming
JITTER_EWMA_ALPHA = 0.3
CHUNK_SIZE = 4096

def fetch_manifest(url: str) -> dict:
    """Baixa o manifesto JSON contendo as qualidades, servidores e duracoes dos segmentos."""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()

def main():
    # Interface de Linha de Comando (CLI)
    parser = argparse.ArgumentParser(description="Cliente de Streaming Adaptativo — Issue 14")
    parser.add_argument(
        "--policy",
        default="rate-based",
        choices=["rate-based", "buffer-based", "hybrid"],
        help="Politica de ABR a ser utilizada (padrao: rate-based)"
    )
    parser.add_argument(
        "--segments", 
        type=int, 
        default=30, 
        help="Quantidade de segmentos para baixar (padrao: 30)"
    )
    parser.add_argument(
        "--output-dir", 
        default="logs", 
        help="Diretorio para salvar o arquivo CSV de metricas (padrao: logs)"
    )
    parser.add_argument(
        "--manifest",
        default="http://137.131.178.229:8080/manifest",
        help="URL do manifesto do servidor (padrao: oficial UnB)"
    )
    parser.add_argument(
        "--force-failover-at",
        type=int,
        default=None,
        help="Forca falha artificial no segmento especificado para testar failover (ex: 15)"
    )
    args = parser.parse_args()

    # Cria as pastas de logs e graficos se nao existirem
    os.makedirs(args.output_dir, exist_ok=True)
    graphs_dir = os.path.join(os.path.dirname(args.output_dir) if os.path.dirname(args.output_dir) else ".", "graphs")
    os.makedirs(graphs_dir, exist_ok=True)

    print("Iniciando cliente adaptativo...")
    print(f"   Manifesto: {args.manifest}")
    print(f"   Politica:  {args.policy}")
    print(f"   Segmentos: {args.segments}\n")

    # Download do Manifesto
    try:
        manifest = fetch_manifest(args.manifest)
    except Exception as e:
        print(f"Erro critico ao baixar manifesto: {e}")
        return

    # Tratamento e extração de representações de qualidade e bitrates do manifesto
    qualities = []
    if "representations" in manifest:
        for rep in manifest["representations"]:
            q_name = rep.get("quality") or rep.get("name") or "unknown"
            q_bitrate = rep.get("bitrate") or rep.get("bitRate") or rep.get("bandwidth")
            
            if q_bitrate is not None:
                try:
                    q_bitrate = int(q_bitrate)
                except ValueError:
                    q_bitrate = None

            # Fallback baseado na resolução caso o bitrate venha nulo
            if q_bitrate is None:
                if "1080" in str(q_name): q_bitrate = 2500
                elif "720" in str(q_name): q_bitrate = 1200
                elif "480" in str(q_name): q_bitrate = 800
                elif "360" in str(q_name): q_bitrate = 400
                else: q_bitrate = 200

            qualities.append({
                "name": q_name,
                "bitrate": q_bitrate
            })
    elif "qualities" in manifest:
        for q in manifest["qualities"]:
            qualities.append({
                "name": q.get("name", "unknown"),
                "bitrate": int(q.get("bitrate", 200))
            })

    # Definição de qualidades padrão caso o parse falhe por completo
    if not qualities:
        print("Aviso: Nenhuma qualidade valida extraida. Usando qualidades padrao.")
        qualities = [
            {"name": "240p", "bitrate": 200},
            {"name": "360p", "bitrate": 400},
            {"name": "480p", "bitrate": 800},
            {"name": "720p", "bitrate": 1200},
            {"name": "1080p", "bitrate": 2500},
        ]

    # Extração de servidores de contingência e duração de segmento
    servers = manifest.get("servers", [])
    if not servers:
        servers = [
            {"id": "A", "url": "http://137.131.178.229:8080", "priority": 1},
            {"id": "B", "url": "http://137.131.178.229:8081", "priority": 2}
        ]

    if "segment" in manifest and "duration" in manifest["segment"]:
        segment_duration = float(manifest["segment"]["duration"])
    elif "segment_duration" in manifest:
        segment_duration = float(manifest["segment_duration"])
    else:
        segment_duration = 4.0

    # Inicialização das classes de controle do player
    if args.policy == "rate-based":
        abr = RateBasedABR()
    elif args.policy == "buffer-based":
        abr = BufferBasedABR()
    else:
        abr = HybridABR()

    buffer_manager = BufferManager(max_buffer=15.0)
    failover = FailoverManager(servers)
    
    # Cabeçalho completo exigido pela especificação (seção 8.3)
    csv_path = os.path.join(args.output_dir, "metrics.csv")
    recorder = MetricsRecorder(output_dir=args.output_dir, batch_size=1, headers=SPEC_HEADERS)

    # Estado inicial das variáveis de medição de rede
    jitter_ewma_ms = 0.0
    vazao_kbps = 1000.0  # Estimativa inicial de partida (1 Mbps)

    # Loop de execução principal orientado a segmentos de mídia
    for seg_index in range(1, args.segments + 1):
        # Tomada de decisão da qualidade através do algoritmo ABR selecionado
        # (vazao_kbps e jitter_ewma_ms vêm da medição do segmento anterior)
        if args.policy == "rate-based":
            selected_quality = abr.select_quality(vazao_kbps, qualities)
        elif args.policy == "buffer-based":
            selected_quality = abr.select_quality(buffer_manager.current_buffer, qualities)
        else:
            selected_quality = abr.select_quality(
                vazao_kbps, jitter_ewma_ms, buffer_manager.current_buffer, qualities
            )

        bitrate_kbps = next((q["bitrate"] for q in qualities if q["name"] == selected_quality), 200)

        # Resolução do endpoint do servidor atual baseado em prioridade e sanidade
        active_server = failover.current_server
        server_url = active_server["url"].rstrip("/")
        server_id = active_server.get("id", "A")

        # FORCAR FALHA ARTIFICIAL para teste de failover (Issue 22)
        if args.force_failover_at and seg_index == args.force_failover_at:
            segment_url = "http://127.0.0.1:9999/segment/force_fail"  # URL impossivel
            print(f"\n*** FORCANDO FALHA ARTIFICIAL no segmento {seg_index} ***", flush=True)
        else:
            segment_url = f"{server_url}/segment/{selected_quality}"

        print(f"[{seg_index:02d}/{args.segments}] Requisitando {selected_quality} de Servidor {server_id}...", end="", flush=True)

        buffer_antes = buffer_manager.current_buffer
        chunk_timestamps = []
        bytes_received = 0
        download_start = time.perf_counter()
        response_success = False

        # Download por chunks com stream habilitado para medição de vazão real e jitter
        try:
            resp = requests.get(segment_url, stream=True, timeout=5.0)
            if resp.status_code == 200:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        chunk_timestamps.append(time.perf_counter())
                        bytes_received += len(chunk)
                response_success = True
            else:
                print(f" Erro HTTP {resp.status_code}")
        except (requests.RequestException, Exception) as e:
            print(f" Erro de Conexao: {e}")

        # Mecanismo de failover automático caso a primeira requisição falhe
        if not response_success:
            print(f"\nAviso: Falha detectada no Servidor {server_id}. Iniciando failover...")
            migrated = failover.try_failover(segment=seg_index)
            if migrated:
                new_server = failover.current_server
                server_id = new_server.get("id", "B")
                segment_url = f"{new_server['url'].rstrip('/')}/segment/{selected_quality}"
                print(f"Migrado com sucesso para o Servidor {server_id}. Re-tentando download...")

                chunk_timestamps = []
                bytes_received = 0
                download_start = time.perf_counter()
                try:
                    resp = requests.get(segment_url, stream=True, timeout=5.0)
                    resp.raise_for_status()
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            chunk_timestamps.append(time.perf_counter())
                            bytes_received += len(chunk)
                    response_success = True
                except Exception as e:
                    print(f"Falha catastrofica: Servidor de contingencia tambem falhou. {e}")
            else:
                print("Falha catastrofica: Nenhum servidor secundario passou no Health Check.")

        download_end = time.perf_counter()
        download_time_s = download_end - download_start

        # Fallback temporal em caso de timeout/queda total (sem bytes recebidos)
        if not response_success:
            download_time_s = segment_duration * 2

        # Vazão medida a partir dos bytes reais recebidos / tempo decorrido
        vazao_kbps = (bytes_received * 8) / (download_time_s * 1000) if download_time_s > 0 else 0.1

        # Cálculo estatístico de variação de atraso (Jitter) entre chunks
        jitter_network_ms = 0.0
        if len(chunk_timestamps) >= 2:
            intervals = [t2 - t1 for t1, t2 in zip(chunk_timestamps, chunk_timestamps[1:])]
            if len(intervals) >= 2:
                variations = [abs(i2 - i1) for i1, i2 in zip(intervals, intervals[1:])]
                jitter_network_ms = (sum(variations) / len(variations)) * 1000.0

        # Aplicação do filtro EWMA estabilizador de Jitter
        if seg_index == 1:
            jitter_ewma_ms = jitter_network_ms
        else:
            jitter_ewma_ms = (JITTER_EWMA_ALPHA * jitter_network_ms) + ((1.0 - JITTER_EWMA_ALPHA) * jitter_ewma_ms)

        # Atualização do modelo temporal do buffer do player
        buffer_manager.add_segment(segment_duration)
        buffer_manager.consume(download_time_s)

        # Detecção matemática de travamentos na reprodução (Stall e Rebuffering)
        # Trava se o download demorou mais que o buffer disponível antes dele
        stall_duration_s = max(0.0, download_time_s - buffer_antes)
        rebuffer_event = 1 if stall_duration_s > 0 or buffer_manager.is_rebuffering() else 0
        buffer_can_play = 1 if buffer_manager.can_play() else 0

        print(f" OK | Vazao: {vazao_kbps:.1f} kbps | Buffer: {buffer_manager.current_buffer:.2f}s | Stall: {stall_duration_s:.2f}s")

        # Escrita incremental dos dados no registrador de métricas (CSV)
        recorder.record_segment({
            "segment":            seg_index,
            "timestamp":          datetime.now().isoformat(),
            "server_id":          server_id,
            "quality":            selected_quality,
            "bitrate_kbps":       bitrate_kbps,
            "vazao_kbps":         round(vazao_kbps, 2),
            "download_time_s":    round(download_time_s, 4),
            "jitter_network_ms":  round(jitter_network_ms, 2),
            "jitter_ewma_ms":     round(jitter_ewma_ms, 2),
            "buffer_level_s":     round(buffer_manager.current_buffer, 2),
            "buffer_can_play":    buffer_can_play,
            "rebuffer_event":     rebuffer_event,
            "stall_duration_s":   round(stall_duration_s, 4),
            "failover_total":     failover.total_failovers,
        })

    recorder.close()
    print(f"\nSimulacao concluida. CSV salvo com sucesso em: {csv_path}")

    # Processamento automático dos gráficos individuais chamando o subprocesso graphs.py
    print("Gerando graficos...")
    try:
        import subprocess
        graphs_script = os.path.join(os.path.dirname(__file__), "graphs.py")
        abs_csv_path = os.path.abspath(recorder.filepath)
        abs_graphs_dir = os.path.abspath("graphs")
        
        os.makedirs(abs_graphs_dir, exist_ok=True)
        
        subprocess.run(
            [sys.executable, graphs_script, abs_csv_path, "--output-dir", abs_graphs_dir],
            check=True
        )
        print(f"Graficos gerados com sucesso na pasta: {abs_graphs_dir}")
    except Exception as e:
        print(f"Falha ao gerar graficos automaticamente: {e}")
        print(f"Dica: Voce pode gerar manualmente rodando: python client/graphs.py {recorder.filepath} --output-dir graphs")

if __name__ == "__main__":
    main()