$(document).ready(function() {



    // Получаем текущую дату и время на стороне клиента
    const clientDate = new Date();

    // Получаем смещение часового пояса пользователя относительно UTC в минутах
    const timeZoneOffset = clientDate.getTimezoneOffset();

    // Преобразуем смещение часового пояса в формат часы:минуты
    const hoursOffset = Math.floor(Math.abs(timeZoneOffset) / 60);
    const minutesOffset = Math.abs(timeZoneOffset) % 60;
    const timeZoneSign = timeZoneOffset < 0 ? '+' : '-';
    const timeZone = `${timeZoneSign}${hoursOffset}:${minutesOffset}`;
    const timeOffset = timeZoneSign + hoursOffset



    const user_time_offset_input = document.getElementById('user_time_offset');
    user_time_offset_input.value = timeOffset;

});

