
from flask import Flask, render_template, url_for, request, redirect, session, flash, jsonify, Response, Blueprint, send_file
from flask_jwt_extended import get_jwt_identity
from flask_login import current_user, login_required, login_user

from sqlalchemy import Column, Integer, String, ForeignKey, and_, or_
import json
from _models import Exercise, Muscle, ExerciseMuscle, db, User, Plan, TrainingExercise, \
    Training, UserTraining, UserTrainingExercise, Plan_Trainings, Localization
import config
# from _logic import *


from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, unset_jwt_cookies

api = Blueprint('api', __name__)

# ------------------------------------------LOGIN/LOGOUT------------------------------------
def get_user_from_token():
    username = get_jwt_identity()
    user = User.query.filter_by(name=username).first()
    return user

@api.route('/login', methods=['POST'])
def API_login():
    from _logic import get_pref_lang
    languages = config.LANGUAGES
    default_language = get_pref_lang()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(name=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            access_token = create_access_token(identity=username)
            response = {
                'access_token': access_token,
                'logged': True,
                'default_language': default_language,
                'user': {
                    'name': current_user.name,
                    'role': current_user.role,
                    'language': current_user.language,
                    'preferences': current_user.preferences,
                    'date_registration': current_user.date_registration,
                },
            }
            return jsonify(response)

    return jsonify({'logged': False})


@api.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # print('LOGOUT')
    response = jsonify({'msg': 'Logout successful'})
    unset_jwt_cookies(response)
    return response


@api.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200

# -----------------------------------PLANS ---------------------------------------------------------------
@api.route('/plans', methods=['GET'])
@jwt_required()
def api_get_plans():

    current_user = get_user_from_token()
    languages = config.LANGUAGES

    conditions = or_(Plan.owner == current_user.name, Plan.owner == 'admin')
    plans = Plan.query.filter(conditions).all()
    plan_ids = [plan.id for plan in plans]

    plan_trainings = Plan_Trainings.query.filter(Plan_Trainings.plan_id.in_(plan_ids)).all()
    trainings_ids = [plan_training.training_id for plan_training in plan_trainings]
    trains = Training.query.filter(Training.training_id.in_(trainings_ids)).all()

    trainings_in_plan = {}  # {plan: [trains], ...}
    plans_local_names = {} # {plan: local_name}
    json_trainings_in_plan = []

    plan_local_name = {}
    for plan in plans:
        if plan.local_names:
            json_names = json.loads(plan.local_names)
            plan_local_name[plan.id] = json_names.get(current_user.language, plan.name)
        else:
            plan_local_name[plan.id] = plan.name

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

                    trainings_in_plan[plan].append({
                        'train_local_name':train_local_name,
                        'train_time':train_time,
                        'ex_loc_names_user_lang':ex_loc_names_user_lang})

    for plan in plans:
        tip = trainings_in_plan[plan]
        if plan.owner != current_user.name:
            owner = User.query.filter_by(name=plan.owner).first()
            user_img_id = owner.id
        else:
            user_img_id = current_user.id
        img_url = f'{user_img_id}-{plan.img}'
        json_trainings_in_plan.append(({'plan_id':plan.id, 'img': img_url, 'plan_name':plan.name, 'plan_owner':plan.owner, 'plan_local_name':plan_local_name[plan.id], 'tip':tip}))

    response = Response(json.dumps(json_trainings_in_plan, ensure_ascii=False))
    response.mimetype = 'application/json; charset=utf-8'
    return response


@api.route('/get_plan/<plan_id>', methods=['GET'])
def api_get_plan(plan_id):
    print(f'PLAN REQUEST id={plan_id}')
    plan_dict = {}
    plan = Plan.query.get(plan_id)
    # print(plan)
    plan_trainings = Plan_Trainings.query.filter(Plan_Trainings.plan_id == plan_id).all()
    workouts_count = len(plan_trainings)

    plan_owner = User.query.filter_by(name=plan.owner).first()
    plan_owner_id = plan_owner.id
    plan_dict['plan_id'] = plan_id
    plan_dict['plan_name'] = plan.name
    plan_dict['plan_owner'] = plan.owner
    plan_dict['plan_owner_id'] = plan_owner_id
    plan_dict['plan_img'] = plan.img
    plan_dict['workouts_count'] = workouts_count
    plan_dict['workouts'] = []


    for plan_training in plan_trainings:
        training_id = plan_training.training_id
        train = Training.query.get(training_id)
        train_exercises = TrainingExercise.query.filter_by(training_id=training_id).all()

        workout_duration = 0
        for train_exercise in train_exercises:
            exercise = Exercise.query.get(train_exercise.exercise_id)
            workout_duration += exercise.time_per_set*3

        plan_dict['workouts'].append({  'PT_id': plan_training.id,
                                        'workout_id': training_id,
                                        'workout_name': train.name,
                                        'exercises_count': len(train_exercises),
                                        'workout_duration': workout_duration
                                      })

    # print(json.dumps(plan_dict, ensure_ascii=False, indent=4))
    response = Response(json.dumps(plan_dict, ensure_ascii=False))
    response.mimetype = 'application/json; charset=utf-8'
    return response

# ----------------------------------WORKOUTS -----------------------------------------------------------

@api.route('/get_workouts', methods = ['GET'])
@jwt_required()
def api_get_workouts():
    # print('WORKOUTS GET Request')
    workouts = []
    local_names_dict = {}
    current_user = get_user_from_token()
    user_language = current_user.language

    conditions = or_(Training.owner == 'admin', Training.owner == current_user.name)

    AllWorkouts = Training.query.filter(conditions).all()
    response_data = []

    for workout in AllWorkouts:

        local_names = workout.local_names
        # print(local_names)
        if local_names:
            local_names_dict = json.loads(local_names)
            local_name = local_names_dict.get(current_user.language, workout.name)
        else:
            local_name = workout.name

        training_exercises = TrainingExercise.query.filter_by(training_id=workout.training_id).all()
        workout_duration = 0
        for train_exercise in training_exercises:
            exercise = Exercise.query.get(train_exercise.exercise_id)
            workout_duration += exercise.time_per_set * 3
        exercises_count = len(training_exercises)
        # print(f'training_id = {workout.training_id}\nname={local_name}\nowner={workout.owner}')
        response_data.append({'id': workout.training_id,
                              'name': local_name,
                              'owner': workout.owner,
                              'exercises_count': exercises_count,
                              'duration': workout_duration
                              })
        # print(f'id:{workout.training_id}\nname:{local_name}\nowner:{workout.owner}/n')
    response = Response(json.dumps(response_data))
    response.mimetype = 'application/json; charset=utf-8'
    return response


@api.route('/plan_add', methods = ['POST'])
@jwt_required()
def api_plan_add():
    current_user = get_user_from_token()
    user_language = current_user.language

    plan_id = request.form['plan_id']
    workout_id = request.form['workout_id']
    # print(f'Recieved POST: plan_id={plan_id}, workout_id={workout_id}')
    plan = Plan.query.get(plan_id)

    # тут проверка на овнера

    PT = Plan_Trainings(plan_id=plan_id, training_id=workout_id)
    try:
        db.session.add(PT)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'fail'})


    response = jsonify({'status': 'OK'})
    return response


@api.route('/plan_del_wk', methods = ['POST'])
@jwt_required()
def api_plan_del_wk():
    PT_id = request.form['PT_id']
    PT = Plan_Trainings.query.get(PT_id)
    try:
        db.session.delete(PT)
        db.session.commit()
    except:
        db.session.rollback()
        return jsonify({'status': 'fail'})
    print(f'Del request PT_id={PT_id}')
    return jsonify({'status': 'OK'})

# -----------------------------------UTILS---------------------------------------------------------------
@api.route('/get_img/<id_name>')
def api_get_img(id_name):
    try:
        id = id_name.split("-", 1)[0]
        img = id_name.split("-", 1)[1]
        url = f'./static/users/{id}/{img}'
        return send_file(url, mimetype='image/png')
    except Exception as e:
        return 'not found'


