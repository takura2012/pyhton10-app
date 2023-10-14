DEBUG = True
SQLALCHEMY_DATABASE_URI = 'sqlite:///fitness.db'
SESSION_TYPE = 'filesystem'
RESERVED_NAMES = ['admin', 'админ', 'old_training']

ACCOUNT_TYPES_EN = {
    'user': 'Standart account',
    'paid_user': 'Paid account',
    'premium': 'Premium account',
    'admin': 'admin'
}

ACCOUNT_COLORS = {
    'user': '#202050',
    'paid_user': '#32CD32',
    'premium': '#4169E1',
    'admin': '#DC143C'
}

ACCOUNT_TYPES_RU = {
    'user': 'Registered',
    'paid_user': 'Paid',
    'premium': 'Premium',
    'admin': 'Administrator'
}

TRAINING_LEVELS = {
    '1': 'Не занимался ранее',
    '2': 'Легкие тренировки/восстановление',
    '3': 'Регулярные средние тренировки',
    '4': 'Регулярные силовые тренировки'
                   }

BMI = {
    16: 'Выраженный дефицит массы тела',
    19: 'Недостаточная (дефицит) масса тела',
    25: 'Норма',
    30: 'Избыточная масса тела (предожирение)',
    35: 'Ожирение 1 степени',
    40: 'Ожирение 2 степени',
    100: 'Ожирение 3 степени'
}

TARGETS = ['Разминка', 'Пресс', 'Ноги', 'Спина', 'Грудь', 'Ягодицы', 'Бицепс', 'Трицепс', 'Плечи', 'Кардио']

LOC_TARGETS = {
    'EN': ['All', 'Stretching', 'Abs', 'Legs', 'Back', 'Chest', 'Hips', 'Biceps', 'Triceps', 'Shoulders', 'Cardio'],
    'RU': ['Все', 'Разминка', 'Пресс', 'Ноги', 'Спина', 'Грудь', 'Ягодицы', 'Бицепс', 'Трицепс', 'Плечи', 'Кардио'],
    'UA': ['Всі', 'Розминка', 'Прес', 'Ноги', 'Спина', 'Груди', 'Сідниці', 'Біцепс', 'Трицепс', 'Плечі', 'Кардіо'],
    'PL': ['Wszystko', 'Rozgrzewka', 'Brzuch', 'Nogi', 'Plecy', 'Klatka piersiowa', 'Pośladki', 'Biceps', 'Triceps', 'Ramiona', 'Kardio']
}


NO_WEIGHT_TARGETS = ['Разминка', 'Пресс', 'Кардио']

FILTERS_LOCATION = {
    '1': 'In_the_gym',
    '2': 'At_home',
    '3': 'Sports_field'
            }

FILTERS_SEX = {
    '4': 'For_men',
    '5': 'For_women'
}

FILTERS_INVENTORY = {
    '6': 'Without_equipment',
    '7': 'With_equipment'
}

FILTERS_TYPE = {
    '8': 'Strength_training',
    '9': 'Warm-up',
    '10': 'Cardio'
}

FILTERS_LEVEL = {
    '11': 'For_beginners'
}

FILTER_TARGETS = ['Все']+TARGETS

FILTER_LIST = [FILTERS_LOCATION, FILTERS_SEX, FILTERS_INVENTORY, FILTERS_TYPE, FILTERS_LEVEL]

LANGUAGES = ['EN', 'RU', 'UA', 'PL']
SECTORS = ['Application', 'Exercises', 'Trainings', 'Plans', 'Modals']