"""Implementação do algoritmo Adaptive Bitrate (ABR)."""

from typing import List, Dict, Optional
from datetime import datetime


class RateBasedABR:
    """Algoritmo ABR baseado em vazão para seleção de qualidade."""

    SAFETY_FACTOR = 0.85  # Margem de segurança de 15% para evitar escolher acima da rede real
    DEFAULT_MIN_QUALITY = "240p"

    def __init__(self):
        """Inicializa o algoritmo e guarda o histórico de decisões."""
        self.decision_history = []
        self.current_quality = None

    def select_quality(
        self, throughput_kbps: float, qualities: List[Dict]
    ) -> str:
        """
        Seleciona a qualidade com base na vazão observada.

        Algoritmo:
        1. Calcula o limite seguro: vazão * SAFETY_FACTOR.
        2. Procura a maior qualidade cujo bitrate seja menor ou igual ao limite.
        3. Se nenhuma qualidade couber, usa a menor qualidade disponível.

        Argumentos:
            throughput_kbps: Vazão medida em kbps.
            qualities: Lista de qualidades com os campos 'name' e 'bitrate'.

        Retorna:
            Nome da qualidade selecionada, por exemplo '240p' ou '720p'.

        Erros:
            ValueError: Se a lista de qualidades estiver vazia ou malformada.
            TypeError: Se throughput_kbps não for numérico.
        """
        if not isinstance(throughput_kbps, (int, float)):
            raise TypeError(f"throughput_kbps must be numeric, got {type(throughput_kbps)}")

        if not qualities or len(qualities) == 0:
            raise ValueError("Qualities list is empty")

        # Valida se cada qualidade tem o formato esperado pelo algoritmo.
        for q in qualities:
            if not isinstance(q, dict) or "name" not in q or "bitrate" not in q:
                raise ValueError(f"Invalid quality format: {q}")

        # Aplica uma margem de segurança para não usar 100% da vazão medida.
        # Isso reduz a chance de rebuffering quando a rede oscila logo depois.
        safety_limit = throughput_kbps * self.SAFETY_FACTOR

        # Ordena as qualidades da menor para a maior taxa de bits.
        # Assim conseguimos percorrer todas e ficar com a melhor que ainda cabe.
        sorted_qualities = sorted(qualities, key=lambda q: q["bitrate"])

        # Seleciona a maior qualidade cujo bitrate não ultrapassa o limite seguro.
        selected_quality = None
        for quality in sorted_qualities:
            if quality["bitrate"] <= safety_limit:
                selected_quality = quality["name"]

        # Caso nem a menor qualidade caiba no limite, usa um fallback conservador.
        if selected_quality is None:
            # Dá preferência para 240p, que é a qualidade mínima esperada no projeto.
            min_qualities = [q for q in qualities if q["name"] == self.DEFAULT_MIN_QUALITY]
            if min_qualities:
                selected_quality = self.DEFAULT_MIN_QUALITY
            else:
                # Se 240p não existir no manifesto, usa a menor qualidade disponível.
                selected_quality = sorted_qualities[0]["name"]

        # Registra a decisão para análise posterior e para contar trocas de qualidade.
        self._record_decision(throughput_kbps, safety_limit, selected_quality)
        self.current_quality = selected_quality

        return selected_quality

    def _record_decision(
        self, throughput: float, limit: float, quality: str
    ) -> None:
        """
        Registra uma decisão de seleção de qualidade no histórico.

        Argumentos:
            throughput: Vazão medida no momento da decisão.
            limit: Limite seguro usado pelo algoritmo.
            quality: Qualidade selecionada.
        """
        decision = {
            "timestamp": datetime.now(),
            "throughput_kbps": throughput,
            "safety_limit_kbps": limit,
            "selected_quality": quality,
        }
        self.decision_history.append(decision)

    def get_decision_history(self) -> List[Dict]:
        """
        Retorna o histórico completo de decisões.

        Retorna:
            Lista de dicionários com vazão, limite seguro e qualidade escolhida.
        """
        return self.decision_history.copy()

    def get_last_decision(self) -> Optional[Dict]:
        """
        Retorna a última decisão de seleção de qualidade.

        Retorna:
            Dicionário da última decisão ou None se ainda não houve decisão.
        """
        if self.decision_history:
            return self.decision_history[-1].copy()
        return None

    def get_decision_count(self, quality: Optional[str] = None) -> int:
        """
        Conta decisões no total ou filtradas por uma qualidade específica.

        Argumentos:
            quality: Nome da qualidade usada como filtro. Se for None, retorna o total.

        Retorna:
            Número de decisões que correspondem ao filtro informado.
        """
        if quality is None:
            return len(self.decision_history)

        return sum(
            1 for d in self.decision_history if d["selected_quality"] == quality
        )

    def get_quality_switches(self) -> List[Dict]:
        """
        Retorna todas as trocas de qualidade registradas no histórico.

        Retorna:
            Lista com a qualidade anterior, a nova qualidade, timestamp e vazão.
        """
        if len(self.decision_history) < 2:
            return []

        switches = []
        for i in range(1, len(self.decision_history)):
            prev_quality = self.decision_history[i - 1]["selected_quality"]
            curr_quality = self.decision_history[i]["selected_quality"]

            if prev_quality != curr_quality:
                switches.append(
                    {
                        "from_quality": prev_quality,
                        "to_quality": curr_quality,
                        "timestamp": self.decision_history[i]["timestamp"],
                        "throughput_kbps": self.decision_history[i]["throughput_kbps"],
                    }
                )

        return switches

    def reset_history(self) -> None:
        """Limpa o histórico e remove a qualidade atual."""
        self.decision_history = []
        self.current_quality = None

    def __repr__(self) -> str:
        """Retorna uma representação resumida do estado do ABR."""
        return (
            f"RateBasedABR(current_quality={self.current_quality}, "
            f"decisions={len(self.decision_history)}, "
            f"safety_factor={self.SAFETY_FACTOR})"
        )
