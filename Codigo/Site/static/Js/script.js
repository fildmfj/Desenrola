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

    
});

