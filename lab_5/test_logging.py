#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для демонстрации логирования
"""

import sys
import os
from logger_config import get_module_logger

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Тестируем логирование
test_logger = get_module_logger("test")


def demonstrate_logging_levels():
    """Демонстрация разных уровней логирования"""
    test_logger.debug("Это сообщение уровня DEBUG - видно только в файле")
    test_logger.info("Это сообщение уровня INFO - видно в консоли и файле")
    test_logger.warning("Это сообщение уровня WARNING - возможно, есть проблема")
    test_logger.error("Это сообщение уровня ERROR - произошла ошибка")

    try:
        # Имитация ошибки для демонстрации логирования исключений
        result = 10 / 0
    except ZeroDivisionError as e:
        test_logger.error("Ошибка деления на ноль", exc_info=True)


def demonstrate_file_analysis():
    """Демонстрация анализа файла"""
    test_logger.info("Запуск демонстрации анализа файла")

    test_file = "test_api_list.md"
    if os.path.exists(test_file):
        test_logger.info(f"Тестовый файл найден: {test_file}")

        with open(test_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        test_logger.info(f"Прочитано строк: {len(lines)}")

        # Простой анализ
        categories = [line.strip() for line in lines if line.startswith('## ') and not line.startswith('###')]
        test_logger.info(f"Найдено категорий: {len(categories)}")

        for category in categories:
            test_logger.debug(f"Категория: {category}")
    else:
        test_logger.warning(f"Тестовый файл не найден: {test_file}")


if __name__ == "__main__":
    test_logger.info("=" * 60)
    test_logger.info("НАЧАЛО ТЕСТИРОВАНИЯ ЛОГИРОВАНИЯ")
    test_logger.info("=" * 60)

    demonstrate_logging_levels()
    demonstrate_file_analysis()

    test_logger.info("=" * 60)
    test_logger.info("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    test_logger.info("=" * 60)

    print("\nПроверьте папку 'logs/' для просмотра полных логов.")
    print("В консоли видны только сообщения уровня INFO и выше.")