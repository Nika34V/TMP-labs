# -*- coding: utf-8 -*-
"""
Расширенная конфигурация логирования для проверки формата API-листа
"""

import logging
import sys
import json
import traceback
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Dict, Any, Optional


class StructuredLogger:
    """Класс для структурированного логирования с дополнительными метаданными"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context = {}

    def add_context(self, **kwargs):
        """Добавляет контекстную информацию к логам"""
        self.context.update(kwargs)

    def clear_context(self):
        """Очищает контекстную информацию"""
        self.context.clear()

    def _prepare_extra(self, extra: Optional[Dict] = None) -> Dict:
        """Подготавливает дополнительные данные для логирования"""
        result = {'context': self.context.copy()}
        if extra:
            result.update(extra)
        return result

    def debug(self, msg: str, extra: Optional[Dict] = None, exc_info: bool = False):
        """Логирование уровня DEBUG"""
        self.logger.debug(msg, extra=self._prepare_extra(extra), exc_info=exc_info)

    def info(self, msg: str, extra: Optional[Dict] = None, exc_info: bool = False):
        """Логирование уровня INFO"""
        self.logger.info(msg, extra=self._prepare_extra(extra), exc_info=exc_info)

    def warning(self, msg: str, extra: Optional[Dict] = None, exc_info: bool = False):
        """Логирование уровня WARNING"""
        self.logger.warning(msg, extra=self._prepare_extra(extra), exc_info=exc_info)

    def error(self, msg: str, extra: Optional[Dict] = None, exc_info: bool = False):
        """Логирование уровня ERROR"""
        self.logger.error(msg, extra=self._prepare_extra(extra), exc_info=exc_info)

    def critical(self, msg: str, extra: Optional[Dict] = None, exc_info: bool = False):
        """Логирование уровня CRITICAL"""
        self.logger.critical(msg, extra=self._prepare_extra(extra), exc_info=exc_info)

    def exception(self, msg: str, extra: Optional[Dict] = None):
        """Логирование исключения с traceback"""
        self.logger.error(msg, extra=self._prepare_extra(extra), exc_info=True)

    def log_validation_error(self, error_type: str, details: Dict, severity: str = "error"):
        """Специализированное логирование ошибок валидации"""
        extra = {
            'error_type': error_type,
            'validation_details': details,
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        }

        level_map = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL
        }

        level = level_map.get(severity, logging.ERROR)
        message = f"Validation {severity.upper()}: {error_type} - {details.get('message', '')}"

        self.logger.log(level, message, extra=self._prepare_extra(extra))

    def log_performance_metric(self, metric_name: str, value: float, unit: str = "ms"):
        """Логирование метрик производительности"""
        extra = {
            'metric_name': metric_name,
            'metric_value': value,
            'metric_unit': unit,
            'is_performance_metric': True
        }
        self.info(f"Performance: {metric_name} = {value}{unit}", extra=extra)


class ErrorTrackingHandler(logging.Handler):
    """Специальный обработчик для отслеживания ошибок"""

    def __init__(self):
        super().__init__()
        self.error_counts = {}
        self.error_details = []
        self.setLevel(logging.WARNING)

    def emit(self, record):
        try:
            # Подсчитываем ошибки по типам
            error_type = getattr(record, 'error_type', 'unknown')
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

            # Сохраняем детали ошибки
            error_detail = {
                'timestamp': datetime.now().isoformat(),
                'level': record.levelname,
                'message': record.getMessage(),
                'type': error_type,
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }

            # Добавляем дополнительную информацию из extra
            if hasattr(record, 'validation_details'):
                error_detail['validation_details'] = record.validation_details
            if hasattr(record, 'context'):
                error_detail['context'] = record.context

            self.error_details.append(error_detail)

            # Ограничиваем размер истории ошибок
            if len(self.error_details) > 100:
                self.error_details = self.error_details[-50:]

        except Exception:
            self.handleError(record)

    def get_error_summary(self) -> Dict:
        """Возвращает сводку по ошибкам"""
        return {
            'total_errors': sum(self.error_counts.values()),
            'error_counts': dict(self.error_counts),
            'recent_errors': self.error_details[-10:] if self.error_details else []
        }

    def clear_errors(self):
        """Очищает историю ошибок"""
        self.error_counts.clear()
        self.error_details.clear()


class ExceptionLogger:
    """Класс для централизованного логирования исключений"""

    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.exception_counts = {}

    def log_exception(self, exception: Exception, context: Optional[Dict] = None,
                      level: str = "error") -> Dict:
        """
        Логирует исключение с полной информацией

        Returns:
            Словарь с информацией об исключении
        """
        exc_type = type(exception).__name__
        self.exception_counts[exc_type] = self.exception_counts.get(exc_type, 0) + 1

        exc_info = {
            'type': exc_type,
            'message': str(exception),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat(),
            'count': self.exception_counts[exc_type]
        }

        if context:
            exc_info['context'] = context

        # Логируем в зависимости от уровня
        log_method = getattr(self.logger, level)
        log_method(f"Exception: {exc_type} - {str(exception)}",
                   extra={'exception_info': exc_info})

        return exc_info

    def get_exception_stats(self) -> Dict:
        """Возвращает статистику по исключениям"""
        return {
            'total_exceptions': sum(self.exception_counts.values()),
            'exception_counts': dict(self.exception_counts),
            'most_common': max(self.exception_counts.items(), key=lambda x: x[1])
            if self.exception_counts else ('none', 0)
        }


def setup_logger(name: str = "api_format_checker") -> logging.Logger:
    """
    Настройка и возврат логгера с обработчиками ошибок

    Args:
        name: Имя логгера

    Returns:
        Настроенный логгер
    """
    # Создаём логгер
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    # Форматы для разных обработчиков
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)-35s | %(levelname)-8s | %(module)-15s | %(funcName)-25s:%(lineno)-4d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '%(levelname)-8s | %(module_short)-20s | %(message)s'
    )

    error_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s.%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%H:%M:%S'
    )

    # 1. Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # 2. Основной файловый обработчик
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    main_log = log_dir / "api_checker.log"
    main_handler = RotatingFileHandler(
        main_log,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=10,
        encoding='utf-8'
    )
    main_handler.setLevel(logging.DEBUG)
    main_handler.setFormatter(detailed_formatter)

    # 3. Обработчик для ошибок (отдельный файл)
    error_log = log_dir / "errors.log"
    error_handler = TimedRotatingFileHandler(
        error_log,
        when='midnight',
        interval=1,
        backupCount=14,  # 2 недели
        encoding='utf-8'
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(error_formatter)

    # 4. Обработчик для отслеживания ошибок
    error_tracker = ErrorTrackingHandler()

    # 5. JSON обработчик для структурированных данных
    json_log = log_dir / "structured.json"

    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                'timestamp': datetime.now().isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'message': record.getMessage(),
                'process': record.process,
                'thread': record.threadName
            }

            # Добавляем дополнительные поля из extra
            for key, value in record.__dict__.items():
                if key.startswith('_') or key in ['args', 'created', 'exc_info',
                                                  'exc_text', 'filename', 'levelno',
                                                  'lineno', 'module', 'msecs', 'msg',
                                                  'name', 'pathname', 'process',
                                                  'relativeCreated', 'thread',
                                                  'threadName']:
                    continue

                if key not in log_record and value is not None:
                    # Сериализуем специальные типы
                    if hasattr(value, '__dict__'):
                        log_record[key] = str(value)
                    else:
                        log_record[key] = value

            # Добавляем traceback для исключений
            if record.exc_info:
                log_record['exception'] = {
                    'type': str(record.exc_info[0].__name__),
                    'message': str(record.exc_info[1]),
                    'traceback': self.formatException(record.exc_info)
                }

            return json.dumps(log_record, ensure_ascii=False)

    json_handler = logging.FileHandler(json_log, encoding='utf-8')
    json_handler.setLevel(logging.INFO)
    json_handler.setFormatter(JSONFormatter())

    # Фильтры
    class ContextFilter(logging.Filter):
        def filter(self, record):
            # Добавляем короткое имя модуля
            record.module_short = record.name.split('.')[-1] if '.' in record.name else record.name

            # Добавляем timestamp для быстрого доступа
            if not hasattr(record, 'log_timestamp'):
                record.log_timestamp = datetime.now().isoformat()

            return True

    context_filter = ContextFilter()

    # Применяем фильтры и обработчики
    for handler in [console_handler, main_handler, error_handler, json_handler, error_tracker]:
        handler.addFilter(context_filter)
        logger.addHandler(handler)

    # Логируем инициализацию
    logger.debug("=" * 100)
    logger.debug("РАСШИРЕННЫЙ ЛОГГЕР ИНИЦИАЛИЗИРОВАН")
    logger.debug(f"Имя: {name}")
    logger.debug(f"Уровень: {logging.getLevelName(logger.level)}")
    logger.debug(f"Обработчики: {len(logger.handlers)}")
    logger.debug(f"Основной лог: {main_log}")
    logger.debug(f"Лог ошибок: {error_log}")
    logger.debug(f"JSON лог: {json_log}")
    logger.debug("=" * 100)

    return logger


def create_structured_logger(module_name: str) -> StructuredLogger:
    """
    Создаёт структурированный логгер для модуля

    Args:
        module_name: Имя модуля

    Returns:
        Структурированный логгер
    """
    logger_name = f"api_format_checker.{module_name}"
    logging.getLogger(logger_name)  # Создаём логгер если не существует

    structured_logger = StructuredLogger(logger_name)

    # Добавляем контекст по умолчанию
    structured_logger.add_context(
        module=module_name,
        pid=os.getpid(),
        startup_time=datetime.now().isoformat()
    )

    return structured_logger


def get_error_tracker() -> Optional[ErrorTrackingHandler]:
    """Возвращает обработчик отслеживания ошибок если он существует"""
    main_logger = logging.getLogger("api_format_checker")
    for handler in main_logger.handlers:
        if isinstance(handler, ErrorTrackingHandler):
            return handler
    return None


def get_exception_stats() -> Dict:
    """Возвращает статистику по исключениям из всех логгеров"""
    error_tracker = get_error_tracker()
    if error_tracker:
        return error_tracker.get_error_summary()
    return {'total_errors': 0, 'error_counts': {}, 'recent_errors': []}


# Инициализация глобальных логгеров
import os

main_logger = setup_logger()

# Создаём специализированные логгеры
validation_logger = create_structured_logger("validation")
error_logger = create_structured_logger("errors")
stats_logger = create_structured_logger("statistics")
perf_logger = create_structured_logger("performance")

# Создаём логгер исключений
exception_logger = ExceptionLogger(error_logger)