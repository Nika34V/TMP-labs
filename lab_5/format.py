# -*- coding: utf-8 -*-

import re
import sys
import os
import time
import json
from string import punctuation
from typing import List, Tuple, Dict, Set, Optional, Any
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from datetime import datetime

# Импорт модуля логирования
from logger_config import (
    logger,
    validation_logger,
    field_logger,
    entry_logger,
    stats_logger,
    get_module_logger
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


@dataclass
class APIEntry:
    """Класс для представления записи API"""
    line_number: int
    title: str
    description: str
    auth: str
    https: str
    cors: str
    category: str = ""
    raw_line: str = ""

    def to_dict(self) -> Dict:
        """Конвертирует в словарь"""
        return asdict(self)

    def get_validation_data(self) -> Dict:
        """Возвращает данные для валидации"""
        return {
            'line': self.line_number,
            'title': self.title,
            'description_length': len(self.description),
            'auth': self.auth,
            'https': self.https,
            'cors': self.cors,
            'category': self.category
        }


@dataclass
class ValidationResult:
    """Результат валидации одного поля"""
    field_name: str
    is_valid: bool
    message: str
    expected: Any = None
    actual: Any = None
    severity: str = "error"  # error, warning, info

    def to_log_dict(self) -> Dict:
        """Конвертирует в словарь для логирования"""
        return {
            'field': self.field_name,
            'valid': self.is_valid,
            'message': self.message,
            'expected': self.expected,
            'actual': self.actual,
            'severity': self.severity
        }


@dataclass
class EntryValidationSummary:
    """Сводка по валидации записи"""
    entry_number: int
    total_checks: int
    passed_checks: int
    failed_checks: int
    warnings: int
    entry_data: Dict
    validation_results: List[ValidationResult]

    @property
    def success_rate(self) -> float:
        """Процент успешных проверок"""
        if self.total_checks == 0:
            return 0.0
        return (self.passed_checks / self.total_checks) * 100

    def to_dict(self) -> Dict:
        """Конвертирует в словарь"""
        return {
            'entry_number': self.entry_number,
            'total_checks': self.total_checks,
            'passed_checks': self.passed_checks,
            'failed_checks': self.failed_checks,
            'warnings': self.warnings,
            'success_rate': self.success_rate,
            'entry_data': self.entry_data,
            'results': [r.to_log_dict() for r in self.validation_results]
        }


class EntryValidator:
    """Валидатор записей API"""

    def __init__(self):
        self.stats = {
            'total_entries': 0,
            'total_checks': 0,
            'passed_checks': 0,
            'failed_checks': 0,
            'warnings': 0,
            'by_field': defaultdict(lambda: {'passed': 0, 'failed': 0}),
            'by_category': defaultdict(lambda: {'entries': 0, 'passed': 0, 'failed': 0}),
            'validation_times': []
        }

    def validate_entry(self, line_num: int, segments: List[str], category: str = "") -> List[ValidationResult]:
        """Валидирует одну запись API"""
        start_time = time.time()

        field_logger.info(f"Начало валидации записи на строке {line_num + 1}")

        # Создаём объект записи
        entry = APIEntry(
            line_number=line_num + 1,
            title=segments[index_title] if len(segments) > index_title else "",
            description=segments[index_desc] if len(segments) > index_desc else "",
            auth=segments[index_auth] if len(segments) > index_auth else "",
            https=segments[index_https] if len(segments) > index_https else "",
            cors=segments[index_cors] if len(segments) > index_cors else "",
            category=category,
            raw_line="|".join(segments)
        )

        # Выполняем проверки
        validation_results = []

        # Проверка заголовка
        title_results = self._validate_title(line_num, entry.title)
        validation_results.extend(title_results)

        # Проверка описания
        desc_results = self._validate_description(line_num, entry.description)
        validation_results.extend(desc_results)

        # Проверка аутентификации
        auth_results = self._validate_auth(line_num, entry.auth)
        validation_results.extend(auth_results)

        # Проверка HTTPS
        https_results = self._validate_https(line_num, entry.https)
        validation_results.extend(https_results)

        # Проверка CORS
        cors_results = self._validate_cors(line_num, entry.cors)
        validation_results.extend(cors_results)

        # Обновляем статистику
        self._update_statistics(entry, validation_results)

        # Создаём сводку
        summary = self._create_validation_summary(entry, validation_results)

        # Логируем результат
        self._log_validation_result(entry, summary)

        # Измеряем время
        elapsed_time = time.time() - start_time
        self.stats['validation_times'].append(elapsed_time)

        field_logger.debug(f"Валидация записи завершена за {elapsed_time:.3f} секунд")

        return validation_results

    def _validate_title(self, line_num: int, raw_title: str) -> List[ValidationResult]:
        """Валидация заголовка"""
        field_logger.debug(f"Валидация заголовка: '{raw_title[:50]}...'")

        results = []
        entry_data = {'line': line_num + 1, 'field': 'title', 'value': raw_title}

        # Проверка синтаксиса Markdown ссылки
        title_match = link_re.match(raw_title)
        if not title_match:
            result = ValidationResult(
                field_name="title",
                is_valid=False,
                message='Title syntax should be "[TITLE](LINK)"',
                expected="[TITLE](URL)",
                actual=raw_title,
                severity="error"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.ERROR, entry_data, "title_syntax", "[TITLE](LINK)", raw_title, "failed"
            )
        else:
            title = title_match.group(1)

            # Проверка на окончание "API"
            if title.upper().endswith(' API'):
                result = ValidationResult(
                    field_name="title",
                    is_valid=False,
                    message='Title should not end with "... API"',
                    expected="Not ending with 'API'",
                    actual=title,
                    severity="error"
                )
                results.append(result)

                validation_logger.log_validation_result(
                    logging.ERROR, entry_data, "title_ending", "Not ending with 'API'", title, "failed"
                )
            else:
                result = ValidationResult(
                    field_name="title",
                    is_valid=True,
                    message="Title syntax is correct",
                    severity="info"
                )
                results.append(result)

                validation_logger.log_validation_result(
                    logging.INFO, entry_data, "title_syntax", "[TITLE](LINK)", raw_title, "passed"
                )

        return results

    def _validate_description(self, line_num: int, description: str) -> List[ValidationResult]:
        """Валидация описания"""
        field_logger.debug(f"Валидация описания (длина: {len(description)}): '{description[:50]}...'")

        results = []
        entry_data = {'line': line_num + 1, 'field': 'description', 'value': description[:100]}

        # Проверка заглавной первой буквы
        first_char = description[0] if description else ''
        if first_char and first_char.upper() != first_char:
            result = ValidationResult(
                field_name="description",
                is_valid=False,
                message='First character of description is not capitalized',
                expected="Capital letter",
                actual=first_char,
                severity="error"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.ERROR, entry_data, "description_capitalization", "Capital letter", first_char, "failed"
            )
        else:
            result = ValidationResult(
                field_name="description",
                is_valid=True,
                message="Description starts with capital letter",
                severity="info"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.INFO, entry_data, "description_capitalization", "Capital letter", first_char, "passed"
            )

        # Проверка пунктуации в конце
        last_char = description[-1] if description else ''
        if last_char in punctuation:
            result = ValidationResult(
                field_name="description",
                is_valid=False,
                message=f'Description should not end with {last_char}',
                expected="No punctuation at end",
                actual=last_char,
                severity="error"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.ERROR, entry_data, "description_punctuation", "No punctuation", last_char, "failed"
            )
        else:
            result = ValidationResult(
                field_name="description",
                is_valid=True,
                message="Description ends without punctuation",
                severity="info"
            )
            results.append(result)

        # Проверка длины
        desc_length = len(description)
        if desc_length > max_description_length:
            result = ValidationResult(
                field_name="description",
                is_valid=False,
                message=f'Description should not exceed {max_description_length} characters',
                expected=f"≤ {max_description_length} chars",
                actual=f"{desc_length} chars",
                severity="error"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.ERROR, entry_data, "description_length", f"≤ {max_description_length}", desc_length, "failed"
            )
        else:
            # Предупреждение для слишком коротких описаний
            if desc_length < 20:
                result = ValidationResult(
                    field_name="description",
                    is_valid=True,
                    message="Description is very short",
                    expected="≥ 20 chars recommended",
                    actual=f"{desc_length} chars",
                    severity="warning"
                )
                results.append(result)
                self.stats['warnings'] += 1

                validation_logger.log_validation_result(
                    logging.WARNING, entry_data, "description_length", "≥ 20 recommended", desc_length, "warning"
                )
            else:
                result = ValidationResult(
                    field_name="description",
                    is_valid=True,
                    message=f"Description length is acceptable ({desc_length} chars)",
                    severity="info"
                )
                results.append(result)

        return results

    def _validate_auth(self, line_num: int, auth: str) -> List[ValidationResult]:
        """Валидация поля аутентификации"""
        field_logger.debug(f"Валидация аутентификации: '{auth}'")

        results = []
        entry_data = {'line': line_num + 1, 'field': 'auth', 'value': auth}

        backtick = '`'
        auth_clean = auth.replace(backtick, '')

        # Проверка обратных кавычек для не-"No" значений
        if auth_clean != 'No' and (not auth.startswith(backtick) or not auth.endswith(backtick)):
            result = ValidationResult(
                field_name="auth",
                is_valid=False,
                message='Auth value is not enclosed with `backticks`',
                expected=f"`{auth_clean}`",
                actual=auth,
                severity="error"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.ERROR, entry_data, "auth_backticks", f"`{auth_clean}`", auth, "failed"
            )
        else:
            result = ValidationResult(
                field_name="auth",
                is_valid=True,
                message="Auth value properly formatted",
                severity="info"
            )
            results.append(result)

        # Проверка допустимых значений
        if auth_clean not in auth_keys:
            result = ValidationResult(
                field_name="auth",
                is_valid=False,
                message=f'{auth} is not a valid Auth option',
                expected=f"One of {auth_keys}",
                actual=auth,
                severity="error"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.ERROR, entry_data, "auth_value", auth_keys, auth, "failed"
            )
        else:
            result = ValidationResult(
                field_name="auth",
                is_valid=True,
                message=f"Auth value '{auth_clean}' is valid",
                severity="info"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.INFO, entry_data, "auth_value", auth_keys, auth_clean, "passed"
            )

        return results

    def _validate_https(self, line_num: int, https: str) -> List[ValidationResult]:
        """Валидация поля HTTPS"""
        field_logger.debug(f"Валидация HTTPS: '{https}'")

        results = []
        entry_data = {'line': line_num + 1, 'field': 'https', 'value': https}

        if https not in https_keys:
            result = ValidationResult(
                field_name="https",
                is_valid=False,
                message=f'{https} is not a valid HTTPS option',
                expected=f"One of {https_keys}",
                actual=https,
                severity="error"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.ERROR, entry_data, "https_value", https_keys, https, "failed"
            )
        else:
            result = ValidationResult(
                field_name="https",
                is_valid=True,
                message=f"HTTPS value '{https}' is valid",
                severity="info"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.INFO, entry_data, "https_value", https_keys, https, "passed"
            )

        return results

    def _validate_cors(self, line_num: int, cors: str) -> List[ValidationResult]:
        """Валидация поля CORS"""
        field_logger.debug(f"Валидация CORS: '{cors}'")

        results = []
        entry_data = {'line': line_num + 1, 'field': 'cors', 'value': cors}

        if cors not in cors_keys:
            result = ValidationResult(
                field_name="cors",
                is_valid=False,
                message=f'{cors} is not a valid CORS option',
                expected=f"One of {cors_keys}",
                actual=cors,
                severity="error"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.ERROR, entry_data, "cors_value", cors_keys, cors, "failed"
            )
        else:
            result = ValidationResult(
                field_name="cors",
                is_valid=True,
                message=f"CORS value '{cors}' is valid",
                severity="info"
            )
            results.append(result)

            validation_logger.log_validation_result(
                logging.INFO, entry_data, "cors_value", cors_keys, cors, "passed"
            )

        return results

    def _update_statistics(self, entry: APIEntry, results: List[ValidationResult]):
        """Обновляет статистику валидации"""
        self.stats['total_entries'] += 1
        self.stats['total_checks'] += len(results)

        # Статистика по категориям
        if entry.category:
            cat_stats = self.stats['by_category'][entry.category]
            cat_stats['entries'] += 1

            # Считаем успешные/неуспешные проверки для этой записи
            passed_in_entry = sum(1 for r in results if r.is_valid and r.severity != 'warning')
            failed_in_entry = sum(1 for r in results if not r.is_valid)

            cat_stats['passed'] += passed_in_entry
            cat_stats['failed'] += failed_in_entry

        # Статистика по полям
        for result in results:
            field_stats = self.stats['by_field'][result.field_name]
            if result.is_valid and result.severity != 'warning':
                field_stats['passed'] += 1
                self.stats['passed_checks'] += 1
            elif not result.is_valid:
                field_stats['failed'] += 1
                self.stats['failed_checks'] += 1
            elif result.severity == 'warning':
                self.stats['warnings'] += 1

    def _create_validation_summary(self, entry: APIEntry, results: List[ValidationResult]) -> EntryValidationSummary:
        """Создаёт сводку по валидации записи"""
        total_checks = len(results)
        passed_checks = sum(1 for r in results if r.is_valid and r.severity != 'warning')
        failed_checks = sum(1 for r in results if not r.is_valid)
        warnings = sum(1 for r in results if r.severity == 'warning')

        return EntryValidationSummary(
            entry_number=self.stats['total_entries'],
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            warnings=warnings,
            entry_data=entry.get_validation_data(),
            validation_results=results
        )

    def _log_validation_result(self, entry: APIEntry, summary: EntryValidationSummary):
        """Логирует результат валидации записи"""
        entry_data = {
            'line': entry.line_number,
            'title': entry.title[:50] + '...' if len(entry.title) > 50 else entry.title,
            'category': entry.category,
            'validation_summary': summary.to_dict()
        }

        if summary.failed_checks > 0:
            entry_logger.warning(
                f"Entry #{summary.entry_number} (L{entry.line_number}): FAILED - {summary.failed_checks} errors",
                extra={'api_entry': entry_data, 'validation_type': 'entry_failed'}
            )
        elif summary.warnings > 0:
            entry_logger.info(
                f"Entry #{summary.entry_number} (L{entry.line_number}): PASSED with {summary.warnings} warnings",
                extra={'api_entry': entry_data, 'validation_type': 'entry_warning'}
            )
        else:
            entry_logger.info(
                f"Entry #{summary.entry_number} (L{entry.line_number}): PASSED - all checks OK",
                extra={'api_entry': entry_data, 'validation_type': 'entry_passed'}
            )

        # Детальное логирование через специализированный логгер
        validation_logger.log_entry_validation(
            summary.entry_number,
            summary.total_checks,
            summary.passed_checks,
            summary.failed_checks,
            entry_data
        )

    def get_statistics(self) -> Dict:
        """Возвращает статистику валидации"""
        total_time = sum(self.stats['validation_times']) if self.stats['validation_times'] else 0
        avg_time = total_time / len(self.stats['validation_times']) if self.stats['validation_times'] else 0

        stats = self.stats.copy()
        stats['total_validation_time'] = total_time
        stats['average_validation_time'] = avg_time

        if stats['total_checks'] > 0:
            stats['success_rate'] = (stats['passed_checks'] / stats['total_checks']) * 100
        else:
            stats['success_rate'] = 0

        # Добавляем статистику по полям
        stats['field_success_rates'] = {}
        for field, field_stats in stats['by_field'].items():
            total = field_stats['passed'] + field_stats['failed']
            if total > 0:
                stats['field_success_rates'][field] = (field_stats['passed'] / total) * 100

        # Статистика по категориям
        stats['category_success_rates'] = {}
        for category, cat_stats in stats['by_category'].items():
            total_checks = cat_stats['passed'] + cat_stats['failed']
            if total_checks > 0:
                stats['category_success_rates'][category] = (cat_stats['passed'] / total_checks) * 100

        return stats

    def log_final_statistics(self):
        """Логирует итоговую статистику"""
        stats = self.get_statistics()

        stats_logger.info("=" * 100)
        stats_logger.info("ИТОГОВАЯ СТАТИСТИКА ВАЛИДАЦИИ")
        stats_logger.info("=" * 100)

        stats_logger.info(f"Всего записей: {stats['total_entries']}")
        stats_logger.info(f"Всего проверок: {stats['total_checks']}")
        stats_logger.info(f"Успешных проверок: {stats['passed_checks']} ({stats.get('success_rate', 0):.1f}%)")
        stats_logger.info(f"Неуспешных проверок: {stats['failed_checks']}")
        stats_logger.info(f"Предупреждений: {stats['warnings']}")
        stats_logger.info(f"Общее время валидации: {stats['total_validation_time']:.3f} сек")
        stats_logger.info(f"Среднее время на запись: {stats['average_validation_time']:.3f} сек")

        # Статистика по полям
        stats_logger.info("\nСТАТИСТИКА ПО ПОЛЯМ:")
        for field, field_stats in sorted(stats['by_field'].items()):
            total = field_stats['passed'] + field_stats['failed']
            success_rate = stats['field_success_rates'].get(field, 0)
            stats_logger.info(f"  {field:15s}: {field_stats['passed']:3d}/{total:3d} ({success_rate:5.1f}%)")

        # Статистика по категориям
        if stats['by_category']:
            stats_logger.info("\nСТАТИСТИКА ПО КАТЕГОРИЯМ:")
            for category, cat_stats in sorted(stats['by_category'].items()):
                total_checks = cat_stats['passed'] + cat_stats['failed']
                success_rate = stats['category_success_rates'].get(category, 0)
                stats_logger.info(
                    f"  {category:20s}: {cat_stats['entries']:2d} entries, {cat_stats['passed']:3d}/{total_checks:3d} checks ({success_rate:5.1f}%)")

        stats_logger.info("=" * 100)

        # Сохраняем статистику в JSON для дальнейшего анализа
        self._save_statistics_to_file(stats)

    def _save_statistics_to_file(self, stats: Dict):
        """Сохраняет статистику в JSON файл"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        stats_file = log_dir / f"validation_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False, default=str)
            stats_logger.info(f"Статистика сохранена в: {stats_file}")
        except Exception as e:
            stats_logger.error(f"Ошибка сохранения статистики: {e}")


def error_message(line_number: int, message: str) -> str:
    line = line_number + 1
    return f'(L{line:03d}) {message}'


def get_categories_content(contents: List[str]) -> Tuple[Categories, CategoriesLineNumber]:
    """Извлекает категории и их содержимое из файла"""
    module_logger.info("Начало извлечения категорий и API из файла")

    categories = {}
    category_line_num = {}
    current_category = None
    api_count_in_category = 0

    for line_num, line_content in enumerate(contents):
        if line_content.startswith(anchor):
            # Сохраняем статистику предыдущей категории
            if current_category and api_count_in_category > 0:
                module_logger.debug(f"Категория '{current_category}': {api_count_in_category} API")

            category = line_content.split(anchor)[1].strip()
            categories[category] = []
            category_line_num[category] = line_num
            current_category = category
            api_count_in_category = 0

            module_logger.info(f"Обнаружена категория: '{category}' на строке {line_num + 1}")
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
                module_logger.debug(f"API #{api_count_in_category} в '{current_category}': {title}")

    # Логируем статистику по последней категории
    if current_category and api_count_in_category > 0:
        module_logger.debug(f"Категория '{current_category}': {api_count_in_category} API")

    module_logger.info(f"Извлечение завершено: {len(categories)} категорий")
    for category, api_list in categories.items():
        module_logger.debug(f"  '{category}': {len(api_list)} API")

    return (categories, category_line_num)


def check_file_format(lines: List[str]) -> List[str]:
    """Основная функция проверки формата файла"""
    logger.info("=" * 100)
    logger.info(f"НАЧАЛО ПРОВЕРКИ ФОРМАТА ФАЙЛА")
    logger.info("=" * 100)

    start_time = time.time()

    err_msgs = []
    category_title_in_index = []

    # Создаём валидатор
    validator = EntryValidator()
    entry_logger.info("Валидатор записей инициализирован")

    # Получение категорий из файла
    categories, category_line_num = get_categories_content(lines)

    # Проверка отдельных записей
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
                current_category = category_name
                category_start_line = line_num

                logger.info(f"Обработка категории: '{current_category}'")

            continue

        # Пропускаем неинтересные строки
        if not line_content.startswith('|') or line_content.startswith('|---'):
            continue

        # Проверяем запись
        total_entries += 1
        entries_by_category[current_category] += 1

        segments = line_content.split('|')[1:-1]

        # Проверка количества колонок
        if len(segments) < num_segments:
            err_msg = error_message(line_num,
                                    f'entry does not have all the required columns (have {len(segments)}, need {num_segments})')
            err_msgs.append(err_msg)
            entry_logger.error(
                f"Недостаточно колонок в записи на строке {line_num + 1}: {len(segments)} вместо {num_segments}")
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
            field_logger.warning(f"Проблемы с пробелами в записи на строке {line_num + 1}: позиции {spacing_issues}")

        segments = [segment.strip() for segment in segments]

        # Валидация записи
        validation_results = validator.validate_entry(line_num, segments, current_category)

        # Конвертируем результаты валидации в сообщения об ошибках
        for result in validation_results:
            if not result.is_valid:
                err_msg = error_message(line_num, result.message)
                err_msgs.append(err_msg)

        # Логируем прогресс
        if total_entries % 5 == 0:
            entry_logger.info(f"Проверено {total_entries} записей...")

    # Логируем итоговую статистику валидации
    validator.log_final_statistics()

    # Вывод общей статистики
    elapsed_time = time.time() - start_time

    logger.info("=" * 100)
    logger.info("ОБЩАЯ СТАТИСТИКА ПРОВЕРКИ")
    logger.info("=" * 100)
    logger.info(f"Общее время проверки: {elapsed_time:.2f} секунд")
    logger.info(f"Всего записей API: {total_entries}")
    logger.info(f"Всего категорий: {len(categories)}")
    logger.info(f"Найдено ошибок: {len(err_msgs)}")

    # Статистика по категориям
    if entries_by_category:
        logger.info("Записей по категориям:")
        for category, count in sorted(entries_by_category.items()):
            logger.info(f"  {category}: {count} записей")

    logger.info("=" * 100)

    return err_msgs


def analyze_file_content(lines: List[str]) -> Dict:
    """
    Анализ содержимого файла для логирования статистики

    Args:
        lines: Строки файла

    Returns:
        Словарь со статистикой
    """
    module_logger.info("Анализ содержимого файла")

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

    module_logger.info(f"Анализ завершен: {stats['total_lines']} строк, {len(stats['categories'])} категорий")
    module_logger.debug(f"Распределение по типам строк: {dict(stats['lines_by_type'])}")

    return stats


def main(filename: str) -> None:
    logger.info("=" * 100)
    logger.info(f"ЗАПУСК ПРОГРАММЫ ПРОВЕРКИ API-ЛИСТА")
    logger.info(f"Файл: {filename}")
    logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 100)

    try:
        # Логирование информации о файле
        if not os.path.exists(filename):
            error_msg = f"Файл не найден: {filename}"
            logger.critical(error_msg)
            print(error_msg)
            sys.exit(1)

        file_size = os.path.getsize(filename)
        file_mtime = datetime.fromtimestamp(os.path.getmtime(filename)).strftime('%Y-%m-%d %H:%M:%S')

        logger.info(f"Информация о файле:")
        logger.info(f"  Размер: {file_size} байт ({file_size / 1024:.1f} KB)")
        logger.info(f"  Путь: {os.path.abspath(filename)}")
        logger.info(f"  Время изменения: {file_mtime}")

        with open(filename, mode='r', encoding='utf-8') as file:
            lines = list(line.rstrip() for line in file)

        # Анализ содержимого файла
        stats = analyze_file_content(lines)

        logger.info("СТАТИСТИКА ФАЙЛА:")
        logger.info(f"  Всего строк: {stats['total_lines']}")
        logger.info(
            f"  Непустых строк: {stats['non_empty_lines']} ({stats['non_empty_lines'] / stats['total_lines'] * 100:.1f}%)")
        logger.info(f"  Категорий: {len(stats['categories'])}")
        logger.info(f"  Строк с API: {stats['table_lines']}")

        file_format_err_msgs = check_file_format(lines)

        if file_format_err_msgs:
            logger.error("=" * 100)
            logger.error("РЕЗУЛЬТАТ ПРОВЕРКИ: НЕУДАЧА ❌")
            logger.error("=" * 100)

            # Анализ типов ошибок
            error_categories = Counter()
            for err_msg in file_format_err_msgs:
                print(err_msg)
                logger.error(err_msg, extra={'validation_type': 'error_output'})

                # Классификация ошибок
                err_lower = err_msg.lower()
                if "title" in err_lower:
                    error_categories['title'] += 1
                elif "description" in err_lower:
                    error_categories['description'] += 1
                elif "auth" in err_lower:
                    error_categories['auth'] += 1
                elif "https" in err_lower:
                    error_categories['https'] += 1
                elif "cors" in err_lower:
                    error_categories['cors'] += 1
                elif "column" in err_lower:
                    error_categories['columns'] += 1
                elif "segment" in err_lower:
                    error_categories['formatting'] += 1
                else:
                    error_categories['other'] += 1

            # Детальная статистика ошибок
            logger.error("ДЕТАЛЬНАЯ СТАТИСТИКА ОШИБОК:")
            for err_type, count in sorted(error_categories.items(), key=lambda x: x[1], reverse=True):
                percentage = count / len(file_format_err_msgs) * 100
                logger.error(f"  {err_type.title()}: {count} ({percentage:.1f}%)")

            logger.error(f"Всего ошибок: {len(file_format_err_msgs)}")
            logger.error("=" * 100)
            sys.exit(1)
        else:
            logger.info("=" * 100)
            logger.info("РЕЗУЛЬТАТ ПРОВЕРКИ: УСПЕХ ✅")
            logger.info("=" * 100)
            logger.info("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
            logger.info("Файл соответствует всем требованиям формата.")

    except FileNotFoundError:
        error_msg = f"Файл не найден: {filename}"
        logger.critical(error_msg, exc_info=True)
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
    logger.debug("=" * 100)
    logger.debug("СКРИПТ ЗАПУЩЕН НАПРЯМУЮ")
    logger.debug(f"Python: {sys.version}")
    logger.debug(f"Аргументы: {sys.argv}")
    logger.debug("=" * 100)

    num_args = len(sys.argv)

    if num_args < 2:
        error_msg = 'No .md file passed (file should contain Markdown table syntax)'
        logger.error(error_msg)
        print(error_msg)
        sys.exit(1)

    filename = sys.argv[1]
    logger.info(f"Целевой файл: {filename}")

    main(filename)