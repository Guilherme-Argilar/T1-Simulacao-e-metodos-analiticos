import random
import heapq
from collections import defaultdict
from typing import List, Tuple, Dict

class SimuladorFila:
    def __init__(self, num_servidores: int, capacidade_fila: int, 
                 tempo_chegada_min: float, tempo_chegada_max: float,
                 tempo_atendimento_min: float, tempo_atendimento_max: float,
                 seed: int = None):
        """
        Inicializa o simulador de fila G/G/c/K
        
        Args:
            num_servidores: Número de servidores (c)
            capacidade_fila: Capacidade total do sistema (K)
            tempo_chegada_min: Tempo mínimo entre chegadas
            tempo_chegada_max: Tempo máximo entre chegadas
            tempo_atendimento_min: Tempo mínimo de atendimento
            tempo_atendimento_max: Tempo máximo de atendimento
            seed: Semente para reprodutibilidade
        """
        self.num_servidores = num_servidores
        self.capacidade_fila = capacidade_fila
        self.tempo_chegada_min = tempo_chegada_min
        self.tempo_chegada_max = tempo_chegada_max
        self.tempo_atendimento_min = tempo_atendimento_min
        self.tempo_atendimento_max = tempo_atendimento_max
        
        if seed:
            random.seed(seed)

        self.tempo_atual = 0.0
        self.tempo_ultimo_evento = 0.0
        self.clientes_perdidos = 0
        self.clientes_atendidos = 0
        self.contador_aleatorios = 0
        

        self.estado_atual = 0
        self.tempo_por_estado = defaultdict(float)
        

        self.eventos = []
        

        self.servidores_ocupados = []
        
    def gerar_tempo_chegada(self) -> float:
        """Gera tempo entre chegadas (uniforme)"""
        self.contador_aleatorios += 1
        return random.uniform(self.tempo_chegada_min, self.tempo_chegada_max)
    
    def gerar_tempo_atendimento(self) -> float:
        """Gera tempo de atendimento (uniforme)"""
        self.contador_aleatorios += 1
        return random.uniform(self.tempo_atendimento_min, self.tempo_atendimento_max)
    
    def atualizar_tempo_estado(self, novo_tempo: float):
        """Atualiza o tempo acumulado no estado atual"""
        tempo_decorrido = novo_tempo - self.tempo_ultimo_evento
        self.tempo_por_estado[self.estado_atual] += tempo_decorrido
        self.tempo_ultimo_evento = novo_tempo
    
    def processar_chegada(self, tempo_evento: float):
        """Processa evento de chegada de cliente"""
        self.atualizar_tempo_estado(tempo_evento)
        self.tempo_atual = tempo_evento
        
        if self.estado_atual < self.capacidade_fila:
            self.estado_atual += 1
            if len(self.servidores_ocupados) < self.num_servidores:
                tempo_atendimento = self.gerar_tempo_atendimento()
                tempo_fim_atendimento = self.tempo_atual + tempo_atendimento
                heapq.heappush(self.eventos, (tempo_fim_atendimento, 'saida'))
                self.servidores_ocupados.append(tempo_fim_atendimento)
        else:
            self.clientes_perdidos += 1
        
        if self.contador_aleatorios < 100000:
            tempo_entre_chegadas = self.gerar_tempo_chegada()
            proxima_chegada = self.tempo_atual + tempo_entre_chegadas
            heapq.heappush(self.eventos, (proxima_chegada, 'chegada'))
    
    def processar_saida(self, tempo_evento: float):
        """Processa evento de saída de cliente"""
        self.atualizar_tempo_estado(tempo_evento)
        self.tempo_atual = tempo_evento
        
        self.servidores_ocupados.remove(tempo_evento)
        self.clientes_atendidos += 1
        
        clientes_em_fila = self.estado_atual - len(self.servidores_ocupados) - 1
        
        if clientes_em_fila > 0:
            tempo_atendimento = self.gerar_tempo_atendimento()
            tempo_fim_atendimento = self.tempo_atual + tempo_atendimento
            heapq.heappush(self.eventos, (tempo_fim_atendimento, 'saida'))
            self.servidores_ocupados.append(tempo_fim_atendimento)
        
        self.estado_atual -= 1
    
    def executar_simulacao(self, limite_aleatorios: int = 100000):
        """
        Executa a simulação até usar o número especificado de aleatórios
        """
        heapq.heappush(self.eventos, (2.0, 'chegada'))
        
        while self.eventos and self.contador_aleatorios <= limite_aleatorios:
            tempo_evento, tipo_evento = heapq.heappop(self.eventos)
            
            if tipo_evento == 'chegada':
                self.processar_chegada(tempo_evento)
            elif tipo_evento == 'saida':
                self.processar_saida(tempo_evento)
        
        self.atualizar_tempo_estado(self.tempo_atual)
    
    def calcular_distribuicao_probabilidades(self) -> Dict[int, float]:
        """Calcula a distribuição de probabilidades dos estados"""
        tempo_total = sum(self.tempo_por_estado.values())
        distribuicao = {}
        
        for estado in range(self.capacidade_fila + 1):
            if estado in self.tempo_por_estado:
                distribuicao[estado] = self.tempo_por_estado[estado] / tempo_total
            else:
                distribuicao[estado] = 0.0
        
        return distribuicao
    
    def validar_resultados(self) -> str:
        """Valida a consistência dos resultados da simulação"""
        erros = []
        avisos = []
        
        distribuicao = self.calcular_distribuicao_probabilidades()
        soma_prob = sum(distribuicao.values())
        if abs(soma_prob - 1.0) > 0.001:
            erros.append(f"Soma das probabilidades = {soma_prob:.6f} (deveria ser 1.0)")
        
        for estado, tempo in self.tempo_por_estado.items():
            if tempo < 0:
                erros.append(f"Tempo negativo no estado {estado}: {tempo}")
        
        if self.contador_aleatorios > 100001:
            avisos.append(f"Usou {self.contador_aleatorios} aleatorios (esperado <= 100001)")
        
        if self.num_servidores == 1 and self.clientes_perdidos == 0:
            avisos.append("G/G/1/K sem perdas pode indicar sistema subdimensionado na simulacao")
        
        tempo_medio_chegada = (self.tempo_chegada_min + self.tempo_chegada_max) / 2
        tempo_esperado_min = tempo_medio_chegada * 40000
        if self.tempo_atual < tempo_esperado_min:
            avisos.append(f"Tempo de simulacao pode estar muito curto: {self.tempo_atual:.2f}")
        
        resultado = []
        if erros:
            resultado.append("ERROS ENCONTRADOS:")
            for erro in erros:
                resultado.append(f"  [ERRO] {erro}")
        else:
            resultado.append("[OK] Nenhum erro de consistencia encontrado")
        
        if avisos:
            resultado.append("\nAVISOS:")
            for aviso in avisos:
                resultado.append(f"  [AVISO] {aviso}")
        
        return "\n".join(resultado)
    
    def relatorio(self) -> str:
        """Gera relatório completo da simulação"""
        distribuicao = self.calcular_distribuicao_probabilidades()
        tempo_total = sum(self.tempo_por_estado.values())
        
        relatorio = []
        relatorio.append("=" * 60)
        relatorio.append(f"RELATORIO DE SIMULACAO - G/G/{self.num_servidores}/{self.capacidade_fila}")
        relatorio.append("=" * 60)
        relatorio.append(f"Parametros:")
        relatorio.append(f"  - Tempo entre chegadas: [{self.tempo_chegada_min}, {self.tempo_chegada_max}]")
        relatorio.append(f"  - Tempo de atendimento: [{self.tempo_atendimento_min}, {self.tempo_atendimento_max}]")
        relatorio.append(f"  - Numero de servidores: {self.num_servidores}")
        relatorio.append(f"  - Capacidade do sistema: {self.capacidade_fila}")
        relatorio.append("")
        
        relatorio.append("Resultados da Simulacao:")
        relatorio.append(f"  - Tempo global de simulacao: {self.tempo_atual:.2f}")
        relatorio.append(f"  - Numeros aleatorios utilizados: {self.contador_aleatorios}")
        relatorio.append(f"  - Clientes atendidos: {self.clientes_atendidos}")
        relatorio.append(f"  - Clientes perdidos: {self.clientes_perdidos}")
        if (self.clientes_atendidos + self.clientes_perdidos) > 0:
            taxa_perda = self.clientes_perdidos / (self.clientes_atendidos + self.clientes_perdidos)
            relatorio.append(f"  - Taxa de perda: {taxa_perda:.4f} ({taxa_perda*100:.2f}%)")
        relatorio.append("")
        
        relatorio.append("Distribuicao de Probabilidades dos Estados:")
        relatorio.append("-" * 40)
        relatorio.append(f"{'Estado':<10} {'Tempo Acum.':<15} {'Probabilidade':<15}")
        relatorio.append("-" * 40)
        
        for estado in sorted(distribuicao.keys()):
            tempo = self.tempo_por_estado.get(estado, 0)
            prob = distribuicao[estado]
            relatorio.append(f"{estado:<10} {tempo:<15.2f} {prob:<15.4f}")
        
        relatorio.append("-" * 40)
        
        relatorio.append("")
        relatorio.append("Metricas de Desempenho:")
        
        L = sum(estado * prob for estado, prob in distribuicao.items())
        relatorio.append(f"  - Numero medio de clientes no sistema (L): {L:.4f}")
        
        prob_vazio = distribuicao.get(0, 0)
        taxa_ocupacao = 1 - prob_vazio
        relatorio.append(f"  - Taxa de ocupacao do sistema: {taxa_ocupacao:.4f}")
        
        relatorio.append("")
        relatorio.append("Validacao dos Resultados:")
        relatorio.append(self.validar_resultados())
        
        relatorio.append("=" * 60)
        
        return "\n".join(relatorio)


def main():
    print("SIMULADOR DE FILAS - G/G/c/K")
    print("=" * 60)
    print()
    

    print("Executando simulação G/G/1/5...")
    sim1 = SimuladorFila(
        num_servidores=1,
        capacidade_fila=5,
        tempo_chegada_min=2,
        tempo_chegada_max=5,
        tempo_atendimento_min=3,
        tempo_atendimento_max=5,
        seed=42  
    )
    sim1.executar_simulacao(limite_aleatorios=100000)
    print(sim1.relatorio())
    print("\n\n")
    
    print("Executando simulação G/G/2/5...")
    sim2 = SimuladorFila(
        num_servidores=2,
        capacidade_fila=5,
        tempo_chegada_min=2,
        tempo_chegada_max=5,
        tempo_atendimento_min=3,
        tempo_atendimento_max=5,
        seed=42  
    )
    sim2.executar_simulacao(limite_aleatorios=100000)
    print(sim2.relatorio())
    

    with open("resultados_simulacao.txt", "w", encoding="utf-8") as f:
        f.write("SIMULADOR DE FILAS - G/G/c/K\n")
        f.write("=" * 60 + "\n\n")
        

        sim1_file = SimuladorFila(1, 5, 2, 5, 3, 5, seed=42)
        sim1_file.executar_simulacao(limite_aleatorios=100000)
        f.write(sim1_file.relatorio())
        f.write("\n\n")
        
        sim2_file = SimuladorFila(2, 5, 2, 5, 3, 5, seed=42)
        sim2_file.executar_simulacao(limite_aleatorios=100000)
        f.write(sim2_file.relatorio())
    
    print("\n" + "=" * 60)
    print("Resultados salvos em 'resultados_simulacao.txt'")


if __name__ == "__main__":
    main()