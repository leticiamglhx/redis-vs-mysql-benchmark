import argparse
import json
import uuid
from datetime import datetime, timezone
from time import perf_counter
from urllib.parse import quote

from conexoes import conectar_redis
from dados_comuns import CAMPOS, PADRAO_AMOSTRA, carregar_amostra, registrar_resultado, sha256

RANKING = 'taxi:ranking:bairros'
BAIRROS = 'taxi:bairros'
CONTADOR = 'taxi:contador:corridas'



CARGA_LUA = r'''
local function tipo(chave)
    return redis.call('TYPE', chave).ok
end
local function exigir(chave, esperado)
    local t = tipo(chave)
    if t ~= 'none' and t ~= esperado then error('Tipo incompatível: '..chave) end
end
exigir(KEYS[1], 'hash')
exigir(KEYS[2], 'set')
exigir(KEYS[3], 'zset')
exigir(KEYS[4], 'string')
if redis.call('EXISTS', KEYS[4]) == 1 then
    if not string.match(redis.call('GET', KEYS[4]), '^%d+$') then
        error('Contador inválido')
    end
end
local existe = redis.call('EXISTS', KEYS[1])
if existe == 1 and redis.call('HGET', KEYS[1], '_laboratorio') ~= 'taxigov-v1' then
    error('Hash existente pertence a outra carga; nenhuma substituição automática')
end
local anterior = redis.call('HGET', KEYS[1], 'bairro_origem') or ''
local indice_anterior = redis.call('HGET', KEYS[1], '_indice') or ''
local dados = cjson.decode(ARGV[1])
local bairro = dados['bairro_origem']
if indice_anterior ~= '' then exigir(indice_anterior, 'set') end
if KEYS[5] ~= '' then exigir(KEYS[5], 'set') end
if anterior ~= bairro and anterior ~= '' then
    redis.call('SREM', indice_anterior, dados['id'])
    local restantes = redis.call('ZINCRBY', KEYS[3], -1, anterior)
    if tonumber(restantes) <= 0 then
        redis.call('ZREM', KEYS[3], anterior)
        redis.call('SREM', KEYS[2], anterior)
    end
end
for campo, valor in pairs(dados) do redis.call('HSET', KEYS[1], campo, valor) end
redis.call('HSET', KEYS[1], '_laboratorio', 'taxigov-v1', '_indice', KEYS[5])
if bairro ~= '' then
    redis.call('SADD', KEYS[2], bairro)
    redis.call('SADD', KEYS[5], dados['id'])
    if existe == 0 or anterior ~= bairro then redis.call('ZINCRBY', KEYS[3], 1, bairro) end
end
if existe == 0 then redis.call('INCR', KEYS[4]) end
return 1 - existe
'''


def chave(identificador):
    return f'taxi:corrida:{identificador}'


def indice_bairro(bairro):
    return 'taxi:bairro:' + quote(bairro, safe='')


def consultar(cliente, identificador):
    registro = cliente.hgetall(chave(identificador))
    return {campo: registro.get(campo, '') for campo in CAMPOS} if registro else None


def ranking(cliente, quantidade=10):
    return cliente.zrevrange(RANKING, 0, quantidade - 1, withscores=True)


def argumentos(corrida):
    bairro = corrida['bairro_origem']
    return [chave(corrida['id']), BAIRROS, RANKING, CONTADOR,
            indice_bairro(bairro) if bairro else ''], [json.dumps(corrida, ensure_ascii=False)]


def carregar(cliente, corridas, modo='pipeline', lote=1000):
    if modo not in ('individual', 'pipeline') or lote <= 0:
        raise ValueError('Modo ou lote inválido.')
    script = cliente.register_script(CARGA_LUA)

    cliente.script_load(CARGA_LUA)
    novos = 0
    inicio = perf_counter()
    if modo == 'individual':
        for corrida in corridas:
            keys, args = argumentos(corrida)
            novos += script(keys=keys, args=args)
    else:
        with cliente.pipeline(transaction=False) as pipe:
            for inicio_lote in range(0, len(corridas), lote):
                for corrida in corridas[inicio_lote:inicio_lote + lote]:
                    keys, args = argumentos(corrida)
                    script(keys=keys, args=args, client=pipe)
                novos += sum(pipe.execute())
    return perf_counter() - inicio, novos


def demonstrar_cache(cliente):
    nome = f'taxi:cache:demonstracao:{uuid.uuid4().hex}'
    cliente.set(nome, 'cache temporario', ex=60)
    cliente.expire(nome, 60)
    return {'chave': nome, 'existe': bool(cliente.exists(nome)), 'ttl': cliente.ttl(nome)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--amostra', default=PADRAO_AMOSTRA)
    parser.add_argument('--modo', choices=['individual', 'pipeline', 'comparar'], default='pipeline')
    parser.add_argument('--lote', type=int, default=1000)
    parser.add_argument('--demo-cache', action='store_true')
    args = parser.parse_args()
    corridas = carregar_amostra(args.amostra)
    cliente = conectar_redis()
    try:
        cliente.ping()
        execucao = datetime.now(timezone.utc).isoformat()
        modos = ['individual', 'pipeline'] if args.modo == 'comparar' else [args.modo]
        if args.modo == 'comparar':

            carregar(cliente, corridas, 'pipeline', args.lote)
        for modo in modos:
            tempo, novos = carregar(cliente, corridas, modo, args.lote)
            registrar_resultado('resultados/cargas.jsonl', {
                'execucao': execucao, 'banco': 'redis', 'modo': modo,
                'registros': len(corridas), 'novos': novos, 'segundos': tempo,
                'lote': args.lote, 'sha256_amostra': sha256(args.amostra),
                'cenario': 'recarga aquecida' if args.modo == 'comparar' else 'carga ou atualização',
            })
            print(f'Redis {modo}: {len(corridas)} registros; {novos} novos; {tempo:.6f} s.')
        if args.demo_cache:
            print(demonstrar_cache(cliente))
    finally:
        cliente.close()


if __name__ == '__main__':
    main()
