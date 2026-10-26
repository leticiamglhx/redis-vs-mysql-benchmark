import os
import unittest
import uuid

from carregar_redis import CARGA_LUA
from conexoes import conectar_redis
from conexoes import conectar_mysql
from carregar_mysql import UPSERT, consultar
from dados_comuns import CAMPOS, validar_corrida
from pathlib import Path
from test_projeto import corrida
import json


@unittest.skipUnless(os.getenv('TESTAR_REDIS') == '1', 'Defina TESTAR_REDIS=1 para testar servidor real.')
class TestRedisReal(unittest.TestCase):
    def test_recarga_e_mudanca_bairro_nao_duplicam_ranking(self):
        cliente = conectar_redis()
        prefixo = 'taxi:teste:' + uuid.uuid4().hex
        nomes = [prefixo + ':' + s for s in ('corrida', 'bairros', 'ranking', 'contador', 'bairroA', 'bairroB')]
        script = cliente.register_script(CARGA_LUA)
        registro = corrida()
        try:
            self.assertEqual(script(keys=nomes[:5], args=[json.dumps(registro)]), 1)
            self.assertEqual(script(keys=nomes[:5], args=[json.dumps(registro)]), 0)
            self.assertEqual(cliente.get(nomes[3]), '1')
            self.assertEqual(cliente.zscore(nomes[2], 'Centro'), 1)
            registro['bairro_origem'] = 'Outro'
            script(keys=nomes[:4] + [nomes[5]], args=[json.dumps(registro)])
            self.assertIsNone(cliente.zscore(nomes[2], 'Centro'))
            self.assertEqual(cliente.zscore(nomes[2], 'Outro'), 1)
            self.assertEqual(cliente.scard(nomes[4]), 0)
            self.assertEqual(cliente.smembers(nomes[5]), {'0001'})
        finally:

            cliente.delete(*nomes)
            cliente.close()


@unittest.skipUnless(os.getenv('TESTAR_MYSQL') == '1', 'Defina TESTAR_MYSQL=1 para testar servidor real.')
class TestMySQLReal(unittest.TestCase):
    def test_upsert_preserva_id_e_nao_duplica(self):
        conexao = conectar_mysql()
        try:
            ddl = (Path(__file__).resolve().parent.parent / 'banco.sql').read_text(encoding='utf-8')
            ddl = ddl[ddl.index('CREATE TABLE'):].strip().rstrip(';')
            ddl = ddl.replace('CREATE TABLE IF NOT EXISTS', 'CREATE TEMPORARY TABLE')
            with conexao.cursor() as cursor:
                cursor.execute(ddl)
                original = corrida()
                cursor.executemany(UPSERT, [tuple(original[c] for c in CAMPOS)] * 2)
                cursor.execute('SELECT COUNT(*) FROM corrida')
                self.assertEqual(cursor.fetchone()[0], 1)
            self.assertEqual(validar_corrida(consultar(conexao, '0001')), original)
        finally:
            conexao.close()
