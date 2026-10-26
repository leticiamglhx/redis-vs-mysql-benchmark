import importlib.util


def verificar():
    faltantes = [nome for nome in ('redis', 'mysql')
                 if importlib.util.find_spec(nome) is None]
    if faltantes:
        print('Dependências ausentes: ' + ', '.join(faltantes))
        print(r'Execute: .\.venv\Scripts\python.exe -m pip install -r requirements.txt')
        return 1

    from conexoes import conectar_mysql, conectar_redis

    sucesso = True
    cliente = None
    try:
        cliente = conectar_redis()
        if not cliente.ping():
            raise RuntimeError('PING não confirmado')
        print('Redis: OK (PING)')
    except Exception as erro:

        print(f'Redis: falha ({type(erro).__name__}). Confira serviço, porta e autenticação.')
        sucesso = False
    finally:
        if cliente is not None:
            cliente.close()

    conexao = cursor = None
    try:
        conexao = conectar_mysql()
        cursor = conexao.cursor()
        cursor.execute('SELECT DATABASE(), 1')
        banco, resposta = cursor.fetchone()
        if resposta != 1:
            raise RuntimeError('Consulta não confirmada')
        print(f'MySQL: OK (SELECT 1; banco: {banco})')
    except Exception as erro:
        print(f'MySQL: falha ({type(erro).__name__}). Confira serviço, .env, senha e banco.')
        sucesso = False
    finally:
        if cursor is not None:
            cursor.close()
        if conexao is not None:
            conexao.close()
    return 0 if sucesso else 1


if __name__ == '__main__':
    raise SystemExit(verificar())
