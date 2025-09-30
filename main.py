import random
import heapq
import yaml
from collections import defaultdict
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class TipoEvento(Enum):
    CHEGADA = "chegada"
    SAIDA   = "saida"
    PASSAGEM= "passagem"


@dataclass(order=True)
class Evento:
    tempo: float
    tipo: TipoEvento = field(compare=False)
    fila_origem: str = field(compare=False)
    fila_destino: Optional[str] = field(default=None, compare=False)

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
        self.capacidade = float("inf") if capacidade is None or capacidade < 0 else capacidade
        self.min_chegada = min_chegada
        self.max_chegada = max_chegada
        self.min_servico = min_servico
        self.max_servico = max_servico

        # estado
        self.clientes_no_sistema = 0
        self.servidores_ocupados: List[float] = []

        self.clientes_recebidos = 0
        self.clientes_atendidos = 0
        self.clientes_perdidos = 0
        self.tempo_por_estado = defaultdict(float)
        self.ultimo_tempo_atualizacao = 0.0

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


class Simulador:
    def __init__(self, arquivo_yaml: Optional[str] = None):
        self.filas: Dict[str, Fila] = {}
        self.escalonador = Escalonador()
        self.tempo_atual = 0.0

        self.contador_aleatorios = 0
        self.limite_aleatorios = 100000

        self.chegadas_iniciais: Dict[str, float] = {}
        self.usar_seed = False
        self.seed = None

        if arquivo_yaml:
            self.carregar_configuracao(arquivo_yaml)

    def carregar_configuracao(self, arquivo: str):
        with open(arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read()
            marca = "!PARAMETERS"
            i = conteudo.find(marca)
            if i != -1:
                conteudo = conteudo[i + len(marca) :]
            cfg = yaml.safe_load(conteudo)

        self.limite_aleatorios = int(cfg.get("rndnumbersPerSeed", self.limite_aleatorios))
        self.chegadas_iniciais = dict(cfg.get("arrivals", {}))

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

        for con in cfg.get("network", []):
            origem = con["source"]
            destino = con["target"]
            prob = float(con["probability"])
            if origem in self.filas:
                self.filas[origem].destinos[destino] = prob

        seeds = cfg.get("seeds", [])
        if seeds:
            self.seed = seeds[0]
            self.usar_seed = True
            random.seed(self.seed)

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
        return None
    def acumula_tempo(self, tempo_evento: float):
        for fila in self.filas.values():
            fila.atualizar_tempo_estado(tempo_evento)
        self.tempo_atual = tempo_evento

    def processar_chegada(self, ev: Evento):
        fila = self.filas[ev.fila_origem]
        self.acumula_tempo(ev.tempo)

        if fila.tem_espaco():
            fila.add_customer()
            if fila.tem_servidor_livre():
                tserv = self.gerar_tempo_servico(fila)
                if tserv is not None:
                    tfim = self.tempo_atual + tserv
                    self.escalonador.adicionar_evento(Evento(tfim, TipoEvento.SAIDA, ev.fila_origem))
                    fila.servidores_ocupados.append(tfim)
        else:
            fila.increment_loss()

        if fila.min_chegada is not None and fila.max_chegada is not None:
            tgap = self.gerar_tempo_chegada(fila)
            if tgap is not None:
                self.escalonador.adicionar_evento(
                    Evento(self.tempo_atual + tgap, TipoEvento.CHEGADA, ev.fila_origem)
                )

    def processar_saida(self, ev: Evento):
        fila = self.filas[ev.fila_origem]
        self.acumula_tempo(ev.tempo)

        try:
            fila.servidores_ocupados.remove(ev.tempo)
        except ValueError:
            if fila.servidores_ocupados:
                fila.servidores_ocupados.pop(0)

        clientes_esperando = max(0, fila.clientes_no_sistema - len(fila.servidores_ocupados) - 1)

        if clientes_esperando > 0:
            tserv = self.gerar_tempo_servico(fila)
            if tserv is not None:
                tfim = self.tempo_atual + tserv
                self.escalonador.adicionar_evento(Evento(tfim, TipoEvento.SAIDA, ev.fila_origem))
                fila.servidores_ocupados.append(tfim)

        fila.remove_customer()

        destino = self.determinar_destino(fila)
        if destino and destino in self.filas:
            self.escalonador.adicionar_evento(
                Evento(ev.tempo, TipoEvento.PASSAGEM, ev.fila_origem, destino)
            )

    def processar_passagem(self, ev: Evento):
        self.acumula_tempo(ev.tempo)
        fila_destino = self.filas[ev.fila_destino]

        if fila_destino.tem_espaco():
            fila_destino.add_customer()
            if fila_destino.tem_servidor_livre():
                tserv = self.gerar_tempo_servico(fila_destino)
                if tserv is not None:
                    tfim = self.tempo_atual + tserv
                    self.escalonador.adicionar_evento(Evento(tfim, TipoEvento.SAIDA, ev.fila_destino))
                    fila_destino.servidores_ocupados.append(tfim)
        else:
            fila_destino.increment_loss()

    def executar(self):
        for nome_fila, t0 in self.chegadas_iniciais.items():
            if nome_fila in self.filas:
                self.escalonador.adicionar_evento(Evento(float(t0), TipoEvento.CHEGADA, nome_fila))

        while self.escalonador.tem_eventos() and self.contador_aleatorios < self.limite_aleatorios:
            ev = self.escalonador.proximo_evento()
            if ev.tipo == TipoEvento.CHEGADA:
                self.processar_chegada(ev)
            elif ev.tipo == TipoEvento.SAIDA:
                self.processar_saida(ev)
            elif ev.tipo == TipoEvento.PASSAGEM:
                self.processar_passagem(ev)

        for fila in self.filas.values():
            fila.atualizar_tempo_estado(self.tempo_atual)

    def gerar_relatorio(self) -> str:
        linhas = []
        linhas.append("=" * 86)
        linhas.append("SIMULADOR DE REDE DE FILAS")
        linhas.append("=" * 86)
        linhas.append(f"Tempo global da simulacao: {self.tempo_atual:.4f}")
        linhas.append(f"Numeros aleatorios usados : {self.contador_aleatorios} (limite {self.limite_aleatorios})")
        if self.usar_seed:
            linhas.append(f"Seed: {self.seed}")
        linhas.append("")

        for nome in sorted(self.filas.keys()):
            f = self.filas[nome]
            linhas.append("=" * 86)
            linhas.append(f"FILA {nome}")
            linhas.append("-" * 86)
            cap = "Infinita" if f.get_capacity() == float("inf") else str(int(f.get_capacity()))
            linhas.append(f"Servidores: {f.get_servers()} | Capacidade: {cap}")
            if f.min_chegada is not None and f.max_chegada is not None:
                linhas.append(f"Chegadas exogenas: {f.min_chegada} .. {f.max_chegada}")
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
                    linhas.append(f"{estado:>4}     {t:>14.4f}      {prob:>12.4%}")

                L = sum(estado * (t / tempo_total) for estado, t in f.tempo_por_estado.items())
                linhas.append("")
                linhas.append(f"Numero de perdas: {f.clientes_perdidos}")
                linhas.append(f"L (numero medio no sistema): {L:.6f}")
            else:
                linhas.append("Sem tempo acumulado (simulacao terminou antes de transicionar estados).")

            linhas.append("")

        linhas.append("=" * 86)
        return "\n".join(linhas)

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
