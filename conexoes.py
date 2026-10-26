import os
from pathlib import Path

def carregar_ambiente():

    caminho = Path(__file__).resolve().parent / '.env'
    if not caminho.exists():
        return
    for numero, linha in enumerate(caminho.read_text(encoding='utf-8-sig').splitlines(), 1):
        linha = linha.strip()
        if not linha or linha.startswith('#'):
            continue
        nome, separador, valor = linha.partition('=')
        nome, valor = nome.strip(), valor.strip()
        if not separador or not nome.isidentifier():
            raise ValueError(f'.env: sintaxe inválida na linha {numero}.')
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ('"', "'"):
            valor = valor[1:-1]
        os.environ.setdefault(nome, valor)


carregar_ambiente()


def inteiro(nome, padrao, minimo, maximo):
    valor = int(os.getenv(nome, str(padrao)))
    if not minimo <= valor <= maximo:
        raise ValueError(f'{nome} deve estar entre {minimo} e {maximo}.')
    return valor


def conectar_redis():
    import redis

    return redis.Redis(
        host=os.getenv('REDIS_HOST', '127.0.0.1'),
        port=inteiro('REDIS_PORT', 6379, 1, 65535),
        db=inteiro('REDIS_DB', 0, 0, 2147483647),
        password=os.getenv('REDIS_PASSWORD') or None,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


def conectar_mysql():
    import mysql.connector

    if not os.getenv('MYSQL_PASSWORD'):
        raise ValueError('Defina MYSQL_PASSWORD no .env com a senha atual do MySQL.')
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST', '127.0.0.1'),
        port=inteiro('MYSQL_PORT', 3307, 1, 65535),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.environ['MYSQL_PASSWORD'],
        database=os.getenv('MYSQL_DATABASE', 'taxigov'),
        connection_timeout=5,
    )
