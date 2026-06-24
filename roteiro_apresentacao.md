# Roteiro de Apresentação — TR2 Adaptive Streaming

## Antes de apresentar

Abrir dois terminais na pasta do projeto e deixar os comandos prontos, **sem rodar ainda**:

```bash
# Terminal 1 — simulação
python3 client/main.py --segments 60 --policy hybrid

# Terminal 2 — gráfico ao vivo
python3 client/live_graph.py --policy hybrid
```

---

## 1. "O que mudou da P2 para a P3?"

**Problema da P2:** ela só olha para o buffer. Se a rede cair abruptamente, o buffer precisa esvaziar antes de qualquer reação — a política é cega ao estado da rede.

**O que a P3 resolve:**

| Critério | P2 (Buffer-Based) | P3 (HybridABR) |
|---|---|---|
| Trocas de qualidade | 1 (ficou em 360p o tempo todo) | 2 (subiu: 240p → 360p → 480p) |
| Reação à rede | Só depois que o buffer cai | Preventiva via EWMA |
| Instabilidade de jitter | Não verifica | Penaliza antes de subir |
| Proteção de buffer | Sim (regra principal) | Sim (RESERVOIR = 6 s) |

> Dado real: P2 ficou em 360p mesmo com rede boa. P3 subiu para 480p quando a rede permitiu.

---

## 2. Perguntas teóricas

### "Como funciona a Política 3?"

Três critérios combinados:

1. **EWMA da vazão** (α=0.3) — média móvel exponencial para estimar o que a rede vai aguentar no próximo segmento, sem reagir a picos isolados.
2. **Proteção de buffer** — se o buffer cair abaixo de 6 s (RESERVOIR), força qualidade mínima independente da rede.
3. **Penalidade de jitter** — se a rede estiver instável, desconta o score antes de subir de qualidade. Fórmula: `score = bitrate × (1 - k × jitter_normalizado)`, com k=2.0.

> *"A P3 escolhe a maior qualidade que a rede aguenta, mas só sobe se a rede estiver estável e o buffer estiver seguro."*

---

### "Por que o buffer fica parado no teto (~14.6 s)?"

Comportamento correto. O player tem limite de buffer (MAX_BUFFER ≈ 15 s). Quando está cheio, para de baixar por um instante para não desperdiçar banda. No gráfico aparece como a linha roxa plana — é o controle de fluxo do DASH.

---

### "Como vocês identificaram o failover no Wireshark?"

Filtro usado:
```
frame.number == 984 or frame.number == 985
```

| Frame | Evento |
|---|---|
| 984 | TCP FIN/ACK encerrando conexão com Servidor A (porta 8080) |
| 985 | TCP SYN iniciando conexão com Servidor B (porta 8081) |

Diferença de tempo: **3.136 ms**. O CSV confirma: segmento 14 no Servidor A com `failover_total=0`, segmento 15 em srv-B com `failover_total=1`.

---

## 3. Simulação

**Rodar Terminal 2 primeiro** (gráfico abre aguardando dados), depois Terminal 1:

```bash
# Terminal 2 — abre o gráfico (deixar visível)
python3 client/live_graph.py --policy hybrid

# Terminal 1 — inicia a simulação
python3 client/main.py --segments 60 --policy hybrid
```

O gráfico atualiza a cada 1.5 s. O título mostra o estado atual em tempo real:
`seg 12 | servidor: A | qualidade: 480p | buffer: 14.6 s`

**Se o professor pedir failover** — parar e rodar:
```bash
python3 client/main.py --segments 30 --policy hybrid --force-failover-at 15
```

---

## 4. Perguntas sobre a simulação

### "O que cada coisa no gráfico significa?"

- **Área roxa** — nível do buffer em segundos (eixo esquerdo)
- **Pontilhado azul** — vazão medida em kbps (eixo direito)
- **Degrau verde** — qualidade selecionada em bitrate nominal (eixo direito)
- **Linha vermelha** — rebuffering (buffer zerou, player parou)
- **Linha laranja tracejada** — failover (troca de servidor)

---

### "O que acontece quando o servidor cai?"

Apontar para o gráfico no segmento 15:
- Linha **laranja** aparece = troca de servidor confirmada
- Pontilhado **azul** cai um pouco = servidor B tem menos capacidade (~700 kbps vs ~1000 kbps)
- Área **roxa** cai de 14.6 s para 14.2 s = **sem rebuffering**, queda de só 0.44 s de buffer
- Degrau **verde** sobe para 480p no failover e estabiliza em 360p = política conservadora no novo servidor

> Handoff em **3.136 ms** — o usuário não perceberia nada.

---

### Números para citar

| Métrica | Rate-Based (P1) | Buffer-Based (P2) | Hybrid P3 |
|---|---|---|---|
| Trocas de qualidade | 4 | 1 | 2 |
| Qualidade modal | 480p | 360p | 360p |
| Buffer mínimo | 3.47 s | 3.75 s | 3.76 s |
| Rebuffering | 1 | 1 | 1 |
| Handoff no failover | — | — | **3.136 ms** |
| Queda de buffer no failover | — | — | **0.44 s** |
