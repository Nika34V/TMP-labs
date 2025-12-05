# -*- coding: utf-8 -*-

import re
import sys
import os
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
            module_logger.debug(f"Найдена категория: '{category}' на строке {line_num + 1}")
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
            module_logger.debug(f"Добавлен API '{title}' в категорию '{category}'")

    module_logger.debug(f"Извлечено {len(categories)} категорий")
    for category, api_list in categories.items():
        module_logger.debug(f"  - '{category}': {len(api_list)} API")

    return (categories, category_line_num)


def check_alphabetical_order(lines: List[str]) -> List[str]:
    module_logger.debug("Проверка алфавитного порядка категорий")

    err_msgs = []

    categories, category_line_num = get_categories_content(contents=lines)

    for category, api_list in categories.items():
        if len(api_list) > 0:
            module_logger.debug(f"Проверка алфавитного порядка для категории '{category}' ({len(api_list)} API)")

            sorted_list = sorted(api_list)
            if sorted_list != api_list:
                err_msg = error_message(
                    category_line_num[category],
                    f'{category} category is not alphabetical order'
                )
                err_msgs.append(err_msg)
                module_logger.warning(f"Категория '{category}' не в алфавитном порядке")
                module_logger.debug(f"Ожидаемый порядок: {sorted_list}")
                module_logger.debug(f"Фактический порядок: {api_list}")
            else:
                module_logger.debug(f"Категория '{category}' в правильном алфавитном порядке")
        else:
            module_logger.debug(f"Категория '{category}' пустая, пропуск проверки порядка")

    if err_msgs:
        module_logger.info(f"Найдено {len(err_msgs)} ошибок алфавитного порядка")
    else:
        module_logger.info("Все категории в алфавитном порядке")

    return err_msgs


def check_title(line_num: int, raw_title: str) -> List[str]:
    module_logger.debug(f"Проверка заголовка на строке {line_num + 1}: '{raw_title}'")

    err_msgs = []

    title_match = link_re.match(raw_title)

    # url should be wrapped in "[TITLE](LINK)" Markdown syntax
    if not title_match:
        err_msg = error_message(line_num, 'Title syntax should be "[TITLE](LINK)"')
        err_msgs.append(err_msg)
        module_logger.debug(f"Некорректный синтаксис заголовка: {raw_title}")
    else:
        title = title_match.group(1)
        module_logger.debug(f"Извлечён заголовок: '{title}'")

        # do not allow "... API" in the entry title
        if title.upper().endswith(' API'):
            err_msg = error_message(line_num, 'Title should not end with "... API". Every entry is an API here!')
            err_msgs.append(err_msg)
            module_logger.debug(f"Заголовок заканчивается на 'API': {title}")

    if not err_msgs:
        module_logger.debug(f"Заголовок на строке {line_num + 1} корректен")

    return err_msgs


def check_description(line_num: int, description: str) -> List[str]:
    module_logger.debug(
        f"Проверка описания на строке {line_num + 1} (длина: {len(description)}): '{description[:50]}...'")

    err_msgs = []

    first_char = description[0]
    if first_char.upper() != first_char:
        err_msg = error_message(line_num, 'first character of description is not capitalized')
        err_msgs.append(err_msg)
        module_logger.debug(f"Первая буква не заглавная: '{first_char}'")

    last_char = description[-1]
    if last_char in punctuation:
        err_msg = error_message(line_num, f'description should not end with {last_char}')
        err_msgs.append(err_msg)
        module_logger.debug(f"Описание заканчивается пунктуацией: '{last_char}'")

    desc_length = len(description)
    if desc_length > max_description_length:
        err_msg = error_message(line_num,
                                f'description should not exceed {max_description_length} characters (currently {desc_length})')
        err_msgs.append(err_msg)
        module_logger.debug(f"Описание слишком длинное: {desc_length} > {max_description_length}")

    if not err_msgs:
        module_logger.debug(f"Описание на строке {line_num + 1} корректно")

    return err_msgs


def check_auth(line_num: int, auth: str) -> List[str]:
    module_logger.debug(f"Проверка аутентификации на строке {line_num + 1}: '{auth}'")

    err_msgs = []

    backtick = '`'
    if auth != 'No' and (not auth.startswith(backtick) or not auth.endswith(backtick)):
        err_msg = error_message(line_num, 'auth value is not enclosed with `backticks`')
        err_msgs.append(err_msg)
        module_logger.debug(f"Аутентификация не в обратных кавычках: {auth}")

    auth_clean = auth.replace(backtick, '')
    if auth_clean not in auth_keys:
        err_msg = error_message(line_num, f'{auth} is not a valid Auth option')
        err_msgs.append(err_msg)
        module_logger.debug(f"Недопустимое значение аутентификации: {auth}, ожидалось: {auth_keys}")

    if not err_msgs:
        module_logger.debug(f"Аутентификация на строке {line_num + 1} корректа: {auth}")

    return err_msgs


def check_https(line_num: int, https: str) -> List[str]:
    module_logger.debug(f"Проверка HTTPS на строке {line_num + 1}: '{https}'")

    err_msgs = []

    if https not in https_keys:
        err_msg = error_message(line_num, f'{https} is not a valid HTTPS option')
        err_msgs.append(err_msg)
        module_logger.debug(f"Недопустимое значение HTTPS: {https}, ожидалось: {https_keys}")

    if not err_msgs:
        module_logger.debug(f"HTTPS на строке {line_num + 1} корректен: {https}")

    return err_msgs


def check_cors(line_num: int, cors: str) -> List[str]:
    module_logger.debug(f"Проверка CORS на строке {line_num + 1}: '{cors}'")

    err_msgs = []

    if cors not in cors_keys:
        err_msg = error_message(line_num, f'{cors} is not a valid CORS option')
        err_msgs.append(err_msg)
        module_logger.debug(f"Недопустимое значение CORS: {cors}, ожидалось: {cors_keys}")

    if not err_msgs:
        module_logger.debug(f"CORS на строке {line_num + 1} корректен: {cors}")

    return err_msgs


def check_entry(line_num: int, segments: List[str]) -> List[str]:
    module_logger.debug(f"Начало проверки записи на строке {line_num + 1}")

    raw_title = segments[index_title]
    description = segments[index_desc]
    auth = segments[index_auth]
    https = segments[index_https]
    cors = segments[index_cors]

    module_logger.debug(
        f"Поля записи: title='{raw_title[:30]}...', desc='{description[:30]}...', auth='{auth}', https='{https}', cors='{cors}'")

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

    if err_msgs:
        module_logger.debug(f"Найдено {len(err_msgs)} ошибок в записи на строке {line_num + 1}")
    else:
        module_logger.debug(f"Запись на строке {line_num + 1} прошла все проверки успешно")

    return err_msgs


def check_file_format(lines: List[str]) -> List[str]:
    module_logger.info(f"Начало проверки формата файла ({len(lines)} строк)")

    err_msgs = []
    category_title_in_index = []

    # Логирование информации о файле
    non_empty_lines = [line for line in lines if line.strip()]
    module_logger.info(f"Непустых строк: {len(non_empty_lines)}")

    table_lines = [line for line in lines if line.startswith('|') and not line.startswith('|---')]
    module_logger.info(f"Строк с данными API: {len(table_lines)}")

    alphabetical_err_msgs = check_alphabetical_order(lines)
    err_msgs.extend(alphabetical_err_msgs)

    num_in_category = min_entries_per_category + 1
    category = ''
    category_line = 0
    total_entries = 0

    module_logger.debug(f"Минимальное количество записей в категории: {min_entries_per_category}")

    for line_num, line_content in enumerate(lines):
        module_logger.debug(f"Обработка строки {line_num + 1}: {line_content[:50]}...")

        category_title_match = category_title_in_index_re.match(line_content)
        if category_title_match:
            category_title = category_title_match.group(1)
            category_title_in_index.append(category_title)
            module_logger.debug(f"Найдена категория в индексе: '{category_title}'")

        # check each category for the minimum number of entries
        if line_content.startswith(anchor):
            category_match = anchor_re.match(line_content)
            if category_match:
                category_name = category_match.group(1)
                module_logger.debug(f"Найдена категория в основном содержании: '{category_name}'")

                if category_name not in category_title_in_index:
                    err_msg = error_message(line_num, f'category header ({category_name}) not added to Index section')
                    err_msgs.append(err_msg)
                    module_logger.warning(f"Категория '{category_name}' отсутствует в индексе")
            else:
                err_msg = error_message(line_num, 'category header is not formatted correctly')
                err_msgs.append(err_msg)
                module_logger.warning(f"Некорректный формат заголовка категории: {line_content}")

            if num_in_category < min_entries_per_category:
                err_msg = error_message(category_line,
                                        f'{category} category does not have the minimum {min_entries_per_category} entries (only has {num_in_category})')
                err_msgs.append(err_msg)
                module_logger.warning(
                    f"Категория '{category}' имеет недостаточно записей: {num_in_category} < {min_entries_per_category}")

            category = line_content.split(' ')[1]
            category_line = line_num
            module_logger.info(f"Начата обработка категории: '{category}'")
            num_in_category = 0
            continue

        # skips lines that we do not care about
        if not line_content.startswith('|') or line_content.startswith('|---'):
            continue

        num_in_category += 1
        total_entries += 1
        segments = line_content.split('|')[1:-1]

        module_logger.debug(f"Запись #{total_entries} в категории '{category}', сегментов: {len(segments)}")

        if len(segments) < num_segments:
            err_msg = error_message(line_num,
                                    f'entry does not have all the required columns (have {len(segments)}, need {num_segments})')
            err_msgs.append(err_msg)
            module_logger.warning(f"Недостаточно колонок в записи: {len(segments)} вместо {num_segments}")
            continue

        # Проверка форматирования пробелов
        spacing_issues = []
        for i, segment in enumerate(segments):
            left_spaces = len(segment) - len(segment.lstrip())
            right_spaces = len(segment) - len(segment.rstrip())

            if left_spaces != 1 or right_spaces != 1:
                spacing_issues.append(i)

        if spacing_issues:
            err_msg = error_message(line_num, 'each segment must start and end with exactly 1 space')
            err_msgs.append(err_msg)
            module_logger.debug(f"Проблемы с пробелами в сегментах: {spacing_issues}")

        segments = [segment.strip() for segment in segments]
        entry_err_msgs = check_entry(line_num, segments)
        err_msgs.extend(entry_err_msgs)

    # Финальная проверка для последней категории
    if num_in_category < min_entries_per_category:
        err_msg = error_message(category_line,
                                f'{category} category does not have the minimum {min_entries_per_category} entries (only has {num_in_category})')
        err_msgs.append(err_msg)
        module_logger.warning(
            f"Последняя категория '{category}' имеет недостаточно записей: {num_in_category} < {min_entries_per_category}")

    module_logger.info(f"Проверка завершена. Всего записей: {total_entries}, категорий: {len(category_title_in_index)}")
    module_logger.info(f"Найдено ошибок: {len(err_msgs)}")

    return err_msgs


def analyze_file_content(lines: List[str]) -> Dict:
    """
    Анализ содержимого файла для логирования статистики

    Args:
        lines: Строки файла

    Returns:
        Словарь со статистикой
    """
    stats = {
        'total_lines': len(lines),
        'non_empty_lines': 0,
        'category_lines': 0,
        'table_lines': 0,
        'separator_lines': 0,
        'index_lines': 0,
        'categories': []
    }

    for line in lines:
        line_stripped = line.strip()

        if line_stripped:
            stats['non_empty_lines'] += 1

            if line.startswith('###'):
                stats['category_lines'] += 1
                category_name = line.replace('###', '').strip()
                stats['categories'].append(category_name)
            elif line.startswith('|'):
                if line.startswith('|---'):
                    stats['separator_lines'] += 1
                else:
                    stats['table_lines'] += 1
            elif line.startswith('*'):
                stats['index_lines'] += 1

    return stats


def main(filename: str) -> None:
    module_logger.info("=" * 60)
    module_logger.info(f"Запуск проверки файла: {filename}")
    module_logger.info("=" * 60)

    try:
        # Логирование информации о файле
        if not os.path.exists(filename):
            error_msg = f"Файл не найден: {filename}"
            module_logger.critical(error_msg)
            print(error_msg)
            sys.exit(1)

        file_size = os.path.getsize(filename)
        module_logger.info(f"Размер файла: {file_size} байт")
        module_logger.info(f"Путь к файлу: {os.path.abspath(filename)}")

        with open(filename, mode='r', encoding='utf-8') as file:
            lines = list(line.rstrip() for line in file)

        # Анализ содержимого файла
        stats = analyze_file_content(lines)
        module_logger.info(f"Статистика файла:")
        module_logger.info(f"  Всего строк: {stats['total_lines']}")
        module_logger.info(f"  Непустых строк: {stats['non_empty_lines']}")
        module_logger.info(f"  Категорий: {len(stats['categories'])}")
        module_logger.info(f"  Строк с API: {stats['table_lines']}")
        module_logger.info(f"  Строк индекса: {stats['index_lines']}")

        if stats['categories']:
            module_logger.info(f"  Найденные категории: {', '.join(stats['categories'][:5])}")
            if len(stats['categories']) > 5:
                module_logger.info(f"  ... и ещё {len(stats['categories']) - 5}")

        module_logger.debug(f"Файл успешно загружен: {len(lines)} строк")

        file_format_err_msgs = check_file_format(lines)

        if file_format_err_msgs:
            module_logger.info("-" * 60)
            module_logger.info("РЕЗУЛЬТАТ ПРОВЕРКИ: НЕУДАЧА")
            module_logger.info("-" * 60)

            error_categories = {}
            for err_msg in file_format_err_msgs:
                print(err_msg)
                module_logger.error(err_msg)

                # Анализ типов ошибок для статистики
                if "alphabetical" in err_msg:
                    error_categories['alphabetical'] = error_categories.get('alphabetical', 0) + 1
                elif "Title" in err_msg:
                    error_categories['title'] = error_categories.get('title', 0) + 1
                elif "description" in err_msg:
                    error_categories['description'] = error_categories.get('description', 0) + 1
                elif "auth" in err_msg:
                    error_categories['auth'] = error_categories.get('auth', 0) + 1
                elif "HTTPS" in err_msg:
                    error_categories['https'] = error_categories.get('https', 0) + 1
                elif "CORS" in err_msg:
                    error_categories['cors'] = error_categories.get('cors', 0) + 1
                else:
                    error_categories['other'] = error_categories.get('other', 0) + 1

            # Логирование статистики ошибок
            module_logger.info("Статистика ошибок:")
            for err_type, count in error_categories.items():
                module_logger.info(f"  {err_type}: {count} ошибок")

            module_logger.error(f"Проверка завершилась с ошибками: {len(file_format_err_msgs)} ошибок")
            sys.exit(1)
        else:
            module_logger.info("-" * 60)
            module_logger.info("РЕЗУЛЬТАТ ПРОВЕРКИ: УСПЕХ")
            module_logger.info("-" * 60)
            module_logger.info("Проверка успешно завершена. Ошибок не найдено.")

    except FileNotFoundError:
        error_msg = f"Файл не найден: {filename}"
        module_logger.critical(error_msg)
        print(error_msg)
        sys.exit(1)
    except UnicodeDecodeError as e:
        error_msg = f"Ошибка кодировки файла: {str(e)}"
        module_logger.critical(error_msg, exc_info=True)
        print(error_msg)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Неожиданная ошибка: {str(e)}"
        module_logger.critical(error_msg, exc_info=True)
        print(error_msg)
        sys.exit(1)


if __name__ == '__main__':
    module_logger.debug("=" * 60)
    module_logger.debug("Скрипт запущен напрямую")
    module_logger.debug(f"Python версия: {sys.version}")
    module_logger.debug(f"Рабочая директория: {os.getcwd()}")
    module_logger.debug("=" * 60)

    num_args = len(sys.argv)

    if num_args < 2:
        error_msg = 'No .md file passed (file should contain Markdown table syntax)'
        module_logger.error(error_msg)
        print(error_msg)
        sys.exit(1)

    filename = sys.argv[1]
    module_logger.debug(f"Аргументы командной строки: {sys.argv}")
    module_logger.info(f"Целевой файл: {filename}")

    main(filename)