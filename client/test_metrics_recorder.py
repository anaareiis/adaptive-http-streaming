import os
import csv
from datetime import datetime
import pytest
from metrics import MetricsRecorder

def test_metrics_recorder_complete_flow(tmp_path):
    """
    Testa se o MetricsRecorder cria o ficheiro CSV com o cabeçalho correto,
    respeita o tamanho do lote (batch_size) em memória e grava os dados com precisão.
    """
    # 1. Configuração do ambiente de teste isolado usando tmp_path
    custom_log_dir = tmp_path / "test_logs"
    
    # Inicializa o gravador com um lote de tamanho 2 para testar o acionamento do flush
    recorder = MetricsRecorder(output_dir=str(custom_log_dir), batch_size=2)
    
    # Verifica se o ficheiro foi criado e se a pasta foi gerada automaticamente
    assert os.path.exists(recorder.filepath)
    
    # 2. Preparação de dados fictícios para simular os segmentos
    segmento_1 = {
        "segment_id": 1,
        "timestamp": "2026-05-19T22:00:01",
        "quality": "240p",
        "bitrate_kbps": 200,
        "throughput_kbps": 1884,
        "buffer_level_secs": 4.0,
        "rebuffering_occurred": False,
        "quality_changed": False
    }
    
    segmento_2 = {
        "segment_id": 2,
        "timestamp": "2026-05-19T22:00:05",
        "quality": "360p",
        "bitrate_kbps": 400,
        "throughput_kbps": 2909,
        "buffer_level_secs": 7.0,
        "rebuffering_occurred": False,
        "quality_changed": True
    }
    
    segmento_3 = {
        "segment_id": 3,
        "timestamp": "2026-05-19T22:00:10",
        "quality": "360p",
        "bitrate_kbps": 400,
        "throughput_kbps": 1500,
        "buffer_level_secs": 5.5,
        "rebuffering_occurred": True,
        "quality_changed": False
    }

    # 3. Execução do Teste de Escrita e Validação do Mecanismo de Buffer de Memória
    
    # Grava o segmento 1 -> Deve ficar apenas na memória (comprimento do buffer == 1)
    recorder.record_segment(segmento_1)
    assert len(recorder.buffer_data) == 1
    
    # Abre o ficheiro para verificar que ainda só contém o cabeçalho (não houve flush)
    with open(recorder.filepath, mode='r', encoding='utf-8') as f:
        linhas = list(csv.reader(f))
        assert len(linhas) == 1  # Apenas a linha do cabeçalho
        
    # Grava o segmento 2 -> Atinge o batch_size (2), deve forçar o flush automático para o disco
    recorder.record_segment(segmento_2)
    assert len(recorder.buffer_data) == 0  # Buffer limpo após o flush
    
    # Grava o segmento 3 -> Fica retido na memória (comprimento do buffer == 1)
    recorder.record_segment(segmento_3)
    assert len(recorder.buffer_data) == 1
    
    # Fecha o recorder -> Deve forçar o flush do segmento residual (segmento 3) antes de encerrar
    recorder.close()
    assert len(recorder.buffer_data) == 0

    # 4. Verificação Final do Conteúdo do Ficheiro CSV em Disco
    with open(recorder.filepath, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        linhas = list(reader)
        
        # Validação das colunas do cabeçalho
        cabecalho_esperado = [
            "segment_id", "timestamp", "quality", "bitrate_kbps", 
            "throughput_kbps", "buffer_level_secs", "rebuffering_occurred", "quality_changed"
        ]
        assert linhas[0] == cabecalho_esperado
        
        # Validação do total de linhas (Cabeçalho + 3 Segmentos = 4 linhas)
        assert len(linhas) == 4
        
        # Validação da exatidão dos dados do Segmento 1
        assert linhas[1][0] == "1"
        assert linhas[1][2] == "240p"
        assert linhas[1][4] == "1884"
        assert linhas[1][6] == "False"
        assert linhas[1][7] == "False"
        
        # Validação do Segmento 2 (onde a qualidade mudou)
        assert linhas[2][0] == "2"
        assert linhas[2][2] == "360p"
        assert linhas[2][7] == "True"
        
        # Validação do Segmento 3 (onde ocorreu rebuffer devido a quebra na rede)
        assert linhas[3][0] == "3"
        assert linhas[3][5] == "5.5"
        assert linhas[3][6] == "True"