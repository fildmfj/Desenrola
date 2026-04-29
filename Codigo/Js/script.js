console.log("O JavaScript foi carregado com sucesso!");
function verificar() {
    
    const valor = document.getElementById('campoID').value;
    
    const regexMatricula = /^20\d{2}1[A-Z]{2}\.[A-Z]{3}_I0\d{3}$/;
    const regexSiape = /^\d{7,8}$/;

    if (regexMatricula.test(valor)) {
        alert("Matrícula válida! Redirecionando para área do Aluno...");
        window.location.href = "Alunos.html"
    } else if (regexSiape.test(valor)) {
        alert("SIAPE válido! Redirecionando para área do Servidor...");
        window.location.href = "Professores.html"
    } else {
        alert("Formato inválido para o tipo selecionado.");
    }
}
function abrirModal(tipo) {
    const modal = document.getElementById('modal-info');
    const titulo = document.getElementById('modal-titulo');
    const texto = document.getElementById('modal-texto');

    
    if (tipo === 'sobre') {
        titulo.innerText = "Sobre o Desenrola";
        texto.innerText = "O Desenrola é um sistema que visa abrir um canal de comunicação entre discente e docente.";
    } else if (tipo === 'contato') {
        titulo.innerText = "Contato";
        texto.innerText = "E-mail: suporte@desenrola.com\nTelefone: (51) 1234-5678";
    } else if (tipo === 'ajuda') {
        titulo.innerText = "Ajuda";
        texto.innerText = "Digite sua matrícula se for aluno ou SIAPE se for servidor. Dúvidas? Fale com a TI.";
    }

    modal.style.display = "block"; 
}

function fecharModal() {
    document.getElementById('modal-info').style.display = "none";
}

window.onclick = function(event) {
    const modal = document.getElementById('modal-info');
    if (event.target == modal) {
        fecharModal();
    }
}

const checkbox = document.getElementById('termos');
const btnEnviar = document.querySelector('button[type="submit"]');

btnEnviar.disabled = true;

checkbox.addEventListener('change', function termos() {
  if (this.checked) {
    btnEnviar.disabled = false;
  } else {
    btnEnviar.disabled = true;
  }
});