$(document).ready(function() {
    $('#select_train').on('change', function() {
        const hidden_train_id = document.getElementById('hidden_train_id');
        const select_train = document.getElementById('select_train');
        const selectedValue = select_train.value; // Получаем значение после изменения

        // Устанавливаем значение в скрытое поле
        const url = selectedValue;
        hidden_train_id.value = url;

        // Создаем объект requestData с нужными данными
        var requestData = {
            train_id: selectedValue,
        };

        // Выполняем AJAX-запрос с данными
        $.ajax({
            url: '/ajax_plan_training_view',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(requestData),
            success: function(response) {
                $('#ajax_data').html(response);
            },
            error: function(error) {
                console.error('Произошла ошибка:', error);
            }
        });
    });

    $('#select_train').trigger('change');



    $('#noweight_checkbox').on('change', function(){
        if ($(this).is(':checked')) {
            // Если чекбокс отмечен, скрываем элементы с name="element_to_hide"
            $('[name="element_to_hide"]').css('display', 'block');
        } else {
            // Если чекбокс не отмечен, показываем элементы с name="element_to_hide"
            $('[name="element_to_hide"]').css('display', 'none'); // или 'inline', 'flex', и т.д., в зависимости от вашего дизайна
        }
    });


    $('[name="plan_new_radio_filter"]').on('change', function(){

        var checkedValue = $(this).val();
        if (checkedValue === "personal") {
            $('option[data-owner="admin"]').css('display', 'none');
            $('option:not([data-owner="admin"])').css('display', 'block');
        } else if (checkedValue === "common") {
            $('option[data-owner="admin"]').css('display', 'block');
            $('option:not([data-owner="admin"])').css('display', 'none');
        } else {
            $('option[data-owner="admin"]').css('display', 'block');
            $('option:not([data-owner="admin"])').css('display', 'block');
        }

    });

    $('#flash_close_btn').on('click', function(){
        $(this).closest('.custom-flash-warning').remove();
    });



    $('.get-code-link').on('click', function(){

        const key_input = document.getElementById('localization_key');
        const key_value = "{{local_dict["+"'"+key_input.value+"'"+"][current_user.language]}}"

        // Создаем временный элемент input
        const input = document.createElement('input');
        input.value = key_value;
        
        // Добавляем его на страницу (он не видим для пользователя)
        document.body.appendChild(input);

        // Выделяем текст в input
        input.select();

        // Копируем текст в буфер обмена
        document.execCommand('copy');

        // Удаляем временный элемент input
        document.body.removeChild(input);



        console.log('key_value', key_value)
    });


    $('#chk_follow').on('change', function(){

        $.ajax({
            url: '/follow_change_status',
            method: 'POST',
            success: function(response) {
                console.log('AjReq - Done')
            },
            error: function(error) {
                console.error('Произошла ошибка:', error);
            }
        });


    });




});
