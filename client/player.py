import os
import time
import requests
from datetime import datetime
from abr import RateBasedABR
from buffer_manager import BufferManager
from metrics import MetricsRecorder

def run_live_player(manifest_url):
    # 1. Inicializa os componentes
    abr = RateBasedABR()
    buffer_manager = BufferManager(max_buffer=60.0)
    recorder = MetricsRecorder(output_dir="logs", batch_size=1)
    
    # Lista de qualidades extraída do manifesto do professor (exemplo básico)
    qualities = [
        {"name": "240p", "bitrate": 200},
        {"name": "480p", "bitrate": 400},
        {"name": "1080p", "bitrate": 1200},
    ]
    
    # baixar pelo menos 10 segmentos
    total_segments = 10 
    measured_throughput = 1000.0 # Valor inicial de partida (1 Mbps)
    previous_quality = None

    print(f"🎬 Iniciando Player Real conectando em: {manifest_url}")

    for seg_id in range(1, total_segments + 1):
        # ABR escolhe a melhor qualidade com base na última medição de vazão
        selected_quality = abr.select_quality(measured_throughput, qualities)
        bitrate_kbps = next(q["bitrate"] for q in qualities if q["name"] == selected_quality)
        quality_changed = (previous_quality is not None) and (selected_quality != previous_quality)

        # -------------------------------------------------------------
        # MUDANÇA DA DEMO: DOWNLOAD REAL DO SEGMENTO VIA HTTP
        # -------------------------------------------------------------
        # Monta a URL do chunk correspondente (o formato exato depende do servidor do prof)
        segment_url = f"{manifest_url}/segment_{selected_quality}_{seg_id}.m4s"
        
        start_time = time.time()
        try:
            response = requests.get(segment_url, timeout=5)
            response.raise_for_status()
            
            # Tamanho do arquivo baixado em bits
            file_size_bits = len(response.content) * 8
            # Tempo exato gasto na transferência de rede
            download_time = time.time() - start_time
            
            # Cálculo real da vazão obtida (kbps)
            measured_throughput = (file_size_bits / download_time) / 1000.0
            
        except Exception as e:
            print(f"❌ Erro ao baixar segmento {seg_id}: {e}")
            # Em caso de falha de rede, assume um valor baixo de segurança
            measured_throughput = 100.0 
            download_time = 4.0 
        # -------------------------------------------------------------

        # Atualiza a lógica do buffer com o tempo real gasto no download
        segment_duration = 4.0 # Duração do vídeo contido no chunk
        buffer_manager.add_segment(segment_duration)
        buffer_manager.consume(download_time)
        
        # Monta o dicionário com as 8 colunas exatas exigidas na Issue 6
        log_data = {
            "segment_id": seg_id,
            "timestamp": datetime.now().isoformat(),
            "quality": selected_quality,
            "bitrate_kbps": bitrate_kbps,
            "throughput_kbps": int(measured_throughput),
            "buffer_level_secs": round(buffer_manager.current_buffer, 2),
            "rebuffering_occurred": buffer_manager.is_rebuffering(),
            "quality_changed": quality_changed
        }
        
        recorder.record_segment(log_data)
        previous_quality = selected_quality
        
        print(f"📦 Chunk {seg_id:02d}/{total_segments} ({selected_quality}) baixado em {download_time:.2f}s | Rede: {int(measured_throughput)} kbps")
        
    recorder.close()
    print("✨ Download dos 10 segmentos concluído e CSV salvo com sucesso!")

if __name__ == "__main__":
    # Na apresentação, vocês vão alterar para a URL real fornecida pelo professor
    SERVER_URL = "http://localhost:8080" 
    run_live_player(SERVER_URL)
