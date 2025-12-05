# -*- coding: utf-8 -*-
"""
Конфигурация логирования для проверки формата API-листа
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler


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

    # Расширенный формат для логов
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)-25s | %(levelname)-8s | %(funcName)-20s:%(lineno)-4d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '%(levelname)-8s | %(name)-15s | %(message)s'
    )

    # 1. Обработчик для консоли (только INFO и выше)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # 2. Обработчик для файла с ротацией (DEBUG и выше)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_filename = log_dir / "api_checker.log"

    # Ротация файлов: 5 файлов по 1MB каждый
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=1024 * 1024,  # 1MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # 3. Обработчик для ошибок в отдельный файл
    error_log_filename = log_dir / "api_checker_errors.log"
    error_handler = RotatingFileHandler(
        error_log_filename,
        maxBytes=512 * 1024,  # 512KB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.WARNING)  # Только WARNING и выше
    error_handler.setFormatter(detailed_formatter)

    # Фильтр для именования ошибок
    class ModuleFilter(logging.Filter):
        def filter(self, record):
            record.module_short = record.name.split('.')[-1] if '.' in record.name else record.name
            return True

    module_filter = ModuleFilter()
    console_handler.addFilter(module_filter)

    # Добавляем обработчики к логгеру
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    # Логируем создание логгера
    logger.debug("=" * 80)
    logger.debug(f"ЛОГГЕР ИНИЦИАЛИЗИРОВАН: {name}")
    logger.debug(f"Консоль: уровень {console_handler.level} ({logging.getLevelName(console_handler.level)})")
    logger.debug(f"Основной файл: {log_filename}, уровень {file_handler.level}")
    logger.debug(f"Файл ошибок: {error_log_filename}, уровень {error_handler.level}")
    logger.debug(f"Ротация: 1MB на файл, 5 бэкапов")
    logger.debug("=" * 80)

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
    if module_name.startswith("check_"):
        logger.setLevel(logging.DEBUG)
    elif module_name in ["file_analysis", "category_validator"]:
        logger.setLevel(logging.INFO)

    return logger


# Создаём специализированные логгеры для разных модулей
logger = setup_logger()

# Логгеры для конкретных задач
category_logger = get_module_logger("category_validator")
index_logger = get_module_logger("index_validator")
structure_logger = get_module_logger("structure_analyzer")