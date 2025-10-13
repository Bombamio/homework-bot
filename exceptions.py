HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_is_dict(response):
    """Проверяет, что ответ API — это словарь."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём.')


def check_required_keys(response):
    """Проверяет наличие и тип обязательных ключей в ответе API."""
    required_keys = (
        ('current_date', int),
        ('homeworks', list),
    )
    for key, expected_type in required_keys:
        if key not in response:
            raise KeyError(f'В ответе отсутствует обязательное поле "{key}".')
        if not isinstance(response[key], expected_type):
            raise TypeError(f'Поле "{key}" имеет неверный тип данных.')


def check_homework_structure(homework):
    """Проверяет корректность структуры отдельного объекта домашки."""
    if not isinstance(homework, dict):
        raise TypeError('Каждый элемент в homeworks должен быть словарём.')

    for key in ('homework_name', 'status'):
        if key not in homework:
            raise KeyError(f'В объекте homework отсутствует ключ "{key}".')
        if not isinstance(homework[key], str):
            raise TypeError(f'Элемент "{key}" имеет неверный тип данных.')

    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Недопустимый статус: {status}')
