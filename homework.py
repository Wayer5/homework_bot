"""Бот для проверки домашнего задания."""
from dotenv import load_dotenv
import requests
import time
import telegram
from telegram.ext import Updater
import logging
from http import HTTPStatus
import os

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)


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

updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
timestamp = int(time.time())


def check_tokens():
    """Проверка токенов."""
    if not all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        logger.critical("Отсутствуют обязательные переменные окружения")
        return False
    return True


def send_message(bot, message):
    """Посылание сообщения."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug("Успешная отправка сообщения в Telegram")
    except Exception as e:
        logger.error(f"Сбой при отправке сообщения в Telegram: {e}")


def get_api_answer(timestamp):
    """Получение ответа."""
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
        homework_statuses.raise_for_status()
        if homework_statuses.status_code != HTTPStatus.OK:
            raise requests.exceptions.HTTPError(
                f"Ошибка при запросе: {homework_statuses.status_code}"
                )
    except requests.exceptions.HTTPError as e:
        logger.error(f"Ошибка при запросе: {e.response.status_code}")
        return {}
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к эндпоинту: {e}")
        return {}
    if homework_statuses.status_code != HTTPStatus.OK:
        logger.error(f"Ошибка при запрос: {homework_statuses.status_code}")
        return {}
    return homework_statuses.json()


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
        logging.debug('Отсутствуют новые статусы домашних работ')
    return homeworks


def parse_status(homework):
    """Парсинг."""
    if 'homework_name' not in homework:
        raise ValueError("Отсутствует ключ 'homework_name' в ответе API")

    homework_name = homework['homework_name']
    status = homework.get('status', 'unknown')
    verdict = HOMEWORK_VERDICTS.get(status)

    if verdict is None:
        raise ValueError(f"Недокументированный статус работы: {status}")

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы программы."""
    if not check_tokens():
        logging.critical('Отсутствует обязательная переменная окружения')
        return
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            timestamp = response.get('current_date', timestamp)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
