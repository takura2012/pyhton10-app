from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.schema import ForeignKeyConstraint
from datetime import datetime
from flask_login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash

db = SQLAlchemy()


class Exercise(db.Model):
    __tablename__ = 'exercises'

    exercise_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), default='New exercise')
    localized_name = db.Column(db.Text)
    target = db.Column(db.String(20), default='')
    description = db.Column(db.String(300), default='')
    localized_description = db.Column(db.Text)
    difficulty = db.Column(db.Integer, default=1)
    time_per_set = db.Column(db.Integer, default=1)
    counter = db.Column(db.Integer, default=0)
    filters = db.Column(JSON, default=[])  # LOCATION_FILTERS.keys

    user_training_exercises = relationship('UserTrainingExercise', back_populates='exercise')
    muscles = relationship('Muscle', secondary='exercise_muscles')
    training = db.relationship('Training', secondary='training_exercises', overlaps="exercises")
    training_exercises = relationship('TrainingExercise', back_populates='exercise')

    def __repr__(self):
        return 'Exercise %r' % self.exercise_id

    @classmethod
    def update_counters(cls):
        exercises = cls.query.all()  # Получаем все записи класса Exercise из базы данных
        for counter, exercise in enumerate(exercises, start=1):
            exercise.counter = counter
        try:
            db.session.commit()  # Сохраняем изменения в базе данных
        except Exception as e:
            db.session.rollback()  # Откатываем изменения в случае возникновения ошибки
            raise e


class Muscle(db.Model):
    __tablename__ = 'muscles'

    muscle_id = db.Column(db.Integer, primary_key=True)
    muscle_name = db.Column(db.String(50), nullable=False)
    counter = db.Column(db.Integer, default=0)

    exercises = db.relationship('Exercise', secondary='exercise_muscles', overlaps="muscles")

    def __repr__(self):
        return 'Muscle %r' % self.muscle_id

    @classmethod
    def update_counters(cls):
        muscles = cls.query.all()  # Получаем все записи класса Muscle из базы данных
        for counter, muscle in enumerate(muscles, start=1):
            muscle.counter = counter
        try:
            db.session.commit()  # Сохраняем изменения в базе данных
        except Exception as e:
            db.session.rollback()  # Откатываем изменения в случае возникновения ошибки
            raise e


class ExerciseMuscle(db.Model):
    __tablename__ = 'exercise_muscles'

    exercise_id = Column(Integer, ForeignKey('exercises.exercise_id', ondelete='CASCADE'), primary_key=True)
    muscle_id = Column(Integer, ForeignKey('muscles.muscle_id', ondelete='CASCADE'), primary_key=True)
    percent = Column(Integer, default=0)


class Training(db.Model):
    __tablename__ = 'trainings'

    training_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    local_names = db.Column(db.Text)
    owner = db.Column(db.String(80), default='admin')

    exercises = relationship('Exercise', secondary='training_exercises', overlaps="trainings")
    user_trainings = relationship('UserTraining', back_populates='training', cascade='all, delete-orphan')
    plans = relationship('Plan', secondary='plan_trainings', back_populates='trainings')

    def __repr__(self):
        return 'Training %r' % self.training_id


class TrainingExercise(db.Model):
    __tablename__ = 'training_exercises'

    id = db.Column(db.Integer, primary_key=True)
    training_id = db.Column(db.Integer, db.ForeignKey('trainings.training_id', ondelete='CASCADE'))
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.exercise_id', ondelete='CASCADE'))
    sets = db.Column(db.Integer)
    repetitions = db.Column(db.Integer)
    exercise = relationship('Exercise', back_populates='training_exercises')


class Plan(db.Model):
    __tablename__ = 'plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, default='New Plan')
    local_names = db.Column(db.Text)
    owner = db.Column(db.String, default='Admin')

    trainings = relationship('Training', secondary='plan_trainings', back_populates='plans')


class Plan_Trainings(db.Model):
    __tablename__ = 'plan_trainings'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id', ondelete='CASCADE'))
    training_id = db.Column(db.Integer,db.ForeignKey('trainings.training_id', ondelete='CASCADE'))


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(80), nullable=False, default='user')
    email = db.Column(db.String(80), unique=True, nullable=False)
    language = db.Column(db.String(20), default='EN')
    preferences = db.Column(db.Text, default=[])
    date_registration = Column(db.DateTime)
    date_last_activity = Column(db.DateTime)

    trainings = relationship('UserTraining', back_populates='user')

    def __repr__(self):
        return f'User: {self.name} '


class UserTraining(db.Model):
    __tablename__ = 'user_trainings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    training_id = Column(Integer, ForeignKey('trainings.training_id'))
    assigned = Column(db.Boolean, default=False)
    completed = Column(db.Boolean, default=False)
    date_started = Column(db.DateTime)
    date_completed = Column(db.DateTime)
    train_note = Column(db.String, default='')

    user = relationship('User', back_populates='trainings')
    training = relationship('Training', back_populates='user_trainings')
    training_exercises = relationship('UserTrainingExercise', back_populates='user_training')


class UserTrainingExercise(db.Model):
    __tablename__ = 'user_training_exercises'
    id = Column(Integer, primary_key=True)
    user_training_id = Column(Integer, ForeignKey('user_trainings.id', ondelete='CASCADE'))
    exercise_id = Column(Integer, ForeignKey('exercises.exercise_id', ondelete='CASCADE'))
    sets = Column(Integer)
    repetitions = Column(Integer)
    weight = Column(Integer)
    completed = Column(db.Boolean, default=False)
    skipped = Column(db.Boolean, default=False)

    user_training = relationship('UserTraining', back_populates='training_exercises')
    exercise = relationship('Exercise', back_populates='user_training_exercises')


class Localization(db.Model):
    __tablename__ = 'localization'
    id = Column(Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True)
    sector = db.Column(db.String(50))
    translations = Column(db.Text)

    def __repr__(self):
        return f'Translation: {self.id}'


if __name__ == '__main__':
    # Запуск приложения Flask (только для тестирования)
    pass
