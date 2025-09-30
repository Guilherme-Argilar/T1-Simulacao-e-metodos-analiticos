"""
Simulador de Filas em Tandem (2 filas em série)
Etapa 2 - Versão Simples e Extensível
"""

import random
import heapq
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

class Fila:
    """Classe para representar uma fila individual"""
    def __init__(self, id_fila: int, num_servidores: int, capacidade: int,
                 tempo_chegada_min: float = None, tempo_chegada_max: float = None,
                 tempo_atendimento_min: float = None, tempo_atendimento_max: float = None):
        self.id = id_fila
        self.num_servidores = num_servidores
        self.capacidade = capacidade
        self.tempo_chegada_min = tempo_chegada_min
        self.tempo_chegada_max = tempo_chegada_max
        self.tempo_atendimento_min = tempo_atendimento_min
        self.tempo_atendimento_max = tempo_atendimento_max
        
        # Estado atual
        self.clientes_no_sistema = 0
        self.servidores_ocupados = []  # Lista com tempos de fim de atendimento
        
        # Estatísticas
        self.clientes_atendidos = 0
        self.clientes_perdidos = 0
        self.tempo_por_estado = defaultdict(float)
        self.ultimo_tempo_atualizacao = 0.0
        
    def tem_espaco(self) -> bool:
        """Verifica se há espaço na fila"""
        return self.clientes_no_sistema < self.capacidade
    
    def tem_servidor_livre(self) -> bool:
        """Verifica se há servidor disponível"""
        return len(self.servidores_ocupados) < self.num_servidores
    
    def atualizar_tempo_estado(self, tempo_atual: float):
        """Atualiza o tempo acumulado no estado atual"""
        tempo_decorrido = tempo_atual - self.ultimo_tempo_atualizacao
        self.tempo_por_estado[self.clientes_no_sistema] += tempo_decorrido
        self.ultimo_tempo_atualizacao = tempo_atual


class SimuladorFilasTandem:
    """Simulador para filas em tandem (série)"""
    
    def __init__(self, seed: int = None):
        if seed:
            random.seed(seed)
        
        self.filas: Dict[int, Fila] = {}
        self.tempo_atual = 0.0
        self.contador_aleatorios = 0
        self.eventos = []  # Heap de eventos
        
        # Matriz de roteamento (origem -> destino -> probabilidade)
        self.roteamento = {}
        
    def adicionar_fila(self, fila: Fila):
        """Adiciona uma fila ao sistema"""
        self.filas[fila.id] = fila
        
    def definir_roteamento(self, origem: int, destino: int, probabilidade: float = 1.0):
        """Define roteamento entre filas (preparado para redes genéricas)"""
        if origem not in self.roteamento:
            self.roteamento[origem] = {}
        self.roteamento[origem][destino] = probabilidade
        
    def gerar_tempo_chegada(self, fila: Fila) -> float:
        """Gera tempo entre chegadas"""
        self.contador_aleatorios += 1
        return random.uniform(fila.tempo_chegada_min, fila.tempo_chegada_max)
    
    def gerar_tempo_atendimento(self, fila: Fila) -> float:
        """Gera tempo de atendimento"""
        self.contador_aleatorios += 1
        return random.uniform(fila.tempo_atendimento_min, fila.tempo_atendimento_max)
    
    def processar_chegada_externa(self, id_fila: int, tempo_evento: float):
        """Processa chegada de cliente externo ao sistema"""
        fila = self.filas[id_fila]
        fila.atualizar_tempo_estado(tempo_evento)
        self.tempo_atual = tempo_evento
        
        if fila.tem_espaco():
            fila.clientes_no_sistema += 1
            
            # Se há servidor livre, inicia atendimento
            if fila.tem_servidor_livre():
                tempo_atendimento = self.gerar_tempo_atendimento(fila)
                tempo_fim = self.tempo_atual + tempo_atendimento
                heapq.heappush(self.eventos, (tempo_fim, 'saida', id_fila))
                fila.servidores_ocupados.append(tempo_fim)
        else:
            fila.clientes_perdidos += 1
        
        # Agenda próxima chegada externa (se configurada)
        if fila.tempo_chegada_min is not None and self.contador_aleatorios < 100000:
            tempo_entre_chegadas = self.gerar_tempo_chegada(fila)
            proxima_chegada = self.tempo_atual + tempo_entre_chegadas
            heapq.heappush(self.eventos, (proxima_chegada, 'chegada_externa', id_fila))
    
    def processar_saida(self, id_fila: int, tempo_evento: float):
        """Processa saída de cliente de uma fila"""
        fila = self.filas[id_fila]
        fila.atualizar_tempo_estado(tempo_evento)
        self.tempo_atual = tempo_evento
        
        # Remove servidor que terminou
        fila.servidores_ocupados.remove(tempo_evento)
        fila.clientes_atendidos += 1
        
        # Verifica se há clientes esperando na fila
        clientes_esperando = fila.clientes_no_sistema - len(fila.servidores_ocupados) - 1
        
        if clientes_esperando > 0:
            # Inicia atendimento do próximo cliente
            tempo_atendimento = self.gerar_tempo_atendimento(fila)
            tempo_fim = self.tempo_atual + tempo_atendimento
            heapq.heappush(self.eventos, (tempo_fim, 'saida', id_fila))
            fila.servidores_ocupados.append(tempo_fim)
        
        # Atualiza estado
        fila.clientes_no_sistema -= 1
        
        # Rotear cliente para próxima fila (se houver)
        if id_fila in self.roteamento:
            destinos = self.roteamento[id_fila]
            # Para tandem simples, sempre vai para a próxima fila
            for destino_id, probabilidade in destinos.items():
                # Aqui poderia ter lógica probabilística para redes complexas
                self.processar_chegada_interna(destino_id, tempo_evento)
    
    def processar_chegada_interna(self, id_fila: int, tempo_evento: float):
        """Processa chegada de cliente vindo de outra fila"""
        fila = self.filas[id_fila]
        fila.atualizar_tempo_estado(tempo_evento)
        
        if fila.tem_espaco():
            fila.clientes_no_sistema += 1
            
            # Se há servidor livre, inicia atendimento
            if fila.tem_servidor_livre():
                tempo_atendimento = self.gerar_tempo_atendimento(fila)
                tempo_fim = self.tempo_atual + tempo_atendimento
                heapq.heappush(self.eventos, (tempo_fim, 'saida', id_fila))
                fila.servidores_ocupados.append(tempo_fim)
        else:
            fila.clientes_perdidos += 1
    
    def executar_simulacao(self, tempo_primeira_chegada: float = 1.5, limite_aleatorios: int = 100000):
        """Executa a simulação completa"""
        # Inicializa primeira chegada na fila 1 (entrada do sistema)
        heapq.heappush(self.eventos, (tempo_primeira_chegada, 'chegada_externa', 1))
        
        # Processa eventos
        while self.eventos and self.contador_aleatorios <= limite_aleatorios:
            tempo_evento, tipo_evento, id_fila = heapq.heappop(self.eventos)
            
            if tipo_evento == 'chegada_externa':
                self.processar_chegada_externa(id_fila, tempo_evento)
            elif tipo_evento == 'saida':
                self.processar_saida(id_fila, tempo_evento)
        
        # Atualiza tempo final para todas as filas
        for fila in self.filas.values():
            fila.atualizar_tempo_estado(self.tempo_atual)
    
    def calcular_distribuicao_probabilidades(self, fila: Fila) -> Dict[int, float]:
        """Calcula distribuição de probabilidades para uma fila"""
        tempo_total = sum(fila.tempo_por_estado.values())
        if tempo_total == 0:
            return {i: 0.0 for i in range(fila.capacidade + 1)}
        
        distribuicao = {}
        for estado in range(fila.capacidade + 1):
            distribuicao[estado] = fila.tempo_por_estado.get(estado, 0.0) / tempo_total
        return distribuicao
    
    def gerar_relatorio(self) -> str:
        """Gera relatório completo da simulação"""
        relatorio = []
        relatorio.append("=" * 70)
        relatorio.append("SIMULADOR DE FILAS EM TANDEM")
        relatorio.append("=" * 70)
        relatorio.append(f"Tempo global de simulacao: {self.tempo_atual:.2f}")
        relatorio.append(f"Numeros aleatorios utilizados: {self.contador_aleatorios}")
        relatorio.append("")
        
        # Relatório de cada fila
        for id_fila in sorted(self.filas.keys()):
            fila = self.filas[id_fila]
            distribuicao = self.calcular_distribuicao_probabilidades(fila)
            
            relatorio.append("=" * 70)
            relatorio.append(f"FILA {id_fila}")
            relatorio.append("-" * 70)
            
            # Configuração
            relatorio.append("Configuracao:")
            if fila.tempo_chegada_min is not None:
                relatorio.append(f"  - Chegadas externas: [{fila.tempo_chegada_min}, {fila.tempo_chegada_max}]")
            else:
                relatorio.append(f"  - Chegadas externas: Nao (recebe de outras filas)")
            relatorio.append(f"  - Tempo atendimento: [{fila.tempo_atendimento_min}, {fila.tempo_atendimento_max}]")
            relatorio.append(f"  - Servidores: {fila.num_servidores}")
            relatorio.append(f"  - Capacidade: {fila.capacidade}")
            relatorio.append("")
            
            # Resultados
            relatorio.append("Resultados:")
            relatorio.append(f"  - Clientes atendidos: {fila.clientes_atendidos}")
            relatorio.append(f"  - Clientes perdidos: {fila.clientes_perdidos}")
            total = fila.clientes_atendidos + fila.clientes_perdidos
            if total > 0:
                taxa_perda = fila.clientes_perdidos / total
                relatorio.append(f"  - Taxa de perda: {taxa_perda:.4f} ({taxa_perda*100:.2f}%)")
            relatorio.append("")
            
            # Distribuição de probabilidades
            relatorio.append("Distribuicao de Probabilidades:")
            relatorio.append(f"{'Estado':<10} {'Tempo Acum.':<15} {'Probabilidade':<15}")
            relatorio.append("-" * 45)
            
            for estado in range(fila.capacidade + 1):
                tempo = fila.tempo_por_estado.get(estado, 0.0)
                prob = distribuicao[estado]
                relatorio.append(f"{estado:<10} {tempo:<15.2f} {prob:<15.4f}")
            
            # Métricas
            L = sum(estado * prob for estado, prob in distribuicao.items())
            relatorio.append("")
            relatorio.append(f"  L (numero medio no sistema): {L:.4f}")
            
            if distribuicao[0] > 0:
                taxa_ocupacao = 1 - distribuicao[0]
            else:
                taxa_ocupacao = 1.0
            relatorio.append(f"  Taxa de ocupacao: {taxa_ocupacao:.4f}")
            relatorio.append("")
        
        # Roteamento configurado
        relatorio.append("=" * 70)
        relatorio.append("CONFIGURACAO DE ROTEAMENTO:")
        for origem, destinos in self.roteamento.items():
            for destino, prob in destinos.items():
                relatorio.append(f"  Fila {origem} -> Fila {destino}: {prob*100:.0f}%")
        
        relatorio.append("=" * 70)
        
        return "\n".join(relatorio)


def main():
    """Função principal - Executa a simulação solicitada"""
    
    print("SIMULADOR DE FILAS EM TANDEM - ETAPA 2")
    print("=" * 70)
    print()
    
    # Criar simulador
    sim = SimuladorFilasTandem(seed=42)
    
    # Configurar Fila 1: G/G/2/3, chegadas 1..4, atendimento 3..4
    fila1 = Fila(
        id_fila=1,
        num_servidores=2,
        capacidade=3,
        tempo_chegada_min=1,
        tempo_chegada_max=4,
        tempo_atendimento_min=3,
        tempo_atendimento_max=4
    )
    
    # Configurar Fila 2: G/G/1/5, sem chegadas externas, atendimento 2..3
    fila2 = Fila(
        id_fila=2,
        num_servidores=1,
        capacidade=5,
        tempo_chegada_min=None,  # Sem chegadas externas
        tempo_chegada_max=None,
        tempo_atendimento_min=2,
        tempo_atendimento_max=3
    )
    
    # Adicionar filas ao simulador
    sim.adicionar_fila(fila1)
    sim.adicionar_fila(fila2)
    
    # Definir roteamento: Fila 1 -> Fila 2 (100%)
    sim.definir_roteamento(origem=1, destino=2, probabilidade=1.0)
    
    # Executar simulação
    print("Executando simulacao...")
    print("  - Primeiro cliente chega em t=1.5")
    print("  - Limite: 100.000 numeros aleatorios")
    print()
    
    sim.executar_simulacao(tempo_primeira_chegada=1.5, limite_aleatorios=100000)
    
    # Gerar e exibir relatório
    relatorio = sim.gerar_relatorio()
    print(relatorio)
    
    # Salvar em arquivo
    with open("resultados_tandem.txt", "w", encoding="utf-8") as f:
        f.write(relatorio)
    
    print("\n" + "=" * 70)
    print("Resultados salvos em 'resultados_tandem.txt'")
    
    # Instruções de uso
    print("\n" + "=" * 70)
    print("INSTRUCOES DE USO:")
    print("-" * 70)
    print("1. Para executar a simulacao padrao:")
    print("   python simulador_tandem.py")
    print()
    print("2. Para configurar suas proprias filas:")
    print("   - Crie objetos Fila com os parametros desejados")
    print("   - Adicione as filas ao simulador")
    print("   - Defina o roteamento entre elas")
    print("   - Execute a simulacao")
    print()
    print("3. Estrutura para redes genericas:")
    print("   - Use definir_roteamento() com probabilidades")
    print("   - Suporta multiplos destinos por fila")
    print("   - Facil extensao para topologias complexas")
    print("=" * 70)


if __name__ == "__main__":
    main()