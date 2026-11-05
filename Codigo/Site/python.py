from contextlib import contextmanager
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
import hashlib
import re
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.secret_key = 'f01e5011b1c1ff3e0a556e0d607eca775021a2e1d0ec19626e225a00b4b85dc9'
socketio = SocketIO(app)

# Configuração MySQL
DB_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'desenrola',
    'charset': 'utf8mb4'
}


# ══════════════════════════════════════════════════════════════
# Banco de dados
# ══════════════════════════════════════════════════════════════

def get_db():
    return mysql.connector.connect(**DB_config)


@contextmanager
def db():
    """Abre conexão + cursor (dictionary) e fecha tudo no final.

    Uso:
        with db() as (conn, cursor):
            cursor.execute(...)

    Se der erro dentro do bloco, faz rollback e repassa a exceção.
    """
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        yield conn, cursor
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def listar(cursor, sql, params=()):
    """execute + fetchall numa linha só."""
    cursor.execute(sql, params)
    return cursor.fetchall()


def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()


# ══════════════════════════════════════════════════════════════
# Identificação, sessão e controle de acesso
# ══════════════════════════════════════════════════════════════

MATRICULA = re.compile(r'^20\d{2}1[A-Z]{2}\.[A-Z]{3}_I0\d{3}$')
SIAPE = re.compile(r'^\d{7,8}$')
ADMIN = re.compile(r'^ADM_00\d{1}$')


def detectar_tipo(identi):
    if MATRICULA.match(identi):
        return 'aluno'
    if SIAPE.match(identi):
        return 'professor'
    if ADMIN.match(identi):
        return 'adm'
    return None

TOPICOS_FEEDBACK = {
    'professor':    'Professor',
    'plano_ensino': 'Plano de ensino',
    'aula':         'Aula',
    'disciplina':   'Disciplina',
    'avaliacoes':   'Avaliações',
    'material':     'Material didático',
    'outro':        'Outro',
}

def destino_por_tipo(tipo):
    """Redirect para o painel do tipo, ou None se o tipo for desconhecido."""
    rotas = {'aluno': 'alunos', 'professor': 'professores', 'adm': 'adm'}
    rota = rotas.get(tipo)
    return redirect(url_for(rota)) if rota else None


def iniciar_sessao(id_usuario, identificacao, tipo, nome):
    """Único lugar que grava o login na sessão (usado por login e cadastro)."""
    session.clear()
    session['usuario_id'] = id_usuario
    session['identificacao'] = identificacao
    session['tipo'] = tipo
    session['nome'] = nome or identificacao


def acesso(*tipos):
    """Restringe a rota a um ou mais tipos de usuário: @acesso('aluno')."""
    def decorador(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if 'usuario_id' not in session:
                flash('Acesso restrito.', 'erro')
                return redirect(url_for('login'))
            if session.get('tipo') not in tipos:
                # logado com outro tipo: manda para o painel dele
                return destino_por_tipo(session.get('tipo')) or redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapper
    return decorador


def somente_visitante(view):
    """Quem já está logado vai direto para o painel (login e cadastro)."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if 'usuario_id' in session:
            destino = destino_por_tipo(session.get('tipo'))
            if destino:
                return destino
        return view(*args, **kwargs)
    return wrapper


@app.after_request
def sem_cache(resp):
    # Evita que o botão "voltar" mostre login/painel antigos do cache
    if request.endpoint != 'static':
        resp.headers['Cache-Control'] = 'no-store'
    return resp


# ══════════════════════════════════════════════════════════════
# Handlers do painel ADM — um por ação (adicionar/alterar/deletar).
# Cada handler recebe o cursor, a conexão e o form da requisição, e é
# responsável por validar, executar a query e disparar o flash.
# ══════════════════════════════════════════════════════════════

# --- Curso ------------------------------------------------------

def handle_adicionar_curso(cursor, conn, form):
    nome_curso = form.get('nome_curso', '').strip()
    sigla_curso = form.get('sigla_curso', '').strip()

    if nome_curso == "" or sigla_curso == "":
        flash('Nome e sigla do curso não podem ser vazios.', 'danger')
        return

    cursor.execute("SELECT * FROM curso WHERE nome = %s", (nome_curso,))
    if cursor.fetchone():
        flash('Curso já existe.', 'danger')
        return

    cursor.execute(
        "INSERT INTO curso (nome, sigla) VALUES (%s, %s)",
        (nome_curso, sigla_curso)
    )
    conn.commit()
    flash('Curso adicionado com sucesso!', 'success')


def handle_alterar_curso(cursor, conn, form):
    curso_id = form.get('curso_id')
    novo_nome = form.get('novo_nome', '').strip()
    nova_sigla = form.get('nova_sigla', '').strip()

    if not curso_id:
        flash('Selecione um curso para alterar.', 'danger')
        return
    if novo_nome == "" or nova_sigla == "":
        flash('Nome e sigla do curso não podem ser vazios.', 'danger')
        return

    cursor.execute(
        "UPDATE curso SET nome=%s, sigla=%s WHERE id_curso=%s",
        (novo_nome, nova_sigla, curso_id)
    )
    conn.commit()
    flash('Curso alterado com sucesso!', 'success')


def handle_deletar_curso(cursor, conn, form):
    excluir_sigla = form.get('excluir_sigla', '').strip()

    if excluir_sigla == "":
        flash('Selecione um curso para excluir.', 'danger')
        return

    # Um curso pode ter disciplinas vinculadas — checa antes de tentar
    # apagar para dar um aviso claro em vez do erro cru do MySQL.
    cursor.execute(
        "SELECT COUNT(*) AS total FROM disciplina WHERE id_curso = "
        "(SELECT id_curso FROM curso WHERE sigla = %s)",
        (excluir_sigla,)
    )
    vinculadas = cursor.fetchone()['total']
    if vinculadas > 0:
        flash(f'Não é possível excluir: existem {vinculadas} disciplina(s) vinculadas a este curso.', 'danger')
        return

    cursor.execute("DELETE FROM curso WHERE sigla=%s", (excluir_sigla,))
    conn.commit()
    flash('Curso deletado com sucesso!', 'success')


# --- Período ------------------------------------------------------

def handle_adicionar_periodo(cursor, conn, form):
    inicio_periodo = form.get('inicio_periodo', '').strip()
    fim_periodo = form.get('fim_periodo', '').strip()
    descricao = form.get('descricao', '').strip()

    if inicio_periodo == "" or fim_periodo == "" or descricao == "":
        flash('Datas do período não podem ser vazias.', 'danger')
        return

    try:
        # Converte de DD/MM/AAAA (formato brasileiro) para AAAA-MM-DD (formato americano)
        inicio_periodo_us = datetime.strptime(inicio_periodo, '%d/%m/%Y').strftime('%Y-%m-%d')
        fim_periodo_us = datetime.strptime(fim_periodo, '%d/%m/%Y').strftime('%Y-%m-%d')
    except ValueError as e:
        flash(f'{e} Formato de data inválido. Use DD/MM/AAAA.', 'danger')
        return

    cursor.execute(
        "SELECT * FROM periodo WHERE data_inicio = %s AND data_fim = %s",
        (inicio_periodo_us, fim_periodo_us)
    )
    if cursor.fetchone():
        flash('Período já existe.', 'danger')
        return

    cursor.execute(
        "INSERT INTO periodo (data_inicio, data_fim, descricao) VALUES (%s, %s, %s)",
        (inicio_periodo_us, fim_periodo_us, descricao)
    )
    conn.commit()
    flash('Período adicionado com sucesso!', 'success')


def handle_alterar_periodo(cursor, conn, form):
    periodo_id = form.get('periodo_id')
    nova_data_inicio = form.get('nova_data_inicio', '').strip()
    nova_data_fim = form.get('nova_data_fim', '').strip()
    nova_descricao = form.get('nova_descricao', '').strip()

    if not periodo_id:
        flash('Selecione um período para alterar.', 'danger')
        return
    if nova_data_inicio == "" or nova_data_fim == "" or nova_descricao == "":
        flash('Datas do período não podem ser vazias.', 'danger')
        return

    try:
        nova_data_inicio_us = datetime.strptime(nova_data_inicio, '%d/%m/%Y').strftime('%Y-%m-%d')
        nova_data_fim_us = datetime.strptime(nova_data_fim, '%d/%m/%Y').strftime('%Y-%m-%d')
    except ValueError as e:
        flash(f'{e} Formato de data inválido. Use DD/MM/AAAA.', 'danger')
        return

    cursor.execute(
        "UPDATE periodo SET data_inicio=%s, data_fim=%s, descricao=%s WHERE id_periodo=%s",
        (nova_data_inicio_us, nova_data_fim_us, nova_descricao, periodo_id)
    )
    conn.commit()
    flash('Período alterado com sucesso!', 'success')


def handle_deletar_periodo(cursor, conn, form):
    periodo_id = form.get('periodo_id')

    if not periodo_id:
        flash('Selecione um período para excluir.', 'danger')
        return

    # Um período pode ter disciplinas vinculadas (disciplina_periodo),
    # que por sua vez podem ter alunos matriculados. Checa antes de
    # apagar para não estourar a foreign key com um erro cru do MySQL.
    cursor.execute(
        "SELECT COUNT(*) AS total FROM disciplina_periodo WHERE id_periodo = %s",
        (periodo_id,)
    )
    vinculadas = cursor.fetchone()['total']
    if vinculadas > 0:
        flash(f'Não é possível excluir: existem {vinculadas} disciplina(s) vinculadas a este período.', 'danger')
        return

    cursor.execute("DELETE FROM periodo WHERE id_periodo=%s", (periodo_id,))
    conn.commit()
    flash('Período deletado com sucesso!', 'success')


# --- Aluno ------------------------------------------------------

def handle_adicionar_aluno(cursor, conn, form):
    matricula_aluno = form.get('matricula_aluno', '').strip()
    nome_aluno = form.get('nome_aluno', '').strip()
    email_aluno = form.get('email_aluno', '').strip()
    senha_aluno = form.get('senha_aluno', '').strip()

    if not all([matricula_aluno, nome_aluno, email_aluno, senha_aluno]):
        flash('Todos os campos devem ser preenchidos.', 'danger')
        return

    cursor.execute("SELECT * FROM usuario WHERE identificacao = %s", (matricula_aluno,))
    if cursor.fetchone():
        flash('Aluno já existe.', 'danger')
        return

    cursor.execute(
        "INSERT INTO usuario (identificacao, tipo, nome, email, senha_hash, alterar_senha) "
        "VALUES (%s,%s,%s,%s,%s,0)",
        (matricula_aluno, 'aluno', nome_aluno, email_aluno, hash_senha(senha_aluno))
    )
    conn.commit()
    flash('Aluno adicionado com sucesso!', 'success')


def handle_alterar_aluno(cursor, conn, form):
    id_usuario = form.get('id_usuario', '')
    matricula_aluno = form.get('matricula_aluno', '').strip()
    nome_aluno = form.get('nome_aluno', '').strip()
    email_aluno = form.get('email_aluno', '').strip()
    senha_aluno = form.get('senha_aluno', '').strip()

    if not id_usuario:
        flash('Selecione um aluno para alterar.', 'danger')
        return
    if matricula_aluno == "" or nome_aluno == "" or email_aluno == "":
        flash('Matrícula, nome e email não podem ser vazios.', 'danger')
        return

    # Senha só é atualizada se o campo vier preenchido — evita
    # sobrescrever a senha do aluno com o hash de uma string vazia.
    if senha_aluno:
        cursor.execute(
            "UPDATE usuario SET identificacao=%s, nome=%s, email=%s, senha_hash=%s WHERE id_usuario=%s",
            (matricula_aluno, nome_aluno, email_aluno, hash_senha(senha_aluno), id_usuario)
        )
    else:
        cursor.execute(
            "UPDATE usuario SET identificacao=%s, nome=%s, email=%s WHERE id_usuario=%s",
            (matricula_aluno, nome_aluno, email_aluno, id_usuario)
        )
    conn.commit()
    flash('Aluno alterado com sucesso!', 'success')


def handle_deletar_aluno(cursor, conn, form):
    matricula_aluno = form.get('matricula_aluno', '').strip()

    if matricula_aluno == "":
        flash('Matrícula do aluno não pode ser vazia.', 'danger')
        return

    cursor.execute("DELETE FROM usuario WHERE identificacao=%s", (matricula_aluno,))
    conn.commit()
    flash('Aluno deletado com sucesso!', 'success')


# --- Professor ------------------------------------------------------

def handle_adicionar_professor(cursor, conn, form):
    siape_professor = form.get('siape_professor', '').strip()
    nome_professor = form.get('nome_professor', '').strip()
    email_professor = form.get('email_professor', '').strip()
    senha_professor = form.get('senha_professor', '').strip()

    if not all([siape_professor, nome_professor, email_professor, senha_professor]):
        flash('Todos os campos devem estar preenchidos.', 'danger')
        return

    cursor.execute("SELECT * FROM usuario WHERE identificacao = %s", (siape_professor,))
    if cursor.fetchone():
        flash('Professor já existe.', 'danger')
        return

    cursor.execute(
        "INSERT INTO usuario (identificacao, tipo, nome, email, senha_hash, alterar_senha) "
        "VALUES (%s,%s,%s,%s,%s,0)",
        (siape_professor, 'professor', nome_professor, email_professor, hash_senha(senha_professor))
    )
    conn.commit()
    flash('Professor adicionado com sucesso!', 'success')


def handle_alterar_professor(cursor, conn, form):
    id_usuario = form.get('id_usuario', '')
    siape_professor = form.get('siape_professor', '').strip()
    nome_professor = form.get('nome_professor', '').strip()
    email_professor = form.get('email_professor', '').strip()
    senha_professor = form.get('senha_professor', '').strip()

    if not id_usuario:
        flash('Selecione um professor para alterar.', 'danger')
        return
    if siape_professor == "" or nome_professor == "" or email_professor == "":
        flash('SIAPE, nome e email não podem ser vazios.', 'danger')
        return

    # Mesma regra do aluno: senha só é trocada se o campo vier preenchido.
    if senha_professor:
        cursor.execute(
            "UPDATE usuario SET identificacao=%s, nome=%s, email=%s, senha_hash=%s WHERE id_usuario=%s",
            (siape_professor, nome_professor, email_professor, hash_senha(senha_professor), id_usuario)
        )
    else:
        cursor.execute(
            "UPDATE usuario SET identificacao=%s, nome=%s, email=%s WHERE id_usuario=%s",
            (siape_professor, nome_professor, email_professor, id_usuario)
        )
    conn.commit()
    flash('Professor alterado com sucesso!', 'success')


def handle_deletar_professor(cursor, conn, form):
    siape_professor = form.get('siape_professor', '').strip()

    if siape_professor == "":
        flash('SIAPE do professor não pode ser vazio.', 'danger')
        return

    cursor.execute("DELETE FROM usuario WHERE identificacao=%s", (siape_professor,))
    conn.commit()
    flash('Professor deletado com sucesso!', 'success')


# --- Disciplina ------------------------------------------------------

def handle_adicionar_disciplina(cursor, conn, form):
    nome = form.get('nome_disciplina', '').strip()
    cod = form.get('cod_disciplina', '').strip()
    periodo = form.get('periodo_disciplina', '').strip()
    sigla_curso = form.get('sigla_curso', '').strip()

    if not all([nome, cod, periodo, sigla_curso]):
        flash('Todos os campos são obrigatórios.', 'danger')
        return

    cursor.execute("SELECT id_curso FROM curso WHERE sigla = %s", (sigla_curso,))
    curso = cursor.fetchone()
    if not curso:
        flash('Curso inválido.', 'danger')
        return

    cursor.execute("SELECT 1 FROM disciplina WHERE codigo = %s", (cod,))
    if cursor.fetchone():
        flash('Já existe uma disciplina com esse código.', 'danger')
        return

    cursor.execute(
        "INSERT INTO disciplina (nome, codigo, periodo, id_curso) VALUES (%s,%s,%s,%s)",
        (nome, cod, periodo, curso['id_curso'])
    )
    conn.commit()
    flash('Disciplina adicionada com sucesso!', 'success')


def handle_alterar_disciplina(cursor, conn, form):
    codigo_original = form.get('codigo_original', '').strip()
    nome = form.get('nome_disciplina', '').strip()
    cod = form.get('cod_disciplina', '').strip()
    periodo = form.get('periodo_disciplina', '').strip()

    if not codigo_original:
        flash('Selecione uma disciplina para alterar.', 'danger')
        return
    if not all([nome, cod, periodo]):
        flash('Todos os campos são obrigatórios.', 'danger')
        return

    # se o código mudou, não pode colidir com outra disciplina
    if cod != codigo_original:
        cursor.execute("SELECT 1 FROM disciplina WHERE codigo = %s", (cod,))
        if cursor.fetchone():
            flash('Já existe uma disciplina com esse código.', 'danger')
            return

    # id_curso NÃO está no UPDATE: o curso da disciplina é imutável aqui
    cursor.execute(
        "UPDATE disciplina SET nome=%s, codigo=%s, periodo=%s WHERE codigo=%s",
        (nome, cod, periodo, codigo_original)
    )
    if cursor.rowcount == 0:
        flash('Disciplina não encontrada.', 'danger')
        return
    conn.commit()
    flash('Disciplina alterada com sucesso!', 'success')


def handle_deletar_disciplina(cursor, conn, form):
    codigo = form.get('cod_disciplina', '').strip()
    if not codigo:
        flash('Selecione uma disciplina para excluir.', 'danger')
        return

    cursor.execute("DELETE FROM disciplina WHERE codigo=%s", (codigo,))
    conn.commit()
    flash('Disciplina deletada com sucesso!', 'success')


# Mapa "nome do botão" → handler. Novas ações só precisam de uma
# função nova e uma linha aqui — a rota /adm não muda.
ACOES_ADM = {
    'adicionar_curso': handle_adicionar_curso,
    'alterar_curso': handle_alterar_curso,
    'deletar_curso': handle_deletar_curso,

    'adicionar_periodo': handle_adicionar_periodo,
    'alterar_periodo': handle_alterar_periodo,
    'deletar_periodo': handle_deletar_periodo,

    'adicionar_aluno': handle_adicionar_aluno,
    'alterar_aluno': handle_alterar_aluno,
    'deletar_aluno': handle_deletar_aluno,

    'adicionar_professor': handle_adicionar_professor,
    'alterar_professor': handle_alterar_professor,
    'deletar_professor': handle_deletar_professor,

    'adicionar_disciplina': handle_adicionar_disciplina,
    'alterar_disciplina': handle_alterar_disciplina,
    'deletar_disciplina': handle_deletar_disciplina,
}


def executar_acao_adm(cursor, conn, form):
    """Descobre o handler pelo botão clicado e roda com tratamento de erro."""
    handler = ACOES_ADM.get(form.get('btn'))
    if handler is None:
        flash('Ação desconhecida.', 'danger')
        return
    try:
        handler(cursor, conn, form)
    except Exception as e:
        conn.rollback()
        flash(f'Erro: {e}. Tente novamente.', 'danger')


def dados_painel_adm(cursor):
    """Tudo que o ADM.html precisa para montar dropdowns e selects."""
    periodos = listar(cursor, "SELECT id_periodo, descricao, data_inicio, data_fim FROM periodo")
    for p in periodos:
        p['inicio_br'] = p['data_inicio'].strftime('%d/%m/%Y')
        p['fim_br'] = p['data_fim'].strftime('%d/%m/%Y')

    por_tipo = {r['tipo']: r['total'] for r in listar(cursor, """
        SELECT u.tipo, COUNT(*) AS total
        FROM mensagem m
        JOIN usuario u ON u.id_usuario = m.id_remetente
        GROUP BY u.tipo
    """)}

    return {
        'cursos': listar(cursor, "SELECT id_curso, nome, sigla FROM curso"),
        'periodos': periodos,
        'alunos': listar(cursor, "SELECT id_usuario, identificacao, nome, email FROM usuario WHERE tipo='aluno'"),
        'professores': listar(cursor, "SELECT id_usuario, identificacao, nome, email FROM usuario WHERE tipo='professor'"),
        'disciplinas': listar(cursor, """
            SELECT d.nome, d.codigo, d.periodo, c.sigla AS curso_sigla
            FROM disciplina d
            JOIN curso c ON c.id_curso = d.id_curso
            ORDER BY d.nome
        """),
        'msgs_alunos': por_tipo.get('aluno', 0),
        'msgs_professores': por_tipo.get('professor', 0),
    }


# ══════════════════════════════════════════════════════════════
# Conversas (usado por /alunos e /professores)
# ══════════════════════════════════════════════════════════════

SQL_CONVERSAS = '''
    SELECT
        u.id_usuario, u.nome, u.identificacao,
        MAX(m.criado_em) AS ultima_mensagem,
        (SELECT CONCAT(
            CASE WHEN m2.id_remetente = %(uid)s THEN 'Você: ' ELSE CONCAT(ur.nome, ': ') END,
            m2.conteudo
        ) FROM mensagem m2
        JOIN usuario ur ON ur.id_usuario = m2.id_remetente
        WHERE (m2.id_remetente = %(uid)s AND m2.id_destinatario = u.id_usuario)
            OR (m2.id_remetente = u.id_usuario AND m2.id_destinatario = %(uid)s)
        ORDER BY m2.criado_em DESC LIMIT 1) AS ultimo_texto
    FROM mensagem m
    JOIN usuario u ON u.id_usuario = CASE
        WHEN m.id_remetente = %(uid)s THEN m.id_destinatario
        ELSE m.id_remetente
    END
    WHERE m.id_remetente = %(uid)s OR m.id_destinatario = %(uid)s
    GROUP BY u.id_usuario, u.nome, u.identificacao
    ORDER BY ultima_mensagem DESC
'''


def buscar_conversas(cursor, usuario_id):
    conversas = listar(cursor, SQL_CONVERSAS, {'uid': usuario_id})
    for c in conversas:
        c['ultima_mensagem'] = c['ultima_mensagem'].strftime('%d/%m/%Y %H:%M')
    return conversas


# ══════════════════════════════════════════════════════════════
# Rotas
# ══════════════════════════════════════════════════════════════

@app.route('/')
def inicio():
    return render_template('InicioSite.html')


@app.route('/login', methods=['GET', 'POST'])
@somente_visitante
def login():
    if request.method == 'POST':
        identificacao = request.form.get('identificacao', '').strip()
        senha = request.form.get('senha', '').strip()

        if not detectar_tipo(identificacao):
            flash('Matricula ou SIAPE invalido.', 'erro')
            return render_template('Login.html')

        with db() as (conn, cursor):
            cursor.execute(
                'SELECT * FROM usuario WHERE identificacao = %s AND senha_hash = %s',
                (identificacao, hash_senha(senha))
            )
            usuario = cursor.fetchone()

        if not usuario:
            flash('Usuário ou senha incorretos.', 'erro')
            return render_template('Login.html')

        destino = destino_por_tipo(usuario['tipo'])
        if destino is None:
            flash('Tipo de usuário desconhecido.', 'erro')
            return render_template('Login.html')

        iniciar_sessao(usuario['id_usuario'], usuario['identificacao'],
                       usuario['tipo'], usuario['nome'])
        return destino

    return render_template('Login.html')


def validar_cadastro(tipo, senha, confirmar_senha, aceite_termos):
    """Devolve a mensagem de erro, ou None se estiver tudo certo."""
    if tipo not in ('aluno', 'professor'):
        return 'Matrícula ou SIAPE com formato inválido.'
    if senha != confirmar_senha:
        return 'As senhas não coincidem.'
    if len(senha) < 6:
        return 'A senha deve ter pelo menos 6 caracteres.'
    if not aceite_termos:
        return 'Você precisa aceitar os termos de uso.'
    return None


def registrar_usuario(cursor, conn, identificacao, tipo, senha, nome):
    """Cria a conta, ou ativa uma conta pré-cadastrada pelo admin.

    Devolve o id do usuário, ou None se a conta já foi ativada antes
    (nesse caso nada é alterado: ninguém troca a senha de uma conta ativa).
    """
    cursor.execute(
        'SELECT id_usuario FROM usuario WHERE identificacao = %s',
        (identificacao,)
    )
    existente = cursor.fetchone()

    if existente is None:
        # Usuário novo → já nasce com senha definida por ele mesmo
        cursor.execute(
            'INSERT INTO usuario (identificacao, tipo, senha_hash, nome, alterar_senha) '
            'VALUES (%s, %s, %s, %s, 1)',
            (identificacao, tipo, hash_senha(senha), nome or identificacao)
        )
        conn.commit()
        return cursor.lastrowid

    # Pré-cadastrado pelo admin → só pode ser ativado UMA vez.
    # O "AND alterar_senha = 1" no UPDATE garante isso mesmo que dois
    # cadastros cheguem ao mesmo tempo.
    cursor.execute(
        'UPDATE usuario SET senha_hash = %s, nome = %s, alterar_senha = 0 '
        'WHERE id_usuario = %s AND alterar_senha = 1',
        (hash_senha(senha), nome or identificacao, existente['id_usuario'])
    )
    conn.commit()
    return existente['id_usuario'] if cursor.rowcount else None


@app.route('/cadastro', methods=['GET', 'POST'])
@somente_visitante
def cadastro():
    if request.method == 'GET':
        return render_template('Cadastro.html')

    identificacao = request.form.get('identificacao', '').strip()
    senha = request.form.get('senha', '').strip()
    confirmar_senha = request.form.get('confirmar_senha', '').strip()
    aceite_termos = request.form.get('termos')
    nome = request.form.get('nome', '').strip()
    tipo = detectar_tipo(identificacao)

    erro = validar_cadastro(tipo, senha, confirmar_senha, aceite_termos)
    if erro:
        flash(erro, 'erro')
        return render_template('Cadastro.html')

    try:
        with db() as (conn, cursor):
            id_usuario = registrar_usuario(cursor, conn, identificacao, tipo, senha, nome)
    except Exception:
        flash('Erro ao salvar cadastro. Tente novamente.', 'erro')
        return render_template('Cadastro.html')

    if id_usuario is None:
        flash('Esta identificação já possui cadastro. Faça login.', 'erro')
        return render_template('Cadastro.html')

    iniciar_sessao(id_usuario, identificacao, tipo, nome)
    flash('Cadastro realizado com sucesso!', 'sucesso')
    return destino_por_tipo(tipo)


@app.route('/adm', methods=['GET', 'POST'])
@acesso('adm')
def adm():
    if request.method == 'POST':
        with db() as (conn, cursor):
            executar_acao_adm(cursor, conn, request.form)
        # POST → redirect → GET: atualizar a página não reenvia o formulário
        return redirect(url_for('adm'))

    with db() as (conn, cursor):
        dados = dados_painel_adm(cursor)
    return render_template('ADM.html', **dados)


@app.route('/alunos')
@acesso('aluno')
def alunos():
    uid = session['usuario_id']

    with db() as (conn, cursor):
        # Disciplinas matriculadas pelo aluno (com curso e professor)
        lista_disciplinas = listar(cursor, '''
            SELECT d.nome,
                d.codigo,
                c.nome  AS curso_nome,
                c.sigla AS curso_sigla,
                u.nome  AS professor_nome,
                p.descricao AS periodo_descricao,
                m.situacao,
                dp.id_disciplina_periodo
            FROM matricula_disciplina m
            JOIN disciplina_periodo dp ON dp.id_disciplina_periodo = m.id_disciplina
            JOIN disciplina d  ON d.id_disciplina  = dp.id_disciplina
            JOIN curso      c  ON c.id_curso       = d.id_curso
            JOIN usuario    u  ON u.id_usuario     = dp.id_professor
            JOIN periodo    p  ON p.id_periodo     = dp.id_periodo
            WHERE m.id_aluno = %s
            ORDER BY p.data_inicio DESC, d.nome
        ''', (uid,))

        # Professores das disciplinas do aluno (sem repetição)
        lista_professores = listar(cursor, '''
            SELECT DISTINCT u.id_usuario,
                            u.nome,
                            u.identificacao,
                            u.email
            FROM usuario u
            JOIN disciplina_periodo   dp ON dp.id_professor = u.id_usuario
            JOIN matricula_disciplina m  ON m.id_disciplina = dp.id_disciplina_periodo
            WHERE m.id_aluno = %s
            ORDER BY u.nome
        ''', (uid,))

        conversas = buscar_conversas(cursor, uid)

    return render_template('Alunos.html',
                           disciplinas=lista_disciplinas,
                           professores=lista_professores,
                           conversas=conversas,
                           topicos_feedback=TOPICOS_FEEDBACK,
                           tipos_post=TIPOS_POST)

def meu_feedback_para_json(r):
    texto = r['texto']
    return {
        'id': r['id_feedback'],
        'topico': TOPICOS_FEEDBACK.get(r['topico'], r['topico']),
        'disciplina': r['disciplina'],
        'periodo': r['periodo'],
        'texto': texto,
        'resumo': ' '.join(texto.split())[:120],
        'data': r['criado_em'].strftime('%d/%m/%Y %H:%M'),
        'anonimo': bool(r['anonimo']),
        'resposta': r['resposta'],
        'respondido_em': r['respondido_em'].strftime('%d/%m/%Y %H:%M') if r['respondido_em'] else None,
        'resposta_nova': bool(r['resposta']) and not r['resposta_lida'],
        'turma': r['id_disciplina_periodo'],
    }


@app.route('/api/meus-feedbacks')
@acesso('aluno')
def api_meus_feedbacks():
    with db() as (conn, cursor):
        linhas = listar(cursor, '''
            SELECT f.id_feedback, f.topico, f.texto, f.criado_em, f.anonimo,
                   f.resposta, f.respondido_em, f.resposta_lida, f.id_disciplina_periodo,
                   d.nome AS disciplina, p.descricao AS periodo
            FROM feedback f
            JOIN disciplina_periodo dp ON dp.id_disciplina_periodo = f.id_disciplina_periodo
            JOIN disciplina d ON d.id_disciplina = dp.id_disciplina
            JOIN periodo p ON p.id_periodo = dp.id_periodo
            WHERE f.id_aluno = %s
            ORDER BY f.criado_em DESC
            LIMIT 200
        ''', (session['usuario_id'],))
    return {'feedbacks': [meu_feedback_para_json(r) for r in linhas]}


@app.route('/api/meus-feedbacks/<int:id_feedback>/lido', methods=['POST'])
@acesso('aluno')
def api_meu_feedback_lido(id_feedback):
    with db() as (conn, cursor):
        cursor.execute(
            'UPDATE feedback SET resposta_lida = TRUE WHERE id_feedback = %s AND id_aluno = %s',
            (id_feedback, session['usuario_id'])
        )
        conn.commit()
    return {'ok': True}

@app.route('/feedback', methods=['POST'])
@acesso('aluno')
def enviar_feedback():
    topico = request.form.get('topico', '')
    # o navegador manda quebra de linha como \r\n; contamos como 1 caractere
    texto = request.form.get('texto', '').replace('\r\n', '\n').strip()
    anonimo = 1 if request.form.get('anonimo') else 0
    try:
        id_dp = int(request.form.get('disciplina', ''))
    except ValueError:
        id_dp = None

    if id_dp is None or topico not in TOPICOS_FEEDBACK:
        flash('Selecione a disciplina e o tópico.', 'erro')
        
    elif not texto:
        flash('Escreva o seu feedback.', 'erro')
    elif len(texto) > 2000:
        flash('O feedback pode ter no máximo 2000 caracteres.', 'erro')
    else:
        with db() as (conn, cursor):
            # confere se o aluno realmente está matriculado nessa disciplina
            cursor.execute(
                'SELECT 1 FROM matricula_disciplina WHERE id_aluno = %s AND id_disciplina = %s',
                (session['usuario_id'], id_dp)
            )
            if not cursor.fetchone():
                flash('Você não está matriculado nessa disciplina.', 'erro')
            else:
                cursor.execute(
                    'INSERT INTO feedback (id_aluno, id_disciplina_periodo, topico, texto, anonimo) '
                    'VALUES (%s, %s, %s, %s, %s)',
                    (session['usuario_id'], id_dp, topico, texto, anonimo)
                )
                conn.commit()
                flash('Feedback enviado! Obrigado.', 'sucesso')
                notificar_professor(cursor, id_dp, topico)

    return redirect(url_for('alunos'))

def feedback_para_json(r):
    texto = r['texto']
    return {
        'id': r['id_feedback'],
        'topico': TOPICOS_FEEDBACK.get(r['topico'], r['topico']),
        'disciplina': r['disciplina'],
        'periodo': r['periodo'],
        'autor': r['autor'],                 # None quando o aluno enviou como anônimo
        'texto': texto,
        'resumo': ' '.join(texto.split())[:120],
        'data': r['criado_em'].strftime('%d/%m/%Y %H:%M'),
        'lido': bool(r['lido']),
        'resposta': r['resposta'],
        'respondido_em': r['respondido_em'].strftime('%d/%m/%Y %H:%M') if r['respondido_em'] else None,
    }


@app.route('/api/feedbacks')
@acesso('professor')
def api_feedbacks():
    """?novos=1 → só os não lidos | ?disciplina=<id> → todos daquela disciplina."""
    filtros = ['dp.id_professor = %s']
    params = [session['usuario_id']]

    id_turma = request.args.get('turma', type=int)
    if id_turma:
        filtros.append('dp.id_disciplina_periodo = %s')
        params.append(id_turma)

    if request.args.get('novos'):
        filtros.append('f.lido = FALSE')
    id_disciplina = request.args.get('disciplina', type=int)
    if id_disciplina:
        filtros.append('dp.id_disciplina = %s')
        params.append(id_disciplina)

    # os filtros acima são fixos; só os valores entram como parâmetros
    with db() as (conn, cursor):
        linhas = listar(cursor, f'''
            SELECT f.id_feedback, f.topico, f.texto, f.criado_em, f.lido, f.resposta, f.respondido_em,
                   CASE WHEN f.anonimo = 1 THEN NULL ELSE u.nome END AS autor,
                   d.nome AS disciplina,
                   p.descricao AS periodo
            FROM feedback f
            JOIN disciplina_periodo dp ON dp.id_disciplina_periodo = f.id_disciplina_periodo
            JOIN disciplina d ON d.id_disciplina = dp.id_disciplina
            JOIN periodo p ON p.id_periodo = dp.id_periodo
            JOIN usuario u ON u.id_usuario = f.id_aluno
            WHERE {' AND '.join(filtros)}
            ORDER BY f.criado_em DESC
            LIMIT 200
        ''', tuple(params))

    return {'feedbacks': [feedback_para_json(r) for r in linhas]}


@app.route('/api/feedbacks/<int:id_feedback>/lido', methods=['POST'])
@acesso('professor')
def api_feedback_lido(id_feedback):
    with db() as (conn, cursor):
        # o JOIN garante que só o professor da disciplina marca como lido
        cursor.execute('''
            UPDATE feedback f
            JOIN disciplina_periodo dp ON dp.id_disciplina_periodo = f.id_disciplina_periodo
            SET f.lido = TRUE
            WHERE f.id_feedback = %s AND dp.id_professor = %s
        ''', (id_feedback, session['usuario_id']))
        conn.commit()
    return {'ok': True}


def notificar_professor(cursor, id_dp, topico):
    """Avisa em tempo real o professor da disciplina. Não envia o autor."""
    cursor.execute('''
        SELECT dp.id_professor, d.nome AS disciplina
        FROM disciplina_periodo dp
        JOIN disciplina d ON d.id_disciplina = dp.id_disciplina
        WHERE dp.id_disciplina_periodo = %s
    ''', (id_dp,))
    alvo = cursor.fetchone()
    if alvo and alvo['id_professor']:
        socketio.emit('novo_feedback',
                      {'disciplina': alvo['disciplina'], 'topico': TOPICOS_FEEDBACK[topico]},
                      to=f"usuario_{alvo['id_professor']}")

@app.route('/api/feedbacks/<int:id_feedback>/responder', methods=['POST'])
@acesso('professor')
def api_feedback_responder(id_feedback):
    texto = ((request.get_json(silent=True) or {}).get('texto') or '').replace('\r\n', '\n').strip()
    if not texto:
        return {'erro': 'Escreva a resposta.'}, 400
    if len(texto) > 2000:
        return {'erro': 'A resposta pode ter no máximo 2000 caracteres.'}, 400

    with db() as (conn, cursor):
        # o JOIN garante que só o professor da disciplina responde,
        # e "resposta IS NULL" impede responder duas vezes
        cursor.execute('''
            UPDATE feedback f
            JOIN disciplina_periodo dp ON dp.id_disciplina_periodo = f.id_disciplina_periodo
            SET f.resposta = %s, f.respondido_em = NOW(),
                f.resposta_lida = FALSE, f.lido = TRUE
            WHERE f.id_feedback = %s AND dp.id_professor = %s AND f.resposta IS NULL
        ''', (texto, id_feedback, session['usuario_id']))
        conn.commit()
        if cursor.rowcount == 0:
            return {'erro': 'Feedback não encontrado ou já respondido.'}, 404

        notificar_aluno_resposta(cursor, id_feedback)
        cursor.execute('SELECT respondido_em FROM feedback WHERE id_feedback = %s', (id_feedback,))
        quando = cursor.fetchone()['respondido_em']

    return {'ok': True, 'resposta': texto, 'respondido_em': quando.strftime('%d/%m/%Y %H:%M')}


def notificar_aluno_resposta(cursor, id_feedback):
    """Avisa o aluno em tempo real. Funciona igual para feedback anônimo."""
    cursor.execute('''
        SELECT f.id_aluno, d.nome AS disciplina
        FROM feedback f
        JOIN disciplina_periodo dp ON dp.id_disciplina_periodo = f.id_disciplina_periodo
        JOIN disciplina d ON d.id_disciplina = dp.id_disciplina
        WHERE f.id_feedback = %s
    ''', (id_feedback,))
    alvo = cursor.fetchone()
    if alvo:
        socketio.emit('feedback_respondido', {'disciplina': alvo['disciplina']},
                      to=f"usuario_{alvo['id_aluno']}")

TIPOS_POST = {'duvida': 'Dúvida', 'curiosidade': 'Curiosidade', 'outro': 'Outro'}


def erro_json(msg, status=400):
    return {'erro': msg}, status


def texto_valido(valor, limite):
    """Texto sem espaços nas pontas, ou None se vazio / maior que o limite."""
    texto = (valor or '').replace('\r\n', '\n').strip()
    return texto if texto and len(texto) <= limite else None


def pode_ver_turma(cursor, id_dp):
    """Aluno matriculado na turma, ou professor dela."""
    tipo = session.get('tipo')
    if tipo == 'aluno':
        sql = 'SELECT 1 FROM matricula_disciplina WHERE id_aluno = %s AND id_disciplina = %s'
    elif tipo == 'professor':
        sql = ('SELECT 1 FROM disciplina_periodo '
               'WHERE id_professor = %s AND id_disciplina_periodo = %s')
    else:
        return False
    cursor.execute(sql, (session['usuario_id'], id_dp))
    return cursor.fetchone() is not None


def buscar_posts(cursor, uid, onde, params):
    # "onde" é sempre um texto fixo do código; só os valores entram como parâmetros
    return listar(cursor, f'''
        SELECT p.id_post, p.id_disciplina_periodo, p.id_autor, p.tipo, p.titulo, p.texto,
               p.resolvido, p.criado_em, u.nome AS autor, u.tipo AS autor_tipo,
               (SELECT COUNT(*) FROM forum_resposta r WHERE r.id_post = p.id_post) AS respostas,
               (SELECT COUNT(*) FROM forum_voto v
                 WHERE v.alvo = 'post' AND v.id_alvo = p.id_post) AS votos,
               EXISTS (SELECT 1 FROM forum_voto v
                 WHERE v.alvo = 'post' AND v.id_alvo = p.id_post
                   AND v.id_usuario = %s) AS votei
        FROM forum_post p
        JOIN usuario u ON u.id_usuario = p.id_autor
        WHERE {onde}
        ORDER BY p.criado_em DESC
        LIMIT 100
    ''', (uid, *params))


def post_para_json(r):
    return {
        'id': r['id_post'],
        'tipo': TIPOS_POST.get(r['tipo'], r['tipo']),
        'titulo': r['titulo'],
        'texto': r['texto'],
        'resumo': ' '.join(r['texto'].split())[:200],
        'autor': r['autor'],
        'autor_tipo': r['autor_tipo'],
        'data': r['criado_em'].strftime('%d/%m/%Y %H:%M'),
        'resolvido': bool(r['resolvido']),
        'respostas': r['respostas'],
        'votos': r['votos'],
        'votei': bool(r['votei']),
    }


def resposta_para_json(r):
    return {
        'id': r['id_resposta'],
        'texto': r['texto'],
        'autor': r['autor'],
        'autor_tipo': r['autor_tipo'],
        'data': r['criado_em'].strftime('%d/%m/%Y %H:%M'),
        'aceita': bool(r['aceita']),
        'votos': r['votos'],
        'votei': bool(r['votei']),
    }


@app.route('/api/turma/<int:id_dp>/posts')
@acesso('aluno', 'professor')
def api_forum_posts(id_dp):
    uid = session['usuario_id']
    with db() as (conn, cursor):
        if not pode_ver_turma(cursor, id_dp):
            return erro_json('Sem acesso a esta disciplina.', 403)
        posts = buscar_posts(cursor, uid, 'p.id_disciplina_periodo = %s', (id_dp,))
    return {'posts': [post_para_json(p) for p in posts]}


@app.route('/api/turma/<int:id_dp>/posts', methods=['POST'])
@acesso('aluno', 'professor')
def api_forum_criar_post(id_dp):
    dados = request.get_json(silent=True) or {}
    tipo = dados.get('tipo', '')
    titulo = texto_valido(dados.get('titulo'), 150)
    texto = texto_valido(dados.get('texto'), 2000)

    if tipo not in TIPOS_POST:
        return erro_json('Escolha o tipo da publicação.')
    if not titulo:
        return erro_json('Escreva um título (até 150 caracteres).')
    if not texto:
        return erro_json('Escreva o texto (até 2000 caracteres).')

    with db() as (conn, cursor):
        if not pode_ver_turma(cursor, id_dp):
            return erro_json('Sem acesso a esta disciplina.', 403)
        cursor.execute(
            'INSERT INTO forum_post (id_disciplina_periodo, id_autor, tipo, titulo, texto) '
            'VALUES (%s, %s, %s, %s, %s)',
            (id_dp, session['usuario_id'], tipo, titulo, texto)
        )
        conn.commit()
    return {'ok': True}


@app.route('/api/posts/<int:id_post>')
@acesso('aluno', 'professor')
def api_forum_post(id_post):
    uid = session['usuario_id']
    with db() as (conn, cursor):
        posts = buscar_posts(cursor, uid, 'p.id_post = %s', (id_post,))
        if not posts:
            return erro_json('Publicação não encontrada.', 404)
        post = posts[0]
        if not pode_ver_turma(cursor, post['id_disciplina_periodo']):
            return erro_json('Sem acesso a esta disciplina.', 403)

        respostas = listar(cursor, '''
            SELECT r.id_resposta, r.texto, r.aceita, r.criado_em,
                   u.nome AS autor, u.tipo AS autor_tipo,
                   (SELECT COUNT(*) FROM forum_voto v
                     WHERE v.alvo = 'resposta' AND v.id_alvo = r.id_resposta) AS votos,
                   EXISTS (SELECT 1 FROM forum_voto v
                     WHERE v.alvo = 'resposta' AND v.id_alvo = r.id_resposta
                       AND v.id_usuario = %s) AS votei
            FROM forum_resposta r
            JOIN usuario u ON u.id_usuario = r.id_autor
            WHERE r.id_post = %s
            ORDER BY r.aceita DESC, votos DESC, r.criado_em ASC
        ''', (uid, id_post))

    return {
        'post': post_para_json(post),
        'respostas': [resposta_para_json(r) for r in respostas],
        # quem perguntou, ou o professor da turma, escolhe a melhor resposta
        'pode_aceitar': post['id_autor'] == uid or session['tipo'] == 'professor',
    }


@app.route('/api/posts/<int:id_post>/respostas', methods=['POST'])
@acesso('aluno', 'professor')
def api_forum_responder(id_post):
    texto = texto_valido((request.get_json(silent=True) or {}).get('texto'), 2000)
    if not texto:
        return erro_json('Escreva a resposta (até 2000 caracteres).')

    with db() as (conn, cursor):
        cursor.execute('SELECT id_disciplina_periodo FROM forum_post WHERE id_post = %s',
                       (id_post,))
        post = cursor.fetchone()
        if not post:
            return erro_json('Publicação não encontrada.', 404)
        if not pode_ver_turma(cursor, post['id_disciplina_periodo']):
            return erro_json('Sem acesso a esta disciplina.', 403)
        cursor.execute(
            'INSERT INTO forum_resposta (id_post, id_autor, texto) VALUES (%s, %s, %s)',
            (id_post, session['usuario_id'], texto)
        )
        conn.commit()
    return {'ok': True}


@app.route('/api/voto', methods=['POST'])
@acesso('aluno', 'professor')
def api_forum_voto():
    dados = request.get_json(silent=True) or {}
    alvo, id_alvo = dados.get('alvo'), dados.get('id')
    if alvo not in ('post', 'resposta') or not isinstance(id_alvo, int):
        return erro_json('Voto inválido.')
    uid = session['usuario_id']

    with db() as (conn, cursor):
        if alvo == 'post':
            cursor.execute('SELECT id_disciplina_periodo FROM forum_post WHERE id_post = %s',
                           (id_alvo,))
        else:
            cursor.execute('''
                SELECT p.id_disciplina_periodo
                FROM forum_resposta r JOIN forum_post p ON p.id_post = r.id_post
                WHERE r.id_resposta = %s
            ''', (id_alvo,))
        turma = cursor.fetchone()
        if not turma or not pode_ver_turma(cursor, turma['id_disciplina_periodo']):
            return erro_json('Publicação não encontrada.', 404)

        # clicar de novo tira o voto
        cursor.execute(
            'DELETE FROM forum_voto WHERE alvo = %s AND id_alvo = %s AND id_usuario = %s',
            (alvo, id_alvo, uid))
        votei = cursor.rowcount == 0
        if votei:
            cursor.execute(
                'INSERT INTO forum_voto (alvo, id_alvo, id_usuario) VALUES (%s, %s, %s)',
                (alvo, id_alvo, uid))
        conn.commit()

        cursor.execute('SELECT COUNT(*) AS n FROM forum_voto WHERE alvo = %s AND id_alvo = %s',
                       (alvo, id_alvo))
        votos = cursor.fetchone()['n']
    return {'votos': votos, 'votei': votei}


@app.route('/api/respostas/<int:id_resposta>/aceitar', methods=['POST'])
@acesso('aluno', 'professor')
def api_forum_aceitar(id_resposta):
    uid = session['usuario_id']
    with db() as (conn, cursor):
        cursor.execute('''
            SELECT r.id_post, p.id_autor, p.id_disciplina_periodo
            FROM forum_resposta r JOIN forum_post p ON p.id_post = r.id_post
            WHERE r.id_resposta = %s
        ''', (id_resposta,))
        r = cursor.fetchone()
        if not r or not pode_ver_turma(cursor, r['id_disciplina_periodo']):
            return erro_json('Resposta não encontrada.', 404)
        if r['id_autor'] != uid and session['tipo'] != 'professor':
            return erro_json('Só quem perguntou ou o professor escolhe a melhor resposta.', 403)

        cursor.execute('UPDATE forum_resposta SET aceita = (id_resposta = %s) WHERE id_post = %s',
                       (id_resposta, r['id_post']))
        cursor.execute('UPDATE forum_post SET resolvido = TRUE WHERE id_post = %s',
                       (r['id_post'],))
        conn.commit()
    return {'ok': True}

@app.route('/professores')
@acesso('professor')
def professores():
    uid = session['usuario_id']

    with db() as (conn, cursor):
        # Disciplinas lecionadas pelo professor (com curso)
        lista_disciplinas = listar(cursor, '''
            SELECT dp.id_disciplina_periodo,
                   d.nome,
                   d.codigo,
                   c.nome  AS curso_nome,
                   c.sigla AS curso_sigla,
                   p.descricao AS periodo_descricao
            FROM disciplina_periodo dp
            JOIN disciplina d ON d.id_disciplina = dp.id_disciplina
            JOIN curso c ON c.id_curso = d.id_curso
            JOIN periodo p ON p.id_periodo = dp.id_periodo
            WHERE dp.id_professor = %s
            ORDER BY d.nome, p.data_inicio DESC
        ''', (uid,))

        lista_alunos = listar(cursor, '''
            SELECT DISTINCT al.id_usuario, al.nome, al.identificacao
            FROM disciplina_periodo dp
            JOIN matricula_disciplina m ON m.id_disciplina = dp.id_disciplina_periodo
            JOIN usuario al ON al.id_usuario = m.id_aluno
            WHERE dp.id_professor = %s
            ORDER BY al.nome
        ''', (uid,))

        conversas = buscar_conversas(cursor, uid)

    return render_template('Professores.html',
                           disciplinas=lista_disciplinas,
                           alunos=lista_alunos,
                           conversas=conversas,
                           tipos_post=TIPOS_POST)


@app.route('/termos')
def termos():
    return render_template('Termos.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('inicio'))


# ══════════════════════════════════════════════════════════════
# API auxiliar
# ══════════════════════════════════════════════════════════════

@app.route('/api/validar-id', methods=['POST'])
def validar_id():
    identificacao = (request.get_json(silent=True) or {}).get('identificacao', '')
    tipo = detectar_tipo(identificacao)
    if tipo == 'adm':          # o formato do ID de admin não pode ser confirmado
        tipo = None
    return jsonify({'validar': tipo is not None, 'tipo': tipo})


@app.route('/mensagens/<int:id_destinatario>')
def get_mensagens(id_destinatario):
    if 'usuario_id' not in session:
        return {'erro': 'não autenticado'}, 401

    uid = session['usuario_id']
    with db() as (conn, cursor):
        msgs = listar(cursor, '''
            SELECT m.conteudo, m.criado_em,
                   m.id_remetente,
                   u.nome AS nome_remetente
            FROM mensagem m
            JOIN usuario u ON u.id_usuario = m.id_remetente
            WHERE (m.id_remetente = %s AND m.id_destinatario = %s)
               OR (m.id_remetente = %s AND m.id_destinatario = %s)
            ORDER BY m.criado_em ASC
        ''', (uid, id_destinatario, id_destinatario, uid))

    # converte datetime para string
    for m in msgs:
        m['criado_em'] = m['criado_em'].strftime('%H:%M')
    return {'mensagens': msgs}


# ══════════════════════════════════════════════════════════════
# Socket.IO (chat)
# ══════════════════════════════════════════════════════════════

def sala_do_chat(id_a, id_b):
    """Sala única entre dois usuários, independente de quem iniciou."""
    return '_'.join(sorted([str(id_a), str(id_b)]))

@socketio.on('connect')
def ao_conectar():
    if 'usuario_id' in session:
        join_room(f"usuario_{session['usuario_id']}")

@socketio.on('entrar_sala')
def entrar_sala(data):
    if 'usuario_id' not in session:
        return
    join_room(sala_do_chat(session['usuario_id'], data['id_destinatario']))


@socketio.on('enviar_mensagem')
def handle_mensagem(data):
    if 'usuario_id' not in session:
        return

    id_dest = data['id_destinatario']
    conteudo = data['conteudo'].strip()
    if not conteudo:
        return

    with db() as (conn, cursor):
        cursor.execute(
            'INSERT INTO mensagem (id_remetente, id_destinatario, conteudo) VALUES (%s, %s, %s)',
            (session['usuario_id'], id_dest, conteudo)
        )
        conn.commit()

    emit('nova_mensagem', {
        'conteudo': conteudo,
        'id_remetente': session['usuario_id'],
        'nome_remetente': session['nome'],
        'criado_em': '__agora__'
    }, to=sala_do_chat(session['usuario_id'], id_dest))


# Inicialização
if __name__ == '__main__':
    socketio.run(app, debug=True)