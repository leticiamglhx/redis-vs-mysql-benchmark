# Redis vs MySQL — Benchmark de Desempenho

Laboratório prático de **Bancos de Dados Chave-Valor**, desenvolvido em Python, com o objetivo de comparar o desempenho do Redis e do MySQL utilizando dados reais de corridas de táxi do Governo Federal.

O projeto explora diferentes modelos de armazenamento, estratégias de consulta e técnicas de otimização, analisando as vantagens e limitações de cada tecnologia.

## Objetivo

Investigar em quais situações um banco de dados chave-valor, como o **Redis**, pode apresentar vantagens de desempenho em relação a um banco de dados relacional, como o **MySQL**.

Para isso, os mesmos registros são armazenados nos dois bancos e submetidos a experimentos de consulta e medição de desempenho.

## Tecnologias utilizadas

- **Python 3** — Desenvolvimento da aplicação
- **Redis** — Banco de dados chave-valor
- **MySQL** — Banco de dados relacional
- **Docker** — Gerenciamento dos ambientes
- **Pandas** — Leitura e tratamento dos dados
- **redis-py** — Integração Python com Redis
- **MySQL Connector** — Integração Python com MySQL
- **Matplotlib** — Visualização dos resultados

## Dataset

O projeto utiliza o **TaxiGov**, conjunto de dados público disponibilizado pelo Governo Federal, contendo informações sobre corridas de táxi.

Os registros são utilizados para representar corridas com atributos como identificador, data, origem, destino, valor e distância, conforme a disponibilidade dos campos no dataset.

**Fonte:** [Dataset TaxiGov — Governo Federal](https://repositorio.dados.gov.br/seges/taxigov/v2/taxigov-corridas-completo.zip)

## Funcionalidades previstas

- Leitura, exploração e tratamento do dataset TaxiGov.
- Armazenamento das corridas em Hashes do Redis.
- Criação de índices auxiliares utilizando Sets.
- Ranking de bairros utilizando Sorted Sets.
- Inserção otimizada de registros com Redis Pipeline.
- Armazenamento equivalente dos registros no MySQL.
- Consulta de corridas por identificador.
- Comparação do tempo de execução das consultas.
- Cálculo de consultas por segundo (QPS).
- Geração de gráficos comparativos.
- Análise de vantagens e limitações dos bancos.

## Estrutura do projeto

```text
redis-vs-mysql-benchmark/
│
├── dados/
│
├── explorar_dados.py
├── tratar_dados.py
├── carregar_redis.py
├── carregar_mysql.py
├── benchmark.py
├── graficos.py
├── main.py
│
├── banco.sql
├── requirements.txt
├── docker-compose.yml
└── README.md
```

*Estrutura planejada, sujeita a ajustes durante o desenvolvimento.*

## Como executar

### 1. Clonar o repositório

```bash
git clone https://github.com/SEU-USUARIO/redis-vs-mysql-benchmark.git
cd redis-vs-mysql-benchmark
```

### 2. Criar o ambiente virtual

```bash
python -m venv .venv
```

Ativar no Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar as dependências

```bash
python -m pip install pandas redis mysql-connector-python matplotlib
```

### 4. Iniciar os bancos de dados

Com o Docker Desktop em execução:

```bash
docker compose up -d redis mysql
```

Caso seja utilizado um arquivo Compose com nome diferente, informe-o utilizando a opção `-f`.

### 5. Executar a aplicação

Após configurar as conexões e carregar os dados:

```bash
python main.py
```

## Menu da aplicação

O sistema disponibilizará um menu interativo:

```text
========== TAXIGOV ==========

1 - Consultar no Redis
2 - Consultar no MySQL
3 - Executar benchmark
4 - Mostrar ranking de bairros
5 - Sair
```

## Experimentos de desempenho

Os benchmarks serão realizados utilizando os mesmos identificadores de corridas em ambos os bancos.

| Quantidade de consultas | Redis | MySQL |
|---|---|---|
| 1.000 | A medir | A medir |
| 10.000 | A medir | A medir |
| 50.000 | A medir | A medir
