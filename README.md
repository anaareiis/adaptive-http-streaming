# Adaptive HTTP Streaming

Projeto final da disciplina Teleinformática e Redes 2 (TR2).

## Objetivo

Implementar um cliente de streaming adaptativo utilizando técnicas de Adaptive Bitrate Streaming (ABR) sobre HTTP, incluindo:

- Medição de throughput e jitter (EWMA)
- Gestão de buffer com detecção de rebuffering
- Três algoritmos ABR: Rate-Based, Buffer-Based e HybridABR
- Failover automático entre servidores
- Coleta de métricas em CSV
- Visualização estática e ao vivo dos resultados

## Instalação

```bash
pip install -r requirements.txt
```

## Como rodar

### Simulação completa (3 políticas)

Roda as 3 políticas sequencialmente e gera os gráficos individuais e comparativos:

```bash
python3 client/run_simulation.py
```

### Cliente real (conecta ao servidor)

```bash
# Escolha a política: rate_based | buffer_based | hybrid
python3 client/main.py --policy hybrid --segments 30

# Com failover forçado no segmento N (para testes)
python3 client/main.py --policy hybrid --segments 30 --force-failover-at 15
```

### Gráficos a partir de um CSV

```bash
python3 client/graphs.py logs/hybrid/metrics_*.csv --output-dir graphs/hybrid
```

### Gráfico comparativo entre políticas

```bash
python3 client/graphs.py --compare logs/rate_based/metrics_*.csv logs/buffer_based/metrics_*.csv logs/hybrid/metrics_*.csv \
  --labels "Rate-Based" "Buffer-Based" "Hybrid" --output-dir graphs/comparison
```

### Visualização ao vivo (durante a simulação)

```bash
# Terminal 1 — inicia a simulação
python3 client/main.py --policy hybrid --segments 60

# Terminal 2 — abre o gráfico e atualiza a cada 1.5 s
python3 client/live_graph.py --policy hybrid
```

### Testes

```bash
cd client && python3 -m pytest -v
```

## Estrutura do Projeto

```
adaptive-streaming/
├── client/
│   ├── abr.py               # Políticas ABR: RateBasedABR, BufferBasedABR, HybridABR
│   ├── buffer_manager.py    # Gestão de buffer e detecção de rebuffering
│   ├── failover.py          # Failover automático entre servidores
│   ├── manifest_parser.py   # Parser do manifest JSON
│   ├── metrics.py           # ThroughputMeter e MetricsRecorder (CSV)
│   ├── graphs.py            # Geração de gráficos estáticos a partir do CSV
│   ├── live_graph.py        # Gráfico ao vivo atualizado em tempo real
│   ├── main.py              # Cliente real (conecta ao servidor HTTP)
│   └── run_simulation.py    # Simulação das 3 políticas com geração de gráficos
│
├── graphs/
│   ├── rate_based/          # Gráficos da Política 1
│   ├── buffer_based/        # Gráficos da Política 2
│   ├── hybrid/              # Gráficos da Política 3 (simulação normal)
│   ├── hybrid_failover/     # Gráficos da Política 3 com evento de failover
│   └── comparison/          # Gráficos comparativos das 3 políticas
│
├── logs/
│   ├── rate_based/          # CSVs da Política 1
│   ├── buffer_based/        # CSVs da Política 2
│   ├── hybrid/              # CSVs da Política 3
│   └── hybrid_failover/     # CSV da sessão com failover
│
├── entrega_issue22/         # Evidências Wireshark (capturas TCP, análise de failover)
├── requirements.txt
└── README.md
```

## Políticas ABR

| Política | Classe | Parâmetros principais |
|---|---|---|
| Rate-Based (P1) | `RateBasedABR` | `SAFETY_FACTOR=0.85` |
| Buffer-Based (P2) | `BufferBasedABR` | `RESERVOIR=6s`, `CUSHION=40s` |
| HybridABR (P3) | `HybridABR` | `EWMA α=0.3`, `jitter k=2.0`, `RESERVOIR=6s` |

## Tecnologias

- Python 3, HTTP, TCP
- Matplotlib, Pandas
- Wireshark (análise de captura TCP)
