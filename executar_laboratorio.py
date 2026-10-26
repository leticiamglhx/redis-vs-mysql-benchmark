import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from benchmark import QUANTIDADES, executar
from carregar_mysql import carregar as carregar_mysql
from carregar_redis import carregar as carregar_redis, demonstrar_cache
from conexoes import conectar_redis
from dados_comuns import PADRAO_AMOSTRA, carregar_amostra, registrar_resultado, sha256
from experimentos import executar_agregacoes
from explorar_dados import explorar
from graficos import gerar
from tratar_dados import tratar
from verificar_conexoes import verificar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configuracao_dados.json')
    parser.add_argument('--limite', type=int, help='Omitir para ler a fonte completa.')
    parser.add_argument('--amostra', default=PADRAO_AMOSTRA)
    parser.add_argument('--consultas', nargs='+', type=int, default=list(QUANTIDADES))
    parser.add_argument('--repeticoes', type=int, default=3)
    parser.add_argument('--lote', type=int, default=1000)
    args = parser.parse_args()
    if args.limite is not None and args.limite <= 0 or args.lote <= 0 or args.repeticoes <= 0 \
            or any(q <= 0 for q in args.consultas):
        parser.error('Limite, lote, repetições e consultas devem ser positivos.')
    if verificar():
        raise SystemExit('Conexões indisponíveis; nenhuma carga foi iniciada.')
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    explorar(argparse.Namespace(arquivo=config['arquivo'], membro_zip=config.get('membro_zip'),
             encoding=config.get('encoding', 'utf-8-sig'), separador=config['separador'],
             coluna_id=config['colunas']['id'], limite=args.limite, saida='resultados/exploracao.json'))
    tratar(args.config, args.amostra, args.limite)
    corridas = carregar_amostra(args.amostra)
    assinatura = sha256(args.amostra)
    execucao = datetime.now(timezone.utc).isoformat()
    tempo = carregar_mysql(corridas, args.lote)
    registrar_resultado('resultados/cargas.jsonl', {
        'execucao': execucao, 'banco': 'mysql', 'modo': 'executemany',
        'registros': len(corridas), 'lote': args.lote, 'segundos': tempo,
        'sha256_amostra': assinatura,
    })
    cliente = conectar_redis()
    try:
        carregar_redis(cliente, corridas, 'pipeline', args.lote)
        for modo in ('individual', 'pipeline'):
            tempo, novos = carregar_redis(cliente, corridas, modo, args.lote)
            registrar_resultado('resultados/cargas.jsonl', {
                'execucao': execucao, 'banco': 'redis', 'modo': modo, 'registros': len(corridas),
                'lote': args.lote, 'segundos': tempo, 'novos': novos,
                'sha256_amostra': assinatura, 'cenario': 'recarga aquecida',
            })
        print(demonstrar_cache(cliente))
    finally:
        cliente.close()
    pasta = executar(args.amostra, args.consultas, args.repeticoes, args.lote)
    gerar(pasta)
    if any(c['bairro_origem'] for c in corridas):
        executar_agregacoes(args.amostra, repeticoes=args.repeticoes, pasta=pasta / 'agregacoes')
    else:
        print('Experimentos por bairro pendentes: não há bairro_origem mapeado na fonte.')
    print('Fluxo concluído. Para os experimentos A-E completos, execute também experimentos.py.')


if __name__ == '__main__':
    main()
