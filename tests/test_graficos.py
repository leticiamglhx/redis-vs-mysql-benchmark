import json
import tempfile
import unittest
from pathlib import Path

from dados_comuns import salvar_json
from graficos import gerar


class TestGraficos(unittest.TestCase):
    def test_quatro_pngs_e_bloqueio_execucao_incompleta(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'incompleto'):
                gerar(pasta)
            salvar_json(pasta / 'concluido.json', {'status': 'concluído'})
            salvar_json(pasta / 'metadados.json', {'sha256_amostra': 'fixture'})
            salvar_json(pasta / 'resumo.json', [
                {'consultas': n, 'redis_s': n / 10, 'mysql_s': n / 5,
                 'redis_pipeline_s': n / 20, 'redis_qps': 10, 'mysql_qps': 5}
                for n in (1, 10)])
            cargas = pasta / 'cargas.jsonl'
            cargas.write_text('\n'.join(json.dumps({
                'banco': 'redis', 'cenario': 'recarga aquecida', 'sha256_amostra': 'fixture',
                'execucao': 'teste', 'modo': modo, 'segundos': tempo,
            }) for modo, tempo in [('individual', 2), ('pipeline', 1)]), encoding='utf-8')
            saida = gerar(pasta, cargas)
            arquivos = list(saida.glob('*.png'))
            self.assertEqual(len(arquivos), 4)
            for arquivo in arquivos:
                self.assertTrue(arquivo.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertGreater(arquivo.stat().st_size, 10000)


if __name__ == '__main__':
    unittest.main()
