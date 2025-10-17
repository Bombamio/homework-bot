import logging
import os
import sys
import time
from contextlib import suppress
from functools import wraps
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot, apihelper

from exceptions import InvalidResponseError


def avoid_duplicates(func):
    """Декоратор, предотвращающий отправку повторяющихся сообщений."""
    last_message = None

    @wraps(func)
    def wrapper(bot, message):
        nonlocal last_message
        if message == last_message:
            logging.debug(
                'Сообщение идентично предыдущему, отправка пропущена.'
            )
            return
        func(bot, message)
        last_message = message

    return wrapper


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
        error_message = 'Отсутствуют обязательные переменные окружения: '
        f'{", ".join(missing)}'
        logging.critical(error_message)
        raise SystemExit(error_message)


@avoid_duplicates
def send_message(bot, message):
    """Отправляет сообщение в Telegram-бот."""
    logging.debug('Начало отправки сообщения...')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f'{message}')
    logging.debug(f'Сообщение отправлено: {message}')


def get_api_answer(timestamp):
    """Делает запрос к API."""
    payload = {'from_date': timestamp}
    logging.debug(
        f'Отправка запроса к API: {ENDPOINT}, '
        f'параметры: {payload}'
    )
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)

    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка при запросе к API: {error}.')

    if response.status_code != HTTPStatus.OK:
        raise InvalidResponseError(
            f'Ошибка запроса к API: {response.status_code}, '
            f'{response.text}'
        )
    logging.debug('Успешно получен ответ от API.')
    return response.json()


def check_required_status(response):
    """Проверяет наличие и тип обязательных ключей в ответе API."""
    if 'homeworks' not in response:
        raise KeyError(
            'В ответе отсутствует обязательное поле "homeworks".'
        )
    elif not isinstance(response['homeworks'], list):
        raise TypeError(
            '"homeworks" имеет неверный тип данных '
            f'"{type(response['homeworks']).__name__}", ожидался list. '
        )


def check_homework_structure(homework):
    """Проверяет корректность структуры отдельного объекта домашки."""
    if not isinstance(homework, dict):
        raise TypeError(
            f'"{homework}" иеет неправильный тип данныйх '
            f'"{type(homework).__name__}", ожидался dict.'
        )


def check_response(response):
    """Проверяет корректность структуры ответа API."""
    logging.debug('Начало проверок структуры API...')

    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API имеет неверный тип данных: '
            f'{type(response).__name__}, ожидался dict.'
        )

    check_required_status(response)

    for homework in response['homeworks']:
        check_homework_structure(homework)

    logging.debug('Успешное завершение проверки структуры API.')
    return True


def parse_status(homework):
    """Формирует сообщение о статусе домашней работы."""
    logging.debug('Начало проверок структуры домашней работы...')
    errors = []
    for key in ('homework_name', 'status'):
        if key not in homework:
            errors.append(f'В объекте homework отсутствует ключ "{key}".')
    if errors:
        raise KeyError(" ".join(errors),)

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Недокументированный статус домашней работы: {status}'
        )

    verdict = HOMEWORK_VERDICTS.get(status)

    logging.debug('Успешное завершение проверки структуры домашней работы.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    logging.info('Бот запущен и готов к работе.')

    # Осноной цикл программы.
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)

            homeworks = response['homeworks']
            if not homeworks:
                logging.debug('Нет новых домашних работ.')
                continue

            message = parse_status(homeworks[0])
            send_message(bot, message)

            timestamp = response.get('current_date', timestamp)

        except (
            requests.exceptions.RequestException, apihelper.ApiException
        ) as error:
            logging.exception(f'Ошибка сети или ОшибкаTelegram API: {error}')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            with suppress(
                apihelper.ApiException,
                requests.exceptions.RequestException
            ):
                send_message(bot, message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s, %(levelname)s, %(message)s, %(funcName)d, '
        '%(lineno)d',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    main()
