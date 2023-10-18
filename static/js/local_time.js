$(document).ready(function() {

    function updateLocalTime() {
                // Здесь вы можете использовать AJAX

                var currentUtcTime = new Date();


                var localTimeElement = document.getElementById("localTime");
                localTimeElement.textContent = currentUtcTime.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            }

    // Обновляйте время каждую секунду
    setInterval(updateLocalTime, 1000);

    // Вызовите функцию сразу после загрузки страницы
    updateLocalTime();


    function submitForm() {
     document.getElementById('tps_form').submit();
    }



    let durationInSeconds = document.getElementById('workout-duration').value;
    console.log(durationInSeconds)
    // Вставляем значение workout_duration_seconds из шаблона Flask

    function formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    function updateTimer() {
        const timerElement = document.getElementById('workout_duration');
        timerElement.textContent = formatTime(durationInSeconds);
        durationInSeconds++;
    }

    function submitForm() {
     document.getElementById('tps_form').submit();
    }

    setInterval(updateTimer, 1000);
    updateTimer();

   });