from datetime import datetime
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
ADMIN = re.compile(r'^ADM_00\d{1}$')

def detectar_tipo(identi):
    if MATRICULA.match(identi):
        return 'aluno'
    if SIAPE.match(identi):
        return 'professor'
    if ADMIN.match(identi):
        return 'admin'
    return None

# Rotas

@app.route('/')
def inicio():
    return render_template('InicioSite.html')
    

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
            elif session['tipo'] == 'professor':
                return redirect(url_for('professores'))
            elif session['tipo'] == 'adm':
                return redirect(url_for('adm'))
            else:
                flash('Tipo de usuário desconhecido.', 'erro')
        else: 
            flash('Usuário ou senha incorretos.', 'erro')
    return render_template('Login.html')

@app.route('/adm', methods=['GET', 'POST'])
def adm():
    if 'usuario_id' not in session or session.get('tipo') != 'adm':
        flash('Acesso restrito.', 'erro')
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    
    if request.method == 'POST':
        botao = request.form.get("btn")

    try:
        
        if botao == "adicionar_curso":
            nome_curso = request.form.get('nome_curso', '').strip()
            sigla_curso = request.form.get('sigla_curso', '').strip()
            if sigla_curso == "" or nome_curso == "":
                flash(f'Nome e sigla do curso não podem ser vazios.', 'danger')
            else:
                cursor.execute("SELECT * FROM curso WHERE nome = %s", (nome_curso,))
                if cursor.fetchone():
                    flash(f'Curso já existe.', 'danger')
                else:
                    cursor.execute(
                        "INSERT INTO curso (nome, sigla) VALUES (%s, %s)",
                        (nome_curso, sigla_curso)
                    )
                    conn.commit()
                    flash('Curso adicionado com sucesso!', 'success')

        elif botao == "alterar_curso":
            curso_id  = request.form.get('curso_id')
            novo_nome = request.form.get('novo_nome', '').strip()
            nova_sigla = request.form.get('nova_sigla', '').strip()

            cursor.execute(
                "UPDATE curso SET nome=%s, sigla=%s WHERE id_curso=%s",
                (novo_nome, nova_sigla, curso_id)
            )
            conn.commit()
            flash('Curso alterado com sucesso!', 'success')

        elif botao == "deletar_curso":
            excluir_sigla = request.form.get('excluir_sigla', '').strip()

            cursor.execute("DELETE FROM curso WHERE sigla=%s", (excluir_sigla,))
            conn.commit()
            flash('Curso deletado com sucesso!', 'success')

        elif botao == "adicionar_periodo":
            inicio_periodo = request.form.get('inicio_periodo', '').strip()
            fim_periodo = request.form.get('fim_periodo', '').strip()
            descricao = request.form.get('descricao', '').strip()
            if inicio_periodo == "" or fim_periodo == "" or descricao == "":
                flash(f'Datas do período não podem ser vazias.', 'danger')
            else:
                try:
                    # Converte de DD/MM/AAAA (formato brasileiro) para AAAA-MM-DD (formato americano)
                    inicio_periodo_us = datetime.strptime(inicio_periodo, '%d/%m/%Y').strftime('%Y-%m-%d')
                    fim_periodo_us = datetime.strptime(fim_periodo, '%d/%m/%Y').strftime('%Y-%m-%d')
                except ValueError as e:
                    flash(f'{e} Formato de data inválido. Use DD/MM/AAAA.', 'danger')
                else:
                    cursor.execute("SELECT * FROM periodo WHERE data_inicio = %s AND data_fim = %s", (inicio_periodo_us, fim_periodo_us))
                    if cursor.fetchone():
                        flash(f'Período já existe.', 'danger')
                    else:
                        cursor.execute(
                            "INSERT INTO periodo (data_inicio, data_fim, descricao) VALUES (%s, %s, %s)",
                            (inicio_periodo_us, fim_periodo_us, descricao)
                        )
                        conn.commit()
                        flash('Período adicionado com sucesso!', 'success')

        elif botao == "alterar_periodo":
            nova_data_inicio = request.form.get('nova_data_inicio', '').strip()
            nova_data_fim = request.form.get('nova_data_fim', '').strip()
            nova_descricao = request.form.get('nova_descricao', '').strip()
            periodo_id = request.form.get('periodo_id')
            if nova_data_inicio == "" or nova_data_fim == "" or nova_descricao == "":
                flash(f'Datas do período não podem ser vazias.', 'danger')
            else:
                cursor.execute(
                    "UPDATE periodo SET data_inicio=%s, data_fim=%s, descricao=%s WHERE id_periodo=%s",
                    (nova_data_inicio, nova_data_fim, nova_descricao, periodo_id)
                )
                conn.commit()
                flash('Período alterado com sucesso!', 'success')

        elif botao == "deletar_periodo":
            excluir_periodo = request.form.get('excluir_periodo', '').strip()
            if excluir_periodo == "":
                flash(f'Datas do período não podem ser vazias.', 'danger')
            else:
                cursor.execute("DELETE FROM periodo WHERE data_inicio=%s", (excluir_periodo,))
                conn.commit()
                flash('Período deletado com sucesso!', 'success')

        elif botao == "adicionar_aluno":
            matricula_aluno = request.form.get('matricula_aluno', '').strip()
            nome_aluno = request.form.get('nome_aluno', '').strip()
            email_aluno = request.form.get('email_aluno', '').strip()
            senha_aluno = request.form.get('senha_aluno', '').strip()

            if matricula_aluno == "" or nome_aluno == "" or email_aluno == "" or senha_aluno == "":
                flash(f'Todos os campos devem ser preenchidos.', 'danger')
            else:
                cursor.execute("SELECT * FROM usuario WHERE identificacao = %s", (matricula_aluno,))
                if cursor.fetchall():
                    flash(f'Aluno já existe.', 'danger')
                else:
                    cursor.execute(
                        "INSERT INTO usuario (identificacao, tipo, nome, email, senha_hash) VALUES (%s,%s,%s,%s,%s)",
                        (matricula_aluno, 'aluno', nome_aluno, email_aluno, hash_senha(senha_aluno))
                    )
                    conn.commit()
                    flash('Aluno adicionado com sucesso!', 'success')

        elif botao == "alterar_aluno":
            matricula_aluno = request.form.get('matricula_aluno', '').strip()
            nome_aluno = request.form.get('nome_aluno', '').strip()
            email_aluno = request.form.get('email_aluno', '').strip()
            senha_aluno = request.form.get('senha_aluno', '').strip()
            id_usuario = request.form.get('id_usuario', '')

            if matricula_aluno == "" or nome_aluno == "" or email_aluno == "" or senha_aluno == "":
                flash(f'Todos os campos devem ser preenchidos.', 'danger')
            else:
                cursor.execute(
                    "UPDATE usuario SET identificacao=%s, nome=%s, email=%s, senha_hash=%s WHERE id_usuario=%s",
                    (matricula_aluno, nome_aluno, email_aluno, hash_senha(senha_aluno), id_usuario)
                )
                conn.commit()
                flash('Aluno alterado com sucesso!', 'success')

        elif botao == "deletar_aluno":
            matricula_aluno = request.form.get('matricula_aluno', '').strip()
            if matricula_aluno == "":
                flash(f'Matrícula do aluno não pode ser vazia.', 'danger')
            else:
                cursor.execute("DELETE FROM usuario WHERE identificacao=%s", (matricula_aluno,))
                conn.commit()
                flash('Aluno deletado com sucesso!', 'success')

        elif botao == "adicionar_professor":
            siape_professor = request.form.get('siape_professor','').strip()
            nome_professor = request.form.get('nome_professor','').strip()
            email_professor = request.form.get('email_professor', '').strip()
            senha_professor = request.form.get('senha_professor', '').strip()
            id_usuario = request.form.get('id_usuario', '')

            if siape_professor == "" or nome_professor == "" or email_professor == "" or senha_professor == "":
                flash(f"Todos os campos devem estar preenchidos.", 'danger')
            else:
                cursor.execute(
                    "SELECT * FROM usuario WHERE identificacao = %s", (siape_professor,)
                )
                if cursor.fetchone():
                    flash(f'Professor já existe.', 'danger')
                else:
                    cursor.execute(
                        "INSERT INTO usuario (identificacao, tipo, nome, email, senha_hash) VALUES (%s,%s,%s,%s,%s)",
                        (siape_professor, 'professor', nome_professor, email_professor, hash_senha(senha_professor))
                    )
                    conn.commit()
                    flash('Professor adicionado com sucesso!', 'success')
                    
        elif botao == "alterar_professor":
            siape_professor = request.form.get('siape_professor','').strip()
            nome_professor = request.form.get('nome_professor','').strip()
            email_professor = request.form.get('email_professor', '').strip()
            senha_professor = request.form.get('senha_professor', '').strip()
            id_usuario = request.form.get('id_usuario', '')

            if siape_professor == "" or nome_professor == "" or email_professor == "" or senha_professor == "":
                flash(f"Todos os campos devem estar preenchidos.", 'danger')
            else:
                cursor.execute(
                    "UPDATE usuario SET identificacao=%s, nome=%s, email=%s, senha_hash=%s WHERE id_usuario=%s",
                    (siape_professor, nome_professor, email_professor, hash_senha(senha_professor), id_usuario)
                )
                conn.commit()
                flash('Professor alterado com sucesso!', 'success')

        elif botao == "deletar_professor":
            siape_professor = request.form.get('siape_professor','').strip()
            if siape_professor == "":
                flash(f'SIAPE do professor não pode ser vazio.', 'danger')
            else:
                cursor.execute("DELETE FROM usuario WHERE identificacao=%s", (siape_professor,))
                conn.commit()
                flash('Professor deletado com sucesso!', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'Erro: {e}. Tente novamente.', 'danger')
        
    cursor.execute("SELECT id_curso, nome, sigla FROM curso")
    lista_cursos = cursor.fetchall()
    cursor.execute("SELECT id_periodo, data_inicio, data_fim FROM periodo ")
    lista_periodo = cursor.fetchall()
    cursor.execute("SELECT id_usuario, identificacao FROM usuario WHERE tipo='aluno'")
    lista_alunos = cursor.fetchall()
    cursor.execute("SELECT id_usuario, identificacao FROM usuario WHERE tipo='professor'")
    lista_professores = cursor.fetchall()

    return render_template('ADM.html', cursos=lista_cursos,
                            periodos=lista_periodo,
                            alunos=lista_alunos,
                            professores=lista_professores)

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
        JOIN disciplina_periodo dp ON dp.id_disciplina_periodo = m.id_disciplina
        JOIN disciplina d  ON d.id_disciplina  = dp.id_disciplina
        JOIN curso      c  ON c.id_curso       = d.id_curso
        JOIN usuario    u  ON u.id_usuario     = dp.id_professor
        JOIN periodo    p  ON p.id_periodo     = dp.id_periodo
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
        JOIN disciplina_periodo   dp ON dp.id_professor = u.id_usuario
        JOIN matricula_disciplina m  ON m.id_disciplina = dp.id_disciplina_periodo
        WHERE m.id_aluno = %s
        ORDER BY u.nome
    ''', (session['usuario_id'],))
    professores = cursor.fetchall()

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
                        conversas=conversas
                        )
 
 
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
        JOIN disciplina_periodo dp ON dp.id_disciplina = d.id_disciplina
        JOIN curso c ON c.id_curso = d.id_curso
        WHERE dp.id_professor = %s
        ORDER BY d.nome
    ''', (session['usuario_id'],))
    disciplinas = cursor.fetchall()


    cursor.execute('''
        SELECT DISTINCT al.id_usuario, al.nome, al.identificacao
        FROM disciplina_periodo dp
        JOIN matricula_disciplina m ON m.id_disciplina = dp.id_disciplina_periodo
        JOIN usuario al ON al.id_usuario = m.id_aluno
        WHERE dp.id_professor = %s
        ORDER BY al.nome
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
                            alunos=alunos,
                            conversas=conversas
                          )

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
