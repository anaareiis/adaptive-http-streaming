import os
import random
from datetime import datetime
import time

# Importando os módulos reais que você já desenvolveu
from abr import RateBasedABR
from buffer_manager import BufferManager
from metrics import MetricsRecorder

# Diretórios na raiz do projeto (um nível acima de client/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
GRAPHS_DIR = os.path.join(BASE_DIR, "graphs")

def simulate_player_session():
    print("🚀 Iniciando simulação para gerar métricas reais...")

    # 1. Configurações Iniciais
    output_dir = LOGS_DIR
    metrics_file = os.path.join(output_dir, "metrics.csv")
    
    # Inicializa os componentes do seu projeto
    abr = RateBasedABR()
    buffer_manager = BufferManager(max_buffer=60.0)
    recorder = MetricsRecorder(output_dir=output_dir, batch_size=1) # Grava na hora
    
    # Qualidades simuladas extraídas do escopo do seu projeto
    qualities = [
        {"name": "240p", "bitrate": 200},
        {"name": "360p", "bitrate": 400},
        {"name": "480p", "bitrate": 800},
        {"name": "720p", "bitrate": 1200},
        {"name": "1080p", "bitrate": 2500},
    ]
    
    segment_duration = 4.0  # Chunks de 4 segundos comuns em TR2
    total_segments = 30     # Simular 2 minutos de vídeo
    
    # 2. Cenário de Rede Variável (Simulando oscilação real de internet)
    # Começa boa, cai drasticamente (gera rebuffer), depois recupera
    network_profile = (
        [3000.0] * 5 +   # 3 Mbps (Alta)
        [1500.0] * 5 +   # 1.5 Mbps (Média)
        [300.0] * 6 +    # 300 kbps (Crise / Vai travar o buffer)
        [900.0] * 4 +    # 900 kbps (Recuperando)
        [4000.0] * 10    # 4 Mbps (Excelente)
    )
    
    previous_quality = None
    elapsed_time = 0.0

    # 3. Loop do Player
    for seg_id in range(1, total_segments + 1):
        # Pega a vazão atual do perfil com uma leve variação aleatória de ruído
        measured_throughput = network_profile[seg_id - 1] * random.uniform(0.85, 1.15)
        
        # Algoritmo ABR escolhe a qualidade
        selected_quality = abr.select_quality(measured_throughput, qualities)
        
        # Encontra o bitrate correspondente
        bitrate_kbps = next(q["bitrate"] for q in qualities if q["name"] == selected_quality)
        
        # Verifica se mudou a qualidade
        quality_changed = (previous_quality is not None) and (selected_quality != previous_quality)
        
        # Atualiza o buffer: Adiciona o segmento baixado
        buffer_manager.add_segment(segment_duration)
        
        # Simula o consumo do buffer pelo player (passaram-se 4s de reprodução)
        # Se a rede estava ruim, o buffer cai
        download_time = (bitrate_kbps / measured_throughput) * segment_duration
        buffer_manager.consume(download_time)
        
        # Verifica se o player travou (Rebuffering)
        rebuffering_occurred = buffer_manager.is_rebuffering()
        
        # Incrementa o tempo do sistema
        elapsed_time += segment_duration
        
        # 4. Monta o dicionário com as 8 colunas exatas da sua Issue 6
        log_data = {
            "segment_id": seg_id,
            "timestamp": datetime.now().isoformat(),
            "quality": selected_quality,
            "bitrate_kbps": bitrate_kbps,
            "throughput_kbps": int(measured_throughput),
            "buffer_level_secs": round(buffer_manager.current_buffer, 2),
            "rebuffering_occurred": rebuffering_occurred,
            "quality_changed": quality_changed
        }
        
        # Grava os dados usando a sua classe MetricsRecorder
        recorder.record_segment(log_data)
        previous_quality = selected_quality
        
        print(f"Segmento {seg_id:02d} | Qualidade: {selected_quality:<5} | Buffer: {buffer_manager.current_buffer:>5.2f}s | Rede: {int(measured_throughput):>4} kbps")
        time.sleep(0.05) # Apenas para animação rápida no terminal
        
    recorder.close()
    print(f"\n✨ Métricas salvas em: {recorder.filepath}")

    # Gera gráficos automaticamente
    from graphs import generate_graphs
    generated = generate_graphs(recorder.filepath, output_dir=GRAPHS_DIR)
    print(f"📊 Gráficos salvos em: {GRAPHS_DIR}/")
    for path in generated.values():
        print(f"   {os.path.basename(path)}")

if __name__ == "__main__":
    simulate_player_session()