# Adaptive HTTP Streaming

Projeto final da disciplina Teleinformática e Redes 2 (TR2).

## Objetivo

Implementar um cliente de streaming adaptativo utilizando técnicas de Adaptive Bitrate Streaming (ABR) sobre HTTP, incluindo:

- Medição de throughput
- Gestão de buffer
- Algoritmos ABR
- Failover entre servidores
- Coleta de métricas
- Análise experimental

## Como rodar

### Instalação

```bash
pip install -r requirements.txt
```

### Simulação local (sem servidor)

Roda a Política 1 (Rate-Based) com um perfil de rede variável simulado e gera os gráficos automaticamente.

**A partir da raiz do projeto** (`adaptive-streaming/`):

```bash
python3 client/run_simulation.py
```

Ou de dentro de `client/`:

```bash
cd client
python3 run_simulation.py
```

Os arquivos gerados ficam em:
- `logs/metrics_YYYYMMDD_HHMMSS.csv` — métricas por segmento
- `graphs/throughput_timeline.png` — vazão e qualidade ao longo do tempo
- `graphs/quality_timeline.png` — qualidade selecionada
- `graphs/buffer_level.png` — nível do buffer
- `graphs/quality_distribution.png` — distribuição de tempo por qualidade
- `graphs/throughput_histogram.png` — histograma de vazão

### Rodar os testes

```bash
cd client
python3 -m pytest -v
```

## Estrutura do Projeto

```
adaptive-streaming/
├── client/
│   ├── abr.py              # Políticas ABR (RateBasedABR, BufferBasedABR)
│   ├── buffer_manager.py   # Gestão de buffer com detecção de rebuffering
│   ├── manifest_parser.py  # Parser do manifest JSON (formatos v1 e v2.0)
│   ├── metrics.py          # ThroughputMeter e MetricsRecorder (CSV)
│   ├── graphs.py           # Geração de gráficos a partir do CSV
│   ├── run_simulation.py   # Simulação local com perfil de rede variável
│   ├── main.py             # Cliente real (conecta ao servidor)
│   └── failover.py         # Failover automático entre servidores
├── logs/                   # CSVs gerados pelas simulações
├── graphs/                 # PNGs gerados pelos gráficos
├── reports/                # Relatórios e documentação
├── requirements.txt
└── README.md
```

## Tecnologias

- Python 3
- HTTP
- TCP
- CSV
- Matplotlib