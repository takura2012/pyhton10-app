from __future__ import print_function
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from datetime import timedelta
import random, config, re
import string
import json
from datetime import datetime
import requests
from flask import request, flash, session
from flask_login import current_user

from _models import Exercise, Muscle, Training, ExerciseMuscle, TrainingExercise, \
    Plan, UserTraining, UserTrainingExercise, Plan_Trainings, User, Localization
from typing import List
from sqlalchemy import or_, and_, desc
from main import db

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# функция вернет список объектов Exercise сумма difficulty у которых будет не превышать max_effort по жадному алгоритму (начиная с больших)

def count_muscles(exercises: Exercise = []):
    id_list = []
    muscles_percent = {}
    pc_mus = {}

    for ex in exercises:
        id_list.append(ex.exercise_id)

    for exercise_muscle in ExerciseMuscle.query.all():
        if exercise_muscle.exercise_id in id_list:
            muscle_id = exercise_muscle.muscle_id
            muscles_percent[muscle_id] = muscles_percent.get(muscle_id, 0) + exercise_muscle.percent

    # print(muscles_percent)
    lp = 100
    for mu, pc in muscles_percent.items():
        lp += 1
        pc = str(lp) + '-' + str(pc)
        pc_mus[pc] = Muscle.query.get(mu)
        # print(f'{pc_mus[pc].muscle_name:<45}: {pc} %')
    # sorted_keys = sorted(pc_mus.keys())
    # sorted_pc_mus = {key: pc_mus[key] for key in sorted_keys}

    return pc_mus


def create_exercises_set(exercises: List[Exercise], max_effort):
    random_exercises = []
    sorted_exercises = sorted(exercises, key=lambda exercise: exercise.difficulty, reverse=True)
    random_exercises = sorted_exercises[1:]
    # random.shuffle(random_exercises)
    random_exercises.insert(0, sorted_exercises[0])

    current_sum = 0
    result = []
    final = []

    for ex in random_exercises:
        if current_sum + ex.difficulty <= max_effort:
            result.append(ex)
            current_sum += ex.difficulty
    final = result[:3]
    return final


def select_exercises(target_list=['Ноги'], efforts=90, excluded=[],
                     filters=[['1'], ['2'], ['3'], ['4'], ['5'], ['6'], ['7'], [8], [9]]):
    selected_exercises = []

    for target in target_list:

        target_exercises = Exercise.query.filter(
            Exercise.target == target,
            # or_(*[Exercise.filters.contains(f) for f in filters])
        ).all()

        # print(f'filters: {filters}')
        # for ex in target_exercises:
        # print(f'{ex.name}: {ex.filters}')

        exercises = [ex for ex in target_exercises if ex.exercise_id not in excluded]

        if exercises:
            targeted_exercises = create_exercises_set(exercises, efforts)
            selected_exercises += targeted_exercises

    return selected_exercises


def get_training_connections(train_id):  # te_info = [te, sets, repetitions] (te- Exercise)

    train = Training.query.get(train_id)
    te_info_list = []

    for te in train.exercises:  # для каждого упражнения te из цикла по training.exercises (класса Training)
        training_exercise = TrainingExercise.query.filter_by(training_id=train.training_id,
                                                             exercise_id=te.exercise_id).first()
        # выбираем по фильтру объекты связей TrainingExercise по training_id и exercise_id
        if training_exercise:  # и выбираем связанные сеты повторы и веса (которые 0 по умолчанию)
            sets = training_exercise.sets
            repetitions = training_exercise.repetitions
            ex_localizations = json.loads(te.localized_name)
            te_info = [te, sets, repetitions, ex_localizations]
            te_info_list.append(te_info)

    return te_info_list


def generate_unique_plan_name(base_name):
    name = base_name
    counter = 1

    while Plan.query.filter_by(name=name).first():
        name = f"{base_name}({counter})"
        counter += 1

    return name


def generate_unique_train_name(base_name):
    name = base_name
    counter = 1

    while Training.query.filter_by(name=name, owner=current_user.name).first():
        name = f"{base_name}({counter})"
        counter += 1

    return name


def assign_plan_to_user(user, plan_id):
    # беру все связи план-тренировка для этого плана
    plan_trainings = Plan_Trainings.query.filter_by(plan_id=plan_id).all()
    # цикл по этим связям
    for plan_train in plan_trainings:
        # создаю связь user_training для пользователя с флагом assigned=True
        user_training = UserTraining(user_id=user.id,
                                     training_id=plan_train.training_id,
                                     assigned=True
                                     )
        db.session.add(user_training)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return e

    # беру из базы новосозданные user_trainings для этого юзера с флагом assigned=True
    user_trainings = UserTraining.query.filter_by(user_id=user.id, assigned=True, completed=False).all()

    # далее создаю связи user_train_exercises , беру сеты и повторы с training_exercise
    user_train_exercises = []
    for user_training in user_trainings:
        train = Training.query.get(user_training.training_id)
        exercises = train.exercises
        for exercise in exercises:
            training_exercise = TrainingExercise.query.filter_by(training_id=train.training_id,
                                                                 exercise_id=exercise.exercise_id).first()
            user_train_exercise = UserTrainingExercise(user_training_id=user_training.id,
                                                       exercise_id=exercise.exercise_id,
                                                       sets=training_exercise.sets,
                                                       repetitions=training_exercise.repetitions,
                                                       weight=0
                                                       )
            user_train_exercises.append(user_train_exercise)

        db.session.add_all(user_train_exercises)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return e

    return True


def del_current_user_plan(user):
    user_trainings = UserTraining.query.filter_by(user_id=user.id, assigned=True, completed=False).all()
    user_trainings_ids = [ut.id for ut in user_trainings]
    user_training_exercises = UserTrainingExercise.query.filter(
        UserTrainingExercise.user_training_id.in_(user_trainings_ids)).all()
    for user_training_exercise in user_training_exercises:
        db.session.delete(user_training_exercise)
    for user_training in user_trainings:
        db.session.delete(user_training)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return e

    return True


def get_user_trains(user):
    trains = UserTraining.query.filter_by(user_id=user.id).all()

    return trains


def get_user_assigned_train(user):
    user_training = UserTraining.query.filter_by(user_id=user.id, assigned=True, completed=False).first()
    if not user_training:
        return None

    train = Training.query.filter_by(training_id=user_training.training_id).first()

    return train


def set_train_complete(user_id, train_id):
    # print(user_id, train_id)
    user_training = UserTraining.query.filter_by(user_id=user_id, training_id=train_id, completed=False).first()
    if user_training:
        user_training.completed = True
        user_training.date_completed = datetime.utcnow()

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(e)
            return e

        user_training_exercises = UserTrainingExercise.query.filter_by(user_training_id=user_training.id,
                                                                       completed=False).all()
        if not user_training_exercises:
            return 'Не найдена связь user_training_exercises'

        for user_training_exercise in user_training_exercises:
            user_training_exercise.completed = True
            user_training_exercise.skipped = True
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(e)
                return e

    return 'OK'


def find_prev_weight(ex_id, user_id):
    user_trainings = UserTraining.query.filter_by(user_id=user_id).all()
    ids = [user_training.id for user_training in user_trainings]
    exercise = Exercise.query.get(ex_id)

    user_training_exercise = UserTrainingExercise.query.filter(
        UserTrainingExercise.user_training_id.in_(ids),
        UserTrainingExercise.exercise_id == ex_id,
        UserTrainingExercise.weight > 0
    ).order_by(desc(UserTrainingExercise.id)).first()

    if user_training_exercise:
        previous_weight = user_training_exercise.weight
    else:
        previous_weight = 0

    return previous_weight


def find_max_weight(exercise_id, user_id):
    user_trainings = UserTraining.query.filter_by(user_id=user_id).all()
    ids = [user_trainings.id for user_trainings in user_trainings]

    user_training_exercises = UserTrainingExercise.query.filter(
        UserTrainingExercise.user_training_id.in_(ids),
        UserTrainingExercise.exercise_id == exercise_id
    ).all()

    max_weight_uts = max(user_training_exercises, key=lambda x: x.weight)
    max_weight = max_weight_uts.weight
    return max_weight


def get_exercise_statistics(user_id):
    exercises_struct = {}
    user_trainings = UserTraining.query.filter_by(user_id=user_id, completed=True).all()

    for user_training in user_trainings:
        user_training_exercises = UserTrainingExercise.query.filter_by(user_training_id=user_training.id).all()
        for user_training_exercise in user_training_exercises:
            ex_id = user_training_exercise.exercise_id
            ex_date_unformat = user_training.date_completed
            ex_date = ex_date_unformat.strftime("%d-%m-%Y")
            ex_weight = user_training_exercise.weight
            ex_skipped = user_training_exercise.skipped
            try:
                exercises_struct[ex_id].append({'date': ex_date, 'weight': ex_weight, 'skipped': ex_skipped})
            except:
                exercises_struct[ex_id] = []
                exercises_struct[ex_id].append({'date': ex_date, 'weight': ex_weight, 'skipped': ex_skipped})

    struc = []
    for ex_id, unsorted_data in exercises_struct.items():
        data = sorted(unsorted_data, key=lambda x: datetime.strptime(x['date'], '%d-%m-%Y'), reverse=True)
        ex = Exercise.query.get(ex_id)
        ex_names = json.loads(ex.localized_name)
        ex_name = ex_names[current_user.language]
        count = len(data)
        skipped_count = len(list(filter(lambda item: item['skipped'], data)))
        struc.append([ex_id, ex_name, count, skipped_count, data, ex.target])

    sorted_struc = sorted(struc, key=lambda struc: struc[2], reverse=True)

    # [[55, 'Разогрев+ разминка (10 минут)', 4, 1, [{'date': '28-08-2023 10:03:04', 'weight': 0, 'skipped': False},
    return sorted_struc


def contains_mixed_alphabets(name):
    # Используем регулярное выражение для поиска и совпадения кириллических и латинских символов
    pattern = re.compile(r'[а-яА-Я]+.*[a-zA-Z]+|[a-zA-Z]+.*[а-яА-Я]+')

    # Если найдено хотя бы одно совпадение, значит, в строке есть и кириллица, и латиница
    if re.search(pattern, name):
        return True
    else:
        return False


def is_valid_email(email):
    # Регулярное выражение для проверки адреса электронной почты
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

    # Используем метод match() для сравнения строки с регулярным выражением
    if re.match(pattern, email):
        return True
    else:
        return False


def generate_random_password(length=6):
    # Определите символы, из которых будет создаваться пароль
    characters = string.ascii_letters + string.digits  # латинские буквы и цифры

    # Генерируйте случайные символы заданной длины
    password = ''.join(random.choice(characters) for _ in range(length))

    return password


def load_localization_dict():
    phrases = Localization.query.all()
    phrases_list = {}
    for phrase in phrases:
        translations_dict = json.loads(phrase.translations)
        phrases_list[phrase.key] = translations_dict

    return phrases_list


def get_pref_lang():
    browser_lang = request.headers.get('Accept-Language')
    if browser_lang is None:
        return 'EN'
    print(f'browser_lang={browser_lang}')
    pls = browser_lang.split(',')
    prefered_languages = [pl[:2] for pl in pls]

    for lng in prefered_languages:
        if lng == 'uk':
            lng = 'UA'
            break
        if lng == 'en':
            lng = 'EN'
            break
        if lng == 'ru':
            lng = 'RU'
            break
        if lng == 'pl':
            lng = 'PL'
            break
        else:
            lng = 'EN'

    # chrome
    # uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7,ru;q=0.6
    # ru,uk-UA;q=0.9,uk;q=0.8,en-US;q=0.7,en;q=0.6
    # uk,ru;q=0.9,uk-UA;q=0.8,en-US;q=0.7,en;q=0.6
    # pl,uk;q=0.9,ru;q=0.8,uk-UA;q=0.7,en-US;q=0.6,en;q=0.5

    # edge
    # ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7
    # uk,en;q=0.9,en-GB;q=0.8,en-US;q=0.7,ru;q=0.6
    # pl,uk;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,ru;q=0.5
    return lng


def local_flash(key):
    languages = config.LANGUAGES
    default_language = 'EN'

    if not current_user or current_user.is_anonymous:
        default_language = get_pref_lang()
    else:
        default_language = current_user.language

    flash_localizations = Localization.query.filter_by(key=key).first()
    local_flash_message = json.loads(flash_localizations.translations)
    flash(local_flash_message[default_language])

    return None


def send_api_email(email, password, user, send_type):
    result = {'status': 400, 'details': 'Email not sended'}
    admin_user = User.query.filter_by(name='admin').first()
    admin_prefs = json.loads(admin_user.preferences)

    languages = config.LANGUAGES
    try:
        language = user.language
    except:
        language = get_pref_lang()



    api_key = admin_prefs['google_api_key']
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "fitapp.developers@gmail.com"
    receiver_email = email
    subject = "Fitness-App password recovery or registration"

    local_letter = {
        'EN': f'''<div style=\"background: #FAFAD2; border-radius: 3px; padding: 20px;\">
                        <h3>Hello, {user.name}!</h3>
                        
                        You have requested the password to app.<br>
                        So we provide to you a new password: <b>{password}</b><br>
                        Don`t forget to change it in your accounts settings!<br>
                        Now you can follow the <u><a href=\"https://teroshynvitaly.pythonanywhere.com/\">link to the application</a></u><br>
                        <br>
                        <br>
                        <i>Best regards, Fit-App developers.</i>
''',
        'RU': f'''<div style=\"background: #FAFAD2; border-radius: 3px; padding: 20px;\">
                        <h3>Здравствуйте, {user.name}!</h3>

                        Вы запросили пароль для приложения.<br>
                        Мы предоставили Вам новый пароль: <b>{password}</b><br>
                        Не забудьте сменить его в настройках акаунта!<br>
                        Теперь вы можете перейти по <u><a href=\"https://teroshynvitaly.pythonanywhere.com/\">ссылке на приложение</a></u><br>
                        <br>
                        <br>
                        <i>С наилучшими пожеланиями, команда разработчиков.</i>
''',
        'UA': f'''<div style=\"background: #FAFAD2; border-radius: 3px; padding: 20px;\">
                            <h3>Вітаємо, {user.name}!</h3>

                            Ви зробили запрос на пароль для додатку.<br>
                            Ми надіслали Вам новий пароль: <b>{password}</b><br>
                            Не забудьте змінити його в настройках акаунта!<br>
                            Тепер ви можете перейти за <u><a href=\"https://teroshynvitaly.pythonanywhere.com/\">посиланням на додаток</a></u><br>
                            <br>
                            <br>
                            <i>Бажаємо всього найкращого, команда розробників.</i>
    ''',
        'PL': f'''<div style=\"background: #FAFAD2; border-radius: 3px; padding: 20px;\">
                            <h3>Gratulacje, {user.name}!</h3>

                            Poprosiłeś o hasło do aplikacji.<br>
                            Wysłaliśmy Ci nowe hasło: <b>{password}</b><br>
                            Nie zapomnij zmienić tego w ustawieniach swojego konta!<br>
                            Możesz teraz przejść do <u><a href=\"https://teroshynvitaly.pythonanywhere.com/\">linku do aplikacji</a></u><br>
                            <br>
                            <br>
                            <i>Wszystkiego najlepszego, zespół programistów</i>
    '''
    }

    html = f'''<div style=\"background: #D3D3D3;\">
                        {local_letter[language]}
                        </div>
'''

    # Создание письма
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject

    message.attach(MIMEText(html, "html"))

    try:
        # Подключение к SMTP-серверу Gmail
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Включение защищенного соединения
            server.login(sender_email, api_key)  # Аутентификация
            server.sendmail(sender_email, receiver_email, message.as_string())  # Отправка письма
            result = {'status': 200, 'details': 'Email was sended'}
    except Exception as e:
        result = {'status': 400, 'details': 'Email not sended (Error sending)'}

    return result


def get_local_time():
    current_utc_time = datetime.utcnow()
    user_time = current_utc_time
    if not current_user.is_anonymous:
        user_prefs = json.loads(current_user.preferences)
        time_delta = timedelta(hours=user_prefs['LTO'])
        user_time = current_utc_time + time_delta

    local_time = user_time.strftime('%H:%M:%S')

    return local_time


def delete_user_data(user_id):
    user = User.query.get(user_id)
    user_plans = Plan.query.filter_by(owner=user.name).all()
    user_plans_ids = [user_plan.id for user_plan in user_plans]
    trains = Training.query.filter_by(owner=user.name).all()
    train_ids = [train.training_id for train in trains]
    user_trainings = UserTraining.query.filter_by(user_id=user.id).all()
    user_trainings_ids = [user_training.id for user_training in user_trainings]

    training_exercises_query = db.session.query(TrainingExercise).filter(TrainingExercise.training_id.in_(train_ids))
    training_exercises_query.delete()
    plan_trainings_query = db.session.query(Plan_Trainings).filter(Plan_Trainings.plan_id.in_(user_plans_ids))
    plan_trainings_query.delete()
    user_training_exercise_query = db.session.query(UserTrainingExercise).filter(
        UserTrainingExercise.user_training_id.in_(user_trainings_ids))
    user_training_exercise_query.delete()

    db.session.query(Plan).filter_by(owner=user.name).delete()
    db.session.query(Training).filter_by(owner=user.name).delete()
    db.session.query(UserTraining).filter_by(user_id=user_id).delete()

    db.session.delete(user)

    db.session.commit()
    return ''


def nd_filter_exercises(used_filters_list, used_target_filter):
    filtered_exercises = []

    # Создаем список условий для каждой группы фильтров - хз как оно работате делал чатГПТ. главное работает
    group_conditions = []
    for group in used_filters_list:
        group_condition = or_(*[Exercise.filters.contains(filter) for filter in group])
        group_conditions.append(group_condition)

    # Объединяем все групповые условия оператором and_
    combined_condition = and_(*group_conditions)

    # Применяем фильтр к запросу
    filtered_exercises = Exercise.query.filter(combined_condition).all()

    if used_target_filter != 'Все':
        exercises = [ex for ex in filtered_exercises if ex.target == used_target_filter]    # отбираю по полю таргет
    else:
        exercises = filtered_exercises  # если фильтр -1 (все) то не фильтрую

    return exercises