from _models import Plan, Training


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

