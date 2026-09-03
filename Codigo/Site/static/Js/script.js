/* ─── Desenrola – script.js ─────────────────────────────────── */

document.addEventListener('DOMContentLoaded', function () {

    // ── 1. Navegação por abas (Dashboard) ─────────────────────
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
            } else if (regexAdmin.test(val)) {
                hintTipo.textContent = '✓ Identificação de administrador reconhecida';
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

        window.abrirChat = function(idProf, nomeProf) {
            idDestinatario = idProf;
            document.getElementById('chat-nome').textContent   = nomeProf;
            document.getElementById('chat-panel').classList.add('aberto');
            document.getElementById('chat-overlay').style.display = 'block';
            socket.emit('entrar_sala', { id_destinatario: idProf });
            carregarHistorico(idProf);
            document.getElementById('chat-input-texto').focus();
        };

        window.fecharChat = function() {
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

        window.enviarMensagem = function() {
            const input = document.getElementById('chat-input-texto');
            const texto = input.value.trim();
            if (!texto || !idDestinatario) return;
            socket.emit('enviar_mensagem', { id_destinatario: idDestinatario, conteudo: texto });
            input.value = '';
            input.focus();
        };

        socket.on('nova_mensagem', msg => {adicionarMensagem(msg, true); atualizarListaConversas(msg);});

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
});

document.querySelectorAll('.dropdown').forEach(function (lista) {
    const btn  = lista.previousElementSibling;   // botão sempre vem antes do <ul>
    const form = lista.nextElementSibling;        // formulário sempre vem depois

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

    // Preenche automaticamente todo campo do form que tiver data-fonte
    lista.addEventListener('click', function (evento) {
        const item = evento.target.closest('a[data-id]');
        if (!item || !lista.contains(item)) return;

        evento.preventDefault();

        form.querySelectorAll('[data-fonte]').forEach(function (campo) {
            campo.value = item.getAttribute(campo.dataset.fonte) || '';
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