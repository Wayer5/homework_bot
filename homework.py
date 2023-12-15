"""Бот для проверки домашнего задания."""
import logging
import os
from http import HTTPStatus
import time

from dotenv import load_dotenv
import requests
import telegram


logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'Token does not exist')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class ApiAnswerError(Exception):
    """Ошибка при обращению к API."""


def check_tokens():
    """Проверка токенов."""
    missing_tokens = [token_name for token_name, token_value in {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }.items() if not token_value]

    if missing_tokens:
        logger.critical(
            f"Отсутствуют обязательные"
            f"переменные окружения: {', '.join(missing_tokens)}"
        )
        return False

    return True


last_message = None


def send_message(bot, message):
    """Посылание сообщения."""
    global last_message
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Успешная отправка сообщения в Telegram')
        # Проверка на совпадение с последним отправленным сообщением.
        # Эта функция уже была прописана
        # в main в прошлой версии. Исходя из текущего замечания,
        # я прописываю ее сюда тоже так как, если
        # в прошлой версии в main она
        # кажется недостаточной(исходя из замечания), то она должна быть и тут.
        # Плюс, прошлое замечание о недостатке это функции
        # было в main, настояще в send_message.
        # Следовательно, я понимаю так, что от меня требуется
        # прописать ее в обоих местах. Эта вся телега
        # на случай вопроса, почему проверка дублируется.
        if message != last_message:
            send_message(bot, message)
            last_message = message
    except Exception as e:
        logger.error(f'Сбой при отправке сообщения в Telegram: {e}')


def get_api_answer(timestamp):
    """Получение ответа."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        response.raise_for_status()

    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
        raise ApiAnswerError('Ошибка при запросе к API')

    if response.status_code != HTTPStatus.OK:
        logger.error(
            f'Статус API отличный от ожидаемого: {response.status_code}'
        )
        raise ApiAnswerError('API не отвечает')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ожидается словарь, получены данные другого типа')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует обязательный ключ "homeworks"')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Ожидается список, получены данные другого типа')
    if not homeworks:
        logger.debug('Отсутствуют новые статусы домашних работ')
    return homeworks


def parse_status(homework):
    """Парсинг."""
    if 'homework_name' not in homework:
        raise ValueError('Отсутствует ключ "homework_name" в ответе API')

    homework_name = homework['homework_name']
    status = homework.get('status', 'unknown')
    verdict = HOMEWORK_VERDICTS.get(status)

    if verdict is None:
        raise ValueError(f'Недокументированный статус работы: {status}')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы программы."""
    if not check_tokens():
        logger.critical('Отсутствует обязательная переменная окружения')
        return

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            timestamp = response.get('current_date', timestamp)

            if homeworks:
                message = parse_status(homeworks[0])

                # Проверка на совпадение с последним отправленным сообщением
                if message != last_message:
                    send_message(bot, message)
                    last_message = message

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
