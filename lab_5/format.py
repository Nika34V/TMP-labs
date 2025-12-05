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
from contextlib import contextmanager

# Импорт расширенного модуля логирования
from logger_config import (
    main_logger,
    validation_logger,
    error_logger,
    stats_logger,
    perf_logger,
    exception_logger,
    get_error_tracker,
    get_exception_stats,
    StructuredLogger
)

# Получаем структурированный логгер для текущего модуля
module_logger = StructuredLogger("api_format_checker.format_checker")

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
class ValidationError:
    """Класс для представления ошибки валидации"""
    line_number: int
    error_type: str
    message: str
    severity: str  # critical, error, warning
    field: Optional[str] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    context: Optional[Dict] = None
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Конвертирует в словарь для логирования"""
        return {
            'line': self.line_number,
            'type': self.error_type,
            'message': self.message,
            'severity': self.severity,
            'field': self.field,
            'expected': self.expected,
            'actual': self.actual,
            'context': self.context or {},
            'timestamp': self.timestamp
        }

    def to_error_message(self) -> str:
        """Форматирует ошибку для вывода пользователю"""
        line = self.line_number + 1
        return f'(L{line:03d}) {self.message}'


class ErrorCollector:
    """Коллектор для сбора и обработки ошибок"""

    def __init__(self):
        self.errors = []
        self.error_counts = Counter()
        self.severity_counts = Counter()
        self.field_counts = defaultdict(Counter)
        self.start_time = time.time()

    def add_error(self, error: ValidationError):
        """Добавляет ошибку в коллектор"""
        self.errors.append(error)
        self.error_counts[error.error_type] += 1
        self.severity_counts[error.severity] += 1

        if error.field:
            self.field_counts[error.field][error.error_type] += 1

        # Логируем ошибку
        self._log_error(error)

    def _log_error(self, error: ValidationError):
        """Логирует ошибку с использованием структурированного логгера"""
        error_data = error.to_dict()

        if error.severity == 'critical':
            error_logger.critical(
                f"Critical validation error at line {error.line_number + 1}: {error.message}",
                extra={
                    'error_type': 'validation_critical',
                    'validation_details': error_data,
                    'line_number': error.line_number
                }
            )
        elif error.severity == 'error':
            error_logger.error(
                f"Validation error at line {error.line_number + 1}: {error.message}",
                extra={
                    'error_type': 'validation_error',
                    'validation_details': error_data,
                    'line_number': error.line_number
                }
            )
        elif error.severity == 'warning':
            error_logger.warning(
                f"Validation warning at line {error.line_number + 1}: {error.message}",
                extra={
                    'error_type': 'validation_warning',
                    'validation_details': error_data,
                    'line_number': error.line_number
                }
            )

    def add_errors(self, errors: List[ValidationError]):
        """Добавляет несколько ошибок"""
        for error in errors:
            self.add_error(error)

    def get_stats(self) -> Dict:
        """Возвращает статистику по ошибкам"""
        elapsed = time.time() - self.start_time

        return {
            'total_errors': len(self.errors),
            'error_types': dict(self.error_counts),
            'severity_distribution': dict(self.severity_counts),
            'field_distribution': {field: dict(counts) for field, counts in self.field_counts.items()},
            'collection_time': elapsed,
            'errors_per_second': len(self.errors) / elapsed if elapsed > 0 else 0
        }

    def log_summary(self):
        """Логирует сводку по ошибкам"""
        stats = self.get_stats()

        error_logger.info("=" * 100)
        error_logger.info("СВОДКА ПО ОШИБКАМ ВАЛИДАЦИИ")
        error_logger.info("=" * 100)

        error_logger.info(f"Всего ошибок: {stats['total_errors']}")
        error_logger.info(f"Время сбора: {stats['collection_time']:.2f} сек")
        error_logger.info(f"Ошибок в секунду: {stats['errors_per_second']:.1f}")

        if stats['severity_distribution']:
            error_logger.info("Распределение по степени серьезности:")
            for severity, count in sorted(stats['severity_distribution'].items()):
                percentage = (count / stats['total_errors'] * 100) if stats['total_errors'] > 0 else 0
                error_logger.info(f"  {severity:10s}: {count:4d} ({percentage:5.1f}%)")

        if stats['error_types']:
            error_logger.info("Типы ошибок:")
            for error_type, count in sorted(stats['error_types'].items(), key=lambda x: x[1], reverse=True)[:10]:
                percentage = (count / stats['total_errors'] * 100) if stats['total_errors'] > 0 else 0
                error_logger.info(f"  {error_type:30s}: {count:4d} ({percentage:5.1f}%)")

        if stats['field_distribution']:
            error_logger.info("Ошибки по полям:")
            for field, error_counts in sorted(stats['field_distribution'].items()):
                total = sum(error_counts.values())
                error_logger.info(f"  {field:15s}: {total:4d} ошибок")
                for err_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
                    error_logger.info(f"    - {err_type:25s}: {count:3d}")

        error_logger.info("=" * 100)

    def save_to_file(self, filename: Optional[str] = None):
        """Сохраняет ошибки в файл"""
        if not filename:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            filename = log_dir / f"validation_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_errors': len(self.errors),
                'stats': self.get_stats()
            },
            'errors': [error.to_dict() for error in self.errors]
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            error_logger.info(f"Ошибки сохранены в файл: {filename}")
            return filename
        except Exception as e:
            exception_logger.log_exception(e, {'action': 'saving_errors'})
            return None

    def clear(self):
        """Очищает коллектор"""
        self.errors.clear()
        self.error_counts.clear()
        self.severity_counts.clear()
        self.field_counts.clear()
        self.start_time = time.time()


@contextmanager
def error_handling_context(operation: str, context: Optional[Dict] = None):
    """
    Контекстный менеджер для обработки ошибок с логированием

    Args:
        operation: Описание операции для логирования
        context: Дополнительный контекст
    """
    start_time = time.time()
    operation_id = f"{operation}_{datetime.now().strftime('%H%M%S')}"

    module_logger.add_context(
        operation=operation,
        operation_id=operation_id,
        start_time=start_time
    )

    if context:
        module_logger.add_context(**context)

    try:
        module_logger.info(f"Начало операции: {operation}")
        yield
        elapsed = time.time() - start_time
        module_logger.info(f"Операция завершена успешно: {operation} ({elapsed:.2f} сек)")
        perf_logger.log_performance_metric(f"{operation}_time", elapsed * 1000, "ms")

    except Exception as e:
        elapsed = time.time() - start_time
        error_logger.error(f"Ошибка в операции: {operation} ({elapsed:.2f} сек)")

        # Логируем исключение с детальной информацией
        exc_info = exception_logger.log_exception(
            e,
            {
                'operation': operation,
                'operation_id': operation_id,
                'elapsed_time': elapsed,
                **module_logger.context
            }
        )

        # Добавляем метрику ошибки
        perf_logger.log_performance_metric(f"{operation}_error", 1, "count")

        raise
    finally:
        module_logger.clear_context()


def error_message(line_number: int, message: str) -> str:
    """Создаёт форматированное сообщение об ошибке"""
    line = line_number + 1
    return f'(L{line:03d}) {message}'


def create_validation_error(line_num: int, error_type: str, message: str,
                            severity: str = "error", **kwargs) -> ValidationError:
    """
    Создаёт объект ошибки валидации

    Args:
        line_num: Номер строки (0-based)
        error_type: Тип ошибки
        message: Сообщение об ошибке
        severity: Степень серьезности (critical, error, warning)
        **kwargs: Дополнительные параметры

    Returns:
        Объект ValidationError
    """
    return ValidationError(
        line_number=line_num,
        error_type=error_type,
        message=message,
        severity=severity,
        **kwargs
    )


def check_title(line_num: int, raw_title: str, error_collector: Optional[ErrorCollector] = None) -> List[str]:
    """Проверяет заголовок API записи"""
    with error_handling_context("check_title", {"line": line_num + 1, "title": raw_title[:100]}):
        validation_logger.debug(f"Проверка заголовка на строке {line_num + 1}")

        err_msgs = []
        validation_errors = []

        title_match = link_re.match(raw_title)

        # Проверка синтаксиса Markdown ссылки
        if not title_match:
            error = create_validation_error(
                line_num=line_num,
                error_type="title_syntax",
                message='Title syntax should be "[TITLE](LINK)"',
                severity="error",
                field="title",
                expected="[TITLE](URL)",
                actual=raw_title
            )
            validation_errors.append(error)
            err_msgs.append(error.to_error_message())
        else:
            title = title_match.group(1)
            validation_logger.debug(f"Извлечён заголовок: '{title}'")

            # Проверка на окончание "API"
            if title.upper().endswith(' API'):
                error = create_validation_error(
                    line_num=line_num,
                    error_type="title_ending",
                    message='Title should not end with "... API". Every entry is an API here!',
                    severity="error",
                    field="title",
                    expected="Not ending with 'API'",
                    actual=title
                )
                validation_errors.append(error)
                err_msgs.append(error.to_error_message())
            else:
                validation_logger.debug(f"Заголовок корректен: '{title}'")

        # Добавляем ошибки в коллектор если он передан
        if error_collector and validation_errors:
            error_collector.add_errors(validation_errors)

        if not err_msgs:
            validation_logger.debug(f"Заголовок на строке {line_num + 1} прошёл проверку")

        return err_msgs


def check_description(line_num: int, description: str, error_collector: Optional[ErrorCollector] = None) -> List[str]:
    """Проверяет описание API записи"""
    with error_handling_context("check_description", {"line": line_num + 1, "desc_length": len(description)}):
        validation_logger.debug(f"Проверка описания на строке {line_num + 1}")

        err_msgs = []
        validation_errors = []

        first_char = description[0] if description else ''
        if first_char and first_char.upper() != first_char:
            error = create_validation_error(
                line_num=line_num,
                error_type="description_capitalization",
                message='first character of description is not capitalized',
                severity="error",
                field="description",
                expected="Capital letter",
                actual=first_char
            )
            validation_errors.append(error)
            err_msgs.append(error.to_error_message())

        last_char = description[-1] if description else ''
        if last_char in punctuation:
            error = create_validation_error(
                line_num=line_num,
                error_type="description_punctuation",
                message=f'description should not end with {last_char}',
                severity="error",
                field="description",
                expected="No punctuation at end",
                actual=last_char
            )
            validation_errors.append(error)
            err_msgs.append(error.to_error_message())

        desc_length = len(description)
        if desc_length > max_description_length:
            error = create_validation_error(
                line_num=line_num,
                error_type="description_length",
                message=f'description should not exceed {max_description_length} characters (currently {desc_length})',
                severity="error",
                field="description",
                expected=f"≤ {max_description_length} chars",
                actual=f"{desc_length} chars"
            )
            validation_errors.append(error)
            err_msgs.append(error.to_error_message())
        elif desc_length < 20:
            # Предупреждение для слишком коротких описаний
            error = create_validation_error(
                line_num=line_num,
                error_type="description_too_short",
                message=f'description is very short ({desc_length} characters)',
                severity="warning",
                field="description",
                expected="≥ 20 chars recommended",
                actual=f"{desc_length} chars"
            )
            validation_errors.append(error)
            # Предупреждения не добавляем в err_msgs, так как это не ошибки

        # Добавляем ошибки в коллектор если он передан
        if error_collector and validation_errors:
            error_collector.add_errors(validation_errors)

        if not err_msgs:
            validation_logger.debug(f"Описание на строке {line_num + 1} прошло проверку")

        return err_msgs


def check_auth(line_num: int, auth: str, error_collector: Optional[ErrorCollector] = None) -> List[str]:
    """Проверяет поле аутентификации"""
    with error_handling_context("check_auth", {"line": line_num + 1, "auth_value": auth}):
        validation_logger.debug(f"Проверка аутентификации на строке {line_num + 1}")

        err_msgs = []
        validation_errors = []

        backtick = '`'
        auth_clean = auth.replace(backtick, '')

        # Проверка обратных кавычек для не-"No" значений
        if auth_clean != 'No' and (not auth.startswith(backtick) or not auth.endswith(backtick)):
            error = create_validation_error(
                line_num=line_num,
                error_type="auth_backticks",
                message='auth value is not enclosed with `backticks`',
                severity="error",
                field="auth",
                expected=f"`{auth_clean}`",
                actual=auth
            )
            validation_errors.append(error)
            err_msgs.append(error.to_error_message())

        # Проверка допустимых значений
        if auth_clean not in auth_keys:
            error = create_validation_error(
                line_num=line_num,
                error_type="auth_invalid_value",
                message=f'{auth} is not a valid Auth option',
                severity="error",
                field="auth",
                expected=f"One of {auth_keys}",
                actual=auth
            )
            validation_errors.append(error)
            err_msgs.append(error.to_error_message())

        # Добавляем ошибки в коллектор если он передан
        if error_collector and validation_errors:
            error_collector.add_errors(validation_errors)

        if not err_msgs:
            validation_logger.debug(f"Аутентификация на строке {line_num + 1} корректна")

        return err_msgs


def check_https(line_num: int, https: str, error_collector: Optional[ErrorCollector] = None) -> List[str]:
    """Проверяет поле HTTPS"""
    with error_handling_context("check_https", {"line": line_num + 1, "https_value": https}):
        validation_logger.debug(f"Проверка HTTPS на строке {line_num + 1}")

        err_msgs = []
        validation_errors = []

        if https not in https_keys:
            error = create_validation_error(
                line_num=line_num,
                error_type="https_invalid_value",
                message=f'{https} is not a valid HTTPS option',
                severity="error",
                field="https",
                expected=f"One of {https_keys}",
                actual=https
            )
            validation_errors.append(error)
            err_msgs.append(error.to_error_message())

        # Добавляем ошибки в коллектор если он передан
        if error_collector and validation_errors:
            error_collector.add_errors(validation_errors)

        if not err_msgs:
            validation_logger.debug(f"HTTPS на строке {line_num + 1} корректен")

        return err_msgs


def check_cors(line_num: int, cors: str, error_collector: Optional[ErrorCollector] = None) -> List[str]:
    """Проверяет поле CORS"""
    with error_handling_context("check_cors", {"line": line_num + 1, "cors_value": cors}):
        validation_logger.debug(f"Проверка CORS на строке {line_num + 1}")

        err_msgs = []
        validation_errors = []

        if cors not in cors_keys:
            error = create_validation_error(
                line_num=line_num,
                error_type="cors_invalid_value",
                message=f'{cors} is not a valid CORS option',
                severity="error",
                field="cors",
                expected=f"One of {cors_keys}",
                actual=cors
            )
            validation_errors.append(error)
            err_msgs.append(error.to_error_message())

        # Добавляем ошибки в коллектор если он передан
        if error_collector and validation_errors:
            error_collector.add_errors(validation_errors)

        if not err_msgs:
            validation_logger.debug(f"CORS на строке {line_num + 1} корректен")

        return err_msgs


def check_entry(line_num: int, segments: List[str], error_collector: Optional[ErrorCollector] = None) -> List[str]:
    """Проверяет запись API"""
    with error_handling_context("check_entry", {"line": line_num + 1, "segment_count": len(segments)}):
        validation_logger.debug(f"Начало проверки записи на строке {line_num + 1}")

        if len(segments) < 5:
            error = create_validation_error(
                line_num=line_num,
                error_type="insufficient_segments",
                message=f'entry does not have all the required columns (have {len(segments)}, need 5)',
                severity="critical",
                field="structure"
            )
            if error_collector:
                error_collector.add_error(error)
            return [error.to_error_message()]

        raw_title = segments[index_title]
        description = segments[index_desc]
        auth = segments[index_auth]
        https = segments[index_https]
        cors = segments[index_cors]

        title_err_msgs = check_title(line_num, raw_title, error_collector)
        desc_err_msgs = check_description(line_num, description, error_collector)
        auth_err_msgs = check_auth(line_num, auth, error_collector)
        https_err_msgs = check_https(line_num, https, error_collector)
        cors_err_msgs = check_cors(line_num, cors, error_collector)

        err_msgs = [
            *title_err_msgs,
            *desc_err_msgs,
            *auth_err_msgs,
            *https_err_msgs,
            *cors_err_msgs
        ]

        if err_msgs:
            validation_logger.warning(f"Найдено {len(err_msgs)} ошибок в записи на строке {line_num + 1}")
        else:
            validation_logger.debug(f"Запись на строке {line_num + 1} прошла все проверки успешно")

        return err_msgs


def check_file_format(lines: List[str]) -> List[str]:
    """Основная функция проверки формата файла"""
    with error_handling_context("check_file_format", {"line_count": len(lines)}):
        main_logger.info("=" * 100)
        main_logger.info(f"НАЧАЛО ПРОВЕРКИ ФОРМАТА ФАЙЛА")
        main_logger.info("=" * 100)

        start_time = time.time()

        # Создаём коллектор ошибок
        error_collector = ErrorCollector()

        # Добавляем контекст для логов
        module_logger.add_context(
            check_type="full_validation",
            file_lines=len(lines),
            start_timestamp=datetime.now().isoformat()
        )

        err_msgs = []
        current_category = ''
        total_entries = 0
        entries_by_category = defaultdict(int)

        main_logger.info("Начало проверки отдельных записей API")

        try:
            for line_num, line_content in enumerate(lines):
                # Определяем категории
                if line_content.startswith(anchor):
                    category_match = anchor_re.match(line_content)
                    if category_match:
                        current_category = category_match.group(1)
                        validation_logger.info(f"Обработка категории: '{current_category}'")
                    continue

                # Пропускаем неинтересные строки
                if not line_content.startswith('|') or line_content.startswith('|---'):
                    continue

                # Проверяем запись
                total_entries += 1
                entries_by_category[current_category] += 1

                segments = line_content.split('|')[1:-1]

                # Проверка форматирования пробелов
                spacing_issues = []
                for i, segment in enumerate(segments):
                    left_spaces = len(segment) - len(segment.lstrip())
                    right_spaces = len(segment) - len(segment.rstrip())

                    if left_spaces != 1 or right_spaces != 1:
                        spacing_issues.append(i)

                if spacing_issues:
                    error = create_validation_error(
                        line_num=line_num,
                        error_type="spacing_format",
                        message='each segment must start and end with exactly 1 space',
                        severity="error",
                        field="formatting",
                        expected="Exactly 1 space at start and end",
                        actual=f"Positions with issues: {spacing_issues}"
                    )
                    error_collector.add_error(error)
                    err_msgs.append(error.to_error_message())

                segments = [segment.strip() for segment in segments]
                entry_err_msgs = check_entry(line_num, segments, error_collector)
                err_msgs.extend(entry_err_msgs)

                # Логируем прогресс
                if total_entries % 10 == 0:
                    validation_logger.info(f"Проверено {total_entries} записей...")

        except Exception as e:
            # Логируем критическую ошибку при проверке
            exc_info = exception_logger.log_exception(
                e,
                {
                    'operation': 'file_validation',
                    'lines_processed': line_num,
                    'current_category': current_category,
                    'total_entries': total_entries
                },
                level="critical"
            )

            error = create_validation_error(
                line_num=line_num,
                error_type="validation_exception",
                message=f'Critical error during validation: {str(e)}',
                severity="critical",
                field="system",
                context=exc_info
            )
            error_collector.add_error(error)
            err_msgs.append(error.to_error_message())

        # Логируем итоговую статистику ошибок
        error_collector.log_summary()

        # Сохраняем ошибки в файл
        if error_collector.errors:
            error_file = error_collector.save_to_file()
            if error_file:
                stats_logger.info(f"Детальная информация об ошибках сохранена в: {error_file}")

        # Вывод общей статистики
        elapsed_time = time.time() - start_time

        stats_logger.info("=" * 100)
        stats_logger.info("ОБЩАЯ СТАТИСТИКА ПРОВЕРКИ")
        stats_logger.info("=" * 100)
        stats_logger.info(f"Общее время проверки: {elapsed_time:.2f} секунд")
        stats_logger.info(f"Всего записей API: {total_entries}")
        stats_logger.info(f"Всего ошибок: {len(err_msgs)}")
        stats_logger.info(f"Ошибок в секунду: {len(err_msgs) / elapsed_time:.1f}" if elapsed_time > 0 else "N/A")

        # Статистика по категориям
        if entries_by_category:
            stats_logger.info("Записей по категориям:")
            for category, count in sorted(entries_by_category.items()):
                stats_logger.info(f"  {category}: {count} записей")

        # Получаем общую статистику по исключениям
        exception_stats = exception_logger.get_exception_stats()
        if exception_stats['total_exceptions'] > 0:
            stats_logger.info(f"Исключений во время проверки: {exception_stats['total_exceptions']}")

        stats_logger.info("=" * 100)

        # Логируем метрики производительности
        perf_logger.log_performance_metric("total_validation_time", elapsed_time * 1000, "ms")
        perf_logger.log_performance_metric("entries_processed", total_entries, "count")
        perf_logger.log_performance_metric("errors_found", len(err_msgs), "count")

        if total_entries > 0:
            perf_logger.log_performance_metric("time_per_entry", (elapsed_time / total_entries) * 1000, "ms")

        return err_msgs


def analyze_file_content(lines: List[str]) -> Dict:
    """Анализирует содержимое файла"""
    with error_handling_context("analyze_file_content", {"line_count": len(lines)}):
        validation_logger.info("Анализ содержимого файла")

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

        try:
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

        except Exception as e:
            exception_logger.log_exception(e, {'operation': 'file_analysis', 'line_num': line_num})
            raise

        validation_logger.info(f"Анализ завершен: {stats['total_lines']} строк, {len(stats['categories'])} категорий")
        validation_logger.debug(f"Распределение по типам строк: {dict(stats['lines_by_type'])}")

        return stats


def main(filename: str) -> None:
    """Основная функция программы"""
    # Устанавливаем контекст для всего запуска
    module_logger.add_context(
        program_run_id=datetime.now().strftime('%Y%m%d_%H%M%S'),
        filename=filename,
        python_version=sys.version,
        platform=sys.platform
    )

    with error_handling_context("main_program_execution", {"filename": filename}):
        main_logger.info("=" * 100)
        main_logger.info(f"ЗАПУСК ПРОГРАММЫ ПРОВЕРКИ API-ЛИСТА")
        main_logger.info(f"Файл: {filename}")
        main_logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        main_logger.info(f"PID: {os.getpid()}")
        main_logger.info("=" * 100)

        try:
            # Проверка существования файла
            if not os.path.exists(filename):
                error_msg = f"Файл не найден: {filename}"
                error = create_validation_error(
                    line_num=0,
                    error_type="file_not_found",
                    message=error_msg,
                    severity="critical",
                    field="system"
                )

                error_logger.critical(error_msg, extra={'validation_details': error.to_dict()})
                print(error_msg)
                sys.exit(1)

            # Сбор информации о файле
            file_size = os.path.getsize(filename)
            file_mtime = datetime.fromtimestamp(os.path.getmtime(filename)).strftime('%Y-%m-%d %H:%M:%S')

            stats_logger.info("ИНФОРМАЦИЯ О ФАЙЛЕ:")
            stats_logger.info(f"  Размер: {file_size} байт ({file_size / 1024:.1f} KB)")
            stats_logger.info(f"  Путь: {os.path.abspath(filename)}")
            stats_logger.info(f"  Время изменения: {file_mtime}")

            # Чтение файла
            with open(filename, mode='r', encoding='utf-8') as file:
                lines = list(line.rstrip() for line in file)

            # Анализ содержимого файла
            stats = analyze_file_content(lines)

            stats_logger.info("СТАТИСТИКА ФАЙЛА:")
            stats_logger.info(f"  Всего строк: {stats['total_lines']}")
            stats_logger.info(
                f"  Непустых строк: {stats['non_empty_lines']} ({stats['non_empty_lines'] / stats['total_lines'] * 100:.1f}%)")
            stats_logger.info(f"  Категорий: {len(stats['categories'])}")
            stats_logger.info(f"  Строк с API: {stats['table_lines']}")

            # Проверка формата файла
            file_format_err_msgs = check_file_format(lines)

            # Получаем общую статистику по ошибкам
            error_tracker = get_error_tracker()
            if error_tracker:
                error_summary = error_tracker.get_error_summary()
                if error_summary['total_errors'] > 0:
                    stats_logger.info(f"Всего ошибок в системе: {error_summary['total_errors']}")

            # Обработка результатов проверки
            if file_format_err_msgs:
                main_logger.error("=" * 100)
                main_logger.error("РЕЗУЛЬТАТ ПРОВЕРКИ: НЕУДАЧА ❌")
                main_logger.error("=" * 100)

                # Выводим ошибки пользователю
                for err_msg in file_format_err_msgs:
                    print(err_msg)
                    main_logger.error(f"Ошибка валидации: {err_msg}", extra={'error_type': 'user_output'})

                # Анализ типов ошибок
                error_categories = Counter()
                for err_msg in file_format_err_msgs:
                    if "Title" in err_msg:
                        error_categories['title'] += 1
                    elif "description" in err_msg:
                        error_categories['description'] += 1
                    elif "auth" in err_msg:
                        error_categories['auth'] += 1
                    elif "HTTPS" in err_msg:
                        error_categories['https'] += 1
                    elif "CORS" in err_msg:
                        error_categories['cors'] += 1
                    elif "column" in err_msg:
                        error_categories['columns'] += 1
                    elif "segment" in err_msg:
                        error_categories['formatting'] += 1
                    elif "Critical" in err_msg:
                        error_categories['critical'] += 1
                    else:
                        error_categories['other'] += 1

                main_logger.error("ДЕТАЛЬНАЯ СТАТИСТИКА ОШИБОК:")
                for err_type, count in sorted(error_categories.items(), key=lambda x: x[1], reverse=True):
                    percentage = count / len(file_format_err_msgs) * 100
                    main_logger.error(f"  {err_type.title()}: {count} ({percentage:.1f}%)")

                main_logger.error(f"Всего ошибок: {len(file_format_err_msgs)}")
                main_logger.error("=" * 100)
                sys.exit(1)
            else:
                main_logger.info("=" * 100)
                main_logger.info("РЕЗУЛЬТАТ ПРОВЕРКИ: УСПЕХ ✅")
                main_logger.info("=" * 100)
                main_logger.info("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
                main_logger.info("Файл соответствует всем требованиям формата.")

        except FileNotFoundError as e:
            error_msg = f"Файл не найден: {filename}"
            exception_logger.log_exception(e, {'filename': filename}, level="critical")
            print(error_msg)
            sys.exit(1)

        except UnicodeDecodeError as e:
            error_msg = f"Ошибка кодировки файла: {str(e)}"
            exception_logger.log_exception(e, {'filename': filename, 'encoding': 'utf-8'}, level="critical")
            print(error_msg)
            sys.exit(1)

        except Exception as e:
            error_msg = f"Критическая ошибка при выполнении программы: {str(e)}"
            exception_logger.log_exception(e,
                                           {
                                               'filename': filename,
                                               'program_run_id': module_logger.context.get('program_run_id'),
                                               'python_version': sys.version
                                           },
                                           level="critical"
                                           )
            print(error_msg)
            sys.exit(1)


if __name__ == '__main__':
    # Инициализация логирования для запуска скрипта
    main_logger.debug("=" * 100)
    main_logger.debug("СКРИПТ ЗАПУЩЕН НАПРЯМУЮ")
    main_logger.debug(f"Аргументы командной строки: {sys.argv}")
    main_logger.debug(f"Рабочая директория: {os.getcwd()}")
    main_logger.debug(f"Пользователь: {os.getenv('USER', os.getenv('USERNAME', 'unknown'))}")
    main_logger.debug("=" * 100)

    if len(sys.argv) < 2:
        error_msg = 'No .md file passed (file should contain Markdown table syntax)'
        error_logger.error(error_msg, extra={'error_type': 'argument_error'})
        print(error_msg)
        sys.exit(1)

    filename = sys.argv[1]
    main_logger.info(f"Целевой файл: {filename}")

    # Запуск основной функции
    main(filename)