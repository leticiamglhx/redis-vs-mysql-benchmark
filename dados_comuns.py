import csv
import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

CAMPOS = ('id', 'data', 'origem', 'destino', 'valor', 'distancia',
          'bairro_origem', 'bairro_destino')
PADRAO_AMOSTRA = 'dados/corridas_tratadas.csv'


def validar_corrida(registro):
    corrida = {campo: '' if registro.get(campo) is None else str(registro.get(campo, '')).strip()
               for campo in CAMPOS}
    for campo in ('id', 'data', 'origem', 'destino'):
        if not corrida[campo]:
            raise ValueError(f'{campo}: valor obrigatório ausente')
    if len(corrida['id']) > 191:
        raise ValueError('id: máximo de 191 caracteres')
    for campo in ('origem', 'destino', 'bairro_origem', 'bairro_destino'):
        if len(corrida[campo]) > 512:
            raise ValueError(f'{campo}: máximo de 512 caracteres')
    data = datetime.fromisoformat(corrida['data'])
    if data.tzinfo is not None:
        raise ValueError('data: normalize o fuso antes de carregar')
    if not 1000 <= data.year <= 9999:
        raise ValueError('data fora do intervalo MySQL DATETIME')
    corrida['data'] = data.isoformat(sep=' ', timespec='microseconds')
    for campo, casas in (('valor', 2), ('distancia', 3)):
        try:
            numero = Decimal(corrida[campo])
            if not numero.is_finite() or numero < 0 or numero >= Decimal('10000000000'):
                raise ValueError(f'{campo}: número fora do intervalo')
            quantizado = numero.quantize(Decimal(10) ** -casas)
            if quantizado != numero:
                raise ValueError(f'{campo}: mais de {casas} casas decimais')
            corrida[campo] = f'{quantizado:.{casas}f}'
        except InvalidOperation as erro:
            raise ValueError(f'{campo}: número inválido') from erro
    return corrida


def carregar_amostra(caminho=PADRAO_AMOSTRA):
    vistos = set()
    corridas = []
    with open(caminho, encoding='utf-8', newline='') as arquivo:
        leitor = csv.DictReader(arquivo)
        if leitor.fieldnames != list(CAMPOS):
            raise ValueError('Cabeçalho incompatível; execute tratar_dados.py.')
        for linha, registro in enumerate(leitor, 2):
            try:
                corrida = validar_corrida(registro)
            except ValueError as erro:
                raise ValueError(f'Linha {linha}: {erro}') from erro
            if corrida['id'] in vistos:
                raise ValueError(f'ID duplicado na linha {linha}')
            vistos.add(corrida['id'])
            corridas.append(corrida)
    if not corridas:
        raise ValueError('Amostra vazia.')
    return corridas


def sha256(caminho):
    resumo = hashlib.sha256()
    with open(caminho, 'rb') as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b''):
            resumo.update(bloco)
    return resumo.hexdigest()


def salvar_json(caminho, conteudo):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2), encoding='utf-8')


def registrar_resultado(caminho, resultado):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open('a', encoding='utf-8') as arquivo:
        arquivo.write(json.dumps(resultado, ensure_ascii=False) + '\n')
