import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parent / 'tmp' / 'matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def salvar(figura, caminho):
    figura.tight_layout()
    figura.savefig(caminho, dpi=160)
    plt.close(figura)


def gerar(pasta_benchmark, cargas='resultados/cargas.jsonl'):
    pasta = Path(pasta_benchmark)
    if not (pasta / 'concluido.json').exists():
        raise ValueError('Benchmark incompleto: marcador concluido.json ausente.')
    resumo = json.loads((pasta / 'resumo.json').read_text(encoding='utf-8'))
    metadados = json.loads((pasta / 'metadados.json').read_text(encoding='utf-8'))
    saida = pasta / 'graficos'
    saida.mkdir(exist_ok=True)
    consultas = [r['consultas'] for r in resumo]
    for arquivo, eixo, series in (
        ('01_tempo.png', 'Tempo mediano (s)', [('Redis', 'redis_s'), ('MySQL', 'mysql_s')]),
        ('02_qps.png', 'Consultas/s (N / tempo mediano)', [('Redis', 'redis_qps'), ('MySQL', 'mysql_qps')]),
        ('03_pipeline.png', 'Tempo mediano (s)', [('Redis individual', 'redis_s'), ('Redis Pipeline', 'redis_pipeline_s')]),
    ):
        fig, ax = plt.subplots(figsize=(8, 5))
        for nome, campo in series:
            ax.plot(consultas, [r[campo] for r in resumo], marker='o', label=nome)
        ax.set(xlabel='Número de consultas', ylabel=eixo, title=eixo + ' — TaxiGov')
        ax.grid(alpha=.3)
        ax.legend()
        salvar(fig, saida / arquivo)
    if Path(cargas).exists():
        registros = [json.loads(l) for l in Path(cargas).read_text(encoding='utf-8').splitlines() if l.strip()]

        pares = {}
        for r in registros:
            if r.get('banco') == 'redis' and r.get('cenario') == 'recarga aquecida' \
                    and r.get('sha256_amostra') == metadados['sha256_amostra']:
                pares.setdefault(r['execucao'], {})[r['modo']] = r
        completos = [p for p in pares.values() if {'individual', 'pipeline'} <= p.keys()]
        if completos:
            par = completos[-1]
            fig, ax = plt.subplots(figsize=(7, 5))
            ax.bar(['Individual', 'Pipeline'], [par[m]['segundos'] for m in ('individual', 'pipeline')])
            ax.set(ylabel='Tempo (s)', title='Redis — recarga aquecida da mesma amostra')
            salvar(fig, saida / '04_carga.png')
        else:
            print('Gráfico 4 pendente: execute carregar_redis.py --modo comparar nesta amostra.')
    else:
        print('Gráfico 4 pendente: arquivo de medições de carga ausente.')
    print(f'Gráficos salvos em {saida}')
    return saida


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('benchmark', help='Pasta de uma execução concluída')
    parser.add_argument('--cargas', default='resultados/cargas.jsonl')
    args = parser.parse_args()
    gerar(args.benchmark, args.cargas)
