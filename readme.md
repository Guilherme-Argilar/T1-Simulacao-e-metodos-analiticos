```markdown
# Queueing Network Simulator

Simulador de rede de filas com topologia arbitrária, configurado via arquivo `.yml`.

## Requisitos

- Python 3.9+
- `pip` atualizado

## Instalação das dependências

```bash
pip install -r requirements.txt
```

**Conteúdo do `requirements.txt`:**
```
pyyaml>=6.0
```

## Como executar

```bash
python main.py model.yml
```

- Substitua `model.yml` pelo seu arquivo de configuração
- A saída é impressa no terminal e salva em `simulation_result.txt`

## Estrutura do projeto

```
.
├── main.py              # Entrada principal
├── simulator.py         # Núcleo do simulador
├── events.py            # Sistema de eventos
├── queue_node.py        # Nó de fila
├── scheduler.py         # Escalonador
├── model.yml            # Exemplo de configuração
└── requirements.txt     # Dependências
```

## Exemplo de uso

```bash
# Clone o repositório (se aplicável)
git clone <seu-repositorio>
cd queueing-network-simulator

# Instale as dependências
pip install -r requirements.txt

# Execute a simulação
python main.py model.yml
```
```