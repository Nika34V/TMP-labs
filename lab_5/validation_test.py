#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование системы валидации записей API
"""

import sys
import os
import tempfile
from pathlib import Path
from logger_config import validation_logger, field_logger, entry_logger, stats_logger


def create_test_file(content: str) -> str:
    """Создаёт временный тестовый файл"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        return f.name


def test_valid_entry():
    """Тестирование корректной записи"""
    entry_logger.info("\n" + "=" * 80)
    entry_logger.info("ТЕСТ: Корректная запись API")
    entry_logger.info("=" * 80)

    content = """# Test API

## Animals
| API | Description | Auth | HTTPS | CORS |
|-----|-------------|------|-------|------|
| [Cat Facts](https://catfact.ninja/) | Daily cat facts about cats and more | `No` | Yes | Yes |
"""

    test_file = create_test_file(content)

    try:
        # Импортируем и запускаем проверку
        import subprocess
        result = subprocess.run(
            [sys.executable, "format.py", test_file],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            entry_logger.info("✓ Корректная запись прошла валидацию")
        else:
            entry_logger.error(f"✗ Корректная запись не прошла валидацию:\n{result.stdout}")

        return result.returncode == 0
    finally:
        os.unlink(test_file)


def test_invalid_entries():
    """Тестирование записей с ошибками"""
    field_logger.info("\n" + "=" * 80)
    field_logger.info("ТЕСТ: Записи с различными ошибками")
    field_logger.info("=" * 80)

    # Файл с преднамеренными ошибками в разных полях
    content = """# Test API

## Test Category
| API | Description | Auth | HTTPS | CORS |
|-----|-------------|------|-------|------|
| [Bad Title API](https://example.com) | Good description here | `No` | Yes | Yes |  <!-- Ошибка: заголовок заканчивается на API -->
| [Good Title](https://example.com) | first letter not capital | `No` | Yes | Yes |  <!-- Ошибка: описание с маленькой буквы -->
| [Another Good](https://example.com) | Good description. | `no backticks` | Yes | Yes |  <!-- Ошибка: auth без backticks -->
| [Yet Another](https://example.com) | Good description | `No` | Maybe | Yes |  <!-- Ошибка: неверное значение HTTPS -->
| [Last One](https://example.com) | Good description | `No` | Yes | Sometimes |  <!-- Ошибка: неверное значение CORS -->
"""

    test_file = create_test_file(content)

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "format.py", test_file],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            errors = result.stdout.strip().split('\n')
            field_logger.info(f"✓ Обнаружено {len(errors)} ошибок (как и ожидалось)")

            # Анализируем типы ошибок
            error_types = set()
            for error in errors:
                if "Title should not end" in error:
                    error_types.add("title_ending")
                elif "first character" in error:
                    error_types.add("description_capitalization")
                elif "backticks" in error:
                    error_types.add("auth_backticks")
                elif "HTTPS" in error:
                    error_types.add("https_value")
                elif "CORS" in error:
                    error_types.add("cors_value")

            field_logger.info(f"  Типы ошибок: {', '.join(sorted(error_types))}")

            # Проверяем логи
            log_dir = Path("logs")
            if log_dir.exists():
                json_logs = list(log_dir.glob("*.json"))
                if json_logs:
                    field_logger.info(f"  Создано JSON логов: {len(json_logs)}")
        else:
            field_logger.error("✗ Ожидались ошибки, но проверка прошла успешно")

        return result.returncode != 0
    finally:
        os.unlink(test_file)


def test_warning_scenarios():
    """Тестирование сценариев с предупреждениями"""
    validation_logger.info("\n" + "=" * 80)
    validation_logger.info("ТЕСТ: Записи с предупреждениями")
    validation_logger.info("=" * 80)

    # Файл с очень короткими описаниями (должны генерировать warnings)
    content = """# Test API

## Test Category
| API | Description | Auth | HTTPS | CORS |
|-----|-------------|------|-------|------|
| [Test API](https://example.com) | Short. | `No` | Yes | Yes |  <!-- Предупреждение: короткое описание -->
| [Test API 2](https://example.com) | Very short | `No` | Yes | Yes |  <!-- Предупреждение: короткое описание -->
"""

    test_file = create_test_file(content)

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "format.py", test_file],
            capture_output=True,
            text=True
        )

        # Проверяем логи на наличие предупреждений
        log_dir = Path("logs")
        if log_dir.exists():
            # Ищем последний лог-файл
            log_files = list(log_dir.glob("api_checker_main.log*"))
            if log_files:
                latest_log = max(log_files, key=lambda x: x.stat().st_mtime)

                with open(latest_log, 'r', encoding='utf-8') as f:
                    log_content = f.read()

                warning_count = log_content.count("WARNING")
                validation_logger.info(f"Найдено предупреждений в логах: {warning_count}")

                if warning_count >= 2:  # Ожидаем минимум 2 предупреждения
                    validation_logger.info("✓ Предупреждения корректно залогированы")
                else:
                    validation_logger.warning("✗ Мало предупреждений в логах")

        return result.returncode == 0  # Предупреждения не должны вызывать ошибку
    finally:
        os.unlink(test_file)


def test_statistics_generation():
    """Тестирование генерации статистики"""
    stats_logger.info("\n" + "=" * 80)
    stats_logger.info("ТЕСТ: Генерация статистики")
    stats_logger.info("=" * 80)

    content = """# Test API

## Category A
| API | Description | Auth | HTTPS | CORS |
|-----|-------------|------|-------|------|
| [API 1](https://example.com) | Description one here | `No` | Yes | Yes |
| [API 2](https://example.com) | Description two here | `apiKey` | Yes | No |

## Category B
| API | Description | Auth | HTTPS | CORS |
|-----|-------------|------|-------|------|
| [API 3](https://example.com) | Description three | `OAuth` | Yes | Unknown |
"""

    test_file = create_test_file(content)

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "format.py", test_file],
            capture_output=True,
            text=True
        )

        # Проверяем создание файла статистики
        log_dir = Path("logs")
        if log_dir.exists():
            stats_files = list(log_dir.glob("validation_stats_*.json"))
            if stats_files:
                latest_stats = max(stats_files, key=lambda x: x.stat().st_mtime)

                import json
                with open(latest_stats, 'r', encoding='utf-8') as f:
                    stats_data = json.load(f)

                stats_logger.info(f"Файл статистики: {latest_stats.name}")
                stats_logger.info(f"  Записей: {stats_data.get('total_entries', 0)}")
                stats_logger.info(f"  Проверок: {stats_data.get('total_checks', 0)}")
                stats_logger.info(f"  Успешных: {stats_data.get('passed_checks', 0)}")

                if stats_data.get('by_category'):
                    stats_logger.info(f"  Категорий: {len(stats_data['by_category'])}")

                stats_logger.info("✓ Статистика успешно сгенерирована")
            else:
                stats_logger.error("✗ Файл статистики не создан")

        return result.returncode == 0
    finally:
        os.unlink(test_file)


def run_all_tests():
    """Запускает все тесты"""
    validation_logger.info("=" * 80)
    validation_logger.info("НАЧАЛО КОМПЛЕКСНОГО ТЕСТИРОВАНИЯ ВАЛИДАЦИИ")
    validation_logger.info("=" * 80)

    tests = [
        ("Корректная запись", test_valid_entry),
        ("Записи с ошибками", test_invalid_entries),
        ("Предупреждения", test_warning_scenarios),
        ("Генерация статистики", test_statistics_generation),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                validation_logger.info(f"✓ ТЕСТ '{test_name}' ПРОЙДЕН")
                passed += 1
            else:
                validation_logger.error(f"✗ ТЕСТ '{test_name}' НЕ ПРОЙДЕН")
        except Exception as e:
            validation_logger.error(f"✗ ТЕСТ '{test_name}' ВЫЗВАЛ ИСКЛЮЧЕНИЕ: {e}")

    validation_logger.info("\n" + "=" * 80)
    validation_logger.info("ИТОГИ ТЕСТИРОВАНИЯ")
    validation_logger.info("=" * 80)
    validation_logger.info(f"Пройдено тестов: {passed}/{total}")

    if passed == total:
        validation_logger.info("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        validation_logger.error(f"❌ ПРОЙДЕНО ТОЛЬКО {passed} ИЗ {total} ТЕСТОВ")

    return passed == total


if __name__ == "__main__":
    # Добавляем текущую директорию в путь для импорта
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    success = run_all_tests()
    sys.exit(0 if success else 1)