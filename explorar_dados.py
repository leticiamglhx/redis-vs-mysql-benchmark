import argparse
import csv
import io
import json
import zipfile
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from dados_comuns import salvar_json


@contextmanager
def abrir_fonte(caminho, membro=None, encoding='utf-8-sig'):
    if zipfile.is_zipfile(caminho):
        with zipfile.ZipFile(caminho) as pacote:
            nomes = [n for n in pacote.namelist() if n.lower().endswith('.csv')]
            if membro is None:
                if len(nomes) != 1:
                    raise ValueError(f'Informe --membro-zip. CSVs disponíveis: {nomes}')
                membro = nomes[0]
            if membro not in nomes:
                raise ValueError('Membro CSV não encontrado no ZIP.')
            with pacote.open(membro) as binario:
                with io.TextIOWrapper(binario, encoding=encoding, newline='') as texto:
                    yield texto
    else:
        with open(caminho, encoding=encoding, newline='') as texto:
            yield texto


def ler_blocos(config, limite=None):
    with abrir_fonte(config['arquivo'], config.get('membro_zip'),
                     config.get('encoding', 'utf-8-sig')) as fonte:
        yield from pd.read_csv(
            fonte, sep=config['separador'], dtype='string',
            keep_default_na=False, chunksize=10000, nrows=limite,
        )


def explorar(args):
    config = {'arquivo': args.arquivo, 'membro_zip': args.membro_zip,
              'encoding': args.encoding, 'separador': args.separador}
    if not config['separador']:
        with abrir_fonte(args.arquivo, args.membro_zip, args.encoding) as fonte:
            config['separador'] = csv.Sniffer().sniff(fonte.read(65536), delimiters=';,\t|').delimiter
    nulos = {}
    registros = 0
    hashes = set()
    ids = set()
    duplicados = ids_duplicados = ids_nulos = 0
    exemplo = None
    tipos = None
    perfil = {}
    for bloco in ler_blocos(config, args.limite):
        if exemplo is None:
            exemplo = bloco.head(5)
            tipos = {str(c): str(t) for c, t in exemplo.replace('', pd.NA).infer_objects().dtypes.items()}
        registros += len(bloco)
        for coluna in bloco.columns:
            nulos[coluna] = nulos.get(coluna, 0) + int(bloco[coluna].str.strip().eq('').sum())
            valores = bloco[coluna].str.strip()
            preenchidos = valores[valores.ne('')]
            estatistica = perfil.setdefault(coluna, {'preenchidos': 0, 'numericos_formato_ponto': 0,
                                                     'comprimento_maximo': 0})
            estatistica['preenchidos'] += len(preenchidos)
            estatistica['numericos_formato_ponto'] += int(pd.to_numeric(preenchidos, errors='coerce').notna().sum())
            estatistica['comprimento_maximo'] = max(estatistica['comprimento_maximo'],
                                                    int(preenchidos.str.len().max()) if len(preenchidos) else 0)

        import hashlib
        for linha in bloco.itertuples(index=False, name=None):
            resumo = hashlib.sha256(json.dumps(linha, ensure_ascii=False).encode()).digest()
            duplicados += resumo in hashes
            hashes.add(resumo)
        if args.coluna_id:
            if args.coluna_id not in bloco:
                raise ValueError('Coluna de ID não encontrada.')
            for valor in bloco[args.coluna_id].str.strip():
                if not valor:
                    ids_nulos += 1
                else:
                    ids_duplicados += valor in ids
                    ids.add(valor)
    if exemplo is None:
        raise ValueError('Arquivo sem registros.')
    relatorio = {
        'arquivo': args.arquivo, 'limite_leitura': args.limite,
        'registros_lidos': registros, 'atributos': len(exemplo.columns),
        'colunas': list(exemplo.columns), 'tipos_leitura': tipos,
        'nota_tipos': 'Leitura textual preserva IDs. Tipos semânticos dependem do dicionário.',
        'nulos_ou_vazios': nulos, 'duplicados_completos_sha256': duplicados,
        'perfil_valores': perfil,
        'coluna_id': args.coluna_id,
        'ids_unicos': len(ids) if args.coluna_id else None,
        'ids_duplicados': ids_duplicados if args.coluna_id else None,
        'ids_nulos': ids_nulos if args.coluna_id else None,
        'configuracao_leitura': config,
    }
    salvar_json(args.saida, relatorio)
    print(exemplo.to_string(index=False))
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    print('Confira o dicionário antes de preencher configuracao_dados.json.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arquivo')
    parser.add_argument('--membro-zip')
    parser.add_argument('--encoding', default='utf-8-sig')
    parser.add_argument('--separador')
    parser.add_argument('--coluna-id')
    parser.add_argument('--limite', type=int)
    parser.add_argument('--saida', default='resultados/exploracao.json')
    args = parser.parse_args()
    if args.limite is not None and args.limite <= 0:
        parser.error('--limite deve ser positivo')
    explorar(args)


if __name__ == '__main__':
    main()
