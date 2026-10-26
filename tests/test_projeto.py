import csv
import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from benchmark import resumo_medicoes, validar_bancos
from dados_comuns import CAMPOS, carregar_amostra, validar_corrida
from explorar_dados import abrir_fonte
from tratar_dados import tratar, converter


def corrida(identificador='0001'):
    return {'id': identificador, 'data': '2024-01-02 10:20:30.000000',
            'origem': 'Endereço A', 'destino': 'Endereço B', 'valor': '1234.50',
            'distancia': '8.250', 'bairro_origem': 'Centro', 'bairro_destino': ''}


class TestDados(unittest.TestCase):
    def test_id_composto_separa_bases_e_codifica_delimitador(self):
        config = {'colunas': {c: c for c in CAMPOS},
                  'id_componentes': ['base_origem', 'id'],
                  'decimal': '.', 'milhar': None,
                  'formato_data': '%Y-%m-%d %H:%M:%S.%f'}
        primeiro = converter({**corrida(), 'base_origem': 'BASE_A'}, config)
        segundo = converter({**corrida(), 'base_origem': 'BASE_B'}, config)
        terceiro = converter({**corrida(), 'base_origem': 'BASE:A'}, config)
        self.assertEqual(primeiro['id'], 'BASE_A:0001')
        self.assertNotEqual(primeiro['id'], segundo['id'])
        self.assertEqual(terceiro['id'], 'BASE%3AA:0001')

    def test_preserva_id_e_decimal(self):
        dados = validar_corrida(corrida())
        self.assertEqual(dados['id'], '0001')
        dados['valor'] = Decimal('1234.50')
        self.assertEqual(validar_corrida(dados), corrida())

    def test_rejeita_nulos_negativos_nan_e_arredondamento(self):
        for campo, valor in [('id', ''), ('valor', 'NaN'), ('valor', '-1'),
                             ('valor', '1.001'), ('distancia', 'Infinity'), ('data', 'inválida')]:
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ValueError):
                validar_corrida({**corrida(), campo: valor})

    def test_zip_ambiguo_exige_membro(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'dados.zip'
            with zipfile.ZipFile(caminho, 'w') as pacote:
                pacote.writestr('a.csv', 'id\n1\n')
                pacote.writestr('b.csv', 'id\n2\n')
            with self.assertRaises(ValueError):
                with abrir_fonte(caminho):
                    pass
            with abrir_fonte(caminho, 'b.csv') as fonte:
                self.assertIn('2', fonte.read())

    def preparar(self, pasta, conflito=False):
        fonte = Path(pasta) / 'real.csv'
        fonte.write_text('codigo;quando;de;para;preco;km;bairro\n'
                         '0001;02/01/2024 10:20:30;Endereço A;Endereço B;1.234,50;8,250;Centro\n'
                         '0001;02/01/2024 10:20:30;Endereço A;Endereço B;'
                         + ('1.235,50' if conflito else '1.234,50') + ';8,250;Centro\n'
                         '0002;02/01/2024 10:20:30;A;B;-1;3;Centro\n', encoding='utf-8')
        config = {'arquivo': str(fonte), 'separador': ';', 'encoding': 'utf-8',
                  'decimal': ',', 'milhar': '.', 'formato_data': '%d/%m/%Y %H:%M:%S',
                  'colunas': dict(zip(CAMPOS, ['codigo', 'quando', 'de', 'para', 'preco', 'km', 'bairro', None]))}
        caminho = Path(pasta) / 'config.json'
        caminho.write_text(json.dumps(config), encoding='utf-8')
        return caminho

    def test_tratamento_audita_rejeicoes_e_duplicados(self):
        with tempfile.TemporaryDirectory() as pasta, redirect_stdout(io.StringIO()):
            config = self.preparar(pasta)
            saida = Path(pasta) / 'amostra.csv'
            tratar(config, saida, None)
            self.assertEqual(carregar_amostra(saida), [corrida()])
            meta = json.loads(saida.with_suffix('.meta.json').read_text(encoding='utf-8'))
            self.assertEqual((meta['lidos'], meta['validos'], meta['rejeitados'], meta['duplicados_identicos']),
                             (3, 1, 1, 1))

    def test_id_conflitante_nao_substitui_amostra_anterior(self):
        with tempfile.TemporaryDirectory() as pasta:
            config = self.preparar(pasta, conflito=True)
            saida = Path(pasta) / 'amostra.csv'
            saida.write_text('amostra anterior', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'conflitante'):
                tratar(config, saida, None)
            self.assertEqual(saida.read_text(encoding='utf-8'), 'amostra anterior')


class TestBenchmark(unittest.TestCase):
    def test_mediana_qps_e_percentuais(self):
        linhas = [{'consultas': 100, 'modo': modo, 'segundos': tempo}
                  for modo, tempos in [('redis', [2, 4, 3]), ('mysql', [6, 9, 12]),
                                       ('redis_pipeline', [1, 2, 1.5])] for tempo in tempos]
        resultado = resumo_medicoes(linhas)[0]
        self.assertEqual(resultado['redis_s'], 3)
        self.assertAlmostEqual(resultado['redis_qps'], 100 / 3)
        self.assertAlmostEqual(resultado['reducao_tempo_redis_pct'], 200 / 3)
        self.assertEqual(resultado['reducao_tempo_pipeline_pct'], 50)

    def test_benchmark_aborta_se_banco_ausente_ou_divergente(self):
        for resultado in ({}, {**corrida(), 'valor': '1.00'}):
            with self.subTest(resultado=resultado):
                redis = MagicMock()
                redis.pipeline.return_value.__enter__.return_value.execute.return_value = [resultado]
                mysql = MagicMock()
                mysql.cursor.return_value.__enter__.return_value.fetchall.return_value = [corrida()]
                with self.assertRaises(ValueError):
                    validar_bancos(redis, mysql, [corrida()])

    def test_validacao_aceita_mesma_amostra(self):
        redis, mysql = MagicMock(), MagicMock()
        redis.pipeline.return_value.__enter__.return_value.execute.return_value = [corrida()]
        mysql.cursor.return_value.__enter__.return_value.fetchall.return_value = [corrida()]
        validar_bancos(redis, mysql, [corrida()])


if __name__ == '__main__':
    unittest.main()
