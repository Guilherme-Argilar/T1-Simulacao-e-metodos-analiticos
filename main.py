"""
Simulador de Filas em Tandem - Versão Melhorada
Alinhado com as diretrizes do Professor Afonso Sales
"""

import random
import heapq
import yaml
from collections import defaultdict
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class TipoEvento(Enum):
    CHEGADA = "chegada"
    SAIDA = "saida"
    PASSAGEM = "passagem"


@dataclass(order=True)
class Evento:
    tempo: float
    tipo: TipoEvento = field(compare=False)
    fila_origem: str = field(compare=False)
    fila_destino: Optional[str] = field(default=None, compare=False)
    
    def __repr__(self):
        return f"Evento({self.tipo.value}, t={self.tempo:.2f}, origem={self.fila_origem})"


class Fila:
    
    def __init__(self, nome: str, servidores: int, capacidade: Optional[int],
                 min_chegada: Optional[float], max_chegada: Optional[float],
                 min_servico: float, max_servico: float):
        self.nome = nome
        self.num_servidores = servidores
        self.capacidade = float('inf') if capacidade is None or capacidade < 0 else capacidade
        self.min_chegada = min_chegada
        self.max_chegada = max_chegada
        self.min_servico = min_servico
        self.max_servico = max_servico
        
        self.clientes_no_sistema = 0
        self.servidores_ocupados = []
        

        self.clientes_recebidos = 0
        self.clientes_atendidos = 0
        self.clientes_perdidos = 0
        self.tempo_por_estado = defaultdict(float)
        self.ultimo_tempo_atualizacao = 0.0
        

        self.destinos = {}
    
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
        tempo_decorrido = tempo_atual - self.ultimo_tempo_atualizacao
        self.tempo_por_estado[self.clientes_no_sistema] += tempo_decorrido
        self.ultimo_tempo_atualizacao = tempo_atual


class Escalonador:
    
    def __init__(self):
        self.eventos = []
    
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


class SimuladorFilasTandem:
    
    def __init__(self, arquivo_yaml: str = None):
        self.filas: Dict[str, Fila] = {}
        self.escalonador = Escalonador()
        self.tempo_atual = 0.0
        self.contador_aleatorios = 0
        self.limite_aleatorios = 100000
        
        self.chegadas_iniciais = {}
        self.usar_seed = False
        self.seed = None
        
        if arquivo_yaml:
            self.carregar_configuracao(arquivo_yaml)
    
    def carregar_configuracao(self, arquivo: str):
        with open(arquivo, 'r', encoding='utf-8') as f:
            conteudo = f.read()
            inicio_params = conteudo.find('!PARAMETERS')
            if inicio_params != -1:
                conteudo = conteudo[inicio_params + len('!PARAMETERS'):]
            config = yaml.safe_load(conteudo)
        
        if 'rndnumbersPerSeed' in config:
            self.limite_aleatorios = config['rndnumbersPerSeed']
        if 'arrivals' in config:
            self.chegadas_iniciais = config['arrivals']
        if 'queues' in config:
            for nome_fila, params in config['queues'].items():
                fila = Fila(
                    nome=nome_fila,
                    servidores=params['servers'],
                    capacidade=params.get('capacity'),
                    min_chegada=params.get('minArrival'),
                    max_chegada=params.get('maxArrival'),
                    min_servico=params['minService'],
                    max_servico=params['maxService']
                )
                self.filas[nome_fila] = fila
        
        if 'network' in config:
            for conexao in config['network']:
                origem = conexao['source']
                destino = conexao['target']
                probabilidade = conexao['probability']
                
                if origem in self.filas:
                    self.filas[origem].destinos[destino] = probabilidade
        
        if 'seeds' in config and len(config['seeds']) > 0:
            self.seed = config['seeds'][0]
            self.usar_seed = True
            random.seed(self.seed)
    
    def gerar_aleatorio(self) -> float:
        self.contador_aleatorios += 1
        return random.random()
    
    def gerar_tempo_chegada(self, fila: Fila) -> float:
        r = self.gerar_aleatorio()
        return fila.min_chegada + r * (fila.max_chegada - fila.min_chegada)
    
    def gerar_tempo_servico(self, fila: Fila) -> float:
        r = self.gerar_aleatorio()
        return fila.min_servico + r * (fila.max_servico - fila.min_servico)
    
    def determinar_destino(self, fila: Fila) -> Optional[str]:
        if not fila.destinos:
            return None
        
        r = self.gerar_aleatorio()
        prob_acumulada = 0.0
        
        for destino, probabilidade in fila.destinos.items():
            prob_acumulada += probabilidade
            if r < prob_acumulada:
                return destino
        
        return None
    
    def processar_chegada(self, evento: Evento):
        fila = self.filas[evento.fila_origem]
        
        self.acumula_tempo(evento.tempo)
        
        if fila.tem_espaco():
            fila.add_customer()
            
            if fila.tem_servidor_livre():
                tempo_servico = self.gerar_tempo_servico(fila)
                tempo_fim = self.tempo_atual + tempo_servico
                
                evento_saida = Evento(
                    tempo=tempo_fim,
                    tipo=TipoEvento.SAIDA,
                    fila_origem=evento.fila_origem
                )
                self.escalonador.adicionar_evento(evento_saida)
                fila.servidores_ocupados.append(tempo_fim)
        else:
            fila.increment_loss()
        
        if fila.min_chegada and self.contador_aleatorios < self.limite_aleatorios - 2:
            tempo_entre = self.gerar_tempo_chegada(fila)
            proxima_chegada = Evento(
                tempo=self.tempo_atual + tempo_entre,
                tipo=TipoEvento.CHEGADA,
                fila_origem=evento.fila_origem
            )
            self.escalonador.adicionar_evento(proxima_chegada)
    
    def processar_saida(self, evento: Evento):
        fila = self.filas[evento.fila_origem]
        
        self.acumula_tempo(evento.tempo)
        
        fila.servidores_ocupados.remove(evento.tempo)
        
        clientes_esperando = fila.get_status() - len(fila.servidores_ocupados) - 1
        
        if clientes_esperando > 0:
            tempo_servico = self.gerar_tempo_servico(fila)
            tempo_fim = self.tempo_atual + tempo_servico
            
            evento_saida = Evento(
                tempo=tempo_fim,
                tipo=TipoEvento.SAIDA,
                fila_origem=evento.fila_origem
            )
            self.escalonador.adicionar_evento(evento_saida)
            fila.servidores_ocupados.append(tempo_fim)
        
        fila.remove_customer()
        
        destino = self.determinar_destino(fila)
        if destino and destino in self.filas:
            evento_passagem = Evento(
                tempo=evento.tempo,
                tipo=TipoEvento.PASSAGEM,
                fila_origem=evento.fila_origem,
                fila_destino=destino
            )
            self.escalonador.adicionar_evento(evento_passagem)
    
    def processar_passagem(self, evento: Evento):
        fila_destino = self.filas[evento.fila_destino]
        
        if fila_destino.tem_espaco():
            fila_destino.add_customer()
            
            if fila_destino.tem_servidor_livre():
                tempo_servico = self.gerar_tempo_servico(fila_destino)
                tempo_fim = self.tempo_atual + tempo_servico
                
                evento_saida = Evento(
                    tempo=tempo_fim,
                    tipo=TipoEvento.SAIDA,
                    fila_origem=evento.fila_destino
                )
                self.escalonador.adicionar_evento(evento_saida)
                fila_destino.servidores_ocupados.append(tempo_fim)
        else:
            fila_destino.increment_loss()
    
    def acumula_tempo(self, tempo_evento: float):
        for fila in self.filas.values():
            fila.atualizar_tempo_estado(tempo_evento)
        self.tempo_atual = tempo_evento
    
    def executar_simulacao(self):
        
        for nome_fila, tempo_inicial in self.chegadas_iniciais.items():
            if nome_fila in self.filas:
                evento = Evento(
                    tempo=tempo_inicial,
                    tipo=TipoEvento.CHEGADA,
                    fila_origem=nome_fila
                )
                self.escalonador.adicionar_evento(evento)
        
        while self.escalonador.tem_eventos() and self.contador_aleatorios < self.limite_aleatorios:
            evento = self.escalonador.proximo_evento()
            
            if evento.tipo == TipoEvento.CHEGADA:
                self.processar_chegada(evento)
            elif evento.tipo == TipoEvento.SAIDA:
                self.processar_saida(evento)
            elif evento.tipo == TipoEvento.PASSAGEM:
                self.processar_passagem(evento)
        
        for fila in self.filas.values():
            fila.atualizar_tempo_estado(self.tempo_atual)
    
    def gerar_relatorio(self) -> str:
        relatorio = []
        relatorio.append("=" * 80)
        relatorio.append("SIMULADOR DE FILAS EM TANDEM")
        relatorio.append("Implementacao conforme diretrizes do Prof. Afonso Sales")
        relatorio.append("=" * 80)
        relatorio.append(f"Tempo global de simulacao: {self.tempo_atual:.2f}")
        relatorio.append(f"Numeros aleatorios utilizados: {self.contador_aleatorios}")
        relatorio.append(f"Limite configurado: {self.limite_aleatorios}")
        if self.usar_seed:
            relatorio.append(f"Seed utilizada: {self.seed}")
        relatorio.append("")
        
        for nome in sorted(self.filas.keys()):
            fila = self.filas[nome]
            relatorio.append("=" * 80)
            relatorio.append(f"FILA: {nome}")
            relatorio.append("-" * 80)
            
            relatorio.append(f"Servidores: {fila.get_servers()}")
            cap_str = "Infinita" if fila.get_capacity() == float('inf') else str(int(fila.get_capacity()))
            relatorio.append(f"Capacidade: {cap_str}")
            
            if fila.min_chegada:
                relatorio.append(f"Chegadas: {fila.min_chegada} ... {fila.max_chegada}")
            relatorio.append(f"Servico: {fila.min_servico} ... {fila.max_servico}")
            relatorio.append("")
            
            tempo_total = sum(fila.tempo_por_estado.values())
            if tempo_total > 0:
                relatorio.append("Estado         Tempo              Probabilidade")
                relatorio.append("-" * 50)
                
                for estado in sorted(fila.tempo_por_estado.keys()):
                    tempo = fila.tempo_por_estado[estado]
                    prob = tempo / tempo_total
                    relatorio.append(f"  {estado:<10} {tempo:>15.4f}      {prob:>10.2%}")
                
                relatorio.append(f"\nNumero de perdas: {fila.clientes_perdidos}")
                
                L = sum(estado * (tempo/tempo_total) 
                       for estado, tempo in fila.tempo_por_estado.items())
                relatorio.append(f"L (numero medio): {L:.4f}")
            
            relatorio.append("")
        
        relatorio.append("=" * 80)
        return "\n".join(relatorio)


def main():
    import sys
    
    if len(sys.argv) > 1:
        arquivo = sys.argv[1]
    else:
        arquivo = 'config_tandem.yml'
    
    print(f"Executando simulacao com arquivo: {arquivo}")
    print()
    
    simulador = SimuladorFilasTandem(arquivo)
    simulador.executar_simulacao()
    
    print(simulador.gerar_relatorio())
    
    with open('resultado_tandem_melhorado.txt', 'w', encoding='utf-8') as f:
        f.write(simulador.gerar_relatorio())
    
    print("\nResultados salvos em 'resultado_tandem_melhorado.txt'")


if __name__ == "__main__":
    main()