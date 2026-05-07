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

## Estrutura do Projeto

```
adaptive-streaming/
├── client/                 # Implementação do cliente DASH/ABR
│   ├── abr.py
│   ├── buffer_manager.py
│   ├── manifest_parser.py
│   ├── metrics.py
│   ├── player.py
│   └── main.py
├── logs/                   # Métricas em CSV
├── graphs/                 # Gráficos gerados
├── reports/                # Documentação e relatórios
├── requirements.txt
├── README.md
└── .gitignore
```

## Tecnologias

- Python 3
- HTTP
- TCP
- CSV
- Matplotlib