````markdown
# Queueing Network Simulator

Simulador de rede de filas com topologia arbitrária, configurado via arquivo `.yml`.

## Requisitos
- Python 3.9+
- `pip` atualizado

## Instalação das dependências
```bash
pip install -r requirements.txt
````

> `requirements.txt`:
>
> ```
> pyyaml>=6.0
> ```

## Como executar

```bash
python main.py model.yml
```

* Substitua `model.yml` pelo seu arquivo de configuração.
* A saída é impressa no terminal e salva em `simulation_result.txt`.

## Estrutura do projeto

* `main.py` — entrada
* `simulator.py`, `events.py`, `queue_node.py`, `scheduler.py` — núcleo do simulador
* `model.yml` — exemplo de configuração

```
```
