"""
Simulador de Filas em Tandem - Versão com suporte a YAML estruturado
Compatível com formato do simulador do módulo 3
"""

import random
import heapq
import yaml
import sys
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any


class Fila:
    """Classe para representar uma fila individual"""
    def __init__(self, nome: str, servidores: int, capacidade: Optional[int],
                 min_chegada: Optional[float], max_chegada: Optional[float],
                 min_servico: float, max_servico: float):
        self.nome = nome
        self.num_servidores = servidores
        # Corrigido: -1 ou None significa capacidade infinita
        if capacidade is None or capacidade < 0:
            self.capacidade = float('inf')
        else:
            self.capacidade = capacidade
        self.min_chegada = min_chegada
        self.max_chegada = max_chegada
        self.min_servico = min_servico
        self.max_servico = max_servico
        
        # Estado atual
        self.clientes_no_sistema = 0
        self.servidores_ocupados = []
        
        # Estatísticas
        self.clientes_recebidos = 0
        self.clientes_atendidos = 0
        self.clientes_perdidos = 0
        self.tempo_por_estado = defaultdict(float)
        self.ultimo_tempo_atualizacao = 0.0
        
        # Roteamento
        self.destinos = {}  # {nome_destino: probabilidade}
    
    def tem_espaco(self) -> bool:
        """Verifica se há espaço na fila"""
        if self.capacidade == float('inf'):
            return True
        return self.clientes_no_sistema < self.capacidade
    
    def tem_servidor_livre(self) -> bool:
        """Verifica se há servidor disponível"""
        return len(self.servidores_ocupados) < self.num_servidores
    
    def atualizar_tempo_estado(self, tempo_atual: float):
        """Atualiza o tempo acumulado no estado atual"""
        tempo_decorrido = tempo_atual - self.ultimo_tempo_atualizacao
        self.tempo_por_estado[self.clientes_no_sistema] += tempo_decorrido
        self.ultimo_tempo_atualizacao = tempo_atual


class SimuladorFilas:
    """Simulador para redes de filas baseado em arquivo YAML"""
    
    def __init__(self, arquivo_yaml: str):
        self.filas: Dict[str, Fila] = {}
        self.tempo_atual = 0.0
        self.contador_aleatorios = 0
        self.eventos = []
        self.chegadas_iniciais = {}
        self.numeros_aleatorios = []
        self.indice_aleatorio = 0
        self.usar_lista_aleatorios = False
        
        self.carregar_configuracao(arquivo_yaml)
    
    def carregar_configuracao(self, arquivo: str):
        """Carrega configuração do arquivo YAML"""
        with open(arquivo, 'r', encoding='utf-8') as f:
            # Ler arquivo completo e processar
            conteudo = f.read()
            # Encontrar onde começam os parâmetros
            inicio_params = conteudo.find('!PARAMETERS')
            if inicio_params != -1:
                conteudo = conteudo[inicio_params + len('!PARAMETERS'):]
            
            config = yaml.safe_load(conteudo)
        
        # Processar chegadas iniciais
        if 'arrivals' in config:
            self.chegadas_iniciais = config['arrivals']
        
        # Criar filas
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
        
        # Configurar rede (roteamento)
        if 'network' in config:
            for conexao in config['network']:
                origem = conexao['source']
                destino = conexao['target']
                probabilidade = conexao['probability']
                
                if origem in self.filas:
                    self.filas[origem].destinos[destino] = probabilidade
        
        # Processar números aleatórios ou seeds
        if 'seeds' in config and 'rndnumbersPerSeed' in config:
            # Usar seeds para gerar números aleatórios
            self.gerar_aleatorios_por_seeds(
                config['seeds'], 
                config['rndnumbersPerSeed']
            )
        elif 'rndnumbers' in config:
            # Usar lista de números aleatórios fornecida
            self.numeros_aleatorios = config['rndnumbers']
            self.usar_lista_aleatorios = True
    
    def gerar_aleatorios_por_seeds(self, seeds: List[int], quantidade: int):
        """Gera números aleatórios baseado em seeds"""
        # Para este simulador, vamos usar apenas a primeira seed
        # Em uma versão mais completa, poderia fazer múltiplas execuções
        if seeds:
            random.seed(seeds[0])
    
    def obter_aleatorio(self) -> float:
        """Obtém próximo número aleatório"""
        self.contador_aleatorios += 1
        
        if self.usar_lista_aleatorios and self.indice_aleatorio < len(self.numeros_aleatorios):
            valor = self.numeros_aleatorios[self.indice_aleatorio]
            self.indice_aleatorio += 1
            return valor
        else:
            return random.random()
    
    def gerar_tempo_chegada(self, fila: Fila) -> float:
        """Gera tempo entre chegadas"""
        r = self.obter_aleatorio()
        return fila.min_chegada + r * (fila.max_chegada - fila.min_chegada)
    
    def gerar_tempo_servico(self, fila: Fila) -> float:
        """Gera tempo de serviço"""
        r = self.obter_aleatorio()
        return fila.min_servico + r * (fila.max_servico - fila.min_servico)
    
    def determinar_destino(self, fila: Fila) -> Optional[str]:
        """Determina próximo destino baseado nas probabilidades"""
        if not fila.destinos:
            return None
        
        r = self.obter_aleatorio()
        prob_acumulada = 0.0
        
        for destino, probabilidade in fila.destinos.items():
            prob_acumulada += probabilidade
            if r < prob_acumulada:
                return destino
        
        return None
    
    def processar_chegada_externa(self, nome_fila: str, tempo_evento: float):
        """Processa chegada externa ao sistema"""
        fila = self.filas[nome_fila]
        fila.atualizar_tempo_estado(tempo_evento)
        self.tempo_atual = tempo_evento
        
        fila.clientes_recebidos += 1
        
        if fila.tem_espaco():
            fila.clientes_no_sistema += 1
            
            if fila.tem_servidor_livre():
                tempo_servico = self.gerar_tempo_servico(fila)
                tempo_fim = self.tempo_atual + tempo_servico
                heapq.heappush(self.eventos, (tempo_fim, 'saida', nome_fila))
                fila.servidores_ocupados.append(tempo_fim)
        else:
            fila.clientes_perdidos += 1
        
        # Agenda próxima chegada se configurada
        if fila.min_chegada is not None and self.contador_aleatorios < 100000:
            tempo_entre_chegadas = self.gerar_tempo_chegada(fila)
            proxima_chegada = self.tempo_atual + tempo_entre_chegadas
            heapq.heappush(self.eventos, (proxima_chegada, 'chegada_externa', nome_fila))
    
    def processar_chegada_interna(self, nome_fila: str, tempo_evento: float):
        """Processa chegada vinda de outra fila"""
        fila = self.filas[nome_fila]
        fila.atualizar_tempo_estado(tempo_evento)
        
        fila.clientes_recebidos += 1
        
        if fila.tem_espaco():
            fila.clientes_no_sistema += 1
            
            if fila.tem_servidor_livre():
                tempo_servico = self.gerar_tempo_servico(fila)
                tempo_fim = self.tempo_atual + tempo_servico
                heapq.heappush(self.eventos, (tempo_fim, 'saida', nome_fila))
                fila.servidores_ocupados.append(tempo_fim)
        else:
            fila.clientes_perdidos += 1
    
    def processar_saida(self, nome_fila: str, tempo_evento: float):
        """Processa saída de uma fila"""
        fila = self.filas[nome_fila]
        fila.atualizar_tempo_estado(tempo_evento)
        self.tempo_atual = tempo_evento
        
        # Remove servidor
        fila.servidores_ocupados.remove(tempo_evento)
        fila.clientes_atendidos += 1
        
        # Verifica clientes esperando
        clientes_esperando = fila.clientes_no_sistema - len(fila.servidores_ocupados) - 1
        
        if clientes_esperando > 0:
            tempo_servico = self.gerar_tempo_servico(fila)
            tempo_fim = self.tempo_atual + tempo_servico
            heapq.heappush(self.eventos, (tempo_fim, 'saida', nome_fila))
            fila.servidores_ocupados.append(tempo_fim)
        
        fila.clientes_no_sistema -= 1
        
        # Rotear cliente
        proximo_destino = self.determinar_destino(fila)
        if proximo_destino and proximo_destino in self.filas:
            self.processar_chegada_interna(proximo_destino, tempo_evento)
    
    def executar_simulacao(self, limite_aleatorios: int = 100000):
        """Executa simulação"""
        # Inicializar chegadas baseado no arquivo
        for nome_fila, tempo_inicial in self.chegadas_iniciais.items():
            if nome_fila in self.filas:
                heapq.heappush(self.eventos, (tempo_inicial, 'chegada_externa', nome_fila))
        
        # Se não houver chegadas específicas, usar filas com minArrival
        if not self.chegadas_iniciais:
            for nome, fila in self.filas.items():
                if fila.min_chegada is not None:
                    heapq.heappush(self.eventos, (1.5, 'chegada_externa', nome))
        
        # Processar eventos
        while self.eventos and self.contador_aleatorios <= limite_aleatorios:
            tempo_evento, tipo_evento, nome_fila = heapq.heappop(self.eventos)
            
            if tipo_evento == 'chegada_externa':
                self.processar_chegada_externa(nome_fila, tempo_evento)
            elif tipo_evento == 'saida':
                self.processar_saida(nome_fila, tempo_evento)
        
        # Atualizar tempo final
        for fila in self.filas.values():
            fila.atualizar_tempo_estado(self.tempo_atual)
    
    def calcular_distribuicao(self, fila: Fila) -> Dict[int, float]:
        """Calcula distribuição de probabilidades"""
        tempo_total = sum(fila.tempo_por_estado.values())
        if tempo_total == 0:
            return {}
        
        distribuicao = {}
        max_estado = int(max(fila.tempo_por_estado.keys())) if fila.tempo_por_estado else 0
        
        for estado in range(max_estado + 1):
            distribuicao[estado] = fila.tempo_por_estado.get(estado, 0.0) / tempo_total
        
        return distribuicao
    
    def gerar_relatorio(self) -> str:
        """Gera relatório completo"""
        relatorio = []
        relatorio.append("=" * 80)
        relatorio.append("SIMULADOR DE REDES DE FILAS - FORMATO YAML")
        relatorio.append("=" * 80)
        relatorio.append(f"Tempo global de simulacao: {self.tempo_atual:.2f}")
        relatorio.append(f"Numeros aleatorios utilizados: {self.contador_aleatorios}")
        if self.usar_lista_aleatorios:
            relatorio.append(f"Usando lista de aleatorios fornecida ({len(self.numeros_aleatorios)} numeros)")
        relatorio.append("")
        
        # Ordenar filas por nome
        nomes_ordenados = sorted(self.filas.keys())
        
        for nome_fila in nomes_ordenados:
            fila = self.filas[nome_fila]
            distribuicao = self.calcular_distribuicao(fila)
            
            relatorio.append("=" * 80)
            relatorio.append(f"FILA: {nome_fila}")
            relatorio.append("-" * 80)
            
            # Configuração
            relatorio.append("Configuracao:")
            relatorio.append(f"  - Servidores: {fila.num_servidores}")
            if fila.capacidade == float('inf'):
                relatorio.append(f"  - Capacidade: Infinita")
            else:
                relatorio.append(f"  - Capacidade: {int(fila.capacidade)}")
            
            if fila.min_chegada is not None:
                relatorio.append(f"  - Tempo entre chegadas: [{fila.min_chegada}, {fila.max_chegada}]")
            relatorio.append(f"  - Tempo de servico: [{fila.min_servico}, {fila.max_servico}]")
            
            # Roteamento
            if fila.destinos:
                relatorio.append("  - Roteamento:")
                for destino, prob in fila.destinos.items():
                    relatorio.append(f"      -> {destino}: {prob*100:.1f}%")
            relatorio.append("")
            
            # Resultados
            relatorio.append("Resultados:")
            relatorio.append(f"  - Clientes recebidos: {fila.clientes_recebidos}")
            relatorio.append(f"  - Clientes atendidos: {fila.clientes_atendidos}")
            relatorio.append(f"  - Clientes perdidos: {fila.clientes_perdidos}")
            
            if fila.clientes_recebidos > 0:
                taxa_perda = fila.clientes_perdidos / fila.clientes_recebidos
                relatorio.append(f"  - Taxa de perda: {taxa_perda:.4f} ({taxa_perda*100:.2f}%)")
            relatorio.append("")
            
            # Distribuição
            if distribuicao:
                relatorio.append("Distribuicao de Probabilidades dos Estados:")
                relatorio.append(f"{'Estado':<10} {'Tempo Acum.':<20} {'Probabilidade':<15}")
                relatorio.append("-" * 55)
                
                for estado in sorted(distribuicao.keys()):
                    tempo = fila.tempo_por_estado.get(estado, 0.0)
                    prob = distribuicao[estado]
                    relatorio.append(f"{estado:<10} {tempo:<20.2f} {prob:<15.4f}")
                
                # Métricas
                L = sum(estado * prob for estado, prob in distribuicao.items())
                relatorio.append("")
                relatorio.append(f"  L (numero medio no sistema): {L:.4f}")
                
                if 0 in distribuicao:
                    taxa_ocupacao = 1 - distribuicao[0]
                else:
                    taxa_ocupacao = 1.0
                relatorio.append(f"  Taxa de ocupacao: {taxa_ocupacao:.4f}")
            
            relatorio.append("")
        
        relatorio.append("=" * 80)
        
        return "\n".join(relatorio)


def criar_yaml_tandem():
    """Cria arquivo YAML para o exemplo de filas em tandem da etapa 2"""
    yaml_content = """#==============================================================================
#  SIMULACAO DE FILAS EM TANDEM - ETAPA 2
#==============================================================================
#
#  Configuracao para duas filas em serie (tandem)
#  Fila 1: G/G/2/3 com chegadas externas
#  Fila 2: G/G/1/5 recebe todos os clientes da Fila 1
#
!PARAMETERS

arrivals:
  Fila1: 1.5

queues:
  Fila1:
    servers: 2
    capacity: 3
    minArrival: 1.0
    maxArrival: 4.0
    minService: 3.0
    maxService: 4.0
  Fila2:
    servers: 1
    capacity: 5
    minService: 2.0
    maxService: 3.0

network:
  - source: Fila1
    target: Fila2
    probability: 1.0

rndnumbersPerSeed: 100000
seeds:
  - 42
"""
    
    with open('config_tandem.yml', 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    
    return 'config_tandem.yml'


def main():
    """Função principal"""
    import sys
    
    print("=" * 80)
    print("SIMULADOR DE FILAS - FORMATO YAML ESTRUTURADO")
    print("=" * 80)
    print()
    
    # Verificar se foi passado arquivo como argumento
    if len(sys.argv) > 1:
        arquivo_yaml = sys.argv[1]
        print(f"Usando arquivo: {arquivo_yaml}")
    else:
        # Criar arquivo de exemplo
        print("Criando arquivo de exemplo para filas em tandem...")
        arquivo_yaml = criar_yaml_tandem()
        print(f"Arquivo criado: {arquivo_yaml}")
    
    print()
    print("Executando simulacao...")
    print()
    
    try:
        # Criar e executar simulador
        sim = SimuladorFilas(arquivo_yaml)
        sim.executar_simulacao(limite_aleatorios=100000)
        
        # Gerar relatório
        relatorio = sim.gerar_relatorio()
        print(relatorio)
        
        # Salvar relatório
        nome_saida = arquivo_yaml.replace('.yml', '_resultados.txt')
        with open(nome_saida, 'w', encoding='utf-8') as f:
            f.write(relatorio)
        
        print(f"\nResultados salvos em '{nome_saida}'")
        
    except Exception as e:
        print(f"Erro ao executar simulacao: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()