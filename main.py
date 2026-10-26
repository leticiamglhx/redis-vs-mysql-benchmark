import argparse

from carregar_mysql import consultar as consultar_mysql
from carregar_redis import consultar as consultar_redis, ranking
from conexoes import conectar_mysql, conectar_redis
from dados_comuns import PADRAO_AMOSTRA


def exibir(corrida):
    if not corrida:
        print('Corrida não encontrada.')
        return
    for campo in ('id', 'origem', 'destino', 'valor', 'distancia'):
        print(f'{campo.capitalize()}: {corrida[campo]}')


def executar_menu(amostra, consultas=None, repeticoes=3):
    while True:
        print('\n========== TAXIGOV ==========\n\n1 - Consultar no Redis\n'
              '2 - Consultar no MySQL\n3 - Executar benchmark\n'
              '4 - Mostrar ranking de bairros\n5 - Sair\n')
        try:
            opcao = input('Escolha uma opção: ').strip()
            if opcao == '5':
                return
            if opcao in ('1', '2'):
                identificador = input('ID da corrida: ').strip()
                if not identificador:
                    print('Informe um ID.')
                    continue
                conexao = conectar_redis() if opcao == '1' else conectar_mysql()
                try:
                    exibir(consultar_redis(conexao, identificador) if opcao == '1'
                           else consultar_mysql(conexao, identificador))
                finally:
                    conexao.close()
            elif opcao == '3':
                from benchmark import executar, QUANTIDADES
                print('Iniciando benchmark. A validação e os testes podem levar alguns minutos.')
                executar(amostra=amostra, quantidades=consultas or QUANTIDADES,
                         repeticoes=repeticoes)
            elif opcao == '4':
                cliente = conectar_redis()
                try:
                    resultados = ranking(cliente)
                    if not resultados:
                        print('Ranking vazio. Confira a carga e o mapeamento de bairro_origem.')
                    for posicao, (bairro, total) in enumerate(resultados, 1):
                        print(f'{posicao}. {bairro}: {int(total)} corridas')
                finally:
                    cliente.close()
            else:
                print('Opção inválida.')
        except (EOFError, KeyboardInterrupt):
            print('\nEncerrado.')
            return
        except FileNotFoundError as erro:
            print(f'Arquivo necessário não encontrado: {erro.filename}.')
            print('Prepare a amostra com tratar_dados.py e carregue os dois bancos antes do benchmark.')
        except ValueError as erro:
            print(f'Não foi possível executar: {erro}')
        except Exception as erro:
            print(f'Operação não concluída ({type(erro).__name__}). '
                  'Confira os dados e execute verificar_conexoes.py.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--amostra', default=PADRAO_AMOSTRA)
    parser.add_argument('--consultas', type=int, nargs='+', help='Quantidades para a opção 3.')
    parser.add_argument('--repeticoes', type=int, default=3)
    args = parser.parse_args()
    executar_menu(args.amostra, args.consultas, args.repeticoes)
