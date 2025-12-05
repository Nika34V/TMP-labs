# -*- coding: utf-8 -*-
"""
Конфигурация логирования для проверки формата API-листа
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


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

    # Формат для логов
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '%(levelname)-8s %(message)s'
    )

    # 1. Обработчик для консоли (только INFO и выше)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # 2. Обработчик для файла (DEBUG и выше)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Имя файла с датой
    log_filename = log_dir / f"api_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # Добавляем обработчики к логгеру
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Логируем создание логгера
    logger.debug(f"Логгер '{name}' инициализирован")
    logger.debug(f"Файл логов: {log_filename}")

    return logger


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Получить логгер для конкретного модуля

    Args:
        module_name: Имя модуля

    Returns:
        Логгер с именем модуля
    """
    return logging.getLogger(f"api_format_checker.{module_name}")


# Глобальный логгер для импорта
logger = setup_logger()