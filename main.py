from flask import Flask, render_template, url_for, request, redirect, session, flash, jsonify
# from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from collections import Counter
import json

from sqlalchemy import Column, Integer, String, ForeignKey, and_, or_
from sqlalchemy.orm import relationship
from datetime import datetime

from flask_session import Session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import logging

from _models import Exercise, Muscle, ExerciseMuscle, db, User, Plan, TrainingExercise, \
    Training, UserTraining, UserTrainingExercise, Plan_Trainings, Localization
import config
from _logic import *

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)  # Устанавливаем уровень логгирования (INFO, DEBUG и т. д.)
logger = logging.getLogger(__name__)
app.config.from_object('config')
app.config['LOGIN_VIEW'] = 'index'

db.init_app(app)
Session(app)
# migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

# -----------------------------------------------REGISTER---------------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_local_dict():
    local_dict = load_localization_dict()
    return {'local_dict': local_dict}


@app.route('/user_login', methods=['POST', 'GET'])
def user_login():

    languages = config.LANGUAGES
    default_language = 'EN'

    browser_lang = request.headers.get('Accept-Language')

    langs = browser_lang.split(';')
    for lang in langs:
        for defined_lang in languages:
            if defined_lang.lower() in lang:
                default_language = defined_lang
                break
        else:
            continue
        break

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(name=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))

        flash_localizations = Localization.query.filter_by(key='Login_error').first()
        local_flash_message = json.loads(flash_localizations.translations)
        flash(local_flash_message[default_language])

    return redirect(url_for('index'))


@app.route('/user_logout')
def user_logout():

    logout_user()

    return redirect(url_for('index'))


@app.route('/register', methods=['POST', 'GET'])
def register():
    default_language = session.get('default_language', 'EN')

    if request.method == 'POST':
        username = request.form['username']
        if contains_mixed_alphabets(username) or username.lower() in config.RESERVED_NAMES or 'admin' in username.lower():

            local_flash('restricted_name')

            return redirect('register')

        password = generate_random_password(8)
        hashed_password = generate_password_hash(password)
        email = request.form['email']

        conditions = or_(User.name == username, User.email == email)
        user = User.query.filter(conditions).first()

        if not user:

            date_registration = datetime.utcnow()
            date_last_activity = date_registration
            LTO = int(request.form.get('LTO', '0'))
            preferences = json.dumps({'follow': True, 'LTO': LTO})
            user = User(name=username, password=hashed_password, email=email, preferences=preferences,
                        language=default_language, date_registration=date_registration, date_last_activity=date_last_activity)
            db.session.add(user)
            try:
                db.session.commit()
                send_email(email, password, username, 'registration')
                local_flash('success_register')
            except:
                local_flash('Base_error')
                return redirect(url_for('register'))
        else:
            local_flash('Error_existing_user')
            # flash('Пользователь с такими данными уже существует')
            return redirect('register')

        return redirect(url_for('index'))


    return render_template('/modals/register.html', default_language=default_language)

# -----------------------------------------------APP---------------------------------

@app.route('/index', methods=['POST', 'GET'])
@app.route('/', methods=['POST', 'GET'])
def index():
    languages = config.LANGUAGES
    default_language = 'EN'
    browser_lang = request.headers.get('Accept-Language', 'EN')

    langs = browser_lang.split(';')
    for lang in langs:
        for defined_lang in languages:
            if defined_lang.lower() in lang:
                default_language = defined_lang
                break
        else:
            continue
        break
    session['default_language'] = default_language

    if not current_user.is_anonymous:
        current_user.date_last_activity = datetime.utcnow()
        try:
            db.session.commit()
        except:
            db.session.rollback()

    try:
        uncompleted_user_trainings = UserTraining.query.filter_by(user_id=current_user.id, assigned=True, completed=False).all()
    except:
        return render_template("index.html", current_user=current_user, default_language=default_language)

    return render_template("index.html", uncompleted_user_trainings=uncompleted_user_trainings, current_user=current_user,
                           default_language=default_language)



# ------------------------------------------------BASE----------------------------------------------------------------

@app.route('/list/<string:counters>/del', methods=['POST','GET'])
@login_required
def list_del(counters):

    if current_user.role != 'admin':
        return redirect(url_for('index'))

    tb = counters[:2]
    counter = counters[2:]
    exercises = Exercise.query.all()
    muscles = Muscle.query.all()
    if tb == 'ex':
        exercise = Exercise.query.filter_by(counter=counter).first()
        try:
            db.session.delete(exercise)
            db.session.commit()
            Exercise.update_counters()
            exercises = Exercise.query.all()
            return render_template('list.html', exercises=exercises, muscles=muscles)
        except Exception as e:
            # local_flash('Base_error')
            return f'Ошибка при удалении упражнения из базы: {e}'
    else:
        # muscle = Muscle.query.get_or_404(id)
        muscle = Muscle.query.filter_by(counter=counter).first()
        try:
            db.session.delete(muscle)
            db.session.commit()
            Muscle.update_counters()
            return render_template('list.html', exercises=exercises, muscles=muscles)
        except:
            return 'Ошибка при удалении из базы'


@app.route('/list/<string:counters>/edit', methods=['POST', 'GET'])
@login_required
def list_edit(counters):

    if current_user.role != 'admin':
        return redirect(url_for('index'))

    targets = config.TARGETS
    languages = config.LANGUAGES
    const_config = {}
    const_config['filter_list'] = config.FILTER_LIST
    index_dict = {}
    index_dict['filter_list'] = []


    tb = counters[:2]   # counters передано сюда в маршруте , вид: ex3 или mu4
    counter = counters[2:]
    exercises = Exercise.query.all()
    muscles = Muscle.query.all()
    if tb == 'ex':  # если передано ex, то работа над редактированием Упражнения
        exercise = Exercise.query.filter_by(counter=counter).first()    # counter - переданное значение счетчика, фильтрую базу по счетчику

        if exercise.localized_name:
            exercise_localized_names = json.loads(exercise.localized_name)
            print(exercise_localized_names)
        else:
            exercise_localized_names={}

        if exercise.filters is None:
            exercise.filters=[]
        if request.method == 'POST':    # если метод ПОСТ (то есть если мы передаем данные с формы к нам сюда на сервер, то далее обрабатываем данные формы и сохраняем в базу
            exercise.name = request.form['name']
            exercise.target = request.form['select_target']  # тут новое поле для класса
            exercise.description = request.form['description']
            exercise.difficulty = request.form['difficulty']
            exercise.time_per_set = request.form['time_per_set']

            exercise_localized_names = {}
            for language in languages:
                exercise_localized_names[language] = request.form.get('exercise_'+language, '')

            exercise.localized_name = json.dumps(exercise_localized_names)

            for i in range(len(const_config['filter_list'])):
                form_list = request.form.getlist('filters' + str(i + 1))
                if any(sublist for sublist in form_list if sublist):
                    index_dict['filter_list'] += form_list

            exercise.filters = index_dict['filter_list']

            percents = request.form.getlist('percents[]')   # получаю список значений полей с именем percents[]

            exercise_muscles = []
            # удаляю из связей старые по exercise_id
            ExerciseMuscle.query.filter_by(exercise_id=exercise.exercise_id).delete()


            for counter, percent in enumerate(percents, start=1):
                if percent != '':
                    muscle = Muscle.query.filter_by(counter=counter).first()    # нахожу Muscle по counter
                    # создаю объект ExerciseMuscle для exercise_id muscle_id percent
                    ExMus = ExerciseMuscle(exercise_id = exercise.exercise_id, muscle_id = muscle.muscle_id, percent = percent)
                    # добавляю его в список
                    exercise_muscles.append(ExMus)
                    # print(f'Упражнение id: {ExMus.exercise_id} - {muscle.muscle_name} (id:{ExMus.muscle_id}) - на {ExMus.percent}%')

            try:
                # сливаю список объектов ExerciseMuscle в базу, которая ранее была очищена
                db.session.add_all(exercise_muscles)
                db.session.commit()
                return render_template('list.html', exercises=exercises, muscles=muscles)
            except Exception as e:
                db.session.rollback()
                return f'Ошибка при сохранения в базу данных: {e}'
        else:   # если метод не ПОСТ (а значит ГЕТ) то мы только зашли на маршрут и генерируем страницу для редактирования Упражнений, отсылая ей данные
            ex_len = len(exercises)


            # Объект Exercise получен в начале по counter
            if exercise is not None:
                muscles_in_ex = exercise.muscles  # Получение списка связанных мышц
                mus_dict = {}
                for muscle in muscles_in_ex:
                    percent = ExerciseMuscle.query.filter_by(exercise_id=exercise.exercise_id, muscle_id=muscle.muscle_id).first().percent
                    mus_dict[muscle.counter] = percent
            else:
                return "Упражнение не найдено."

            # передаем в шаблон упражнение, все мышцы, словарь {счетчик_мышцы:процент}
            return render_template('edit_ex_table.html', exercise=exercise, ex_len=ex_len, muscles=muscles,
                                   mus_dict=mus_dict, targets=targets, const_config=const_config, languages=languages,
                                   exercise_localized_names=exercise_localized_names)
    else:   # если передано не ех (а значит mu) то мы работаем над мускулами
        muscle = Muscle.query.filter_by(counter=counter).first()    # получем по счетчику, и далее по методам ПОСТ или ГЕТ
        if request.method == 'POST':    # ПОСТ- сохраняем данные полученные из формы и генерируем маршрут на список всего
            muscle.muscle_name = request.form['name']
            try:
                db.session.commit()
                return render_template('list.html', exercises=exercises, muscles=muscles)
            except:
                return 'Ошибка при сохранении в базу данных'
        else:   # ГЕТ - генерируем страницу редактирования мышцы, длина списка передается для кнопок назад-вперед
            mu_len = len(muscles)
            return render_template('edit_mus_table.html', muscle=muscle, mu_len=mu_len)


@app.route('/list', methods=['POST', 'GET'])
@login_required
def list():

    if current_user.role != 'admin':
        return redirect(url_for('index'))

    exercises = Exercise.query.all()
    muscles = Muscle.query.all()
    return render_template('list.html', exercises = exercises, muscles = muscles)


@app.route('/create_exercises', methods=['POST','GET'])
@login_required
def create_exercises():
    filters = []
    targets = config.TARGETS
    config_filters = config.FILTER_LIST
    languages = config.LANGUAGES
    if request.method == 'POST':
        name = request.form['name']
        target = request.form['select_target']
        description = request.form['description']
        difficulty = request.form['difficulty']
        time_per_set = int(request.form['time_per_set']) if request.form['time_per_set'] else 0

        for i in range(len(config_filters)):
            form_list = request.form.getlist('filters' + str(i + 1))
            if any(sublist for sublist in form_list if sublist):
                filters += form_list

        default_local_set = {}
        for language in languages:
            default_local_set[language] = 'No localization data'

        localized_name = json.dumps(default_local_set)

        exercise = Exercise(name = name, target=target, description = description, difficulty = difficulty,
                            time_per_set = time_per_set, filters=filters, localized_name=localized_name)

        try:
            db.session.add(exercise)
            db.session.commit()
            Exercise.update_counters()
            link_to_go= f'list/ex{exercise.counter}/edit'

            return redirect(link_to_go)
        except:
            return 'Ошибка при сохранении в базу'
    else:
        return render_template('create_exercises.html', targets=targets, config_filters=config_filters)



# ------------------------------------------------TRAIN----------------------------------------------------------------
@app.route('/train_add_ex', methods=['POST', 'GET'])
@login_required
def train_add_ex():

    if request.method == 'POST':    # при получении данных с формы

        train_id = request.form.get('train_id_hidden')
        if Training.query.get(train_id).owner != current_user.name:
            return redirect('index')
        ex_id = request.form.get('select_exercise')
        sets = request.form.get('sets')
        reps = request.form.get('reps')

        target_filter = request.form.get('target_filter', '-1')
        exercise_filter_list_json = request.form.get('exercise_filter_list_input')
        exercise_filter_list = [inner_list.split(',') for inner_list in exercise_filter_list_json.split(';')]

        # ищу в таблице связей training_exercise по тренировке и упражнениям
        training_exercise = TrainingExercise.query.filter_by(training_id = train_id, exercise_id = int(ex_id)).first()
        if not training_exercise:   # добавлю в базу только если не существует такого
            training_exercise = TrainingExercise(training_id = train_id,
                                                 exercise_id = int(ex_id),
                                                 sets = int(sets),
                                                 repetitions = int(reps))

            try:
                db.session.add(training_exercise)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                local_flash('Base_error')
                return redirect(url_for('edit_train', train_id=train_id))

        exercise_filter_list_str = json.dumps(exercise_filter_list)

        url = url_for('edit_train', train_id=train_id, target_filter=target_filter,
                      exercise_filter_list_str=exercise_filter_list_str)
        return redirect(url)

    return redirect(url_for('index'))


@app.route('/train_del_exercise/<int:train_id>/<int:ex_id>')
@login_required
def train_del_exercise(train_id, ex_id):
    if Training.query.get(train_id).owner != current_user.name:
        return redirect(url_for('index'))

    training_exercise = TrainingExercise.query.filter_by(training_id=train_id, exercise_id=ex_id).first()

    if training_exercise:
        db.session.delete(training_exercise)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            local_flash('Base_error')
            return redirect(url_for('edit_train', train_id=train_id))
            # return f'Ошибка: Не удалось удалить из базы -- {e}'
    else:
        local_flash('Base_error')
        return redirect(url_for('edit_train', train_id=train_id))
        # return 'TrainingExercise не определено'


    return redirect(url_for('edit_train', train_id=train_id))


@app.route('/edit_exercise_in_train/<int:train_id>', methods=['POST', 'GET'])
@login_required
def edit_exercise_in_train(train_id):
    try:
        train = Training.query.get(train_id)
        if train.owner != current_user.name:
            return redirect(url_for('index'))
    except:
        local_flash('Base_error')
        return redirect(url_for('edit_train', train_id=train_id))
        # return 'Ошибка: тренировка не найдена'

    if request.method == 'POST':
        exercise_id = request.form.get('exercise_id')
        sets = request.form.get('modal_sets')
        reps = request.form.get('modal_reps')

        training_exercice = TrainingExercise.query.filter_by(training_id=train_id, exercise_id=exercise_id).first()
        training_exercice.sets = sets
        training_exercice.repetitions = reps

        try:
            db.session.commit()
        except:
            # return 'Ошибка: не удалось перезаписать в базу новые данные'
            local_flash('Base_error')

    return redirect(url_for('edit_train', train_id=train.training_id))


@app.route("/new_train", methods=['POST', 'GET'])
@login_required
def new_train():

    languages = config.LANGUAGES
    empty_locals = {lang: '' for lang in languages}

    if current_user.role != 'admin':
        conditions = or_(Training.owner == 'admin', Training.owner == current_user.name)
    else:
        conditions = or_(Training.owner == 'admin', Training.owner == 'old_training')

    trains_list = Training.query.filter(conditions).all()
    if request.method == 'POST':
        train_name = request.form.get('train_name')
        new_name = generate_unique_train_name(train_name)

        new_train = Training(name=new_name, owner=current_user.name)
        db.session.add(new_train)
        try:
            db.session.commit()
        except:
            db.session.rollback()
            local_flash('Base_error')
            return redirect(url_for('index'))
            # return 'Ошибка при создании новой тренировки (не сохранились изменения в базе)'

        return redirect(url_for('edit_train', train_id=new_train.training_id))


    payload_data = [[train, json.loads(train.local_names) if train.local_names is not None else empty_locals] for train in trains_list]


    return render_template('new_train.html', trains_list=trains_list, payload_data=payload_data)


@app.route('/edit_train/<int:train_id>', methods=['POST', 'GET'])
@login_required
def edit_train(train_id):
    languages = config.LANGUAGES
    train_local_names = {}
    train = Training.query.get(train_id)  # нахожу тренировку по ID которое передано в роуте

    try:
     train_local_names = json.loads(train.local_names)
     train_local_name = train_local_names[current_user.language]
    except:
        for language in languages:
            train_local_names[language] = ''
            train_local_name = train.name


    if train.owner == 'old_training':
        user_trainings = UserTraining.query.filter_by(training_id=train.training_id).all()

        unsorted_train_data = []
        for user_training in user_trainings:
            user = User.query.get(user_training.user_id)
            date = user_training.date_completed
            date = date.strftime('%Y-%m-%d %H:%M:%S')
            unsorted_train_data.append({'train':train, 'user':user, 'date':date})

        train_data = sorted(unsorted_train_data, key=lambda utd: utd['date'])

        return render_template('old_train.html', train_data=train_data)




    const_config_filters = config.FILTER_LIST # основные фильтры из конфига (список списков)
    config_filters = []
    for i in range(len(const_config_filters)):
        config_filters.append({})
        for numb, filter_name in const_config_filters[i].items():
            # print(filter_name)
            localized_filter_name = Localization.query.filter_by(key=filter_name).first()
            localized_filter_names_json = json.loads(localized_filter_name.translations)
            localized_filter_name_json = localized_filter_names_json[current_user.language]
            config_filters[i][numb] = localized_filter_name_json


    config_filter_targets = config.FILTER_TARGETS   # список фильтров таргета - групп мышц
    loc_config_targets = config.LOC_TARGETS
    exercise_filter_list_str = request.args.get('exercise_filter_list_str')
    if exercise_filter_list_str:
        exercise_filter_list = json.loads(exercise_filter_list_str)
    else:
        exercise_filter_list = []

    exercise_filter_list_json = ';'.join([','.join(sublist) for sublist in exercise_filter_list])
    target_filter = request.args.get('target_filter', '-1')

    # Создаем список условий для каждой группы фильтров - хз как оно работате делал чатГПТ. главное работает
    group_conditions = []
    for group in exercise_filter_list:
        group_condition = or_(*[Exercise.filters.contains(filter) for filter in group])
        group_conditions.append(group_condition)

    # Объединяем все групповые условия оператором and_
    combined_condition = and_(*group_conditions)

    # Применяем фильтр к запросу
    filtered_exercises = Exercise.query.filter(combined_condition).all()

    # применяем фильтр по группе мышц



    if int(target_filter) >= 0:
        target_filter_name = config_filter_targets[int(target_filter)+1]
        exercises = [ex for ex in filtered_exercises if ex.target == target_filter_name]    # отбираю по полю таргет
    else:
        exercises = filtered_exercises  # если фильтр -1 (все) то не фильтрую

    exercise_localization_names = [json.loads(ex.localized_name) for ex in exercises]

    # print(exercise_localization_names)

    if train:
        te_info_list = get_training_connections(train.training_id) # функция для получения связанных с тренировкой полей
        # te_info_list = [[Exercise, sets, repetitions, weight], [...], ...]    -
    total_time = 0
    for te_info in te_info_list:
        total_time += te_info[0].time_per_set * te_info[1]



    return render_template('edit_train.html', train=train, te_info_list=te_info_list,
                           exercises=exercises, config_filters=config_filters, exercise_filter_list=exercise_filter_list,
                           config_filter_targets=config_filter_targets, target_filter=target_filter, total_time=total_time,
                           train_id=train_id, exercise_filter_list_json=exercise_filter_list_json,
                           exercise_localization_names=exercise_localization_names, loc_config_targets=loc_config_targets,
                           languages=languages, train_local_names=train_local_names, train_local_name=train_local_name)


@app.route('/save_train_localization', methods=['POST'])
@login_required
def save_train_localization():
    languages = config.LANGUAGES
    train_local_names = {}
    for language in languages:
        train_local_names[language] = request.form.get('train_'+language)
    train_id = request.form.get('train_id')
    train = Training.query.get(train_id)
    train.local_names = json.dumps(train_local_names)
    try:
        db.session.commit()
    except:
        db.session.rollback()
        local_flash('Base_error')

    return redirect(url_for('edit_train', train_id = train_id))


@app.route('/train_rename', methods=['POST', 'GET'])
@login_required
def train_rename():
    if request.method == 'POST':

        train_id = request.form.get('train_id_hidden')

        train = Training.query.get(train_id)
        if train.owner != current_user.name:
            local_flash('No_rename_rights')
            # flash('У вас нет права переименовать эту тренировку')
            return redirect(url_for('edit_train', train_id=train_id))

        train_new_name = request.form.get('train_new_name')

        train.name = train_new_name
        try:
            db.session.commit()
        except:
            db.session.rollback()
            local_flash('Base_error')
            # return 'Не удалось сохранить в базу тренировку с новым именем'
            return redirect(url_for('edit_train', train_id=train.training_id))


    return redirect(url_for('edit_train', train_id=train.training_id))


@app.route("/train_delete", methods=['POST', 'GET'])
@login_required
def train_delete():

    if request.method == 'POST':
        train_id = request.form.get('train_id_hidden')
        train = Training.query.get(train_id)

        if train.owner != current_user.name:
            # flash('У вас нет права удалить эту тренировку')
            local_flash('No_delete_rights')
            return redirect(url_for('edit_train', train_id=train_id))

        user_training = UserTraining.query.filter_by(training_id=train_id).first()
        if user_training:
            train.owner = 'old_training'
            try:
                db.session.commit()
            except:
                local_flash('Base_error')
                # flash('Не удалось переместить тренировку в старые')
                db.session.rollback()
            return redirect(url_for('new_train'))

        user_trains = UserTraining.query.filter_by(training_id=train_id).all()
        user_trains_ids = [user_train.id for user_train in user_trains]
        user_train_exercises = UserTrainingExercise.query.filter(UserTrainingExercise.user_training_id.in_(user_trains_ids)).all()

        for user_train in user_trains:
            db.session.delete(user_train)

        for user_train_exercise in user_train_exercises:
            db.session.delete(user_train_exercise)

        plan_trains = Plan_Trainings.query.filter_by(training_id=train_id).all()
        for plan_train in plan_trains:
            db.session.delete(plan_train)

        db.session.delete(train)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            local_flash('Base_error')
            # return f'Ошибка базы данных: Не удалось удалить тренировку {train.name} (id: {train.training_id})или связанные данные.\n {e}'

    return redirect('new_train')


@app.route("/del_old_train/<int:train_id>")
@login_required
def del_old_train(train_id):
    if current_user.role != 'admin':
        # flash('Операция запрещена: нет прав')
        local_flash('Base_error')
        return redirect(url_for('index'))

    train = Training.query.get(train_id)
    user_trains = UserTraining.query.filter_by(training_id=train_id).all()
    user_trains_ids = [user_train.id for user_train in user_trains]
    user_train_exercises = UserTrainingExercise.query.filter(
        UserTrainingExercise.user_training_id.in_(user_trains_ids)).all()

    for user_train in user_trains:
        db.session.delete(user_train)

    for user_train_exercise in user_train_exercises:
        db.session.delete(user_train_exercise)

    plan_trains = Plan_Trainings.query.filter_by(training_id=train_id).all()
    for plan_train in plan_trains:
        db.session.delete(plan_train)

    db.session.delete(train)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        local_flash('Base_error')
        # return f'Ошибка базы данных: Не удалось удалить тренировку {train.name} (id: {train.training_id})или связанные данные.\n {e}'

    return redirect(url_for('new_train'))


@app.route('/get_exercise_filter_list', methods=['POST', 'GET'])
@login_required
def exercise_filter_list():
    config_filters = config.FILTER_LIST

    exercise_filter_list = []

    if request.method == 'POST':
        train_id = int(request.form.get('train_id'))
        for i in range(len(config_filters)):
            exercise_filter_list.append(request.form.getlist('filters' + str(i + 1)))  # снимаю фильтрі в списки

        exercise_filter_list_str = json.dumps(exercise_filter_list)
        target_filter = request.form.get('select_target')

    url = url_for('edit_train', train_id=train_id, target_filter=target_filter, exercise_filter_list_str=exercise_filter_list_str)
    return redirect(url)


# ------------------------------------------------PLANS----------------------------------------------------------------
@app.route('/plans_all', methods=['POST', 'GET'])
@login_required
def plans_all():
    languages = config.LANGUAGES

    conditions = or_(Plan.owner == current_user.name, Plan.owner == 'admin')
    plans = Plan.query.filter(conditions).all()
    plan_ids = [plan.id for plan in plans]

    plan_trainings = Plan_Trainings.query.filter(Plan_Trainings.plan_id.in_(plan_ids)).all()
    trainings_ids = [plan_training.training_id for plan_training in plan_trainings]
    trains = Training.query.filter(Training.training_id.in_(trainings_ids)).all()


    trainings_in_plan = {}  # {plan: [trains], ...}
    plans_local_names = {} # {plan: local_name}
    for plan in plans:
        plans_local_names[plan] = json.loads(plan.local_names) if plan.local_names is not None else {lang: '' for lang in languages}
        trainings_in_plan[plan] = []
        for plan_train in plan_trainings:

            for train in trains:
                if train.training_id == plan_train.training_id and plan_train.plan_id == plan.id:

                    train_time = 0
                    ex_loc_names_user_lang = []
                    for exercise in train.exercises:
                        te = TrainingExercise.query.filter_by(training_id=train.training_id, exercise_id=exercise.exercise_id).first()
                        train_time += te.sets * exercise.time_per_set
                        ex_loc_names = json.loads(exercise.localized_name)
                        ex_loc_name = ex_loc_names[current_user.language]
                        ex_loc_names_user_lang.append(ex_loc_name)

                    train_local_names = json.loads(train.local_names) if train.local_names is not None else {current_user.language: train.name}
                    train_local_name = train_local_names[current_user.language]

                    trainings_in_plan[plan].append([train_local_name, train_time, ex_loc_names_user_lang])

    # { < Plan 3 >: [[Training 3, 61], [Training 7, 67], [Training 10, 73], [Training 11, 79], [Training 12, 61]],
    # {Plan: [[Training_name, train_time, [exercise_loc_names]] , [Training_name, train_time, [exercise_loc_names]], ..]}
    return render_template('plans_all.html', trainings_in_plan=trainings_in_plan, plans_local_names=plans_local_names)


@app.route('/plan_new/<int:plan_id>', methods=['POST', 'GET'])
@login_required
def plan_new(plan_id):

    languages = config.LANGUAGES
    empty_locals = {lang: '' for lang in languages}
    train_local_names= {}
    plan_trainings = []
    all_plan_trainings = []
    plan_local_names = empty_locals

    conditions = or_(Training.owner == 'admin', Training.owner == current_user.name)
    trainings = Training.query.filter(conditions).all()
    for train in trainings:
        if train.owner == 'admin':
            train_local_names_loads = json.loads(train.local_names)
            train_local_name = train_local_names_loads[current_user.language]
        else:
            train_local_name = train.name

        train_local_names[train] = train_local_name


    plan = Plan.query.get(plan_id)
    if plan:
        plan_local_names = json.loads(plan.local_names) if plan.local_names is not None else empty_locals
        plan_trainings = Plan_Trainings.query.filter_by(plan_id=plan_id).all()


        train_ids = [plan_training.training_id for plan_training in plan_trainings]

        for plan_training in plan_trainings:
            if plan_training.training_id in train_ids:
                train = Training.query.get(plan_training.training_id)
                all_plan_trainings.append([train, plan_training.id])



    if request.method == 'POST' and plan_id == 0:
        plan_name = request.form.get('plan_name')

        unique_name = generate_unique_plan_name(plan_name)

        plan = Plan(name=unique_name, owner=current_user.name)
        db.session.add(plan)

        try:
            db.session.commit()
        except:
            db.session.rollback()
            # flash('Ошибка при сохранении в базу')
            local_flash('Base_error')
            return redirect(url_for('plans_all'))
    else:
        plan = Plan.query.get(plan_id)
        if not plan:
            return redirect(url_for('plans_all'))
        if plan.owner != current_user.name:
            # flash('Вы не можете редактировать этот план')
            local_flash('cannot_edit_plan')
            return redirect(url_for('plans_all'))



    return render_template('plan_new.html', trainings=trainings, plan=plan, plan_trainings=plan_trainings, plan_id=plan.id,
                           all_plan_trainings=all_plan_trainings, languages=languages, plan_local_names=plan_local_names,
                           train_local_names=train_local_names)


@app.route('/save_plan_localization', methods = ['POST'])
@login_required
def save_plan_localization():
    languages = config.LANGUAGES
    plan_id = request.form.get('plan_id')
    plan_local_names = {language: request.form.get('plan_'+language) for language in languages}

    plan = Plan.query.get(plan_id)
    plan.local_names = json.dumps(plan_local_names)
    try:
        db.session.commit()
    except:
        db.session.rollback()
        # flash('Ошибка сохранения в базу данных')
        local_flash('Base_error')
        return redirect(url_for('plans_all'))


    return redirect(url_for('plan_new', plan_id=plan_id))


@app.route('/plan_rename', methods=['POST', 'GET'])
@login_required
def plan_rename():
    if request.method == 'POST':

        plan_id = request.form.get('plan_id')
        plan_new_name = request.form.get('plan_new_name')
        plan = Plan.query.get(plan_id)
        if plan.owner != current_user.name:
            return redirect(url_for('index'))
        plan_new_name = generate_unique_plan_name(plan_new_name)

        plan.name = plan_new_name

        try:
            db.session.commit()
        except:
            db.session.rollback()
            local_flash('Base_error')
            return redirect(url_for('plan_new', plan_id=plan_id))
            # 'Ошибка : не удалось сохранить в базу новое имя плана'

    return redirect(url_for('plan_new', plan_id=plan_id))


@app.route('/plan_delete/<int:plan_id>')
@login_required
def plan_delete(plan_id):
    plan = Plan.query.get(plan_id)
    if plan.owner != current_user.name:
        return redirect(url_for('index'))
    plan_trainings = Plan_Trainings.query.filter_by(plan_id=plan_id).all()
    for plan_training in plan_trainings:
        db.session.delete(plan_training)

    try:
        db.session.commit()
    except Exception as e:
        local_flash('Base_error')
        return redirect(url_for('plans_all'))
        # f'Ошибка: не удалось удалить связи план-тренировки : {e}'

    db.session.delete(plan)
    try:
        db.session.commit()
    except:
        local_flash('Base_error')
        return redirect(url_for('plans_all'))
        # f'Ошибка: не удалось удалить план после удаления связей : {e}'

    return redirect(url_for('plans_all'))


@app.route('/plan_add_train', methods=['POST', 'GET'])
@login_required
def plan_add_train():

    if request.method == 'POST':
        plan_id = request.form.get('hidden_plan_id')
        train_id = request.form.get('hidden_train_id')
        plan = Plan.query.get(plan_id)
        train = Training.query.get(train_id)

        if Plan.query.get(plan_id).owner != current_user.name:
            # flash('У вас нет прав редактировать этот план!')
            local_flash('cannot_edit_plan')
            return redirect(url_for('plans_all'))

        # для дубликатов:
        PT = Plan_Trainings(plan_id=plan_id, training_id=train_id)

        try:
            db.session.add(PT)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            local_flash('Base_error')
            return redirect(url_for('plans_all'))
            # f'Ошибка: не удалось записать в базу добавленные тренировки ---- {e}'

    return redirect(url_for('plan_new', plan_id=plan_id))


@app.route('/del_train_from_plan/<int:plan_trainings_id>')
@login_required
def del_train_from_plan(plan_trainings_id):

    plan_training = Plan_Trainings.query.get(plan_trainings_id)
    plan_id = plan_training.plan_id
    if Plan.query.get(plan_id).owner != current_user.name:
        # flash('У вас нет прав редактировать этот план!')
        local_flash('cannot_edit_plan')
        return redirect(url_for('plans_all'))

    db.session.delete(plan_training)

    try:
        db.session.commit()
    except:
        db.session.rollback()
        local_flash('Base_error')
        return redirect(url_for('plans_all'))
        # 'Ошибка: не удалось удалить связь плана и тренировки'

    return redirect(url_for('plan_new', plan_id=plan_id))


@app.route('/migration')
@login_required
def migration():

    if current_user.role == 'admin':
        user_admin = User.query.filter_by(name='admin').first()

        prefs = json.loads(user_admin.preferences)
        youtube_link = prefs.get('youtube_link','')
        smtp_server = prefs['SMTP_SERVER']
        smtp_port = prefs['SMTP_PORT']
        smtp_username = prefs['SMTP_USERNAME']
        smtp_password = prefs['SMTP_PASSWORD']

    return render_template('migration.html', prefs=prefs)


@app.route('/migration/clear_session')
@login_required
def clear_session():
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    session.clear()
    return redirect('/')

@app.route('/migration/new_base')
@login_required
def migration_new():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    with app.app_context():
        try:
            db.create_all()
            return '<h2>Таблицы добавлены</h2>'
        except Exception as e:
            return f'<h2>Ошибка: {str(e)}</h2>'


@app.route('/set_admin_prefs', methods=['GET', 'POST'])
@login_required
def set_admin_prefs():
    youtube_link = request.form.get('youtube_link', '')
    SMTP_SERVER = request.form.get('SMTP_SERVER', '')
    SMTP_PORT = request.form.get('SMTP_PORT', '')
    SMTP_USERNAME = request.form.get('SMTP_USERNAME', '')
    SMTP_PASSWORD = request.form.get('SMTP_PASSWORD', '')
    SECRET_KEY = request.form.get('SECRET_KEY', '')

    user_prefs = json.loads(current_user.preferences)
    user_prefs['youtube_link'] = youtube_link
    user_prefs['SMTP_SERVER'] = SMTP_SERVER
    user_prefs['SMTP_PORT'] = SMTP_PORT
    user_prefs['SMTP_USERNAME'] = SMTP_USERNAME
    user_prefs['SMTP_PASSWORD'] = SMTP_PASSWORD
    user_prefs['SECRET_KEY'] = SECRET_KEY

    current_user.preferences = json.dumps(user_prefs)

    try:
        db.session.commit()
    except:
        db.session.rollback()
        local_flash('Base_error')

    return redirect(url_for('migration'))

# ------------------------------------------------TRAINING-PROGRESS----------------------------------------------------------------

@app.route('/current_train', methods=['POST', 'GET'])
@login_required
def current_train():

    languages = config.LANGUAGES

    all_user_trains = get_user_trains(current_user)
    current_train = get_user_assigned_train(current_user)


    if not current_train:
        return render_template('current_train.html')

    if current_train.owner == 'admin':
        train_local_names = json.loads(current_train.local_names)
        train_local_name = train_local_names[current_user.language]
    else:
        train_local_name = current_train.name

    current_train_exlist = []
    workout_started = False
    for exercise in current_train.exercises:
        user_train = UserTraining.query.filter_by(user_id=current_user.id,
                                                  training_id=current_train.training_id,
                                                  assigned=True,
                                                  completed=False
                                                  ).first()
        user_training_exercise = UserTrainingExercise.query.filter_by(user_training_id=user_train.id,
                                                                      exercise_id=exercise.exercise_id
                                                                      ).first()
        ex_loc_names = json.loads(exercise.localized_name)
        ex_loc_name = ex_loc_names[current_user.language]
        current_train_exlist.append([ex_loc_name, user_training_exercise.sets, user_training_exercise.repetitions,
                                     user_training_exercise.weight, user_training_exercise.completed])

    return render_template('current_train.html', current_train=current_train, current_train_exlist=current_train_exlist,
                           train_local_name=train_local_name)


@app.route('/assign_training/<int:plan_id>')
@login_required
def assign_training(plan_id):

    if current_user:
        del_current_user_plan(current_user)

        if not assign_plan_to_user(current_user, plan_id):
            # 'Ошибка assign_plan_to_user'
            local_flash('Base_error')

    return redirect(url_for('index'))


@app.route('/user_complete_train/<int:train_id>')
@login_required
def user_complete_train(train_id):

    res = set_train_complete(current_user.id, train_id)
    if res != 'OK':
        # flash('Ошибка при установке завершения тренировки (запись в базу)')
        local_flash('Base_error')
    return redirect(url_for('index'))


@app.route('/train_progress_start', methods=['POST', 'GET'])
@login_required
def train_progress_start():
    user_id = current_user.id


    if request.method == 'POST':
        train_id = request.form.get('train_id')

        # user_id = request.form.get('user_id')
    if request.method == 'GET':
        train_id = request.args.get('train_id')

    # нужно найти user-train-exercise
    user_training = UserTraining.query.filter_by(user_id=user_id, training_id=train_id, assigned=True, completed=False).first()

    user_training_exercises = UserTrainingExercise.query.filter_by(user_training_id=user_training.id).all()

    user_training_exercise = UserTrainingExercise.query.filter_by(user_training_id=user_training.id, completed=False).first()

    workout_started = UserTrainingExercise.query.filter_by(user_training_id=user_training.id, completed=True).first()
    if not workout_started:
        start_time = datetime.utcnow()
        user_training.date_started = start_time
        try:
            db.session.commit()
        except:
            db.session.rollback()
            local_flash('Base_error')
            return redirect(url_for('current_train'))

    position = user_training_exercises.index(user_training_exercise)
    ex_count = len(user_training_exercises)
    progress_percent = round(position/ex_count*100)

    exercise = Exercise.query.get(user_training_exercise.exercise_id)
    previous_weight = find_prev_weight(exercise.exercise_id, user_id)
    max_weight = find_max_weight(exercise.exercise_id, user_id)

    ex_loc_names = json.loads(exercise.localized_name)
    ex_loc_name = ex_loc_names[current_user.language]



    return render_template('current_exercise.html', exercise=exercise, previous_weight=previous_weight,
                           user_training=user_training, user_training_exercise=user_training_exercise,
                           max_weight=max_weight, progress_percent=progress_percent, ex_loc_name=ex_loc_name)


@app.route('/train_progress_next', methods=['POST', 'GET'])
@login_required
def train_progress_next():
    if request.method == 'POST':
        user_training_exercise_id = request.form.get('user_training_exercise_id')
        user_training_id = request.form.get('user_training_id')

    if request.method == 'GET':
        user_training_exercise_id = request.args.get('user_training_exercise_id')
        user_training_id = request.args.get('user_training_id')

    weight = request.form.get('weight', 0)
    try:
        weight = int(weight)
    except:
        weight = 0
    user_training_exercise = UserTrainingExercise.query.get(user_training_exercise_id)
    user_training_exercise.completed = True
    user_training_exercise.weight = weight

    try:
        db.session.commit()
    except:
        db.session.rollback()
        local_flash('Base_error')
        return redirect(url_for('index'))

    user_training = UserTraining.query.get(user_training_id)
    train_id = user_training.training_id
    user_id = user_training.user_id

    user_training_exercises = UserTrainingExercise.query.filter_by(user_training_id=user_training_id, completed=False, skipped=False).first()
    if not user_training_exercises:

        set_train_complete(user_id, train_id)
        user_training_exercises = UserTrainingExercise.query.filter_by(user_training_id=user_training_id).all()
        finish_data = []
        for ute in user_training_exercises:
            ex = Exercise.query.get(ute.exercise_id) # для ссылки на статистику упражнений
            ex_id = ex.exercise_id
            loc_ex_names = json.loads(ex.localized_name)
            ex_name = loc_ex_names[current_user.language]
            ex_skipped = ute.skipped
            weight = ute.weight
            finish_data.append({'ex_id':ex_id, 'ex_name':ex_name, 'ex_skipped':ex_skipped, 'weight':weight})

        return redirect(url_for('statistic_details', user_training_id=user_training.id))
        # return render_template('training_finished.html', finish_data=finish_data, train_note='', user_training_id=user_training_id)




    return redirect(url_for('train_progress_start', _external=True, train_id=train_id))


@app.route('/train_progress_skip', methods=['POST', 'GET'])
@login_required
def train_progress_skip():

    if request.method == 'POST':
        user_training_exercise_id = request.form.get('user_training_exercise_id')
        user_training_id = request.form.get('user_training_id')
        user_training_exercise = UserTrainingExercise.query.get(user_training_exercise_id)
        user_training_exercise.skipped = True

        try:
            db.session.commit()
        except:
            db.session.rollback()
            local_flash('Base_error')
            return redirect(url_for('index'))



    return redirect(url_for('train_progress_next', user_training_exercise_id=user_training_exercise_id,
                            user_training_id=user_training_id))


@app.route('/note_save', methods=['POST', 'GET'])
@login_required
def note_save():
    user_training_id = request.form.get('user_training_id')
    train_note = request.form.get('train_note')
    user_training = UserTraining.query.get(user_training_id)
    user_training.train_note = train_note

    try:
        db.session.commit()
    except:
        db.session.rollback()
        local_flash('Base_error')
        # 'Не удалось сохранить заметку в базу '


    return redirect(url_for('statistic_details', user_training_id=user_training_id))


@app.route('/statistics')
@login_required
def statistics():

    u_utr = UserTraining.query.filter_by(user_id=current_user.id, assigned=True, completed=False).all()
    c_utr = UserTraining.query.filter_by(user_id=current_user.id, assigned=True, completed=True).all()

    uncompleted_trainings = []
    for u_tr in u_utr:
        train = Training.query.get(u_tr.training_id)
        if train:
            local_names = json.loads(train.local_names)
            local_name = local_names[current_user.language]
            uncompleted_trainings.append([train, u_tr.id, local_name])

    completed_trainings = []
    for c_tr in c_utr:
        train = Training.query.get(c_tr.training_id)
        if train:
            local_names = json.loads(train.local_names)
            local_name = local_names[current_user.language]
            # Training, UserTraining.id, количество упражнений, дата завершения
            ex_count=len(train.exercises)
            formatted_datetime = c_tr.date_completed.strftime("%d-%m-%Y %H:%M")
            completed_trainings.append([train, c_tr.id, ex_count, formatted_datetime, local_name])
    completed_trainings.reverse()

    return render_template('statistics.html', uncompleted_trainings=uncompleted_trainings, completed_trainings=completed_trainings,
                           user=current_user)


@app.route('/statistics/delete/<int:user_training_id>')
@login_required
def statistic_delete(user_training_id):

    user_training = UserTraining.query.get(user_training_id)
    if user_training.user_id != current_user.id:
        return redirect(url_for('index'))

    user_training_exercices = UserTrainingExercise.query.filter_by(user_training_id=user_training.id).all()

    for user_training_exercice in user_training_exercices:
        db.session.delete(user_training_exercice)

    db.session.delete(user_training)

    try:
        db.session.commit()
    except:
        db.session.rollback()
        local_flash('Base_error')
        # 'Ошибка: не удалось удалить тренировку'

    return redirect('/statistics')


@app.route('/statistics/details/<int:user_training_id>')
@login_required
def statistic_details(user_training_id):
    user_training = UserTraining.query.get(user_training_id)
    if user_training.user_id != current_user.id:
        local_flash('Base_error')
        return redirect(url_for('index'))
    dict = {}
    unformatteds = Localization.query.all()
    for unformatted in unformatteds:
        key = unformatted.key
        translations = json.loads(unformatted.translations)
        dict[key] = translations[current_user.language]

    train_note = user_training.train_note
    unformatted_start_time = user_training.date_started
    start_time = unformatted_start_time.strftime('%d-%m-%y %H:%M')

    unformatted_finish_time = user_training.date_completed
    finish_time = unformatted_finish_time.strftime('%d-%m-%y %H:%M')

    delta = unformatted_finish_time-unformatted_start_time
    seconds = delta.seconds
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)


    workout_duration = f'{hours} {dict["hours"]}. {minutes} {dict["minutes"]}. {seconds} {dict["seconds"]}.'

    user_training_exercises = UserTrainingExercise.query.filter_by(user_training_id=user_training_id).all()

    finish_data = []
    for ute in user_training_exercises:
        ex = Exercise.query.get(ute.exercise_id)  # для ссылки на статистику упражнений
        ex_id = ex.exercise_id
        loc_ex_names = json.loads(ex.localized_name)
        ex_name = loc_ex_names[current_user.language]
        ex_skipped = ute.skipped
        weight = ute.weight
        finish_data.append({'ex_id': ex_id, 'ex_name': ex_name, 'ex_skipped': ex_skipped, 'weight': weight})

    return render_template('training_finished.html', finish_data=finish_data, train_note=train_note, user_training_id=user_training_id,
                           start_time=start_time, finish_time=finish_time, workout_duration=workout_duration)


@app.route('/statistics/exercises', methods=['POST', 'GET'])
@login_required
def statistics_exercises():
    no_weight_targets = config.NO_WEIGHT_TARGETS
    if request.method == 'POST':

        user_id = request.form.get('user_id')
        trains_count = request.form.get('trains_count')
        include_noweights = True
        exercises_struct = get_exercise_statistics(user_id)
        # [[55, 'Разогрев+ разминка (10 минут)', 4, 1, [{'date': '28-08-2023 10:03:04', 'weight': 0, 'skipped': False},


    return render_template('statistics_exercises.html', exercises_struct=exercises_struct, user_id=user_id, trains_count=trains_count, no_weight_targets=no_weight_targets)


# ---------------------------------------ACCOUNT -------------------------------------------------------------

@app.route('/personal')
@login_required
def personal():
    account_types = config.ACCOUNT_TYPES
    languages = config.LANGUAGES
    if not current_user:
        return render_template('management.html')
    user_account_type = account_types[current_user.role]
    preferences = json.loads(current_user.preferences)

    account_color = config.ACCOUNT_COLORS[current_user.role]
    return render_template('personal.html', user=current_user, user_account_type=user_account_type,
                           account_color=account_color, languages=languages, preferences=preferences)


@app.route('/change_password', methods=['POST', 'GET'])
@login_required
def change_password():

    if request.method == 'POST':
        password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        repeat_new_password = request.form.get('repeat_new_password')

        hashed_password = generate_password_hash(password)

        if check_password_hash(current_user.password, password):
            if new_password == repeat_new_password:
                hashed_password = generate_password_hash(new_password)
                current_user.password = hashed_password
                try:
                    db.session.commit()
                    # flash('Пароль успешно изменен!')
                    local_flash('Password_changed')
                except:
                    db.session.rollback()
                    flash('Не удалось изменить пароль')
            else:
                # flash('Новый пароль - поля не совпадают')
                local_flash('Password_different_fields')
        else:
            # flash('Неверный пароль')
            local_flash('wrong_password')


    return redirect(url_for('personal'))


@app.route('/language_change/<string:lng>')
@login_required
def language_change(lng):
    current_user.language = lng
    try:
        db.session.commit()
    except:
        db.session.rollback()
        local_flash('Base_error')
         # 'Ошибка при смене языка'
    return redirect(url_for('personal'))


@app.route('/follow_change_status', methods = ['POST'])
@login_required
def follow_change_status():
    preferences = json.loads(current_user.preferences)
    if preferences['follow']:
        preferences['follow'] = False
    else:
        preferences['follow'] = True

    prefs_save = json.dumps(preferences)
    current_user.preferences = prefs_save
    try:
        db.session.commit()
    except:
        db.session.rollback()
        return redirect(url_for('personal'))

    return 'True'


@app.route('/restore_account', methods=['POST', 'GET'])
def restore_account():
    default_language = session.get('default_language', 'EN')
    if request.method == 'POST':
        restore_email = request.form.get('restore_email')
        if not is_valid_email(restore_email):
            # flash('Электронная почта введена некорректно')
            local_flash('invalid_email')
        else:
            # flash('Сообщение с восстановлением выслано')
            local_flash('recovery_mail_sended')
            user = User.query.filter_by(email=restore_email).first()
            if user:
                new_password = generate_random_password(8)
                hashed_password = generate_password_hash(new_password)
                user.password = hashed_password
                try:
                    db.session.commit()
                except:
                    # flash('Произошла ошибка при восстановлении пароля')
                    local_flash('Base_error')
                send_email(restore_email, new_password, user.name)
            return redirect('user_login')

    return render_template('/modals/restore_account.html', default_language=default_language)


@app.route('/management')
@login_required
def management():

    if not current_user:
        return render_template('management.html')


    return render_template('management.html', user=current_user)


@app.route('/ajax_plan_training_view', methods=['POST', 'GET'])
@login_required
def ajax_plan_training_view():

    data = request.get_json()

    train_id = data.get('train_id')
    train = Training.query.get(train_id)
    exercises = train.exercises
    response = []

    for exercise in exercises:
        training_exercises = TrainingExercise.query.filter_by(training_id=train_id, exercise_id=exercise.exercise_id).first()
        exercise_loc_names = json.loads(exercise.localized_name)
        exercise_loc_name = exercise_loc_names[current_user.language]
        response.append([exercise_loc_name, training_exercises.sets, training_exercises.repetitions])

    return render_template('/divs/plan_trainings_div.html', response=response)


@app.route('/account')
@login_required
def account():

    return render_template('account.html')


# --------------------------LOCALIZATION--------------------------------------------
@app.route('/localization', methods=['POST', 'GET'])
@login_required
def localization():
    languages = config.LANGUAGES
    sectors = config.SECTORS
    phrase_dict = {}
    sector = 'Application'
    phrases = Localization.query.all()
    phrases_list = []
    for phrase in phrases:
        translations_dict = json.loads(phrase.translations)
        phrases_list.append([phrase.key, translations_dict])

    if request.method == 'GET':
        phrase_key = request.args.get('key', '')

        phrase_obj = Localization.query.filter_by(key=phrase_key).first()
        if phrase_obj:
            phrase_dict = json.loads(phrase_obj.translations)
            sector = phrase_obj.sector

    if request.method == 'POST':
        phrase_key = request.form.get('key', '')
        sector = request.form.get('sector', '')


        for lang in languages:
            phrase_dict[lang] = request.form.get('local_input_'+lang, '')


        phrase = Localization.query.filter_by(key=phrase_key).first()
        if phrase:
            phrase.translations = json.dumps(phrase_dict)
            phrase.sector = sector
        else:
            localized_phrase = Localization(key=phrase_key, translations=json.dumps(phrase_dict), sector=sector)
            db.session.add(localized_phrase)
            phrases_list.append([phrase_key, phrase_dict])
        try:
            db.session.commit()
        except:
            db.session.rollback()
            local_flash('Base_error')

    return render_template('localization.html', languages=languages, phrases_list=phrases_list, phrase_dict=phrase_dict,
                               phrase_key=phrase_key, sectors=sectors, sector=sector)


@app.route('/localization_load_phrase/<string:key>')
@login_required
def localization_load_phrase(key):

    return redirect(url_for('localization', key=key))


@app.route('/instructions')
def instructions():
    languages = config.LANGUAGES
    default_language = 'EN'
    browser_lang = request.headers.get('Accept-Language', 'EN')
    user_admin = User.query.filter_by(name='admin').first()
    user_prefs = json.loads(user_admin.preferences)
    youtube_link = user_prefs['youtube_link']

    langs = browser_lang.split(';')
    for lang in langs:
        for defined_lang in languages:
            if defined_lang.lower() in lang:
                default_language = defined_lang
                break
        else:
            continue
        break

    return render_template('instructions.html', default_language=default_language, youtube_link=youtube_link)

# ------------------------------------------------ADMIN-------------------------------------

@app.route('/users_administration')
def users_administration():

    users = User.query.all()
    users_count = len(users)

    account_types = config.ACCOUNT_TYPES

    account_colors = config.ACCOUNT_COLORS
    sorted_users = sorted(users, key=lambda user: user.date_registration, reverse=True)

    structured_users = {}

    for user in sorted_users:
        structured_user = {}

        user_prefs = json.loads(user.preferences)
        local_time_offset = user_prefs.get('LTO', 0)
        structured_user['id'] = user.id
        structured_user['name'] = user.name
        structured_user['email'] = user.email
        structured_user['role'] = user.role
        structured_user['language'] = user.language
        structured_user['date_registration'] = user.date_registration.strftime('%d-%m-%y %H:%M')
        structured_user['date_last_activity'] = user.date_last_activity.strftime('%d-%m-%y %H:%M')
        structured_user['local_time_offset'] = local_time_offset

        date_registration_short = user.date_registration.strftime('%d-%m-%y')

        try:
            structured_users[date_registration_short].append(structured_user)
        except:
            structured_users[date_registration_short] = []
            structured_users[date_registration_short].append(structured_user)



    return render_template('users.html', structured_users=structured_users, users_count=users_count,
                           account_types=account_types, account_colors=account_colors)


@app.route('/user_details/<int:user_id>')
def user_details(user_id):

    user = User.query.get(user_id)
    prefs = json.loads(user.preferences)

    user_trainings = UserTraining.query.filter_by(user_id=user.id).all()
    user_trainings_ids = [user_training.training_id for user_training in user_trainings]
    trainings = Training.query.filter(Training.training_id.in_(user_trainings_ids)).all()

    trainings_dict = {train.training_id: train.name for train in trainings}

    user_trainings_list = []
    for user_training in user_trainings:
        user_trainings_list.append({'name':trainings_dict[user_training.training_id], 'complete': user_training.completed,
                                    'date_complete': user_training.date_completed.strftime('%d-%m-%y %H:%M') if user_training.date_completed is not None else 'x'})

    sorted_user_trainings = sorted(user_trainings_list, key=lambda ut: ut['date_complete'], reverse=True)

    print(sorted_user_trainings)

    return render_template('user_details.html', user=user, prefs=prefs, sorted_user_trainings=sorted_user_trainings)

# -------------------------------------------------------------------------------------
if __name__ == '__main__':

    # with app.app_context():
        # local_dict = load_localization_dict()

    #     try:
    #         db.create_all()
    #     except Exception as e:
    #         print(e)
    app.run(host='0.0.0.0', debug=True)