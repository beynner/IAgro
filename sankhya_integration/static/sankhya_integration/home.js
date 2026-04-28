// sankhya_integration/static/sankhya_integration/home.js

function handleCardClick(event) {
    // A variável window.PackHouse.isLogged será injetada pelo HTML
    if (!window.PackHouse.isLogged) {
        event.preventDefault(); // Trava a abertura da nova aba
        
        const inputs = document.querySelectorAll('.auth-input');
        inputs.forEach(input => {
            // Remove a classe para resetar a animação caso clique várias vezes
            input.classList.remove('highlight-error');
            void input.offsetWidth; // Truque do JS para forçar o recálculo (reflow)
            input.classList.add('highlight-error');
        });

        // Foca automaticamente no campo de usuário para agilizar a digitação
        const userInput = document.getElementById('auth-user');
        if (userInput) {
            userInput.focus();
        }
        
        return false;
    }
    return true; // Se estiver logado, segue o fluxo normal
}