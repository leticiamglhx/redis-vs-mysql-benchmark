import argparse
import json
import statistics
import uuid
from collections import Counter
from decimal import Decimal
from pathlib import Path
from time import perf_counter

from benchmark import executar, validar_bancos
from carregar_redis import chave, indice_bairro
from conexoes import conectar_mysql, conectar_redis
from dados_comuns import PADRAO_AMOSTRA, carregar_amostra, salvar_json, sha256


def medir(funcao):
    inicio = perf_counter()
    resultado = funcao()
    return resultado, perf_counter() - inicio


def executar_agregacoes(amostra, bairro=None, repeticoes=3, pasta='resultados/agregacoes'):
    if repeticoes < 1:
        raise ValueError('Repetições devem ser positivas.')
    corridas = carregar_amostra(amostra)
    ids = {c['id'] for c in corridas}
    bairros = Counter(c['bairro_origem'] for c in corridas if c['bairro_origem'])
    if not bairros:
        raise ValueError('Dataset sem bairro_origem mapeado; não usar endereço ou cidade como bairro.')
    bairro = bairro or bairros.most_common(1)[0][0]
    if bairro not in bairros:
        raise ValueError('Bairro não encontrado na amostra.')
    redis = conectar_redis()
    mysql = None
    try:
        mysql = conectar_mysql()
        mysql.autocommit = True
        validar_bancos(redis, mysql, corridas)
        ranking_temporario = 'taxi:benchmark:' + uuid.uuid4().hex + ':ranking'

        with redis.pipeline(transaction=True) as pipe:
            pipe.zadd(ranking_temporario, dict(bairros))
            pipe.expire(ranking_temporario, 3600)
            pipe.execute()

        with mysql.cursor() as cursor:
            cursor.execute('CREATE TEMPORARY TABLE benchmark_amostra '
                           '(id VARCHAR(191) COLLATE utf8mb4_bin PRIMARY KEY) CHARACTER SET utf8mb4')
            cursor.executemany('INSERT INTO benchmark_amostra (id) VALUES (%s)', [(i,) for i in ids])

            def sql(consulta, parametros=()):
                cursor.execute(consulta, parametros)
                return cursor.fetchall()

            def hashes_amostra():
                resultados = []
                lista_ids = sorted(ids)
                with redis.pipeline(transaction=False) as pipe:
                    for posicao in range(0, len(lista_ids), 1000):
                        for identificador in lista_ids[posicao:posicao + 1000]:
                            pipe.hgetall(chave(identificador))
                        resultados.extend(pipe.execute())
                return resultados

            def ranking_amostra():
                return [(nome, int(total)) for nome, total in
                        redis.zrevrange(ranking_temporario, 0, 9, withscores=True)]

            def media_redis():
                valores = [Decimal(r['valor']) for r in hashes_amostra()]
                return sum(valores) / len(valores)

            base = ' FROM corrida c JOIN benchmark_amostra a ON a.id = c.id '
            operacoes = {
                'bairro': (
                    lambda: sorted(ids.intersection(redis.smembers(indice_bairro(bairro)))),
                    lambda: sorted(r[0] for r in sql('SELECT c.id' + base + 'WHERE c.bairro_origem = %s', (bairro,))),
                ),
                'top10': (
                    ranking_amostra,
                    lambda: [(r[0], int(r[1])) for r in sql('SELECT c.bairro_origem, COUNT(*)' + base +
                             "WHERE c.bairro_origem <> '' GROUP BY c.bairro_origem "
                             'ORDER BY COUNT(*) DESC, c.bairro_origem DESC LIMIT 10')],
                ),
                'media_valores': (media_redis, lambda: sql('SELECT AVG(c.valor)' + base)[0][0]),
            }
            linhas = []
            for nome, funcoes in operacoes.items():
                for funcao in funcoes:
                    funcao()
                for repeticao in range(1, repeticoes + 1):
                    respostas = {}
                    ordem = (0, 1) if repeticao % 2 else (1, 0)
                    for indice in ordem:
                        resultado, tempo = medir(funcoes[indice])
                        modo = ('redis', 'mysql')[indice]
                        respostas[modo] = resultado
                        linhas.append({'operacao': nome, 'modo': modo, 'repeticao': repeticao,
                                       'segundos': tempo})
                    if nome == 'media_valores':
                        iguais = abs(respostas['redis'] - respostas['mysql']) < Decimal('0.000001')
                    else:
                        iguais = respostas['redis'] == respostas['mysql']
                    if not iguais:
                        raise ValueError(f'Resultados divergentes no experimento {nome}.')
            salvar_json(Path(pasta) / 'agregacoes.json', {
                'sha256_amostra': sha256(amostra), 'registros': len(ids), 'bairro': bairro,
                'escopo': 'IDs da amostra; preparação da tabela temporária fora do tempo',
                'nota_top10': 'Redis consulta Sorted Set temporário pré-computado da amostra; '
                              'MySQL calcula GROUP BY. Preparação fora do tempo; chave expira em 1 h.',
                'medicoes': linhas,
            })
            print(f'Experimentos C-E salvos em {pasta}.')
    finally:
        redis.close()
        if mysql is not None:
            mysql.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--amostra', default=PADRAO_AMOSTRA)
    parser.add_argument('--bairro')
    parser.add_argument('--repeticoes', type=int, default=3)
    args = parser.parse_args()

    executar(args.amostra, [1, 10000], args.repeticoes)
    executar_agregacoes(args.amostra, args.bairro, args.repeticoes)
