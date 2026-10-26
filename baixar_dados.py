import argparse
import urllib.request
import zipfile
from pathlib import Path

from dados_comuns import sha256

URL = 'https://repositorio.dados.gov.br/seges/taxigov/v2/taxigov-corridas-completo.zip'


def baixar(url, destino):
    destino = Path(destino)
    if destino.exists():
        raise FileExistsError(f'Arquivo já existe: {destino}. Escolha outro destino.')
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + '.part')
    if parcial.exists():
        raise FileExistsError(f'Download parcial já existe: {parcial}. Escolha outro destino.')
    with urllib.request.urlopen(url, timeout=60) as resposta, parcial.open('xb') as arquivo:
        while bloco := resposta.read(1024 * 1024):
            arquivo.write(bloco)
    if destino.suffix.lower() == '.zip':
        if not zipfile.is_zipfile(parcial):
            raise ValueError('Resposta não é ZIP. Arquivo parcial preservado para diagnóstico.')
        with zipfile.ZipFile(parcial) as pacote:
            defeito = pacote.testzip()
            if defeito:
                raise ValueError(f'ZIP corrompido: {defeito}')

    parcial.rename(destino)
    print(f'Salvo: {destino}; SHA-256: {sha256(destino)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=URL, help='Também permite URL oficial do arquivo anual ou dicionário.')
    parser.add_argument('--destino', default='dados/taxigov-corridas-completo.zip')
    args = parser.parse_args()
    baixar(args.url, args.destino)
