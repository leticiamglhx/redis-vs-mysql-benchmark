import argparse
import csv
import hashlib
import json
import platform
import random
import statistics
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from time import perf_counter

from carregar_mysql import COLUNAS_SQL, consultar as consultar_mysql
from carregar_redis import chave, conectar_redis, indice_bairro
from conexoes import conectar_mysql
from dados_comuns import (CAMPOS, PADRAO_AMOSTRA, carregar_amostra, salvar_json,
                          sha256, validar_corrida)

QUANTIDADES = (1000, 10000, 50000, 100000, 500000)


def validar_bancos(redis, mysql, corridas, lote=1000):

    with mysql.cursor(dictionary=True) as cursor:
        for posicao in range(0, len(corridas), lote):
            bloco = corridas[posicao:posicao + lote]
            with redis.pipeline(transaction=False) as pipe:
                for corrida in bloco:
                    pipe.hgetall(chave(corrida['id']))
                resultados = pipe.execute()
            ids = [c['id'] for c in bloco]
            cursor.execute(f'SELECT {COLUNAS_SQL} FROM corrida WHERE id IN '
                           f"({', '.join(['%s'] * len(ids))})", ids)
            sql = {r['id']: r for r in cursor.fetchall()}
            for esperado, hash_redis in zip(bloco, resultados):
                identificador = esperado['id']
                if not hash_redis or identificador not in sql:
                    raise ValueError(f'Corrida ausente em um dos bancos: {identificador}')
                if validar_corrida(hash_redis) != esperado or validar_corrida(sql[identificador]) != esperado:
                    raise ValueError(f'Corrida divergente: {identificador}')


def medir_redis(redis, ids, lote=None):
    inicio = perf_counter()
    if lote is None:
        for identificador in ids:
            if not redis.hgetall(chave(identificador)):
                raise ValueError('Corrida removida durante o benchmark.')
    else:
        with redis.pipeline(transaction=False) as pipe:
            for posicao in range(0, len(ids), lote):
                for identificador in ids[posicao:posicao + lote]:
                    pipe.hgetall(chave(identificador))
                if not all(pipe.execute()):
                    raise ValueError('Corrida removida durante o benchmark.')
    return perf_counter() - inicio


def medir_mysql(mysql, ids):
    with mysql.cursor() as cursor:
        inicio = perf_counter()
        for identificador in ids:
            cursor.execute(f'SELECT {COLUNAS_SQL} FROM corrida WHERE id = %s', (identificador,))
            if cursor.fetchone() is None:
                raise ValueError('Corrida removida durante o benchmark.')
        return perf_counter() - inicio


def resumo_medicoes(linhas):
    resumo = []
    for quantidade in sorted({l['consultas'] for l in linhas}):
        tempos = {modo: statistics.median(l['segundos'] for l in linhas
                  if l['consultas'] == quantidade and l['modo'] == modo)
                  for modo in ('redis', 'mysql', 'redis_pipeline')}
        resumo.append({'consultas': quantidade, **{f'{m}_s': t for m, t in tempos.items()},
                       **{f'{m}_qps': quantidade / t for m, t in tempos.items()},
                       'reducao_tempo_redis_pct': (tempos['mysql'] - tempos['redis']) / tempos['mysql'] * 100,
                       'reducao_tempo_pipeline_pct': (tempos['redis'] - tempos['redis_pipeline']) / tempos['redis'] * 100})
    return resumo


def executar(amostra=PADRAO_AMOSTRA, quantidades=QUANTIDADES, repeticoes=3,
             lote=1000, semente=2026, saida='resultados/benchmarks'):
    if repeticoes < 1 or lote < 1 or not quantidades or any(q < 1 for q in quantidades):
        raise ValueError('Quantidades, repetições e lote devem ser positivos.')
    corridas = carregar_amostra(amostra)
    ids_base = [c['id'] for c in corridas]
    redis = conectar_redis()
    mysql = None
    linhas = []
    pasta = Path(saida) / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8])
    pasta.mkdir(parents=True, exist_ok=False)
    metadados = {
        'status': 'em andamento', 'amostra': str(amostra), 'sha256_amostra': sha256(amostra),
        'registros': len(corridas), 'consultas': list(quantidades), 'repeticoes': repeticoes,
        'semente': semente, 'lote_pipeline': lote, 'python': platform.python_version(),
        'plataforma': platform.platform(), 'observacao': 'Não modificar os bancos durante os testes.',
    }
    salvar_json(pasta / 'metadados.json', metadados)
    try:
        redis.ping()
        mysql = conectar_mysql()

        mysql.autocommit = True
        metadados['redis_versao'] = redis.info('server').get('redis_version')
        with mysql.cursor() as cursor:
            cursor.execute('SELECT VERSION()')
            metadados['mysql_versao'] = cursor.fetchone()[0]
        salvar_json(pasta / 'metadados.json', metadados)
        validar_bancos(redis, mysql, corridas, lote)
        aquecimento = ids_base[:min(1000, len(ids_base))]
        medir_redis(redis, aquecimento)
        medir_redis(redis, aquecimento, lote)
        medir_mysql(mysql, aquecimento)
        rng = random.Random(semente)
        with (pasta / 'medicoes.csv').open('w', newline='', encoding='utf-8') as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=['consultas', 'repeticao', 'ordem', 'modo',
                                                         'segundos', 'qps', 'sha256_ids'])
            escritor.writeheader()
            for quantidade in quantidades:
                for repeticao in range(1, repeticoes + 1):
                    ids = rng.choices(ids_base, k=quantidade)
                    assinatura = hashlib.sha256(json.dumps(ids, ensure_ascii=False).encode()).hexdigest()
                    modos = ['redis', 'mysql', 'redis_pipeline']
                    rng.shuffle(modos)
                    for ordem, modo in enumerate(modos, 1):
                        if modo == 'mysql':
                            tempo = medir_mysql(mysql, ids)
                        else:
                            tempo = medir_redis(redis, ids, lote if modo == 'redis_pipeline' else None)
                        if tempo <= 0:
                            raise ValueError('Intervalo de tempo inválido.')
                        linha = {'consultas': quantidade, 'repeticao': repeticao, 'ordem': ordem,
                                 'modo': modo, 'segundos': tempo, 'qps': quantidade / tempo,
                                 'sha256_ids': assinatura}
                        linhas.append(linha)
                        escritor.writerow(linha)
                        arquivo.flush()
                        print(f'{quantidade} consultas | repetição {repeticao} | {modo}: {tempo:.6f} s')
        resumo = resumo_medicoes(linhas)
        salvar_json(pasta / 'resumo.json', resumo)

        validar_bancos(redis, mysql, corridas, lote)
        metadados['status'] = 'concluído'
        salvar_json(pasta / 'metadados.json', metadados)
        salvar_json(pasta / 'concluido.json', {'status': 'concluído', 'medicoes': len(linhas)})
        print(f'Resultados: {pasta}')
        return pasta
    except Exception as erro:
        metadados['status'] = 'falhou'
        salvar_json(pasta / 'metadados.json', metadados)
        salvar_json(pasta / 'falha.json', {'tipo': type(erro).__name__,
                                          'nota': 'Execução incompleta; não usar como resultado final.'})
        raise
    finally:
        redis.close()
        if mysql is not None:
            mysql.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--amostra', default=PADRAO_AMOSTRA)
    parser.add_argument('--consultas', type=int, nargs='+', default=list(QUANTIDADES))
    parser.add_argument('--repeticoes', type=int, default=3)
    parser.add_argument('--lote', type=int, default=1000)
    parser.add_argument('--semente', type=int, default=2026)
    args = parser.parse_args()
    executar(args.amostra, args.consultas, args.repeticoes, args.lote, args.semente)


if __name__ == '__main__':
    main()
