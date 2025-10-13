import logging
import os
import time

import requests
from telebot import TeleBot
from dotenv import load_dotenv


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing = [name for name, value in tokens.items() if not value]
    if missing:
        logging.critical(
            'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing)}'
        )
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-бот."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f'{message}')
        logging.debug(f'Сообщение отправлено: {message}')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != 200:
            raise ConnectionError(
                f'Ошибка запроса к API: {response.status_code}, '
                f'{response.text}'
            )
        return response.json()
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка при запросе к API: {error}.')


def check_response(response):
    """Проверяет корректность структуры ответа API."""
    # 1. Проверка, что ответ — это словарь.
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём.')

    # 2. Проверка обязательных ключей и их типов данных.
    required_keys = (
        ('current_date', int),
        ('homeworks', list)
    )
    for key, expected_type in required_keys:
        if key not in response:
            raise KeyError(f'В ответе отсутствует обязательное поле "{key}".')
        if not isinstance(response[key], expected_type):
            raise TypeError(f'Поле "{key}" имеет неверный тип данных.')

    # 3. Проверка структуры нужных элементов в homeworks.
    for homework in response['homeworks']:
        if not isinstance(homework, dict):
            raise TypeError('Каждый элемент в homeworks должен быть словарём.')

        for key in ('homework_name', 'status'):
            if key not in homework:
                raise KeyError(f'В объекте homework отсутствует ключ "{key}".')
            if not isinstance(homework[key], str):
                raise TypeError(f'Элемента "{key}" имеет неверный тип данных.')

        # 4. Проверка допустимых значений статуса.
        if homework['status'] not in HOMEWORK_VERDICTS:
            raise ValueError(f'Недопустимый статус: {homework['status']}')

    return True


def parse_status(homework):
    """Формирует сообщение о статусе домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе API отсутствует ключ "homework_name".')
    if 'status' not in homework:
        raise KeyError('В ответе API отсутствует ключ "status".')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Недокументированный статус домашней работы: {status}')

    verdict = HOMEWORK_VERDICTS.get(status)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(levelname)s, %(message)s',
        handlers=[logging.StreamHandler()]
    )

    if not check_tokens():
        raise SystemExit('Отсутствуют обязательные переменные окружения!')

    # Создаем объект класса бота
    bot = TeleBot(token=f'{TELEGRAM_TOKEN}')
    timestamp = int(time.time())
    last_message = ''

    logging.info('Бот запущен и готов к работе.')

    # Осноной цикл программы.
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)

            homeworks = response.get('homeworks', [])
            if homeworks:
                message = parse_status(homeworks[0])
                if message != last_message:
                    send_message(bot, message)
                    last_message = message
                else:
                    logging.debug('Новых статусов нет.')
            else:
                logging.debug('Нет новых домашних работ.')

            timestamp = response.get('current_date', timestamp)
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_message:
                send_message(bot, message)
                last_message = message
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
