import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from dados_comuns import CAMPOS, PADRAO_AMOSTRA, salvar_json, sha256, validar_corrida
from explorar_dados import ler_blocos


def converter(linha, config):
    mapeamento = config['colunas']
    dados = {campo: str(linha[mapeamento[campo]]).strip() if mapeamento.get(campo) else ''
             for campo in CAMPOS}
    if config.get('id_componentes'):
        componentes = [str(linha[c]).strip() for c in config['id_componentes']]
        if not all(componentes):
            raise ValueError('id: componente obrigatório ausente')
        dados['id'] = ':'.join(quote(c, safe='') for c in componentes)
    for campo in ('valor', 'distancia'):
        valor = dados[campo]
        if config.get('milhar'):
            valor = valor.replace(config['milhar'], '')
        dados[campo] = valor.replace(config.get('decimal', '.'), '.')
    dados['data'] = datetime.strptime(dados['data'], config['formato_data']).isoformat(sep=' ')
    return validar_corrida(dados)


def tratar(config_path, saida, limite):
    config = json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
    obrigatorios = set(CAMPOS) - {'bairro_origem', 'bairro_destino'}
    if any(not config['colunas'].get(c) or 'PREENCHER' in config['colunas'][c] for c in obrigatorios):
        raise ValueError('Preencha as colunas reais em configuracao_dados.json.')
    if config.get('decimal', '.') == config.get('milhar'):
        raise ValueError('Separadores decimal e de milhar devem ser distintos.')
    saida = Path(saida)
    if saida.resolve() == Path(config['arquivo']).resolve():
        raise ValueError('A saída não pode substituir o arquivo original.')
    saida.parent.mkdir(parents=True, exist_ok=True)
    temporario = saida.with_suffix('.csv.tmp')
    rejeitados_path = saida.with_suffix('.rejeitados.csv')
    vistos = {}
    lidos = rejeitados = repetidos = 0
    with temporario.open('w', encoding='utf-8', newline='') as destino, \
            rejeitados_path.open('w', encoding='utf-8', newline='') as falhas:
        escritor = csv.DictWriter(destino, fieldnames=CAMPOS)
        escritor.writeheader()
        auditoria = csv.writer(falhas)
        auditoria.writerow(['registro_fonte', 'motivo'])
        for bloco in ler_blocos(config, limite):
            ausentes = set(filter(None, config['colunas'].values())) - set(bloco.columns)
            ausentes |= set(config.get('id_componentes', [])) - set(bloco.columns)
            if ausentes:
                raise ValueError(f'Colunas não encontradas: {sorted(ausentes)}')
            for linha in bloco.to_dict('records'):
                lidos += 1
                try:
                    corrida = converter(linha, config)
                except (ValueError, TypeError) as erro:
                    rejeitados += 1
                    auditoria.writerow([lidos, str(erro)])
                    continue
                anterior = vistos.get(corrida['id'])
                assinatura = hashlib.sha256(json.dumps(corrida, sort_keys=True).encode()).digest()
                if anterior is not None:
                    if anterior != assinatura:
                        raise ValueError(f'ID conflitante no registro {lidos}; saída não publicada.')
                    repetidos += 1
                    continue
                vistos[corrida['id']] = assinatura
                escritor.writerow(corrida)
    if not vistos:
        raise ValueError('Nenhum registro válido. Confira o arquivo de rejeições e o mapeamento.')
    temporario.replace(saida)
    resumo = {'fonte': config['arquivo'], 'configuracao': config,
              'limite_leitura': limite, 'lidos': lidos, 'validos': len(vistos),
              'rejeitados': rejeitados, 'duplicados_identicos': repetidos,
              'sha256_amostra': sha256(saida),
              'bairros_disponiveis': bool(config['colunas'].get('bairro_origem')),
              'criterio_amostra': 'primeiros registros da fonte; não é amostra aleatória'}
    salvar_json(saida.with_suffix('.meta.json'), resumo)
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configuracao_dados.json')
    parser.add_argument('--saida', default=PADRAO_AMOSTRA)
    parser.add_argument('--limite', type=int, help='Sem limite: fonte completa; memória cresce com IDs únicos.')
    args = parser.parse_args()
    if args.limite is not None and args.limite <= 0:
        parser.error('--limite deve ser positivo')
    tratar(args.config, args.saida, args.limite)


if __name__ == '__main__':
    main()
