"""
Simulador de Rede de Filas (topologia arbitrária via YAML)
- Multi-seed correto (cada seed independente, agregado ao final)
- Prioridade de eventos em empates: SAIDA < PASSAGEM < CHEGADA
- Inicia múltiplos serviços no mesmo timestamp
- Não credita 0→t0 no estado 0
- Consome exatamente rndnumbersPerSeed por seed

Requisitos: Python 3.9+ e PyYAML (pip install pyyaml)
"""

import random
import heapq
import yaml
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------- Núcleo do simulador ---------------------------- #

class TipoEvento(Enum):
    CHEGADA = "chegada"
    SAIDA = "saida"
    PASSAGEM = "passagem"


# prioridade por tipo (menor = processa antes)
_TIPO_PRI = {
    TipoEvento.SAIDA: 0,
    TipoEvento.PASSAGEM: 1,
    TipoEvento.CHEGADA: 2,
}

_seq_counter = 0  # para desempate estável no heap


@dataclass(order=True)
class Evento:
    # sort key explícita para o heap: (tempo, prioridade_tipo, seq)
    sort_index: tuple = field(init=False, repr=False)
    tempo: float
    tipo: TipoEvento = field(compare=False)
    fila_origem: str = field(compare=False)
    fila_destino: Optional[str] = field(default=None, compare=False)
    _seq: int = field(default=0, compare=False, repr=False)

    def __post_init__(self):
        self.sort_index = (self.tempo, _TIPO_PRI[self.tipo], self._seq)

    def __repr__(self):
        dst = f"->{self.fila_destino}" if self.fila_destino else ""
        return f"Evento({self.tipo.value}, t={self.tempo:.4f}, {self.fila_origem}{dst})"


class Fila:
    def __init__(
        self,
        nome: str,
        servidores: int,
        capacidade: Optional[int],
        min_chegada: Optional[float],
        max_chegada: Optional[float],
        min_servico: float,
        max_servico: float,
    ):
        self.nome = nome
        self.num_servidores = servidores
        self.capacidade = float(
            "inf") if capacidade is None or capacidade < 0 else capacidade
        self.min_chegada = min_chegada
        self.max_chegada = max_chegada
        self.min_servico = min_servico
        self.max_servico = max_servico

        # estado
        self.clientes_no_sistema = 0
        self.servidores_ocupados: List[float] = []   # instantes de término

        # métricas
        self.clientes_recebidos = 0
        self.clientes_atendidos = 0
        self.clientes_perdidos = 0
        self.tempo_por_estado = defaultdict(float)
        self.ultimo_tempo_atualizacao = 0.0

        # roteamento
        self.destinos: Dict[str, float] = {}

    def get_status(self) -> int:
        return self.clientes_no_sistema

    def get_capacity(self) -> float:
        return self.capacidade

    def get_servers(self) -> int:
        return self.num_servidores

    def increment_loss(self):
        self.clientes_perdidos += 1

    def add_customer(self):
        self.clientes_no_sistema += 1
        self.clientes_recebidos += 1

    def remove_customer(self):
        if self.clientes_no_sistema > 0:
            self.clientes_no_sistema -= 1
            self.clientes_atendidos += 1

    def tem_espaco(self) -> bool:
        return self.clientes_no_sistema < self.capacidade

    def tem_servidor_livre(self) -> bool:
        return len(self.servidores_ocupados) < self.num_servidores

    def atualizar_tempo_estado(self, tempo_atual: float):
        delta = tempo_atual - self.ultimo_tempo_atualizacao
        if delta < 0:
            delta = 0
        self.tempo_por_estado[self.clientes_no_sistema] += delta
        self.ultimo_tempo_atualizacao = tempo_atual


class Escalonador:
    def __init__(self):
        self.eventos: List[Evento] = []

    def adicionar_evento(self, evento: Evento):
        heapq.heappush(self.eventos, evento)

    def proximo_evento(self) -> Optional[Evento]:
        if self.eventos:
            return heapq.heappop(self.eventos)
        return None

    def tem_eventos(self) -> bool:
        return len(self.eventos) > 0

    def limpar(self):
        self.eventos.clear()


# ------------------------------ Simulador ----------------------------------- #

class Simulador:
    def __init__(self, arquivo_yaml: Optional[str] = None):
        self._cfg = None
        self.filas: Dict[str, Fila] = {}
        self.escalonador = Escalonador()
        self.tempo_atual = 0.0

        # orçamento de aleatórios (por seed)
        self.contador_aleatorios = 0
        self.limite_aleatorios = 100000

        # config atual
        self.chegadas_iniciais: Dict[str, float] = {}
        self.usar_seed = False
        self.seed = None

        # agregados
        self._agregado_tempo_por_estado: Dict[str, Dict[int, float]] = {}
        self._agregado_perdas: Dict[str, int] = {}
        self._media_tempo_global: float = 0.0
        self._seeds_usadas: List[int] = []

        if arquivo_yaml:
            self.carregar_configuracao(arquivo_yaml)

    # ------------------------------ Configuração ----------------------------- #
    def carregar_configuracao(self, arquivo: str):
        with open(arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read()
            marca = "!PARAMETERS"
            i = conteudo.find(marca)
            if i != -1:
                conteudo = conteudo[i + len(marca):]
            cfg = yaml.safe_load(conteudo)

        self._cfg = cfg
        self._reset_from_cfg(cfg, apply_seed=False)  # não aplicar seed aqui!

    def _reset_from_cfg(self, cfg: dict, apply_seed: bool):
        """Reconstrói TODA a rede a partir de uma config crua (usada a cada seed)."""
        self.filas = {}
        self.escalonador = Escalonador()
        self.tempo_atual = 0.0
        self.contador_aleatorios = 0

        self.limite_aleatorios = int(
            cfg.get("rndnumbersPerSeed", self.limite_aleatorios))
        self.chegadas_iniciais = dict(cfg.get("arrivals", {}))

        # filas
        for nome_fila, p in cfg.get("queues", {}).items():
            self.filas[nome_fila] = Fila(
                nome=nome_fila,
                servidores=int(p["servers"]),
                capacidade=p.get("capacity"),
                min_chegada=p.get("minArrival"),
                max_chegada=p.get("maxArrival"),
                min_servico=float(p["minService"]),
                max_servico=float(p["maxService"]),
            )

        # rede/roteamento
        for con in cfg.get("network", []):
            origem = con["source"]
            destino = con["target"]
            prob = float(con["probability"])
            if origem in self.filas:
                self.filas[origem].destinos[destino] = prob

        # seed só se solicitado explicitamente
        if apply_seed:
            if self.seed is None:
                random.seed()
                self.usar_seed = False
            else:
                random.seed(self.seed)
                self.usar_seed = True

    # ------------------------ Geração pseudo-aleatória ----------------------- #
    def ainda_pode_sortear(self, n: int = 1) -> bool:
        return self.contador_aleatorios + n <= self.limite_aleatorios

    def gerar_aleatorio(self) -> Optional[float]:
        if not self.ainda_pode_sortear():
            return None
        self.contador_aleatorios += 1
        return random.random()

    def gerar_tempo_chegada(self, fila: Fila) -> Optional[float]:
        r = self.gerar_aleatorio()
        if r is None:
            return None
        return fila.min_chegada + r * (fila.max_chegada - fila.min_chegada)

    def gerar_tempo_servico(self, fila: Fila) -> Optional[float]:
        r = self.gerar_aleatorio()
        if r is None:
            return None
        return fila.min_servico + r * (fila.max_servico - fila.min_servico)

    # ------------------------------- Roteamento ------------------------------ #
    def determinar_destino(self, fila: Fila) -> Optional[str]:
        if not fila.destinos:
            return None
        r = self.gerar_aleatorio()
        if r is None:
            return None
        acc = 0.0
        for destino, p in fila.destinos.items():
            acc += p
            if r < acc:
                return destino
        return None  # sobra = saída do sistema

    # --------------------------- Processamento EVT --------------------------- #
    def acumula_tempo(self, tempo_evento: float):
        for fila in self.filas.values():
            fila.atualizar_tempo_estado(tempo_evento)
        self.tempo_atual = tempo_evento

    def _push(self, evento: Evento):
        global _seq_counter
        _seq_counter += 1
        evento._seq = _seq_counter
        evento.sort_index = (evento.tempo, _TIPO_PRI[evento.tipo], evento._seq)
        self.escalonador.adicionar_evento(evento)

    def _start_services(self, fila: "Fila"):
        em_servico = len(fila.servidores_ocupados)
        disponiveis = max(0, fila.clientes_no_sistema - em_servico)
        livres = max(0, fila.num_servidores - em_servico)
        iniciar = min(livres, disponiveis)
        for _ in range(iniciar):
            tserv = self.gerar_tempo_servico(fila)
            if tserv is None:
                return
            tfim = self.tempo_atual + tserv
            self._push(Evento(tfim, TipoEvento.SAIDA, fila.nome))
            fila.servidores_ocupados.append(tfim)

    def processar_chegada(self, ev: Evento):
        fila = self.filas[ev.fila_origem]
        self.acumula_tempo(ev.tempo)

        if fila.tem_espaco():
            fila.add_customer()
            self._start_services(fila)
        else:
            fila.increment_loss()

        if fila.min_chegada is not None and fila.max_chegada is not None:
            tgap = self.gerar_tempo_chegada(fila)
            if tgap is not None:
                self._push(Evento(self.tempo_atual + tgap,
                           TipoEvento.CHEGADA, ev.fila_origem))


    def processar_saida(self, ev: Evento):
        fila = self.filas[ev.fila_origem]
        self.acumula_tempo(ev.tempo)

        # libera o servidor que terminou (tolerante a arredondamentos)
        try:
            fila.servidores_ocupados.remove(ev.tempo)
        except ValueError:
            if fila.servidores_ocupados:
                fila.servidores_ocupados.pop(0)

        # sai um cliente do sistema da fila
        fila.remove_customer()

        # 1) roteia primeiro (consome o RNG de roteamento antes dos RNGs de serviço)
        destino = self.determinar_destino(fila)
        if destino and destino in self.filas:
            self._push(Evento(ev.tempo, TipoEvento.PASSAGEM,
                    ev.fila_origem, destino))

        # 2) depois preenche servidores livres no MESMO timestamp
        self._start_services(fila)

    def processar_passagem(self, ev: Evento):
        self.acumula_tempo(ev.tempo)
        fila_destino = self.filas[ev.fila_destino]

        if fila_destino.tem_espaco():
            fila_destino.add_customer()
            self._start_services(fila_destino)
        else:
            fila_destino.increment_loss()

    # ------------------------------- Execução -------------------------------- #
    def _executar_once(self) -> Tuple[Dict[str, Dict[int, float]], Dict[str, int], float]:
        # t0 = menor tempo de chegada exógena declarada; não contar 0→t0
        t0 = min(self.chegadas_iniciais.values()
                 ) if self.chegadas_iniciais else 0.0
        self.tempo_atual = t0
        for fila in self.filas.values():
            fila.ultimo_tempo_atualizacao = t0

        # agendar chegadas iniciais
        for nome_fila, t0f in self.chegadas_iniciais.items():
            if nome_fila in self.filas:
                self._push(Evento(float(t0f), TipoEvento.CHEGADA, nome_fila))

        # laço principal
        while self.escalonador.tem_eventos() and self.contador_aleatorios < self.limite_aleatorios:
            ev = self.escalonador.proximo_evento()
            if ev.tipo == TipoEvento.SAIDA:
                self.processar_saida(ev)
            elif ev.tipo == TipoEvento.PASSAGEM:
                self.processar_passagem(ev)
            else:  # CHEGADA
                self.processar_chegada(ev)

        # fechar contagem de tempo no instante final
        for fila in self.filas.values():
            fila.atualizar_tempo_estado(self.tempo_atual)

        tempos = {nome: dict(f.tempo_por_estado)
                  for nome, f in self.filas.items()}
        perdas = {nome: f.clientes_perdidos for nome, f in self.filas.items()}
        return tempos, perdas, self.tempo_atual

    def executar(self):
        if self._cfg is None:
            raise RuntimeError("Configuração não carregada.")

        seeds = self._cfg.get("seeds", [])
        if not seeds:
            seeds = [None]

        # acumuladores
        acc_tempos: Dict[str, Dict[int, float]] = {}
        acc_perdas: Dict[str, int] = {}
        tempos_globais: List[float] = []
        self._seeds_usadas = []

        nomes_filas = list(self._cfg.get("queues", {}).keys())
        for nome in nomes_filas:
            acc_tempos[nome] = defaultdict(float)
            acc_perdas[nome] = 0

        for sd in seeds:
            self.seed = sd
            # aplica seed aqui e NÃO dentro do reset
            if sd is None:
                random.seed()
                self.usar_seed = False
            else:
                random.seed(sd)
                self.usar_seed = True
                self._seeds_usadas.append(sd)

            # reset completo (sem seed interna)
            self._reset_from_cfg(self._cfg, apply_seed=False)

            # executa
            tempos, perdas, tglobal = self._executar_once()

            tempos_globais.append(tglobal)
            for nome in nomes_filas:
                for estado, t in tempos[nome].items():
                    acc_tempos[nome][estado] += t
                acc_perdas[nome] += perdas[nome]

        self._agregado_tempo_por_estado = {
            n: dict(d) for n, d in acc_tempos.items()}
        self._agregado_perdas = acc_perdas
        self._media_tempo_global = sum(tempos_globais) / len(tempos_globais)

        # projeta nos objetos (para o relatório)
        for nome in nomes_filas:
            f = self.filas[nome]
            f.tempo_por_estado = defaultdict(
                float, self._agregado_tempo_por_estado[nome])
            f.clientes_perdidos = self._agregado_perdas[nome]
        self.tempo_atual = self._media_tempo_global

    # ------------------------------- Relatório ------------------------------- #
    def gerar_relatorio(self) -> str:
        linhas = []
        linhas.append("=" * 86)
        linhas.append("SIMULADOR DE REDE DE FILAS")
        linhas.append("=" * 86)

        if len(self._seeds_usadas) > 1:
            linhas.append(
                f"Simulation average time: {self._media_tempo_global:.4f}")
            linhas.append(
                f"Seeds utilizadas: {', '.join(map(str, self._seeds_usadas))}")
            linhas.append(f"Aleatorios por seed: {self.limite_aleatorios}")
        else:
            linhas.append(f"Tempo global da simulacao: {self.tempo_atual:.4f}")
            linhas.append(
                f"Numeros aleatorios usados: {self.contador_aleatorios} (limite {self.limite_aleatorios})")
            if self.usar_seed and self.seed is not None:
                linhas.append(f"Seed: {self.seed}")
        linhas.append("")

        for nome in sorted(self.filas.keys()):
            f = self.filas[nome]
            linhas.append("=" * 86)
            linhas.append(f"FILA {nome}")
            linhas.append("-" * 86)
            cap = "Infinita" if f.get_capacity() == float(
                "inf") else str(int(f.get_capacity()))
            linhas.append(f"Servidores: {f.get_servers()} | Capacidade: {cap}")
            if f.min_chegada is not None and f.max_chegada is not None:
                linhas.append(
                    f"Chegadas exogenas: {f.min_chegada} .. {f.max_chegada}")
            else:
                linhas.append("Chegadas exogenas: (nenhuma)")
            linhas.append(f"Servico: {f.min_servico} .. {f.max_servico}")
            if f.destinos:
                linhas.append("Roteamento:")
                acc = 0.0
                for d, p in f.destinos.items():
                    acc += p
                    linhas.append(f"  -> {d}: {p:.3f}")
                if acc < 1.0:
                    linhas.append(f"  -> SAIDA do sistema: {1-acc:.3f}")
            else:
                linhas.append("Roteamento: SAIDA do sistema")

            linhas.append("")
            tempo_total = sum(f.tempo_por_estado.values())
            if tempo_total > 0:
                linhas.append("Estado   Tempo acumulado      Probabilidade")
                linhas.append("-" * 50)
                for estado in sorted(f.tempo_por_estado.keys()):
                    t = f.tempo_por_estado[estado]
                    prob = t / tempo_total
                    linhas.append(
                        f"{estado:>4}     {t:>14.4f}      {prob:>12.4%}")

                L = sum(estado * (t / tempo_total)
                        for estado, t in f.tempo_por_estado.items())
                linhas.append("")
                linhas.append(f"Numero de perdas: {f.clientes_perdidos}")
                linhas.append(f"L (numero medio no sistema): {L:.6f}")
            else:
                linhas.append(
                    "Sem tempo acumulado (simulacao terminou antes de transicionar estados).")

            linhas.append("")

        linhas.append("=" * 86)
        return "\n".join(linhas)


# ----------------------------------- CLI ------------------------------------ #

def main():
    import sys
    arq = sys.argv[1] if len(sys.argv) > 1 else "modelo_fig1.yml"
    print(f"Executando simulacao com '{arq}'\n")
    sim = Simulador(arq)
    sim.executar()
    rel = sim.gerar_relatorio()
    print(rel)
    with open("resultado_simulacao.txt", "w", encoding="utf-8") as f:
        f.write(rel)
    print("\nResultados salvos em 'resultado_simulacao.txt'.")


if __name__ == "__main__":
    main()
