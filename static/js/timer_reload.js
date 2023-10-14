$(document).ready(function() {
    function redirectToAdminPage() {
        // window.location.href = '/users_administration';
    }

    // Запускаем функцию каждую минуту (60 000 миллисекунд)
    setInterval(redirectToAdminPage, 60000);

});
