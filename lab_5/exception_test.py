#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование обработки исключений и ошибок
"""

import sys
import os
import tempfile
from pathlib import Path
from logger_config import exception_logger, error_logger, main_logger


def test_file_not_found():
    """Тестирование обработки ошибки файл не найден"""
    error_logger.info("\n" + "=" * 80)
    error_logger.info("ТЕСТ: Обработка ошибки 'файл не найден'")
    error_logger.info("=" * 80)

    # Создаём временный файл и сразу удаляем его
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        temp_file = f.name

    os.unlink(temp_file)  # Удаляем файл

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "format.py", temp_file],
            capture_output=True,
            text=True
        )

        if result.returncode != 0 and "File not found" in result.stdout:
            error_logger.info("✓ Ошибка 'файл не найден' корректно обработана")
            return True
        else:
            error_logger.error(f"✗ Неожиданный результат: код {result.returncode}")
            error_logger.error(f"Вывод: {result.stdout[:200]}")
            return False
    except Exception as e:
        exception_logger.log_exception(e, {'test': 'file_not_found'})
        return False


def test_unicode_error():
    """Тестирование обработки ошибки кодировки"""
    error_logger.info("\n" + "=" * 80)
    error_logger.info("ТЕСТ: Обработка ошибки кодировки")
    error_logger.info("=" * 80)

    # Создаём файл с некорректной кодировкой
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.md', delete=False) as f:
        # Пишем данные в кодировке, отличной от UTF-8
        f.write(b'\xff\xfe')  # BOM для UTF-16
        f.write("Test content".encode('utf-16'))
        temp_file = f.name

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "format.py", temp_file],
            capture_output=True,
            text=True
        )

        if result.returncode != 0 and ("encoding" in result.stdout.lower() or "Unicode" in result.stdout):
            error_logger.info("✓ Ошибка кодировки корректно обработана")
            return True
        else:
            error_logger.error(f"✗ Неожиданный результат: код {result.returncode}")
            return False
    except Exception as e:
        exception_logger.log_exception(e, {'test': 'unicode_error'})
        return False
    finally:
        os.unlink(temp_file)


def test_malformed_markdown():
    """Тестирование обработки некорректного Markdown"""
    error_logger.info("\n" + "=" * 80)
    error_logger.info("ТЕСТ: Обработка некорректного Markdown")
    error_logger.info("=" * 80)

    content = """# Test

## Category
| API | Description | Auth | HTTPS | CORS
|-----|-------------|------|-------|------
Missing closing pipe
| Another | Good | `No` | Yes | Yes |
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(content)
        temp_file = f.name

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "format.py", temp_file],
            capture_output=True,
            text=True
        )

        # Проверяем логи на наличие информации об ошибках
        log_dir = Path("logs")
        if log_dir.exists():
            error_logs = list(log_dir.glob("errors.log*"))
            if error_logs:
                latest_error_log = max(error_logs, key=lambda x: x.stat().st_mtime)
                with open(latest_error_log, 'r', encoding='utf-8') as f:
                    log_content = f.read()

                if "ERROR" in log_content or "CRITICAL" in log_content:
                    error_logger.info("✓ Ошибки корректно залогированы")
                    return True

        error_logger.warning("⚠ Проверка логов не дала результатов")
        return result.returncode != 0  # Ожидаем ошибку
    except Exception as e:
        exception_logger.log_exception(e, {'test': 'malformed_markdown'})
        return False
    finally:
        os.unlink(temp_file)


def test_exception_logging():
    """Тестирование логирования исключений"""
    exception_logger.info("\n" + "=" * 80)
    exception_logger.info("ТЕСТ: Логирование исключений")
    exception_logger.info("=" * 80)

    # Искусственно вызываем исключения разных типов
    test_exceptions = [
        (ValueError, "Test value error"),
        (TypeError, "Test type error"),
        (KeyError, "test_key"),
        (IndexError, "Index out of range"),
        (AttributeError, "'NoneType' object has no attribute 'test'")
    ]

    logged_exceptions = []

    for exc_type, message in test_exceptions:
        try:
            if exc_type == ValueError:
                raise ValueError(message)
            elif exc_type == TypeError:
                raise TypeError(message)
            elif exc_type == KeyError:
                raise KeyError(message)
            elif exc_type == IndexError:
                raise IndexError(message)
            elif exc_type == AttributeError:
                raise AttributeError(message)
        except Exception as e:
            exc_info = exception_logger.log_exception(
                e,
                {'test': 'exception_logging', 'exception_number': len(logged_exceptions) + 1},
                level="error"
            )
            logged_exceptions.append((exc_type.__name__, exc_info))

    exception_logger.info(f"Залогировано исключений: {len(logged_exceptions)}")

    # Проверяем логи
    log_dir = Path("logs")
    if log_dir.exists():
        json_logs = list(log_dir.glob("structured.json*"))
        if json_logs:
            # Читаем последние строки лога
            latest_log = max(json_logs, key=lambda x: x.stat().st_mtime)
            with open(latest_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-20:]  # Последние 20 строк

            # Ищем логированные исключения
            exception_count = sum(1 for line in lines if '"exception"' in line)
            exception_logger.info(f"Найдено исключений в JSON логах: {exception_count}")

            if exception_count >= len(test_exceptions):
                exception_logger.info("✓ Все исключения корректно залогированы в JSON")
                return True
            else:
                exception_logger.warning(
                    f"⚠ В JSON логах только {exception_count} из {len(test_exceptions)} исключений")
                return False

    exception_logger.error("✗ Не удалось проверить логи")
    return False


def run_all_tests():
    """Запускает все тесты обработки ошибок"""
    main_logger.info("=" * 80)
    main_logger.info("НАЧАЛО ТЕСТИРОВАНИЯ ОБРАБОТКИ ОШИБОК")
    main_logger.info("=" * 80)

    tests = [
        ("Файл не найден", test_file_not_found),
        ("Ошибка кодировки", test_unicode_error),
        ("Некорректный Markdown", test_malformed_markdown),
        ("Логирование исключений", test_exception_logging)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                main_logger.info(f"✓ ТЕСТ '{test_name}' ПРОЙДЕН")
                passed += 1
            else:
                main_logger.error(f"✗ ТЕСТ '{test_name}' НЕ ПРОЙДЕН")
        except Exception as e:
            exception_logger.log_exception(e, {'test': test_name})
            main_logger.error(f"✗ ТЕСТ '{test_name}' ВЫЗВАЛ ИСКЛЮЧЕНИЕ")

    main_logger.info("\n" + "=" * 80)
    main_logger.info("ИТОГИ ТЕСТИРОВАНИЯ ОБРАБОТКИ ОШИБОК")
    main_logger.info("=" * 80)
    main_logger.info(f"Пройдено тестов: {passed}/{total}")

    if passed == total:
        main_logger.info("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        main_logger.error(f"❌ ПРОЙДЕНО ТОЛЬКО {passed} ИЗ {total} ТЕСТОВ")

    return passed == total


if __name__ == "__main__":
    # Добавляем текущую директорию в путь
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    success = run_all_tests()
    sys.exit(0 if success else 1)