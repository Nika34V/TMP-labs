# -*- coding: utf-8 -*-

import re
import sys
import os
import time
from string import punctuation
from typing import List, Tuple, Dict, Set, Optional
from collections import defaultdict, Counter

# Импорт модуля логирования
from logger_config import (
    logger,
    get_module_logger,
    category_logger,
    index_logger,
    structure_logger
)

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
    """Извлекает категории и их содержимое из файла"""
    structure_logger.info("Начало извлечения категорий и API из файла")

    categories = {}
    category_line_num = {}
    current_category = None
    api_count_in_category = 0

    for line_num, line_content in enumerate(contents):
        if line_content.startswith(anchor):
            # Сохраняем статистику предыдущей категории
            if current_category and api_count_in_category > 0:
                category_logger.debug(f"Категория '{current_category}': {api_count_in_category} API")

            category = line_content.split(anchor)[1].strip()
            categories[category] = []
            category_line_num[category] = line_num
            current_category = category
            api_count_in_category = 0

            category_logger.info(f"Обнаружена категория: '{category}' на строке {line_num + 1}")
            continue

        if not line_content.startswith('|') or line_content.startswith('|---'):
            continue

        raw_title = [
            raw_content.strip() for raw_content in line_content.split('|')[1:-1]
        ][0]

        title_match = link_re.match(raw_title)
        if title_match:
            title = title_match.group(1).upper()
            categories[current_category].append(title)
            api_count_in_category += 1

            if api_count_in_category <= 3:  # Логируем только первые 3 для краткости
                category_logger.debug(f"API #{api_count_in_category} в '{current_category}': {title}")

    # Логируем статистику по последней категории
    if current_category and api_count_in_category > 0:
        category_logger.debug(f"Категория '{current_category}': {api_count_in_category} API")

    structure_logger.info(f"Извлечение завершено: {len(categories)} категорий")
    for category, api_list in categories.items():
        structure_logger.debug(f"  '{category}': {len(api_list)} API")

    return (categories, category_line_num)


def analyze_index_section(lines: List[str]) -> Dict:
    """Анализирует раздел индекса"""
    index_logger.info("Анализ раздела индекса")

    index_data = {
        'categories_in_index': [],
        'index_lines': [],
        'malformed_entries': [],
        'total_entries': 0
    }

    in_index_section = False
    index_start_line = -1

    for line_num, line_content in enumerate(lines):
        line_stripped = line_content.strip()

        # Ищем начало индекса
        if line_stripped.lower() in ['## index', '## contents', '## оглавление']:
            in_index_section = True
            index_start_line = line_num
            index_logger.debug(f"Раздел индекса начинается на строке {line_num + 1}")
            continue

        # Если мы в разделе индекса и нашли другую секцию, заканчиваем
        if in_index_section and line_stripped.startswith('##'):
            index_logger.debug(f"Раздел индекса заканчивается на строке {line_num}")
            break

        if in_index_section and line_stripped.startswith('*'):
            index_data['total_entries'] += 1
            index_data['index_lines'].append((line_num, line_content))

            match = category_title_in_index_re.match(line_content)
            if match:
                category_name = match.group(1)
                index_data['categories_in_index'].append(category_name)
                index_logger.debug(f"Категория в индексе: '{category_name}' на строке {line_num + 1}")
            else:
                index_data['malformed_entries'].append((line_num, line_content))
                index_logger.warning(f"Некорректная запись в индексе на строке {line_num + 1}: {line_content}")

    index_logger.info(f"Найдено {len(index_data['categories_in_index'])} категорий в индексе")
    index_logger.info(f"Некорректных записей: {len(index_data['malformed_entries'])}")

    return index_data


def verify_index_consistency(categories_in_file: List[str], categories_in_index: List[str]) -> Dict:
    """Проверяет согласованность между индексом и содержанием"""
    index_logger.info("Проверка согласованности индекса и содержания")

    file_set = set(categories_in_file)
    index_set = set(categories_in_index)

    issues = {
        'missing_in_index': list(file_set - index_set),
        'extra_in_index': list(index_set - file_set),
        'matches': list(file_set & index_set)
    }

    if issues['missing_in_index']:
        index_logger.warning(f"Категории отсутствуют в индексе: {', '.join(issues['missing_in_index'])}")

    if issues['extra_in_index']:
        index_logger.warning(f"Лишние категории в индексе: {', '.join(issues['extra_in_index'])}")

    if not issues['missing_in_index'] and not issues['extra_in_index']:
        index_logger.info("Индекс полностью соответствует содержанию")

    return issues


def check_category_structure(categories: Dict[str, List[str]], category_line_num: Dict[str, int]) -> List[str]:
    """Проверяет структуру категорий"""
    category_logger.info("Проверка структуры категорий")

    err_msgs = []
    category_stats = {}

    for category, api_list in categories.items():
        stats = {
            'count': len(api_list),
            'line': category_line_num[category] + 1,
            'unique_apis': len(set(api_list)),
            'has_duplicates': len(api_list) != len(set(api_list))
        }
        category_stats[category] = stats

        # Проверка минимального количества записей
        if stats['count'] < min_entries_per_category:
            err_msg = error_message(
                category_line_num[category],
                f'{category} category does not have the minimum {min_entries_per_category} entries (only has {stats["count"]})'
            )
            err_msgs.append(err_msg)
            category_logger.warning(f"Категория '{category}' имеет недостаточно записей: {stats['count']}")

        # Проверка дубликатов
        if stats['has_duplicates']:
            duplicates = [item for item, count in Counter(api_list).items() if count > 1]
            err_msg = error_message(
                category_line_num[category],
                f'{category} category has duplicate APIs: {", ".join(duplicates[:3])}'
            )
            err_msgs.append(err_msg)
            category_logger.warning(f"Категория '{category}' содержит дубликаты: {duplicates}")

        # Логируем статистику
        category_logger.debug(f"Категория '{category}': {stats['count']} записей, {stats['unique_apis']} уникальных")

    # Сводная статистика
    total_apis = sum(stats['count'] for stats in category_stats.values())
    avg_per_category = total_apis / len(category_stats) if category_stats else 0

    category_logger.info(f"Сводка по категориям: {len(category_stats)} категорий, {total_apis} API всего")
    category_logger.info(f"Среднее количество API на категорию: {avg_per_category:.1f}")

    # Находим категории с наибольшим и наименьшим количеством API
    if category_stats:
        max_category = max(category_stats.items(), key=lambda x: x[1]['count'])
        min_category = min(category_stats.items(), key=lambda x: x[1]['count'])

        category_logger.info(f"Наибольшая категория: '{max_category[0]}' ({max_category[1]['count']} API)")
        category_logger.info(f"Наименьшая категория: '{min_category[0]}' ({min_category[1]['count']} API)")

    return err_msgs


def check_alphabetical_order(lines: List[str]) -> List[str]:
    """Проверяет алфавитный порядок API в категориях"""
    category_logger.info("Проверка алфавитного порядка в категориях")

    err_msgs = []
    categories, category_line_num = get_categories_content(contents=lines)

    for category, api_list in categories.items():
        if len(api_list) > 0:
            category_logger.debug(f"Проверка порядка для категории '{category}' ({len(api_list)} API)")

            sorted_list = sorted(api_list)
            if sorted_list != api_list:
                # Находим первую позицию, где порядок нарушен
                for i, (actual, expected) in enumerate(zip(api_list, sorted_list)):
                    if actual != expected:
                        category_logger.warning(
                            f"Нарушение порядка в '{category}' на позиции {i + 1}: '{actual}' вместо '{expected}'")
                        break

                err_msg = error_message(
                    category_line_num[category],
                    f'{category} category is not alphabetical order'
                )
                err_msgs.append(err_msg)
                category_logger.warning(f"Категория '{category}' не в алфавитном порядке")
            else:
                category_logger.debug(f"Категория '{category}' в правильном алфавитном порядке")
        else:
            category_logger.debug(f"Категория '{category}' пустая, пропуск проверки порядка")

    if err_msgs:
        category_logger.info(f"Найдено {len(err_msgs)} нарушений алфавитного порядка")
    else:
        category_logger.info("Все категории в алфавитном порядке")

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


def analyze_file_structure(lines: List[str]) -> Dict:
    """Анализирует структуру файла"""
    structure_logger.info("Анализ структуры файла Markdown")

    structure = {
        'sections': [],
        'tables': [],
        'current_section': None,
        'table_in_section': False
    }

    for line_num, line_content in enumerate(lines):
        line_stripped = line_content.strip()

        # Определяем заголовки разделов
        if line_stripped.startswith('#'):
            level = len(line_stripped) - len(line_stripped.lstrip('#'))
            title = line_stripped.lstrip('#').strip()

            section = {
                'level': level,
                'title': title,
                'start_line': line_num,
                'tables': []
            }

            structure['sections'].append(section)
            structure['current_section'] = section
            structure['table_in_section'] = False

            structure_logger.debug(f"Раздел {'#' * level} '{title}' на строке {line_num + 1}")

        # Определяем таблицы
        elif line_stripped.startswith('|'):
            if line_stripped.startswith('|---'):
                # Это разделитель таблицы
                if structure['current_section'] and structure['table_in_section']:
                    structure['current_section']['tables'][-1]['end_line'] = line_num
                    structure_logger.debug(f"Таблица завершена на строке {line_num + 1}")
            else:
                # Это строка данных таблицы
                if not structure['table_in_section']:
                    # Начало новой таблицы
                    table = {
                        'start_line': line_num,
                        'rows': []
                    }
                    if structure['current_section']:
                        structure['current_section']['tables'].append(table)
                    structure['tables'].append(table)
                    structure['table_in_section'] = True

                    structure_logger.debug(f"Начало таблицы на строке {line_num + 1}")

                # Добавляем строку в текущую таблицу
                if structure['current_section'] and structure['current_section']['tables']:
                    structure['current_section']['tables'][-1]['rows'].append(line_stripped)

    # Логируем результаты анализа
    structure_logger.info(f"Найдено разделов: {len(structure['sections'])}")
    structure_logger.info(f"Найдено таблиц: {len(structure['tables'])}")

    for section in structure['sections']:
        table_count = len(section.get('tables', []))
        if table_count > 0:
            structure_logger.info(f"  Раздел '{section['title']}': {table_count} таблиц")

    return structure


def check_file_format(lines: List[str]) -> List[str]:
    """Основная функция проверки формата файла"""
    logger.info("=" * 80)
    logger.info(f"НАЧАЛО ПРОВЕРКИ ФОРМАТА ФАЙЛА")
    logger.info("=" * 80)

    start_time = time.time()

    err_msgs = []
    category_title_in_index = []

    # Анализ структуры файла
    structure = analyze_file_structure(lines)

    # Анализ индекса
    index_data = analyze_index_section(lines)
    category_title_in_index = index_data['categories_in_index']

    # Проверка алфавитного порядка
    alphabetical_err_msgs = check_alphabetical_order(lines)
    err_msgs.extend(alphabetical_err_msgs)

    # Получение категорий из файла
    categories, category_line_num = get_categories_content(lines)

    # Проверка структуры категорий
    category_structure_err_msgs = check_category_structure(categories, category_line_num)
    err_msgs.extend(category_structure_err_msgs)

    # Проверка согласованности индекса и содержания
    categories_in_file = list(categories.keys())
    index_issues = verify_index_consistency(categories_in_file, category_title_in_index)

    # Добавляем ошибки для категорий, отсутствующих в индексе
    for missing_category in index_issues['missing_in_index']:
        if missing_category in category_line_num:
            err_msg = error_message(
                category_line_num[missing_category],
                f'category header ({missing_category}) not added to Index section'
            )
            err_msgs.append(err_msg)
            index_logger.warning(f"Категория '{missing_category}' отсутствует в индексе")

    # Проверка отдельных записей
    num_in_category = min_entries_per_category + 1
    current_category = ''
    category_start_line = 0
    total_entries = 0
    entries_by_category = defaultdict(int)

    logger.info("Начало проверки отдельных записей API")

    for line_num, line_content in enumerate(lines):
        # Определяем категории
        if line_content.startswith(anchor):
            category_match = anchor_re.match(line_content)
            if category_match:
                category_name = category_match.group(1)

                # Проверяем минимальное количество записей для предыдущей категории
                if num_in_category < min_entries_per_category and current_category:
                    err_msg = error_message(
                        category_start_line,
                        f'{current_category} category does not have the minimum {min_entries_per_category} entries (only has {num_in_category})'
                    )
                    err_msgs.append(err_msg)
                    category_logger.warning(
                        f"Категория '{current_category}' имеет недостаточно записей: {num_in_category}")

                current_category = category_name
                category_start_line = line_num
                num_in_category = 0

                logger.info(f"Обработка категории: '{current_category}'")

            continue

        # Пропускаем неинтересные строки
        if not line_content.startswith('|') or line_content.startswith('|---'):
            continue

        # Проверяем запись
        num_in_category += 1
        total_entries += 1
        entries_by_category[current_category] += 1

        segments = line_content.split('|')[1:-1]

        if len(segments) < num_segments:
            err_msg = error_message(line_num,
                                    f'entry does not have all the required columns (have {len(segments)}, need {num_segments})')
            err_msgs.append(err_msg)
            logger.warning(f"Недостаточно колонок в записи на строке {line_num + 1}")
            continue

        # Проверка форматирования
        spacing_issues = []
        for i, segment in enumerate(segments):
            left_spaces = len(segment) - len(segment.lstrip())
            right_spaces = len(segment) - len(segment.rstrip())

            if left_spaces != 1 or right_spaces != 1:
                spacing_issues.append(i)

        if spacing_issues:
            err_msg = error_message(line_num, 'each segment must start and end with exactly 1 space')
            err_msgs.append(err_msg)

        segments = [segment.strip() for segment in segments]
        entry_err_msgs = check_entry(line_num, segments)
        err_msgs.extend(entry_err_msgs)

        # Логируем прогресс
        if total_entries % 10 == 0:
            logger.info(f"Проверено {total_entries} записей...")

    # Проверка последней категории
    if num_in_category < min_entries_per_category and current_category:
        err_msg = error_message(
            category_start_line,
            f'{current_category} category does not have the minimum {min_entries_per_category} entries (only has {num_in_category})'
        )
        err_msgs.append(err_msg)
        category_logger.warning(
            f"Последняя категория '{current_category}' имеет недостаточно записей: {num_in_category}")

    # Вывод статистики
    elapsed_time = time.time() - start_time

    logger.info("=" * 80)
    logger.info("СТАТИСТИКА ПРОВЕРКИ")
    logger.info("=" * 80)
    logger.info(f"Общее время проверки: {elapsed_time:.2f} секунд")
    logger.info(f"Всего записей API: {total_entries}")
    logger.info(f"Всего категорий: {len(categories)}")
    logger.info(f"Найдено ошибок: {len(err_msgs)}")

    # Статистика по категориям
    if entries_by_category:
        logger.info("Записей по категориям:")
        for category, count in sorted(entries_by_category.items()):
            logger.info(f"  {category}: {count} записей")

    # Статистика индекса
    logger.info("Статус индекса:")
    logger.info(f"  Категорий в индексе: {len(category_title_in_index)}")
    logger.info(f"  Отсутствуют в индексе: {len(index_issues['missing_in_index'])}")
    logger.info(f"  Лишние в индексе: {len(index_issues['extra_in_index'])}")

    logger.info("=" * 80)

    return err_msgs


def analyze_file_content(lines: List[str]) -> Dict:
    """
    Анализ содержимого файла для логирования статистики

    Args:
        lines: Строки файла

    Returns:
        Словарь со статистикой
    """
    structure_logger.info("Анализ содержимого файла")

    stats = {
        'total_lines': len(lines),
        'non_empty_lines': 0,
        'category_lines': 0,
        'table_lines': 0,
        'separator_lines': 0,
        'index_lines': 0,
        'header_lines': 0,
        'categories': [],
        'lines_by_type': Counter()
    }

    for line_num, line_content in enumerate(lines):
        line_stripped = line_content.strip()

        if line_stripped:
            stats['non_empty_lines'] += 1

            if line_stripped.startswith('###'):
                stats['category_lines'] += 1
                stats['lines_by_type']['category_header'] += 1
                category_name = line_stripped.replace('###', '').strip()
                stats['categories'].append(category_name)
            elif line_stripped.startswith('##'):
                stats['header_lines'] += 1
                stats['lines_by_type']['section_header'] += 1
            elif line_stripped.startswith('#'):
                stats['header_lines'] += 1
                stats['lines_by_type']['main_header'] += 1
            elif line_stripped.startswith('|'):
                if line_stripped.startswith('|---'):
                    stats['separator_lines'] += 1
                    stats['lines_by_type']['table_separator'] += 1
                else:
                    stats['table_lines'] += 1
                    stats['lines_by_type']['table_row'] += 1
            elif line_stripped.startswith('*'):
                stats['index_lines'] += 1
                stats['lines_by_type']['index_entry'] += 1
            else:
                stats['lines_by_type']['other'] += 1

    structure_logger.info(f"Анализ завершен: {stats['total_lines']} строк, {len(stats['categories'])} категорий")
    structure_logger.debug(f"Распределение по типам строк: {dict(stats['lines_by_type'])}")

    return stats


def main(filename: str) -> None:
    logger.info("=" * 80)
    logger.info(f"ЗАПУСК ПРОГРАММЫ ПРОВЕРКИ API-ЛИСТА")
    logger.info(f"Файл: {filename}")
    logger.info(f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    try:
        # Логирование информации о файле
        if not os.path.exists(filename):
            error_msg = f"Файл не найден: {filename}"
            logger.critical(error_msg)
            print(error_msg)
            sys.exit(1)

        file_size = os.path.getsize(filename)
        file_mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(filename)))

        logger.info(f"Информация о файле:")
        logger.info(f"  Размер: {file_size} байт ({file_size / 1024:.1f} KB)")
        logger.info(f"  Путь: {os.path.abspath(filename)}")
        logger.info(f"  Время изменения: {file_mtime}")
        logger.info(f"  Расширение: {os.path.splitext(filename)[1]}")

        with open(filename, mode='r', encoding='utf-8') as file:
            lines = list(line.rstrip() for line in file)

        # Анализ содержимого файла
        stats = analyze_file_content(lines)

        logger.info("СТАТИСТИКА ФАЙЛА:")
        logger.info(f"  Всего строк: {stats['total_lines']}")
        logger.info(
            f"  Непустых строк: {stats['non_empty_lines']} ({stats['non_empty_lines'] / stats['total_lines'] * 100:.1f}%)")
        logger.info(f"  Заголовков: {stats['header_lines']}")
        logger.info(f"  Категорий: {len(stats['categories'])}")
        logger.info(f"  Строк с API: {stats['table_lines']}")
        logger.info(f"  Строк индекса: {stats['index_lines']}")

        if stats['categories']:
            logger.info(f"  Категории: {', '.join(stats['categories'][:3])}")
            if len(stats['categories']) > 3:
                logger.info(f"  ... и ещё {len(stats['categories']) - 3}")

        file_format_err_msgs = check_file_format(lines)

        if file_format_err_msgs:
            logger.error("=" * 80)
            logger.error("РЕЗУЛЬТАТ ПРОВЕРКИ: НЕУДАЧА ❌")
            logger.error("=" * 80)

            # Анализ типов ошибок
            error_categories = Counter()
            for err_msg in file_format_err_msgs:
                print(err_msg)
                logger.error(err_msg)

                # Классификация ошибок
                if "alphabetical" in err_msg.lower():
                    error_categories['alphabetical_order'] += 1
                elif "title" in err_msg.lower():
                    error_categories['title_format'] += 1
                elif "description" in err_msg.lower():
                    error_categories['description'] += 1
                elif "auth" in err_msg.lower():
                    error_categories['auth'] += 1
                elif "https" in err_msg.lower():
                    error_categories['https'] += 1
                elif "cors" in err_msg.lower():
                    error_categories['cors'] += 1
                elif "category" in err_msg.lower() and "index" in err_msg.lower():
                    error_categories['index_missing'] += 1
                elif "minimum" in err_msg.lower():
                    error_categories['min_entries'] += 1
                elif "columns" in err_msg.lower():
                    error_categories['column_count'] += 1
                elif "segment" in err_msg.lower():
                    error_categories['formatting'] += 1
                else:
                    error_categories['other'] += 1

            # Детальная статистика ошибок
            logger.error("ДЕТАЛЬНАЯ СТАТИСТИКА ОШИБОК:")
            for err_type, count in sorted(error_categories.items(), key=lambda x: x[1], reverse=True):
                percentage = count / len(file_format_err_msgs) * 100
                logger.error(f"  {err_type.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")

            logger.error(f"Всего ошибок: {len(file_format_err_msgs)}")
            logger.error("=" * 80)
            sys.exit(1)
        else:
            logger.info("=" * 80)
            logger.info("РЕЗУЛЬТАТ ПРОВЕРКИ: УСПЕХ ✅")
            logger.info("=" * 80)
            logger.info("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
            logger.info("Файл соответствует всем требованиям формата.")

    except FileNotFoundError:
        error_msg = f"Файл не найден: {filename}"
        logger.critical(error_msg)
        print(error_msg)
        sys.exit(1)
    except UnicodeDecodeError as e:
        error_msg = f"Ошибка кодировки файла: {str(e)}"
        logger.critical(error_msg, exc_info=True)
        print(error_msg)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Неожиданная ошибка: {str(e)}"
        logger.critical(error_msg, exc_info=True)
        print(error_msg)
        sys.exit(1)


if __name__ == '__main__':
    logger.debug("=" * 80)
    logger.debug("СКРИПТ ЗАПУЩЕН НАПРЯМУЮ")
    logger.debug(f"Python: {sys.version}")
    logger.debug(f"Платформа: {sys.platform}")
    logger.debug(f"Аргументы: {sys.argv}")
    logger.debug(f"Рабочая директория: {os.getcwd()}")
    logger.debug("=" * 80)

    num_args = len(sys.argv)

    if num_args < 2:
        error_msg = 'No .md file passed (file should contain Markdown table syntax)'
        logger.error(error_msg)
        print(error_msg)
        sys.exit(1)

    filename = sys.argv[1]
    logger.info(f"Целевой файл: {filename}")

    main(filename)