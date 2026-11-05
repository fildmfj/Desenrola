/* ─── Desenrola – script.js ─────────────────────────────────── */

document.addEventListener('DOMContentLoaded', function () {

    // ── 1. Navegação por abas (Dashboard / Painel ADM) ────────
    const btnNav = document.querySelectorAll('.btn-nav');
    btnNav.forEach(btn => {
        btn.addEventListener('click', function () {
            const secao = this.dataset.secao;

            // Desativa todos os botões e seções
            btnNav.forEach(b => b.classList.remove('ativo'));
            document.querySelectorAll('.secao').forEach(s => s.classList.remove('ativo'));

            // Ativa o clicado
            this.classList.add('ativo');
            const alvo = document.getElementById('secao-' + secao);
            if (alvo) alvo.classList.add('ativo');
        });
    });

    // ── 2. Validação em tempo real da identificação ────────────
    const campoId = document.getElementById('identificacao');
    const hintTipo = document.getElementById('hint-tipo');

    if (campoId && hintTipo) {
        const regexMatricula = /^20\d{2}1[A-Z]{2}\.[A-Z]{3}_I0\d{3}$/;
        const regexSiape     = /^\d{7,8}$/;
        const regexAdmin     = /^ADM_00\d{1}$/;   // faltava: dava ReferenceError

        campoId.addEventListener('input', function () {
            const val = this.value.trim();
            if (!val) {
                hintTipo.textContent = '';
                hintTipo.className = 'hint-tipo';
                return;
            }
            if (regexMatricula.test(val)) {
                hintTipo.textContent = '✓ Matrícula de aluno reconhecida';
                hintTipo.className = 'hint-tipo hint-valido';
            } else if (regexSiape.test(val)) {
                hintTipo.textContent = '✓ SIAPE de professor reconhecido';
                hintTipo.className = 'hint-tipo hint-valido';
            } else {
                hintTipo.textContent = '✗ Formato inválido';
                hintTipo.className = 'hint-tipo hint-invalido';
            }
        });
    }

    // ── 3. Validação de senhas no cadastro ─────────────────────
    const senhaInput    = document.getElementById('senha');
    const confirmaInput = document.getElementById('confirmar_senha');
    const hintSenha     = document.getElementById('hint-senha');
    const btnCadastrar  = document.getElementById('btn-cadastrar');
    const checkTermos   = document.getElementById('termos');

    function verificarHabilitarBotao() {
        if (!btnCadastrar) return;
        const senhasOk   = senhaInput && confirmaInput &&
                           senhaInput.value.length >= 6 &&
                           senhaInput.value === confirmaInput.value;
        const termosOk   = !checkTermos || checkTermos.checked;
        const idOk       = !campoId || campoId.value.trim().length > 0;
        btnCadastrar.disabled = !(senhasOk && termosOk && idOk);
    }

    if (confirmaInput && hintSenha) {
        confirmaInput.addEventListener('input', function () {
            if (!senhaInput.value) return;
            if (this.value === senhaInput.value) {
                hintSenha.textContent = '✓ Senhas coincidem';
                hintSenha.className = 'hint-senha hint-valido';
            } else {
                hintSenha.textContent = '✗ Senhas não coincidem';
                hintSenha.className = 'hint-senha hint-invalido';
            }
            verificarHabilitarBotao();
        });
    }

    if (senhaInput) {
        senhaInput.addEventListener('input', verificarHabilitarBotao);
    }

    // ── 4. Habilitar botão quando termos são aceitos ───────────
    if (checkTermos) {
        checkTermos.addEventListener('change', verificarHabilitarBotao);
    }

    if (campoId) {
        campoId.addEventListener('input', verificarHabilitarBotao);
    }

    // ── 5. Auto-fechar alertas após 4 segundos ─────────────────
    document.querySelectorAll('.alerta').forEach(function (alerta) {
        setTimeout(function () {
            alerta.style.transition = 'opacity 0.5s';
            alerta.style.opacity = '0';
            setTimeout(() => alerta.remove(), 500);
        }, 4000);
    });

    // ── 6. Chat (Socket.IO) ────────────────────────────────────
    const chatPanel = document.getElementById('chat-panel');
    if (chatPanel && typeof io !== 'undefined') {
        const socket = io();
        const meuId  = parseInt(document.body.dataset.usuarioId);
        let idDestinatario = null;

        document.querySelectorAll('.item-conversa[data-usuario-id]').forEach(item => {
            const idOutro = parseInt(item.dataset.usuarioId);
            socket.emit('entrar_sala', { id_destinatario: idOutro });
        });

        document.querySelectorAll('.card-professor[data-usuario-id]').forEach(card => {
            const idOutro = parseInt(card.dataset.usuarioId);
            socket.emit('entrar_sala', { id_destinatario: idOutro });
        });

        window.abrirChat = function (idProf, nomeProf) {
            idDestinatario = idProf;
            document.getElementById('chat-nome').textContent = nomeProf;
            document.getElementById('chat-panel').classList.add('aberto');
            document.getElementById('chat-overlay').style.display = 'block';
            socket.emit('entrar_sala', { id_destinatario: idProf });
            carregarHistorico(idProf);
            document.getElementById('chat-input-texto').focus();
        };

        window.fecharChat = function () {
            document.getElementById('chat-panel').classList.remove('aberto');
            document.getElementById('chat-overlay').style.display = 'none';
            idDestinatario = null;
        };

        function carregarHistorico(idProf) {
            const container = document.getElementById('chat-mensagens');
            container.innerHTML = '<p class="chat-vazio">Carregando…</p>';
            fetch(`/mensagens/${idProf}`)
                .then(r => r.json())
                .then(data => {
                    container.innerHTML = '';
                    if (data.mensagens.length === 0) {
                        container.innerHTML = '<p class="chat-vazio">Nenhuma mensagem ainda. Diga olá!</p>';
                        return;
                    }
                    data.mensagens.forEach(m => adicionarMensagem(m, false));
                    container.scrollTop = container.scrollHeight;
                });
        }

        window.enviarMensagem = function () {
            const input = document.getElementById('chat-input-texto');
            const texto = input.value.trim();
            if (!texto || !idDestinatario) return;
            socket.emit('enviar_mensagem', { id_destinatario: idDestinatario, conteudo: texto });
            input.value = '';
            input.focus();
        };

        socket.on('nova_mensagem', msg => { adicionarMensagem(msg, true); atualizarListaConversas(msg); });
        socket.on('novo_feedback', d => { if (window.notificarFeedback) window.notificarFeedback(d); });
        socket.on('feedback_respondido', d => { if (window.notificarResposta) window.notificarResposta(d); });

        function atualizarListaConversas(msg) {
            const lista = document.querySelector('.lista-conversas');
            if (!lista) return;

            const idOutro = msg.id_remetente === meuId ? idDestinatario : msg.id_remetente;
            const nomeOutro = document.getElementById('chat-nome').textContent;
            const prefixo = msg.id_remetente === meuId ? 'Você: ' : msg.nome_remetente + ': ';

            let item = lista.querySelector(`[data-usuario-id="${idOutro}"]`);

            if (item) {
                item.querySelector('.conversa-info span').textContent = prefixo + msg.conteudo;
                item.querySelector('.data-conversa').textContent = new Date().toLocaleString('pt-BR', {
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit'
                });
                lista.prepend(item);
            } else {
                const div = document.createElement('div');
                div.className = 'item-conversa';
                div.dataset.usuarioId = idOutro;
                div.onclick = () => abrirChat(idOutro, nomeOutro);
                div.innerHTML = `
                    <div class="conversa-info">
                        <strong>${nomeOutro}</strong>
                        <span>${prefixo}${msg.conteudo}</span>
                    </div>
                    <span class="data-conversa">${new Date().toLocaleString('pt-BR', {
                        day: '2-digit', month: '2-digit', year: 'numeric',
                        hour: '2-digit', minute: '2-digit'
                    })}</span>
                `;
                lista.prepend(div);

                const vazio = document.querySelector('#secao-conversas .vazio');
                if (vazio) vazio.remove();
            }
        }

        function adicionarMensagem(msg, rolar) {
            const container = document.getElementById('chat-mensagens');

            const vazio = container.querySelector('.chat-vazio');
            if (vazio) vazio.remove();

            const souEu = msg.id_remetente === meuId;
            const hora  = msg.criado_em === '__agora__'
                ? new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
                : msg.criado_em;

            const div = document.createElement('div');
            div.className = 'msg ' + (souEu ? 'msg-eu' : 'msg-outro');
            div.innerHTML = `
                ${!souEu ? `<span class="msg-remetente">${msg.nome_remetente}</span>` : ''}
                <span class="msg-texto">${msg.conteudo}</span>
                <span class="msg-hora">${hora}</span>
            `;
            container.appendChild(div);
            if (rolar) container.scrollTop = container.scrollHeight;
        }

        const chatInput = document.getElementById('chat-input-texto');
        if (chatInput) {
            chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') enviarMensagem(); });
        }

        const overlay = document.getElementById('chat-overlay');
        if (overlay) overlay.addEventListener('click', fecharChat);
    }

    // ── 7. Dropdowns do painel ADM (genérico) ──────────────────
    // Estrutura esperada dentro de cada .bloco:
    //   <button class="btn-dropdown"> + <ul class="dropdown"> (colados) ... <form>
    // Ao clicar num item, preenche cada campo [data-fonte="data-xxx"] do form
    // com o atributo data-xxx do item clicado (só se o item tiver esse atributo).
    document.querySelectorAll('.dropdown').forEach(function (lista) {
        const btn  = lista.previousElementSibling;               // botão sempre vem antes do <ul>
        const form = lista.parentElement.querySelector('form');  // form do mesmo .bloco

        if (!btn || !form) return;

        // Abre / fecha, posicionando o dropdown sob o botão
        btn.addEventListener('click', function () {
            const vaiAbrir = lista.style.display !== 'block';
            document.querySelectorAll('.dropdown').forEach(d => { d.style.display = 'none'; });

            if (vaiAbrir) {
                lista.style.top = (btn.offsetTop + btn.offsetHeight + 6) + 'px';
                lista.style.left = btn.offsetLeft + 'px';
                lista.style.minWidth = btn.offsetWidth + 'px';
                lista.style.display = 'block';
            }
        });

        // Preenche só os campos cujo data-fonte existe no item clicado
        lista.addEventListener('click', function (evento) {
            const item = evento.target.closest('a');
            if (!item || !lista.contains(item)) return;

            evento.preventDefault();

            form.querySelectorAll('[data-fonte]').forEach(function (campo) {
                const atributo = campo.dataset.fonte;
                if (item.hasAttribute(atributo)) {
                    campo.value = item.getAttribute(atributo);
                }
            });

            lista.style.display = 'none';
        });
    });

    // Fecha qualquer dropdown aberto ao clicar fora dele
    window.addEventListener('click', function (evento) {
        document.querySelectorAll('.dropdown').forEach(function (lista) {
            const btn = lista.previousElementSibling;
            if (btn && !btn.contains(evento.target) && !lista.contains(evento.target)) {
                lista.style.display = 'none';
            }
        });
    });

    // ── 7b. Busca em tempo real dentro dos dropdowns ───────────
    const normalizar = txt => txt.normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim();

    document.querySelectorAll('.dropdown').forEach(function (lista) {
        const campo = lista.querySelector('.busca-dropdown');
        if (!campo) return;

        const itens = Array.from(lista.querySelectorAll('li:not(.dropdown-busca)'));

        const vazio = document.createElement('li');
        vazio.className = 'dropdown-vazio';
        vazio.textContent = 'Nenhum resultado';
        vazio.hidden = true;
        lista.appendChild(vazio);

        function filtrar() {
            const termo = normalizar(campo.value);
            let achou = 0;
            itens.forEach(function (li) {
                const a = li.firstElementChild;
                const bate = normalizar(a.dataset.busca || a.textContent).includes(termo);
                li.hidden = !bate;
                if (bate) achou++;
            });
            vazio.hidden = achou > 0;
        }

        campo.addEventListener('input', filtrar);

        campo.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                const primeiro = itens.find(li => !li.hidden);
                if (primeiro) primeiro.firstElementChild.click();
            } else if (e.key === 'Escape') {
                lista.style.display = 'none';
            }
        });

        // Ao abrir a lista: limpa a busca anterior e foca o campo
        lista.previousElementSibling.addEventListener('click', function () {
            if (lista.style.display === 'block') {
                campo.value = '';
                filtrar();
                campo.focus();
            }
        });
    });

    // ── 8. Filtro curso → disciplinas (Alterar Disciplina) ─────
    // Cada bloco com [data-filtro] tem 2 dropdowns: cursos e disciplinas.
    // Ao escolher um curso, só as disciplinas dele aparecem na 2ª lista.
    // Precisa vir DEPOIS da seção 7: o genérico já preenche o campo "Curso".
    document.querySelectorAll('[data-filtro]').forEach(function (bloco) {
        const [listaCurso, listaDisc] = bloco.querySelectorAll('.dropdown');
        if (!listaCurso || !listaDisc) return;

        const btnDisc = listaDisc.previousElementSibling;
        const aviso   = bloco.querySelector('.aviso-vazio');
        const form    = bloco.querySelector('form');

        listaCurso.addEventListener('click', function (e) {
            const item = e.target.closest('a');
            if (!item) return;

            // Limpa a disciplina escolhida antes (inclui o hidden codigo_original;
            // o campo "Curso" é disabled, então não é limpo)
            form.querySelectorAll('input:not([disabled])').forEach(i => { i.value = ''; });

            let qtd = 0;
            listaDisc.querySelectorAll('li').forEach(function (li) {
                const mostrar = li.firstElementChild.dataset.cursoSigla === item.dataset.sigla;
                li.hidden = !mostrar;
                if (mostrar) qtd++;
            });

            btnDisc.hidden = qtd === 0;
            if (aviso) aviso.textContent = qtd ? '' : 'Este curso ainda não tem disciplinas.';
        });
    });
    
    // ── 9. Contador de caracteres do feedback ──────────────────
    const textoFeedback = document.getElementById('texto-feedback');
    const contadorFeedback = document.getElementById('contador-feedback');
    if (textoFeedback && contadorFeedback) {
        textoFeedback.addEventListener('input', function () {
            contadorFeedback.textContent = this.value.length;
        });
    }

    // ── 10. Feedbacks do professor ─────────────────────────────
    const btnNotif = document.getElementById('btn-notificacao');
    const dialogFb = document.getElementById('dialog-feedbacks');
    const btnVoltar = document.getElementById('voltar-feedbacks');

    function el(tag, classe, texto) {
        const n = document.createElement(tag);
        if (classe) n.className = classe;
        if (texto !== undefined) n.textContent = texto;
        return n;
    }

    // GET sem corpo, POST com corpo. Lança Error com a mensagem do servidor.
    function api(url, corpo) {
        const opcoes = corpo === undefined ? {} : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(corpo)
        };
        return fetch(url, opcoes).then(r => r.json().then(function (d) {
            if (!r.ok) throw new Error(d.erro || 'Erro inesperado.');
            return d;
        }));
    }

    if (btnNotif && dialogFb) {
        const badge   = document.getElementById('badge-feedback');
        const titulo  = document.getElementById('titulo-feedbacks');
        const lista   = document.getElementById('lista-feedbacks');
        const detalhe = document.getElementById('detalhe-feedback');

        let novos = 0;                              // feedbacks ainda não lidos
        let atual = { feedbacks: [], vazio: '' };   // lista que está na tela

        // textContent em vez de innerHTML: o texto do aluno nunca vira HTML

        function definirNovos(n) {
            novos = Math.max(0, n);
            badge.textContent = novos > 99 ? '99+' : novos;
            badge.hidden = novos === 0;
        }

        function mostrarLista() {
            detalhe.hidden = true;
            lista.hidden = false;
            btnVoltar.hidden = true;
            lista.replaceChildren();

            if (!atual.feedbacks.length) {
                lista.appendChild(el('p', 'vazio-fb', atual.vazio));
                return;
            }
            atual.feedbacks.forEach(function (f) {
                const item = el('button', 'item-feedback' + (f.lido ? '' : ' nao-lido'));
                item.type = 'button';
                item.append(
                    el('strong', '', f.topico),
                    el('span', '', f.resumo),
                    el('small', '', (f.autor || 'Anônimo') + ' · ' + f.data + (f.resposta ? ' · Respondido' : ''))
                );
                item.addEventListener('click', () => mostrarMensagem(f));
                lista.appendChild(item);
            });
        }

        function mostrarMensagem(f) {
            lista.hidden = true;
            detalhe.hidden = false;
            btnVoltar.hidden = false;
            detalhe.replaceChildren(
                el('h3', '', f.topico),
                el('p', 'meta-fb', (f.autor || 'Anônimo') + ' · ' + f.periodo + ' · ' + f.data),
                el('p', 'texto-fb', f.texto),
                blocoResposta(f)
            );

            if (!f.lido) {                          // abrir a mensagem marca como lida
                f.lido = true;
                definirNovos(novos - 1);
                fetch('/api/feedbacks/' + f.id + '/lido', { method: 'POST' }).catch(() => {});
            }
        }

        function abrirPainel(url, tituloTexto, vazio) {
            titulo.textContent = tituloTexto;
            atual = { feedbacks: [], vazio: vazio };
            detalhe.hidden = true;
            btnVoltar.hidden = true;
            lista.hidden = false;
            lista.replaceChildren(el('p', 'vazio-fb', 'Carregando…'));
            if (!dialogFb.open) dialogFb.showModal();

            fetch(url)
                .then(r => r.json())
                .then(function (d) { atual.feedbacks = d.feedbacks; mostrarLista(); })
                .catch(() => lista.replaceChildren(el('p', 'vazio-fb', 'Não foi possível carregar.')));
        }

        function blocoResposta(f) {
            const caixa = el('div', 'bloco-resposta');

            if (f.resposta) {                         // já respondido: só mostra
                caixa.append(
                    el('h3', '', 'Sua resposta'),
                    el('p', 'meta-fb', f.respondido_em),
                    el('p', 'texto-fb resposta-fb', f.resposta)
                );
                return caixa;
            }

            const campo = el('textarea');
            campo.rows = 4;
            campo.maxLength = 2000;
            campo.placeholder = 'Escreva sua resposta ao aluno…';

            const erro = el('p', 'erro-fb');
            const enviar = el('button', 'btn-responder', 'Responder');
            enviar.type = 'button';

            enviar.addEventListener('click', function () {
                enviar.disabled = true;
                fetch('/api/feedbacks/' + f.id + '/responder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ texto: campo.value })
                })
                    .then(r => r.json().then(d => ({ ok: r.ok, d: d })))
                    .then(function (res) {
                        if (!res.ok) {
                            erro.textContent = res.d.erro || 'Erro ao responder.';
                            enviar.disabled = false;
                            return;
                        }
                        f.resposta = res.d.resposta;
                        f.respondido_em = res.d.respondido_em;
                        mostrarMensagem(f);           // redesenha já mostrando a resposta
                    })
                    .catch(function () {
                        erro.textContent = 'Erro de conexão. Tente novamente.';
                        enviar.disabled = false;
                    });
            });

            caixa.append(el('h3', '', 'Responder ao aluno'), campo, erro, enviar);
            return caixa;
        }

        btnVoltar.addEventListener('click', mostrarLista);

        // 🔔 → feedbacks novos
        btnNotif.addEventListener('click', () =>
            abrirPainel('/api/feedbacks?novos=1', 'Novos feedbacks', 'Nenhum feedback novo.'));

        // clicar numa disciplina → todos os feedbacks dela
        // usado pela página da disciplina (seção 12): feedbacks daquela turma
        window.abrirFeedbacksTurma = function (id, nome) {
            abrirPainel('/api/feedbacks?turma=' + id, 'Feedbacks · ' + nome,
                        'Esta disciplina ainda não recebeu feedback.');
        };

        // aviso em tempo real (chamado pelo socket, ver seção 6)
        window.notificarFeedback = function (d) {
            definirNovos(novos + 1);
            document.querySelectorAll('.toast-feedback').forEach(t => t.remove());
            const toast = el('button', 'toast-feedback',
                             'Novo feedback em ' + d.disciplina + ' (' + d.topico + ')');
            toast.type = 'button';
            toast.addEventListener('click', function () { toast.remove(); btnNotif.click(); });
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 8000);
        };

        // conta os não lidos ao carregar a página
        fetch('/api/feedbacks?novos=1')
            .then(r => r.json())
            .then(d => definirNovos(d.feedbacks.length))
            .catch(() => {});
    }
    
    // ── 11. Meus feedbacks (aluno) ─────────────────────────────
    const listaMeus = document.getElementById('lista-meus-feedbacks');
    const dialogMeu = document.getElementById('dialog-meu-feedback');

    if (listaMeus && dialogMeu) {
        const detalheMeu = document.getElementById('detalhe-meu-feedback');
        const tituloMeu  = document.getElementById('titulo-meu-feedback');
        const badgeResp  = document.getElementById('badge-respostas');
        const abaFeedbacks = document.querySelector('.btn-nav[data-secao="forum"]');

        let meus = [];
        let turmaFiltro = null;                        // disciplina aberta na página do fórum
        window.definirTurmaFeedbacks = function (id) { turmaFiltro = id; mostrarMeus(); };

        function atualizarBadge() {
            const n = meus.filter(f => f.resposta_nova).length;
            badgeResp.textContent = n > 99 ? '99+' : n;
            badgeResp.hidden = n === 0;
        }

        function mostrarMeus() {
            const visiveis = meus.filter(f => f.turma === turmaFiltro);
            listaMeus.replaceChildren();
            if (!visiveis.length) {
                listaMeus.appendChild(el('p', 'vazio', 'Você ainda não enviou feedback para esta disciplina.'));
                atualizarBadge();
                return;
            }
            visiveis.forEach(function (f) {
                const item = el('button', 'item-feedback' + (f.resposta_nova ? ' nao-lido' : ''));
                item.type = 'button';
                const status = f.resposta
                    ? (f.resposta_nova ? 'Resposta nova' : 'Respondido')
                    : 'Aguardando resposta';
                item.append(
                    el('strong', '', f.topico + ' · ' + f.disciplina),
                    el('span', '', f.resumo),
                    el('small', '', status + ' · ' + f.data)
                );
                item.addEventListener('click', () => abrirMeu(f));
                listaMeus.appendChild(item);
            });
            atualizarBadge();
        }

        function abrirMeu(f) {
            tituloMeu.textContent = f.topico + ' · ' + f.disciplina;

            const partes = [
                el('p', 'meta-fb', f.periodo + ' · ' + f.data + ' · ' +
                    (f.anonimo ? 'Enviado como anônimo' : 'Enviado identificado')),
                el('p', 'texto-fb', f.texto)
            ];
            if (f.resposta) {
                partes.push(
                    el('h3', '', 'Resposta do professor'),
                    el('p', 'meta-fb', f.respondido_em),
                    el('p', 'texto-fb resposta-fb', f.resposta)
                );
            } else {
                partes.push(el('p', 'meta-fb', 'Ainda sem resposta do professor.'));
            }
            detalheMeu.replaceChildren(...partes);
            dialogMeu.showModal();

            if (f.resposta_nova) {                  // abrir a resposta marca como vista
                f.resposta_nova = false;
                mostrarMeus();
                fetch('/api/meus-feedbacks/' + f.id + '/lido', { method: 'POST' }).catch(() => {});
            }
        }

        function carregarMeus() {
            return fetch('/api/meus-feedbacks')
                .then(r => r.json())
                .then(function (d) { meus = d.feedbacks; mostrarMeus(); })
                .catch(() => {});
        }

        // aviso em tempo real (chamado pelo socket, ver seção 6)
        window.notificarResposta = function (d) {
            carregarMeus();
            document.querySelectorAll('.toast-feedback').forEach(t => t.remove());
            const toast = el('button', 'toast-feedback',
                             'O professor respondeu seu feedback em ' + d.disciplina);
            toast.type = 'button';
            toast.addEventListener('click', function () {
                toast.remove();
                if (abaFeedbacks) abaFeedbacks.click();
            });
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 8000);
        };

        carregarMeus();
    }

        // ── 12. Fórum da disciplina (aluno) ────────────────────────
    const secaoTurma = document.getElementById('secao-turma');

    if (secaoTurma) {
        const secaoForum   = document.getElementById('secao-forum') || document.getElementById('secao-disciplinas');
        const tituloTurma  = document.getElementById('titulo-turma');
        const feed         = document.getElementById('feed-posts');
        const dialogPost   = document.getElementById('dialog-post-novo');
        const formPost     = document.getElementById('form-post');
        const erroPost     = document.getElementById('erro-post');
        const secaoPost    = document.getElementById('secao-post');
        const thread       = document.getElementById('thread');

        let turma = null;                               // { id, nome } da disciplina aberta

        const nomeAutor = x => (x.autor_tipo === 'professor' ? 'Prof. ' : '') + x.autor;

        function mostrarSecao(secao) {
            document.querySelectorAll('.secao').forEach(s => s.classList.remove('ativo'));
            secao.classList.add('ativo');
        }

        function trocarSub(nome) {
            document.querySelectorAll('.subaba').forEach(b =>
                b.classList.toggle('ativo', b.dataset.sub === nome));
            document.getElementById('sub-posts').hidden = nome !== 'posts';
            document.getElementById('sub-feedbacks').hidden = nome !== 'feedbacks';
        }

        // ▲ de post ou de resposta (clicar de novo tira o voto)
        function botaoVoto(alvo, id, votos, votei) {
            const b = el('button', 'btn-voto' + (votei ? ' votado' : ''), '▲ ' + votos);
            b.type = 'button';
            b.addEventListener('click', function (e) {
                e.stopPropagation();
                api('/api/voto', { alvo: alvo, id: id }).then(function (r) {
                    b.textContent = '▲ ' + r.votos;
                    b.classList.toggle('votado', r.votei);
                }).catch(() => {});
            });
            return b;
        }

        // ── feed ──
        function topoPost(p) {
            const autor = el('div', 'post-autor');
            autor.append(el('strong', '', nomeAutor(p)), el('small', '', p.data));

            const topo = el('div', 'post-topo');
            topo.append(el('div', 'avatar-mini', p.autor[0].toUpperCase()), autor,
                        el('span', 'chip', p.tipo));
            return topo;
        }

        function rodapePost(p) {
            const rodape = el('div', 'post-rodape');
            rodape.append(botaoVoto('post', p.id, p.votos, p.votei),
                          el('span', '', '💬 ' + p.respostas));
            if (p.resolvido) rodape.append(el('span', 'selo-resolvido', '✔ Resolvido'));
            return rodape;
        }

        function cartaoPost(p) {
            const cartao = el('article', 'post' + (p.resolvido ? ' resolvido' : ''));
            cartao.append(topoPost(p), el('h3', '', p.titulo), el('p', '', p.resumo), rodapePost(p));
            cartao.addEventListener('click', () => abrirThread(p.id).then(() => window.scrollTo(0, 0)));
            return cartao;
        }

        function carregarPosts() {
            feed.replaceChildren(el('p', 'vazio', 'Carregando…'));
            api('/api/turma/' + turma.id + '/posts')
                .then(function (d) {
                    feed.replaceChildren();
                    if (!d.posts.length) {
                        feed.appendChild(el('p', 'vazio',
                            'Ainda não há publicações. Seja o primeiro a perguntar!'));
                        return;
                    }
                    d.posts.forEach(p => feed.appendChild(cartaoPost(p)));
                })
                .catch(() => feed.replaceChildren(el('p', 'vazio', 'Não foi possível carregar.')));
        }

        // ── publicação aberta (pergunta + respostas) ──
        function cartaoResposta(r, d, p) {
            const meta = el('div', 'meta', nomeAutor(r) + ' · ' + r.data +
                                           (r.aceita ? ' · ✔ Melhor resposta' : ''));
            const acoes = el('div', 'resposta-acoes');
            acoes.append(botaoVoto('resposta', r.id, r.votos, r.votei));

            if (d.pode_aceitar && !r.aceita) {
                const b = el('button', 'btn-aceitar', '✔ Melhor resposta');
                b.type = 'button';
                b.addEventListener('click', () =>
                    api('/api/respostas/' + r.id + '/aceitar', {})
                        .then(() => abrirThread(p.id))
                        .catch(() => {}));
                acoes.append(b);
            }

            const cartao = el('div', 'resposta-card' + (r.aceita ? ' aceita' : ''));
            cartao.append(meta, el('p', '', r.texto), acoes);
            return cartao;
        }

        function formResposta(p) {
            const campo = el('textarea');
            campo.rows = 3;
            campo.maxLength = 2000;
            campo.placeholder = 'Escreva sua resposta…';

            const erro = el('p', 'erro-fb');
            const enviar = el('button', 'btn-responder', 'Responder');
            enviar.type = 'button';
            enviar.addEventListener('click', function () {
                enviar.disabled = true;
                api('/api/posts/' + p.id + '/respostas', { texto: campo.value })
                    .then(() => abrirThread(p.id))
                    .catch(function (err) {
                        erro.textContent = err.message;
                        enviar.disabled = false;
                    });
            });

            const caixa = el('div', 'nova-resposta');
            caixa.append(el('h3', '', 'Sua resposta'), campo, erro, enviar);
            return caixa;
        }

        function desenharThread(d) {
            const p = d.post;

            const aberto = el('div', 'post-aberto' + (p.resolvido ? ' resolvido' : ''));
            aberto.append(topoPost(p), el('h3', '', p.titulo), el('p', 'corpo', p.texto), rodapePost(p));

            const respostas = el('div', 'respostas');
            d.respostas.forEach(r => respostas.appendChild(cartaoResposta(r, d, p)));

            const n = d.respostas.length;
            const tituloRespostas = n === 0 ? 'Nenhuma resposta ainda'
                                  : n === 1 ? '1 resposta'
                                  : n + ' respostas';

            thread.replaceChildren(
                aberto,
                el('h3', 'thread-respostas-titulo', tituloRespostas),
                respostas,
                formResposta(p)
            );
        }

        function abrirThread(id) {
            return api('/api/posts/' + id)
                .then(function (d) {
                    desenharThread(d);
                    mostrarSecao(secaoPost);
                })
                .catch(() => {});
        }

        // ── navegação: disciplinas → página da disciplina ──
        function abrirTurma(id, nome) {
            turma = { id: Number(id), nome: nome };
            tituloTurma.textContent = nome;
            mostrarSecao(secaoTurma);
            trocarSub('posts');
            if (window.definirTurmaFeedbacks) window.definirTurmaFeedbacks(turma.id);
            carregarPosts();
        }

        document.getElementById('voltar-turma').addEventListener('click', function () {
            mostrarSecao(secaoTurma);
            carregarPosts();
        });
        document.querySelectorAll('.card-disciplina[data-turma]').forEach(card =>
            card.addEventListener('click', () => abrirTurma(card.dataset.turma, card.dataset.nome)));
        document.getElementById('voltar-forum').addEventListener('click', () => mostrarSecao(secaoForum));
        document.querySelectorAll('.subaba').forEach(b =>
            b.addEventListener('click', () => trocarSub(b.dataset.sub)));

        // ── botões da página da disciplina ──
        document.getElementById('btn-nova-publicacao').addEventListener('click', () => dialogPost.showModal());

        const btnFeedback = document.getElementById('btn-abrir-feedback');          // aluno
        if (btnFeedback) {
            btnFeedback.addEventListener('click', function () {
                const dialogFeedback = document.getElementById('dialog-feedback');
                dialogFeedback.querySelector('select[name="disciplina"]').value = turma.id;
                dialogFeedback.showModal();
            });
        }

        const btnVerFeedbacks = document.getElementById('btn-feedbacks-turma');     // professor
        if (btnVerFeedbacks) {
            btnVerFeedbacks.addEventListener('click', () =>
                window.abrirFeedbacksTurma(turma.id, turma.nome));
        }

        // ── formulário de nova publicação ──
        formPost.addEventListener('submit', function (e) {
            e.preventDefault();
            const f = new FormData(formPost);
            api('/api/turma/' + turma.id + '/posts',
                { tipo: f.get('tipo'), titulo: f.get('titulo'), texto: f.get('texto') })
                .then(function () {
                    formPost.reset();
                    erroPost.textContent = '';
                    dialogPost.close();
                    carregarPosts();
                })
                .catch(err => { erroPost.textContent = err.message; });
        });
    }
});

function desenharRosca(el, fatias, rotulo) {
    const total = fatias.reduce((soma, f) => soma + f.valor, 0);
 
    const NS = "http://www.w3.org/2000/svg";
    const R = 80, LARGURA = 38, C = 2 * Math.PI * R;
    const novo = (tag, attrs) => {
        const n = document.createElementNS(NS, tag);
        for (const k in attrs) n.setAttribute(k, attrs[k]);
        return n;
    };
    const pct = v => (total ? (v / total * 100).toFixed(1).replace(".", ",") : "0") + "%";
 
    const svg = novo("svg", { viewBox: "0 0 200 200", width: "100%", height: "100%" });
 
    // anel de fundo (aparece se não houver usuários)
    svg.appendChild(novo("circle", { cx: 100, cy: 100, r: R, fill: "none", stroke: "#e5e7eb", "stroke-width": LARGURA }));
 
    let acumulado = 0;
    fatias.forEach(f => {
        if (!total || !f.valor) return;
        const fracao = f.valor / total;
        const arco = fracao * C;
 
        const circulo = novo("circle", {
            cx: 100, cy: 100, r: R, fill: "none",
            stroke: f.cor, "stroke-width": LARGURA,
            "stroke-dasharray": `${arco} ${C - arco}`,
            "stroke-dashoffset": -acumulado,
            transform: "rotate(-90 100 100)"
        });
        const dica = novo("title", {});
        dica.textContent = `${f.nome}: ${f.valor} (${pct(f.valor)})`;
        circulo.appendChild(dica);
        svg.appendChild(circulo);
 
        // porcentagem em cima da fatia, no meio do arco
        const ang = ((acumulado + arco / 2) / C) * 2 * Math.PI - Math.PI / 2;
        const t = novo("text", {
            x: 100 + R * Math.cos(ang), y: 100 + R * Math.sin(ang),
            "text-anchor": "middle", "dominant-baseline": "middle",
            fill: "#fff", "font-size": 12, "font-weight": "bold",
            "pointer-events": "none"
        });
        t.textContent = pct(f.valor);
        svg.appendChild(t);
 
        acumulado += arco;
    });
 
    // total no centro
    const n = novo("text", {
        x: 100, y: 96, "text-anchor": "middle", "dominant-baseline": "middle",
        fill: "#222", "font-size": 34, "font-weight": "bold"
    });
    n.textContent = total;
    const l = novo("text", {
        x: 100, y: 122, "text-anchor": "middle", fill: "#666", "font-size": 11
    });
    l.textContent = rotulo;
    svg.appendChild(n);
    svg.appendChild(l);
 
    // legenda
    const legenda = document.createElement("div");
    legenda.style.cssText = "display:flex;justify-content:center;gap:18px;margin-top:10px;font-size:14px;";
    fatias.forEach(f => {
        const item = document.createElement("span");
        item.innerHTML = `<span style="display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;background:${f.cor}"></span>${f.nome}`;
        legenda.appendChild(item);
    });
 
    el.innerHTML = "";
    el.style.height = "auto";
    const caixa = document.createElement("div");
    caixa.style.cssText = "width:300px;max-width:100%;height:300px;margin:0 auto;";
    caixa.appendChild(svg);
    el.appendChild(caixa);
    el.appendChild(legenda);
}

document.addEventListener("DOMContentLoaded", () => {
    const usuarios = document.getElementById("graficoUsuarios");
    if (usuarios) {
        desenharRosca(usuarios, [
            { nome: "Alunos",      valor: Number(usuarios.dataset.alunos) || 0,      cor: "#2a7de1" },
            { nome: "Professores", valor: Number(usuarios.dataset.professores) || 0, cor: "#f28c28" }
        ], "usuários");
    }

    const mensagens = document.getElementById("graficoMensagens");
    if (mensagens) {
        desenharRosca(mensagens, [
            { nome: "Alunos",      valor: Number(mensagens.dataset.alunos) || 0,      cor: "#2a7de1" },
            { nome: "Professores", valor: Number(mensagens.dataset.professores) || 0, cor: "#f28c28" }
        ], "mensagens");
    }
});