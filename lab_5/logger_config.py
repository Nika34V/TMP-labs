# -*- coding: utf-8 -*-
"""
Конфигурация логирования для проверки формата API-листа
"""

import logging
import sys
import json
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


def setup_logger(name: str = "api_format_checker") -> logging.Logger:
    """
    Настройка и возврат логгера

    Args:
        name: Имя логгера

    Returns:
        Настроенный логгер
    """
    # Создаём логгер
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Ловим все сообщения

    # Очищаем существующие обработчики (чтобы не дублировались)
    logger.handlers.clear()

    # Форматы для разных обработчиков
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)-30s | %(levelname)-8s | %(funcName)-25s:%(lineno)-4d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '%(levelname)-8s | %(module_short)-15s | %(message)s'
    )

    json_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. Обработчик для консоли (только INFO и выше)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # 2. Обработчик для основного файла с ротацией по размеру
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    main_log_filename = log_dir / "api_checker_main.log"

    main_file_handler = RotatingFileHandler(
        main_log_filename,
        maxBytes=2 * 1024 * 1024,  # 2MB
        backupCount=10,
        encoding='utf-8'
    )
    main_file_handler.setLevel(logging.DEBUG)
    main_file_handler.setFormatter(detailed_formatter)

    # 3. Обработчик для ошибок с ротацией по времени
    error_log_filename = log_dir / "api_checker_errors.log"

    error_file_handler = TimedRotatingFileHandler(
        error_log_filename,
        when='midnight',  # Ротация в полночь
        interval=1,
        backupCount=7,  # Храним 7 дней
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.WARNING)
    error_file_handler.setFormatter(detailed_formatter)

    # 4. Обработчик для JSON логов (машинно-читаемый формат)
    json_log_filename = log_dir / "api_checker_validation.json"

    class JsonLogHandler(logging.FileHandler):
        """Обработчик для записи логов в JSON формате"""

        def emit(self, record):
            try:
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'logger': record.name,
                    'level': record.levelname,
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno,
                    'message': record.getMessage(),
                    'process': record.process,
                    'thread': record.threadName
                }

                # Добавляем дополнительные поля, если есть
                if hasattr(record, 'validation_data'):
                    log_entry['validation_data'] = record.validation_data
                if hasattr(record, 'api_entry'):
                    log_entry['api_entry'] = record.api_entry
                if hasattr(record, 'statistics'):
                    log_entry['statistics'] = record.statistics

                json_line = json.dumps(log_entry, ensure_ascii=False)
                self.stream.write(json_line + '\n')
                self.flush()
            except Exception:
                self.handleError(record)

    json_handler = JsonLogHandler(json_log_filename, encoding='utf-8')
    json_handler.setLevel(logging.INFO)

    # Фильтры
    class ModuleFilter(logging.Filter):
        def filter(self, record):
            record.module_short = record.name.split('.')[-1] if '.' in record.name else record.name
            return True

    class ValidationFilter(logging.Filter):
        """Фильтр для логов валидации"""

        def filter(self, record):
            if not hasattr(record, 'validation_type'):
                record.validation_type = 'general'
            return True

    module_filter = ModuleFilter()
    validation_filter = ValidationFilter()

    # Применяем фильтры
    console_handler.addFilter(module_filter)
    main_file_handler.addFilter(validation_filter)
    json_handler.addFilter(validation_filter)

    # Добавляем обработчики к логгеру
    logger.addHandler(console_handler)
    logger.addHandler(main_file_handler)
    logger.addHandler(error_file_handler)
    logger.addHandler(json_handler)

    # Логируем создание логгера
    logger.debug("=" * 100)
    logger.debug(f"ЛОГГЕР ИНИЦИАЛИЗИРОВАН: {name}")
    logger.debug(f"Консоль: уровень {logging.getLevelName(console_handler.level)}")
    logger.debug(f"Основной файл: {main_log_filename}")
    logger.debug(f"Файл ошибок: {error_log_filename} (ротация ежедневно)")
    logger.debug(f"JSON лог: {json_log_filename}")
    logger.debug(f"Всего обработчиков: {len(logger.handlers)}")
    logger.debug("=" * 100)

    return logger


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Получить логгер для конкретного модуля

    Args:
        module_name: Имя модуля

    Returns:
        Логгер с именем модуля
    """
    logger_name = f"api_format_checker.{module_name}"
    logger = logging.getLogger(logger_name)

    # Устанавливаем уровень для модуля
    if module_name.startswith("validation_"):
        logger.setLevel(logging.DEBUG)
    elif module_name in ["entry_checker", "field_validator"]:
        logger.setLevel(logging.INFO)

    return logger


def create_validation_logger():
    """Создаёт специализированный логгер для валидации"""
    validation_logger = get_module_logger("validation_core")

    # Добавляем дополнительные методы для структурированного логирования
    def log_validation_result(level, entry_data, field, expected, actual, status, details=None):
        """Логирует результат валидации одного поля"""
        extra_data = {
            'validation_data': {
                'field': field,
                'expected': expected,
                'actual': actual,
                'status': status,
                'details': details or {},
                'timestamp': datetime.now().isoformat()
            },
            'api_entry': entry_data
        }

        message = f"Validation {status.upper()}: {field} = '{actual}'"
        if status != 'passed':
            message += f" (expected: {expected})"

        validation_logger.log(level, message, extra=extra_data)

    def log_entry_validation(entry_num, total_fields, passed_fields, failed_fields, entry_data):
        """Логирует результат валидации всей записи"""
        extra_data = {
            'statistics': {
                'entry_number': entry_num,
                'total_fields': total_fields,
                'passed_fields': passed_fields,
                'failed_fields': failed_fields,
                'success_rate': (passed_fields / total_fields * 100) if total_fields > 0 else 0
            },
            'api_entry': entry_data
        }

        status = 'PASSED' if failed_fields == 0 else 'FAILED'
        validation_logger.info(
            f"Entry #{entry_num}: {status} - {passed_fields}/{total_fields} fields passed",
            extra=extra_data
        )

    # Добавляем методы к логгеру
    validation_logger.log_validation_result = log_validation_result
    validation_logger.log_entry_validation = log_entry_validation

    return validation_logger


# Создаём специализированные логгеры
logger = setup_logger()
validation_logger = create_validation_logger()
field_logger = get_module_logger("field_validator")
entry_logger = get_module_logger("entry_checker")
stats_logger = get_module_logger("statistics")