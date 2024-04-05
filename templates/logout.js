// logout.js

window.addEventListener('beforeunload', function (e) {
    // Enviar uma solicitação para fazer logout quando a aba do navegador for fechada
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/logout', false); // Sincrono
    xhr.send();
});
