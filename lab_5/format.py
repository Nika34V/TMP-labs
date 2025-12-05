# -*- coding: utf-8 -*-

import re
import sys
from string import punctuation
from typing import List, Tuple, Dict

# Импорт модуля логирования
from logger_config import logger, get_module_logger

# Получаем логгер для текущего модуля
module_logger = get_module_logger("format_checker")

# Temporary replacement
# The descriptions that contain () at the end must adapt to the new policy later
punctuation = punctuation.replace('()', '')

anchor = '###'
auth_keys = ['apiKey', 'OAuth', 'X-Mashape-Key', 'User-Agent', 'No']
https_keys = ['Yes', 'No']
cors_keys = ['Yes', 'No', 'Unknown']

index_title = 0
index_desc = 1
index_auth = 2
index_https = 3
index_cors = 4

num_segments = 5
min_entries_per_category = 3
max_description_length = 100

anchor_re = re.compile(anchor + '\s(.+)')
category_title_in_index_re = re.compile('\*\s\[(.*)\]')
link_re = re.compile('\[(.+)\]\((http.*)\)')

# Type aliases
APIList = List[str]
Categories = Dict[str, APIList]
CategoriesLineNumber = Dict[str, int]


def error_message(line_number: int, message: str) -> str:
    line = line_number + 1
    return f'(L{line:03d}) {message}'


def get_categories_content(contents: List[str]) -> Tuple[Categories, CategoriesLineNumber]:
    module_logger.debug("Начало извлечения категорий из содержимого файла")

    categories = {}
    category_line_num = {}

    for line_num, line_content in enumerate(contents):

        if line_content.startswith(anchor):
            category = line_content.split(anchor)[1].strip()
            categories[category] = []
            category_line_num[category] = line_num
            continue

        if not line_content.startswith('|') or line_content.startswith('|---'):
            continue

        raw_title = [
            raw_content.strip() for raw_content in line_content.split('|')[1:-1]
        ][0]

        title_match = link_re.match(raw_title)
        if title_match:
            title = title_match.group(1).upper()
            categories[category].append(title)

    module_logger.debug(f"Извлечено {len(categories)} категорий")
    return (categories, category_line_num)


def check_alphabetical_order(lines: List[str]) -> List[str]:
    module_logger.debug("Проверка алфавитного порядка категорий")

    err_msgs = []

    categories, category_line_num = get_categories_content(contents=lines)

    for category, api_list in categories.items():
        if sorted(api_list) != api_list:
            err_msg = error_message(
                category_line_num[category],
                f'{category} category is not alphabetical order'
            )
            err_msgs.append(err_msg)
            module_logger.warning(f"Категория '{category}' не в алфавитном порядке")

    if err_msgs:
        module_logger.info(f"Найдено {len(err_msgs)} ошибок алфавитного порядка")
    else:
        module_logger.debug("Все категории в алфавитном порядке")

    return err_msgs


def check_title(line_num: int, raw_title: str) -> List[str]:
    err_msgs = []

    title_match = link_re.match(raw_title)

    # url should be wrapped in "[TITLE](LINK)" Markdown syntax
    if not title_match:
        err_msg = error_message(line_num, 'Title syntax should be "[TITLE](LINK)"')
        err_msgs.append(err_msg)
    else:
        # do not allow "... API" in the entry title
        title = title_match.group(1)
        if title.upper().endswith(' API'):
            err_msg = error_message(line_num, 'Title should not end with "... API". Every entry is an API here!')
            err_msgs.append(err_msg)

    return err_msgs


def check_description(line_num: int, description: str) -> List[str]:
    err_msgs = []

    first_char = description[0]
    if first_char.upper() != first_char:
        err_msg = error_message(line_num, 'first character of description is not capitalized')
        err_msgs.append(err_msg)

    last_char = description[-1]
    if last_char in punctuation:
        err_msg = error_message(line_num, f'description should not end with {last_char}')
        err_msgs.append(err_msg)

    desc_length = len(description)
    if desc_length > max_description_length:
        err_msg = error_message(line_num,
                                f'description should not exceed {max_description_length} characters (currently {desc_length})')
        err_msgs.append(err_msg)

    return err_msgs


def check_auth(line_num: int, auth: str) -> List[str]:
    err_msgs = []

    backtick = '`'
    if auth != 'No' and (not auth.startswith(backtick) or not auth.endswith(backtick)):
        err_msg = error_message(line_num, 'auth value is not enclosed with `backticks`')
        err_msgs.append(err_msg)

    if auth.replace(backtick, '') not in auth_keys:
        err_msg = error_message(line_num, f'{auth} is not a valid Auth option')
        err_msgs.append(err_msg)

    return err_msgs


def check_https(line_num: int, https: str) -> List[str]:
    err_msgs = []

    if https not in https_keys:
        err_msg = error_message(line_num, f'{https} is not a valid HTTPS option')
        err_msgs.append(err_msg)

    return err_msgs


def check_cors(line_num: int, cors: str) -> List[str]:
    err_msgs = []

    if cors not in cors_keys:
        err_msg = error_message(line_num, f'{cors} is not a valid CORS option')
        err_msgs.append(err_msg)

    return err_msgs


def check_entry(line_num: int, segments: List[str]) -> List[str]:
    raw_title = segments[index_title]
    description = segments[index_desc]
    auth = segments[index_auth]
    https = segments[index_https]
    cors = segments[index_cors]

    title_err_msgs = check_title(line_num, raw_title)
    desc_err_msgs = check_description(line_num, description)
    auth_err_msgs = check_auth(line_num, auth)
    https_err_msgs = check_https(line_num, https)
    cors_err_msgs = check_cors(line_num, cors)

    err_msgs = [
        *title_err_msgs,
        *desc_err_msgs,
        *auth_err_msgs,
        *https_err_msgs,
        *cors_err_msgs
    ]

    return err_msgs


def check_file_format(lines: List[str]) -> List[str]:
    module_logger.info(f"Начало проверки формата файла ({len(lines)} строк)")

    err_msgs = []
    category_title_in_index = []

    alphabetical_err_msgs = check_alphabetical_order(lines)
    err_msgs.extend(alphabetical_err_msgs)

    num_in_category = min_entries_per_category + 1
    category = ''
    category_line = 0

    for line_num, line_content in enumerate(lines):

        category_title_match = category_title_in_index_re.match(line_content)
        if category_title_match:
            category_title_in_index.append(category_title_match.group(1))

        # check each category for the minimum number of entries
        if line_content.startswith(anchor):
            category_match = anchor_re.match(line_content)
            if category_match:
                if category_match.group(1) not in category_title_in_index:
                    err_msg = error_message(line_num,
                                            f'category header ({category_match.group(1)}) not added to Index section')
                    err_msgs.append(err_msg)
            else:
                err_msg = error_message(line_num, 'category header is not formatted correctly')
                err_msgs.append(err_msg)

            if num_in_category < min_entries_per_category:
                err_msg = error_message(category_line,
                                        f'{category} category does not have the minimum {min_entries_per_category} entries (only has {num_in_category})')
                err_msgs.append(err_msg)

            category = line_content.split(' ')[1]
            category_line = line_num
            num_in_category = 0
            continue

        # skips lines that we do not care about
        if not line_content.startswith('|') or line_content.startswith('|---'):
            continue

        num_in_category += 1
        segments = line_content.split('|')[1:-1]
        if len(segments) < num_segments:
            err_msg = error_message(line_num,
                                    f'entry does not have all the required columns (have {len(segments)}, need {num_segments})')
            err_msgs.append(err_msg)
            continue

        for segment in segments:
            # every line segment should start and end with exactly 1 space
            if len(segment) - len(segment.lstrip()) != 1 or len(segment) - len(segment.rstrip()) != 1:
                err_msg = error_message(line_num, 'each segment must start and end with exactly 1 space')
                err_msgs.append(err_msg)

        segments = [segment.strip() for segment in segments]
        entry_err_msgs = check_entry(line_num, segments)
        err_msgs.extend(entry_err_msgs)

    module_logger.info(f"Проверка завершена. Найдено {len(err_msgs)} ошибок")
    return err_msgs


def main(filename: str) -> None:
    module_logger.info(f"Запуск проверки файла: {filename}")

    try:
        with open(filename, mode='r', encoding='utf-8') as file:
            lines = list(line.rstrip() for line in file)

        module_logger.debug(f"Файл успешно загружен: {len(lines)} строк")

        file_format_err_msgs = check_file_format(lines)

        if file_format_err_msgs:
            for err_msg in file_format_err_msgs:
                print(err_msg)
                module_logger.error(err_msg)

            module_logger.error(f"Проверка завершилась с ошибками: {len(file_format_err_msgs)} ошибок")
            sys.exit(1)
        else:
            module_logger.info("Проверка успешно завершена. Ошибок не найдено.")

    except FileNotFoundError:
        error_msg = f"Файл не найден: {filename}"
        module_logger.critical(error_msg)
        print(error_msg)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Неожиданная ошибка: {str(e)}"
        module_logger.critical(error_msg, exc_info=True)
        print(error_msg)
        sys.exit(1)


if __name__ == '__main__':
    module_logger.debug("Скрипт запущен напрямую")

    num_args = len(sys.argv)

    if num_args < 2:
        error_msg = 'No .md file passed (file should contain Markdown table syntax)'
        module_logger.error(error_msg)
        print(error_msg)
        sys.exit(1)

    filename = sys.argv[1]
    module_logger.debug(f"Аргументы командной строки: {sys.argv}")

    main(filename)