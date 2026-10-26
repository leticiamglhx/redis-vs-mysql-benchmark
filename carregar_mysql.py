import argparse
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from conexoes import conectar_mysql
from dados_comuns import CAMPOS, PADRAO_AMOSTRA, carregar_amostra, registrar_resultado, sha256

COLUNAS_SQL = ', '.join(CAMPOS)
UPSERT = f'''INSERT INTO corrida ({COLUNAS_SQL})
    VALUES ({', '.join(['%s'] * len(CAMPOS))}) AS novo
    ON DUPLICATE KEY UPDATE {', '.join(f'{c}=novo.{c}' for c in CAMPOS if c != 'id')}'''


def criar_tabela(conexao):

    texto = Path(__file__).with_name('banco.sql').read_text(encoding='utf-8')
    tabela = texto[texto.index('CREATE TABLE'):].strip().rstrip(';')
    with conexao.cursor() as cursor:
        cursor.execute(tabela)
    conexao.commit()
    with conexao.cursor(dictionary=True) as cursor:
        cursor.execute('SHOW FULL COLUMNS FROM corrida')
        colunas = {c['Field']: c for c in cursor.fetchall()}
    esperados = {'id': 'varchar(191)', 'data': 'datetime(6)', 'origem': 'varchar(512)',
                 'destino': 'varchar(512)', 'valor': 'decimal(12,2)', 'distancia': 'decimal(13,3)',
                 'bairro_origem': 'varchar(512)', 'bairro_destino': 'varchar(512)'}
    if any(c not in colunas or colunas[c]['Type'].lower() != tipo for c, tipo in esperados.items()) \
            or colunas.get('id', {}).get('Key') != 'PRI' \
            or colunas.get('id', {}).get('Collation') != 'utf8mb4_bin':
        raise ValueError('Tabela corrida existente incompatível com banco.sql; '
                         'nenhuma migração automática foi feita.')


def consultar(conexao, identificador):
    with conexao.cursor(dictionary=True) as cursor:
        cursor.execute(f'SELECT {COLUNAS_SQL} FROM corrida WHERE id = %s', (identificador,))
        return cursor.fetchone()


def carregar(corridas, lote=1000):
    if lote <= 0:
        raise ValueError('O lote deve ser positivo.')
    conexao = conectar_mysql()
    try:
        criar_tabela(conexao)
        inicio = perf_counter()
        with conexao.cursor() as cursor:
            for indice in range(0, len(corridas), lote):
                valores = [tuple(c[campo] for campo in CAMPOS) for c in corridas[indice:indice + lote]]
                cursor.executemany(UPSERT, valores)
            conexao.commit()
        return perf_counter() - inicio
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--amostra', default=PADRAO_AMOSTRA)
    parser.add_argument('--lote', type=int, default=1000)
    args = parser.parse_args()
    corridas = carregar_amostra(args.amostra)
    tempo = carregar(corridas, args.lote)
    registrar_resultado('resultados/cargas.jsonl', {
        'execucao': datetime.now(timezone.utc).isoformat(), 'banco': 'mysql',
        'modo': 'executemany', 'registros': len(corridas), 'lote': args.lote,
        'segundos': tempo, 'sha256_amostra': sha256(args.amostra),
    })
    print(f'MySQL: {len(corridas)} registros em {tempo:.6f} s.')


if __name__ == '__main__':
    main()
