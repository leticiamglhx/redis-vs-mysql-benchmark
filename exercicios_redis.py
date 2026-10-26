import uuid

from conexoes import conectar_redis


def executar():
    cliente = conectar_redis()
    prefixo = 'taxi:exercicio:' + uuid.uuid4().hex
    try:
        nome = prefixo + ':teste'
        cliente.set(nome, 'corrida de taxi', ex=120)
        print('GET:', cliente.get(nome), '| EXISTS:', cliente.exists(nome))
        print('DEL da chave criada pelo exercício:', cliente.delete(nome))
        for numero in range(1, 4):
            chave = f'{prefixo}:corrida:{numero}'
            cliente.hset(chave, mapping={'id': numero, 'data': '2024-01-01',
                         'origem': 'Origem didática', 'destino': 'Destino didático',
                         'valor': '10.00', 'distancia': '2.0'})
            cliente.expire(chave, 120)
            print('HGET:', cliente.hget(chave, 'origem'), '| HGETALL:', cliente.hgetall(chave))
        bairros = prefixo + ':bairros'
        cliente.sadd(bairros, 'Centro didático', 'Bairro didático', 'Centro didático')
        cliente.expire(bairros, 120)
        print('SMEMBERS:', cliente.smembers(bairros), '| SCARD:', cliente.scard(bairros),
              '| SISMEMBER:', cliente.sismember(bairros, 'Centro didático'))
        ranking = prefixo + ':ranking'
        cliente.zadd(ranking, {'Centro didático': 2, 'Bairro didático': 1})
        cliente.expire(ranking, 120)
        print('ZRANGE:', cliente.zrange(ranking, 0, -1, withscores=True))
        print('ZREVRANGE:', cliente.zrevrange(ranking, 0, -1, withscores=True))
        contador = prefixo + ':contador'
        cliente.incr(contador)
        cliente.expire(contador, 120)
        print('INCR:', cliente.incr(contador), '| GET:', cliente.get(contador))
        cache = prefixo + ':cache'
        cliente.set(cache, 'temporario', ex=60)
        cliente.expire(cache, 60)
        print('EXPIRE / TTL:', cliente.ttl(cache))
        print('Prefixo didático:', prefixo, '(não utilizado nos benchmarks)')
    finally:
        cliente.close()


if __name__ == '__main__':
    executar()
