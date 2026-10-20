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