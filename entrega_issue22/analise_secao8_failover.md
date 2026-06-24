# Secao 8 - Captura TCP e correlacao com o failover

## Artefatos utilizados

- Captura completa: `Resultados_log.pcapng`
- Recorte do evento: `failover_frames_984_985.pcapng`
- Log do terminal: `Terminal.txt`
- CSV de metricas: `metrics_20260623_205818.csv`
- Graficos: `buffer_level.png`, `quality_timeline.png`, `throughput_timeline.png`

## Evento observado no Wireshark

O failover foi identificado na captura TCP no instante em que a conexao com o Servidor A, porta 8080, foi encerrada e uma nova conexao com o Servidor B, porta 8081, foi iniciada.

Filtro usado no Wireshark:

```wireshark
frame.number == 984 or frame.number == 985
```

Eventos:

| Frame | Timestamp | Origem | Destino | Evento |
| --- | --- | --- | --- | --- |
| 984 | 2026-06-23 20:58:25.281283 | 192.168.0.53:39544 | 137.131.178.229:8080 | TCP FIN/ACK encerrando a conexao com o Servidor A |
| 985 | 2026-06-23 20:58:25.284419 | 192.168.0.53:44062 | 137.131.178.229:8081 | TCP SYN iniciando conexao com o Servidor B |

A diferenca entre os dois pacotes foi de aproximadamente 3,136 ms. Na captura nao foi observado RST nesse ponto; o encerramento da conexao com o Servidor A ocorreu por FIN/ACK.

## Correlacao com o CSV

No CSV, o segmento 14 ainda usa o Servidor A e possui `failover_total=0`:

```text
14,2026-06-23T20:58:25.281468,A,360p,400,1013.23,0.3948,22.22,22.54,14.61,1,0,0.0,0
```

Logo em seguida, o segmento 15 e registrado usando `srv-B` e `failover_total=1`:

```text
15,2026-06-23T20:58:26.212560,srv-B,480p,800,726.63,0.8257,27.15,23.92,14.17,1,0,0.0,1
```

Assim, a captura mostra a transicao TCP imediatamente apos o segmento 14, enquanto o CSV confirma que o segmento seguinte foi baixado do servidor de contingencia e que o contador acumulado de failovers foi incrementado para 1.

## Correlacao com o terminal

O log do terminal confirma que a falha artificial foi provocada no segmento 15:

```text
*** FORCANDO FALHA ARTIFICIAL no segmento 15 ***
Aviso: Falha detectada no Servidor A. Iniciando failover...
Migrado com sucesso para o Servidor srv-B. Re-tentando download...
```

## Interpretacao

Os tres registros sao consistentes entre si: no terminal, a falha e forçada no segmento 15; no Wireshark, a conexao com a porta 8080 e encerrada e uma nova conexao com a porta 8081 e aberta cerca de 3 ms depois; no CSV, o segmento 15 passa a usar `srv-B` e registra `failover_total=1`. Isso demonstra que o mecanismo de failover foi acionado e que a sessao continuou pelo servidor secundario.
