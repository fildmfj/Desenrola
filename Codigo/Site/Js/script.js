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

function telainicial(){
    const entrar = document.getElementById('entrar');
    const cadastro = document.getElementById('cadastro');
    
    entrar.onclick = () => window.location.href = "Login.html";   
    cadastro.onclick = () => window.location.href = "Cadastro.html";

}
