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

# Conexão
def get_db():
    conn = mysql.connector.connect(**DB_config)
    return conn

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# Validação de usuário e identificação do tipo
MATRICULA = re.compile(r'^20\d{2}1[A-Z]{2}\.[A-Z]{3}_I0\d{3}$')
SIAPE = re.compile(r'^\d{7,8}$')

def detectar_tipo(identi):
    if MATRICULA.match(identi):
        return 'aluno'
    if SIAPE.match(identi):
        return 'professor'
    return None

# Rotas

@app.route('/')
def inicio():
    return render_template('InicioSite.html')
    # if 'usuario_id' not in session:
    #     return redirect(url_for('login'))
    # if session.get('tipo') == 'aluno':
    #     return redirect(url_for('alunos'))
    # else:
    #     return render_template('professores.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identificacao = request.form.get('identificacao', '').strip()
        senha = request.form.get('senha', '').strip()

        tipo = detectar_tipo (identificacao)
        if not tipo:
            flash('Matricula ou SIAPE invalido.', 'erro')
            return render_template('Login.html')
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            'SELECT * FROM usuario WHERE identificacao = %s AND senha_hash = %s',
            (identificacao, hash_senha(senha))
        )
        usuario = cursor.fetchone()
        cursor.close()
        conn.close()

        if usuario:
            session['usuario_id'] = usuario['id_usuario']
            session['identificacao'] = usuario['identificacao']
            session['tipo'] = usuario['tipo']
            session['nome'] = usuario['nome'] or usuario['identificacao']
            if session['tipo'] == 'aluno':
                return redirect(url_for('alunos'))
            else:
                return redirect(url_for('professores'))
        else: 
            flash('Usuário ou senha incorretos.', 'erro')
    return render_template('Login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        identificacao = request.form.get('identificacao', '').strip()
        senha = request.form.get('senha', '').strip()
        confirmar_senha = request.form.get('confirmar_senha', '').strip()
        aceite_termos = request.form.get('termos')
        nome = request.form.get('nome', '').strip()

        tipo = detectar_tipo(identificacao)
        if not tipo:
            flash('Matrícula ou SIAPE com formato inválido.', 'erro')
            return render_template('Cadastro.html')

        if senha != confirmar_senha:
            flash('As senhas não coincidem.', 'erro')
            return render_template('Cadastro.html')

        if len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'erro')
            return render_template('Cadastro.html')

        if not aceite_termos:
            flash('Você precisa aceitar os termos de uso.', 'erro')
            return render_template('Cadastro.html')

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                'SELECT id_usuario FROM usuario WHERE identificacao = %s',
                (identificacao,)
            )
            existente = cursor.fetchone()

            if existente:
                # Pré-cadastrado com senha temporária → atualiza senha e nome
                cursor.execute(
                    'UPDATE usuario SET senha_hash = %s, nome = %s WHERE identificacao = %s',
                    (hash_senha(senha), nome or identificacao, identificacao)
                )
            else:
                # Usuário novo → insere
                cursor.execute(
                    'INSERT INTO usuario (identificacao, tipo, senha_hash, nome) VALUES (%s, %s, %s, %s)',
                    (identificacao, tipo, hash_senha(senha), nome or identificacao)
                )
                id = cursor.lastrowid

            conn.commit()
            flash('Cadastro realizado com sucesso!', 'sucesso')
            session['usuario_id'] = id if not existente else existente['id_usuario']
            session['identificacao'] = identificacao
            session['tipo'] = tipo
            session['nome'] = nome or identificacao
            if session['tipo'] == 'aluno':
                return redirect(url_for('alunos'))
            else:
                return redirect(url_for('professores'))

        except Exception as e:
            conn.rollback()
            flash('Erro ao salvar cadastro. Tente novamente.', 'erro')
        finally:
            cursor.close()
            conn.close()

    return render_template('Cadastro.html')

@app.route('/alunos')
def alunos():
    if 'usuario_id' not in session or session.get('tipo') != 'aluno':
        return redirect(url_for('login'))
 
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
 
    # Disciplinas matriculadas pelo aluno (com curso e professor)
    cursor.execute('''
        SELECT d.nome,
            d.codigo,
            c.nome  AS curso_nome,
            c.sigla AS curso_sigla,
            u.nome  AS professor_nome,
            p.descricao AS periodo_descricao,
            m.situacao
        FROM matricula_disciplina m
        JOIN disciplina d  ON d.id_disciplina = m.id_disciplina
        JOIN curso      c  ON c.id_curso      = d.id_curso
        JOIN usuario    u  ON u.id_usuario    = d.id_professor
        JOIN periodo    p  ON p.id_periodo    = m.id_periodo
        WHERE m.id_aluno = %s
        ORDER BY p.data_inicio DESC, d.nome
    ''', (session['usuario_id'],))
    disciplinas = cursor.fetchall()
 
    # Professores das disciplinas do aluno (sem repetição)
    cursor.execute('''
        SELECT DISTINCT u.id_usuario,
                        u.nome,
                        u.identificacao,
                        u.email
        FROM usuario u
        JOIN disciplina d          ON d.id_professor  = u.id_usuario
        JOIN matricula_disciplina m ON m.id_disciplina = d.id_disciplina
        WHERE m.id_aluno = %s
        ORDER BY u.nome
    ''', (session['usuario_id'],))
    professores = cursor.fetchall()
 
    # Feedbacks enviados pelo aluno
    cursor.execute('''
        SELECT f.id_feedback,
               f.assunto,
               f.comentario,
               f.anonimo,
               f.criado_em,
               d.nome  AS disciplina_nome,
               d.codigo AS disciplina_codigo
        FROM feedback f
        JOIN disciplina d ON d.id_disciplina = f.id_disciplina
        WHERE f.id_usuario = %s
        ORDER BY f.criado_em DESC
    ''', (session['usuario_id'],))
    feedbacks = cursor.fetchall()

    cursor.execute('''
        SELECT 
            u.id_usuario, u.nome, u.identificacao,
            MAX(m.criado_em) AS ultima_mensagem,
            (SELECT CONCAT(
                CASE WHEN m2.id_remetente = %s THEN 'Você: ' ELSE CONCAT(ur.nome, ': ') END,
                m2.conteudo
            ) FROM mensagem m2
            JOIN usuario ur ON ur.id_usuario = m2.id_remetente
            WHERE (m2.id_remetente = %s AND m2.id_destinatario = u.id_usuario)
                OR (m2.id_remetente = u.id_usuario AND m2.id_destinatario = %s)
            ORDER BY m2.criado_em DESC LIMIT 1) AS ultimo_texto
        FROM mensagem m
        JOIN usuario u ON u.id_usuario = CASE
            WHEN m.id_remetente = %s THEN m.id_destinatario
            ELSE m.id_remetente
        END
        WHERE m.id_remetente = %s OR m.id_destinatario = %s
        GROUP BY u.id_usuario, u.nome, u.identificacao
        ORDER BY ultima_mensagem DESC
    ''', (
        session['usuario_id'],  # CASE do CONCAT
        session['usuario_id'],  # id_remetente do WHERE interno
        session['usuario_id'],  # id_destinatario do WHERE interno
        session['usuario_id'],  # CASE do JOIN externo
        session['usuario_id'],  # WHERE externo remetente
        session['usuario_id'],  # WHERE externo destinatario
    ))
    conversas = cursor.fetchall()

    for c in conversas:
        c['ultima_mensagem'] = c['ultima_mensagem'].strftime('%d/%m/%Y %H:%M')
 
    cursor.close()
    conn.close()
 
    return render_template('Alunos.html',
                        disciplinas=disciplinas,
                        professores=professores,
                        feedbacks=feedbacks,
                        conversas=conversas)
 
 
@app.route('/professores')
def professores():
    if 'usuario_id' not in session or session.get('tipo') != 'professor':
        return redirect(url_for('login'))
 
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
 
    # Disciplinas lecionadas pelo professor (com curso)
    cursor.execute('''
        SELECT d.id_disciplina,
               d.nome,
               d.codigo,
               c.nome  AS curso_nome,
               c.sigla AS curso_sigla
        FROM disciplina d
        JOIN curso c ON c.id_curso = d.id_curso
        WHERE d.id_professor = %s
        ORDER BY d.nome
    ''', (session['usuario_id'],))
    disciplinas = cursor.fetchall()
 
    # Feedbacks recebidos nas disciplinas do professor
    cursor.execute('''
        SELECT f.id_feedback,
               f.assunto,
               f.comentario,
               f.anonimo,
               f.criado_em,
               d.nome  AS disciplina_nome,
               d.codigo AS disciplina_codigo,
               CASE WHEN f.anonimo = TRUE THEN 'Anônimo'
                    ELSE u.nome END AS aluno_nome
        FROM feedback f
        JOIN disciplina d ON d.id_disciplina = f.id_disciplina
        JOIN usuario    u ON u.id_usuario    = f.id_usuario
        WHERE d.id_professor = %s
        ORDER BY f.criado_em DESC
    ''', (session['usuario_id'],))
    feedbacks = cursor.fetchall()

    cursor.execute('''
        SELECT DISTINCT u.id_usuario, u.nome, u.identificacao
        FROM usuario u
        JOIN matricula_disciplina m ON m.id_aluno = u.id_usuario
        JOIN disciplina d ON d.id_disciplina = m.id_disciplina
        WHERE d.id_professor = %s
        ORDER BY u.nome
    ''', (session['usuario_id'],))
    alunos = cursor.fetchall()

    # Conversas — últimas mensagens por aluno
    cursor.execute('''
        SELECT 
            u.id_usuario, u.nome, u.identificacao,
            MAX(m.criado_em) AS ultima_mensagem,
            (SELECT CONCAT(
                CASE WHEN m2.id_remetente = %s THEN 'Você: ' ELSE CONCAT(ur.nome, ': ') END,
                m2.conteudo
            ) FROM mensagem m2
            JOIN usuario ur ON ur.id_usuario = m2.id_remetente
            WHERE (m2.id_remetente = %s AND m2.id_destinatario = u.id_usuario)
                OR (m2.id_remetente = u.id_usuario AND m2.id_destinatario = %s)
            ORDER BY m2.criado_em DESC LIMIT 1) AS ultimo_texto
        FROM mensagem m
        JOIN usuario u ON u.id_usuario = CASE
            WHEN m.id_remetente = %s THEN m.id_destinatario
            ELSE m.id_remetente
        END
        WHERE m.id_remetente = %s OR m.id_destinatario = %s
        GROUP BY u.id_usuario, u.nome, u.identificacao
        ORDER BY ultima_mensagem DESC
    ''', (
        session['usuario_id'],  # CASE do CONCAT
        session['usuario_id'],  # id_remetente do WHERE interno
        session['usuario_id'],  # id_destinatario do WHERE interno
        session['usuario_id'],  # CASE do JOIN externo
        session['usuario_id'],  # WHERE externo remetente
        session['usuario_id'],  # WHERE externo destinatario
    ))
    conversas = cursor.fetchall()
    for c in conversas:
        c['ultima_mensagem'] = c['ultima_mensagem'].strftime('%d/%m/%Y %H:%M')
 
    cursor.close()
    conn.close()
 
    return render_template('Professores.html',
                           disciplinas=disciplinas,
                           feedbacks=feedbacks,
                           alunos=alunos,
                           conversas=conversas)

@app.route('/termos')
def termos():
    return render_template('Termos.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('inicio'))
# API auxiliar
@app.route('/api/validar-id', methods=['POST'])
def validar_id():
    identificacao = request.json.get('identificacao', '')
    tipo = detectar_tipo(identificacao)
    return jsonify({'validar': tipo is not None, 'tipo': tipo})

@app.route('/mensagens/<int:id_destinatario>')
def get_mensagens(id_destinatario):
    if 'usuario_id' not in session:
        return {'erro': 'não autenticado'}, 401

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT m.conteudo, m.criado_em,
               m.id_remetente,
               u.nome AS nome_remetente
        FROM mensagem m
        JOIN usuario u ON u.id_usuario = m.id_remetente
        WHERE (m.id_remetente = %s AND m.id_destinatario = %s)
           OR (m.id_remetente = %s AND m.id_destinatario = %s)
        ORDER BY m.criado_em ASC
    ''', (session['usuario_id'], id_destinatario,
          id_destinatario, session['usuario_id']))
    msgs = cursor.fetchall()
    cursor.close()
    conn.close()

    # converte datetime para string
    for m in msgs:
        m['criado_em'] = m['criado_em'].strftime('%H:%M')
    return {'mensagens': msgs}

# Evento SocketIO — entrar na sala do chat
@socketio.on('entrar_sala')
def entrar_sala(data):
    # sala única entre dois usuários, independente de quem iniciou
    sala = '_'.join(sorted([
        str(session['usuario_id']),
        str(data['id_destinatario'])
    ]))
    join_room(sala)

# Evento SocketIO — enviar mensagem
@socketio.on('enviar_mensagem')
def handle_mensagem(data):
    id_dest = data['id_destinatario']
    conteudo = data['conteudo'].strip()
    if not conteudo:
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO mensagem (id_remetente, id_destinatario, conteudo) VALUES (%s, %s, %s)',
        (session['usuario_id'], id_dest, conteudo)
    )
    conn.commit()
    cursor.close()
    conn.close()

    sala = '_'.join(sorted([str(session['usuario_id']), str(id_dest)]))

    emit('nova_mensagem', {
        'conteudo': conteudo,
        'id_remetente': session['usuario_id'],
        'nome_remetente': session['nome'],
        'criado_em': '__agora__'
    }, to=sala)


# Inicialização
if __name__ == '__main__':
    socketio.run(app, debug=True)