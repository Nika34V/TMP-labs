#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализ и визуализация ошибок валидации
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from logger_config import error_logger, stats_logger


def load_error_file(error_file: Path) -> Dict:
    """Загружает файл с ошибками"""
    try:
        with open(error_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        error_logger.error(f"Ошибка загрузки файла {error_file}: {e}")
        return None


def analyze_error_file(error_file: Path):
    """Анализирует один файл с ошибками"""
    error_logger.info(f"\nАнализ файла ошибок: {error_file.name}")

    data = load_error_file(error_file)
    if not data:
        return

    metadata = data.get('metadata', {})
    errors = data.get('errors', [])

    error_logger.info(f"  Всего ошибок: {len(errors)}")
    error_logger.info(f"  Создан: {metadata.get('generated_at', 'unknown')}")

    # Анализ по типам ошибок
    error_types = Counter([e.get('type', 'unknown') for e in errors])
    if error_types:
        error_logger.info("  Распределение по типам:")
        for err_type, count in error_types.most_common(5):
            percentage = (count / len(errors)) * 100
            error_logger.info(f"    {err_type:30s}: {count:4d} ({percentage:5.1f}%)")

    # Анализ по строкам
    lines_with_errors = Counter([e.get('line', 0) for e in errors])
    if lines_with_errors:
        error_logger.info(f"  Строк с ошибками: {len(lines_with_errors)}")
        most_problematic = lines_with_errors.most_common(3)
        error_logger.info("  Наиболее проблемные строки:")
        for line, count in most_problematic:
            error_logger.info(f"    Строка {line:4d}: {count:3d} ошибок")

    return data


def compare_error_files(error_files: list):
    """Сравнивает несколько файлов с ошибками"""
    if len(error_files) < 2:
        error_logger.warning("Для сравнения нужно минимум 2 файла ошибок")
        return

    error_logger.info("\n" + "=" * 80)
    error_logger.info("СРАВНЕНИЕ ФАЙЛОВ ОШИБОК")
    error_logger.info("=" * 80)

    all_stats = []
    for error_file in error_files:
        data = load_error_file(error_file)
        if data:
            stats = {
                'file': error_file.name,
                'total_errors': len(data.get('errors', [])),
                'error_types': Counter([e.get('type', 'unknown') for e in data.get('errors', [])]),
                'timestamp': data.get('metadata', {}).get('generated_at', '')
            }
            all_stats.append(stats)

    # Сравниваем количество ошибок
    if all_stats:
        total_errors = [s['total_errors'] for s in all_stats]
        avg_errors = sum(total_errors) / len(total_errors)

        error_logger.info(f"Среднее количество ошибок: {avg_errors:.1f}")
        error_logger.info(f"Минимальное: {min(total_errors)}")
        error_logger.info(f"Максимальное: {max(total_errors)}")

        # Анализ трендов
        if len(all_stats) >= 3:
            recent = all_stats[-1]['total_errors']
            older = all_stats[0]['total_errors']
            trend = "улучшение" if recent < older else "ухудшение" if recent > older else "стабильно"
            change = abs(recent - older)
            error_logger.info(f"Тренд: {trend} ({change} ошибок)")

        # Общие типы ошибок
        all_error_types = Counter()
        for stats in all_stats:
            all_error_types.update(stats['error_types'])

        error_logger.info("\nСамые частые типы ошибок (все файлы):")
        for err_type, count in all_error_types.most_common(5):
            error_logger.info(f"  {err_type:30s}: {count:4d}")


def find_common_errors(error_files: list, min_count: int = 2):
    """Находит ошибки, которые повторяются в нескольких файлах"""
    error_logger.info("\n" + "=" * 80)
    error_logger.info("ПОИСК ОБЩИХ ОШИБОК")
    error_logger.info("=" * 80)

    # Собираем ошибки по сообщениям
    error_messages = defaultdict(list)

    for error_file in error_files:
        data = load_error_file(error_file)
        if data:
            for error in data.get('errors', []):
                message = error.get('message', '')
                error_messages[message].append({
                    'file': error_file.name,
                    'line': error.get('line'),
                    'type': error.get('type')
                })

    # Находим повторяющиеся ошибки
    common_errors = {msg: details for msg, details in error_messages.items()
                     if len(details) >= min_count}

    if common_errors:
        error_logger.info(f"Найдено {len(common_errors)} общих ошибок (повторяются ≥ {min_count} раз):")
        for msg, details in sorted(common_errors.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            files = set(d['file'] for d in details)
            error_logger.info(f"  '{msg[:50]}...'")
            error_logger.info(f"    Встречается в: {len(files)} файлах")
            error_logger.info(f"    Всего случаев: {len(details)}")
    else:
        error_logger.info("Общие ошибки не найдены")


def generate_error_report(error_files: list, output_file: Path):
    """Генерирует отчёт по ошибкам"""
    error_logger.info("\n" + "=" * 80)
    error_logger.info("ГЕНЕРАЦИЯ ОТЧЁТА ПО ОШИБКАМ")
    error_logger.info("=" * 80)

    all_errors = []
    file_stats = []

    for error_file in error_files:
        data = load_error_file(error_file)
        if data:
            file_stat = {
                'filename': error_file.name,
                'total_errors': len(data.get('errors', [])),
                'timestamp': data.get('metadata', {}).get('generated_at', ''),
                'error_types': Counter([e.get('type', 'unknown') for e in data.get('errors', [])])
            }
            file_stats.append(file_stat)
            all_errors.extend(data.get('errors', []))

    # Анализ всех ошибок
    total_errors = len(all_errors)
    error_types = Counter([e.get('type', 'unknown') for e in all_errors])
    severity_dist = Counter([e.get('severity', 'unknown') for e in all_errors])

    # Создаём отчёт
    report = {
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_error_files': len(error_files),
            'total_errors': total_errors,
            'unique_error_types': len(error_types),
            'error_type_distribution': dict(error_types),
            'severity_distribution': dict(severity_dist)
        },
        'file_statistics': file_stats,
        'most_common_errors': error_types.most_common(10),
        'recommendations': generate_recommendations(error_types, severity_dist)
    }

    # Сохраняем отчёт
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        error_logger.info(f"Отчёт сохранён в: {output_file}")
        error_logger.info(f"Всего проанализировано ошибок: {total_errors}")
        error_logger.info(f"Файлов с ошибками: {len(error_files)}")

        # Выводим основные выводы
        if error_types:
            most_common = error_types.most_common(1)[0]
            error_logger.info(f"Самый частый тип ошибки: '{most_common[0]}' ({most_common[1]} раз)")

        if severity_dist:
            error_logger.info("Распределение по степени серьезности:")
            for severity, count in severity_dist.items():
                percentage = (count / total_errors) * 100 if total_errors > 0 else 0
                error_logger.info(f"  {severity:10s}: {count:4d} ({percentage:5.1f}%)")

    except Exception as e:
        error_logger.error(f"Ошибка сохранения отчёта: {e}")


def generate_recommendations(error_types: Counter, severity_dist: Counter) -> List[str]:
    """Генерирует рекомендации на основе анализа ошибок"""
    recommendations = []

    # Проверяем наиболее частые типы ошибок
    for err_type, count in error_types.most_common(3):
        if err_type == 'title_syntax':
            recommendations.append(
                "Частая ошибка: некорректный синтаксис заголовка. "
                "Убедитесь, что заголовки используют формат '[Название](URL)'."
            )
        elif err_type == 'description_capitalization':
            recommendations.append(
                "Частая ошибка: описание не начинается с заглавной буквы. "
                "Все описания должны начинаться с заглавной буквы."
            )
        elif err_type == 'auth_backticks':
            recommendations.append(
                "Частая ошибка: отсутствие обратных кавычек в поле Auth. "
                "Значения Auth (кроме 'No') должны быть обёрнуты в `backticks`."
            )
        elif err_type == 'description_length':
            recommendations.append(
                "Частая ошибка: слишком длинное описание. "
                f"Описание не должно превышать {max_description_length} символов."
            )

    # Проверяем серьёзные ошибки
    if severity_dist.get('critical', 0) > 0:
        recommendations.append(
            "Обнаружены критические ошибки. Проверьте целостность файла и наличие всех обязательных полей."
        )

    if severity_dist.get('warning', 0) > 10:
        recommendations.append(
            "Много предупреждений. Рассмотрите возможность улучшения качества данных, "
            "например, увеличив длину описаний."
        )

    # Общие рекомендации
    if len(error_types) > 10:
        recommendations.append(
            "Обнаружено много различных типов ошибок. "
            "Рекомендуется провести комплексную проверку формата файла."
        )

    if not recommendations:
        recommendations.append("На основе анализа ошибок рекомендации не требуются.")

    return recommendations


def main():
    """Основная функция анализа ошибок"""
    error_logger.info("=" * 80)
    error_logger.info("АНАЛИЗ ОШИБОК ВАЛИДАЦИИ")
    error_logger.info("=" * 80)

    log_dir = Path("logs")
    if not log_dir.exists():
        error_logger.error(f"Директория {log_dir} не существует")
        return

    # Находим все файлы с ошибками
    error_files = list(log_dir.glob("validation_errors_*.json"))

    if not error_files:
        error_logger.warning("Файлы с ошибками не найдены")
        return

    error_logger.info(f"Найдено файлов с ошибками: {len(error_files)}")

    # Сортируем по времени создания (сначала самые новые)
    error_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    # Анализируем последние 3 файла
    recent_files = error_files[:3]
    for error_file in recent_files:
        analyze_error_file(error_file)

    # Сравниваем файлы если их достаточно
    if len(error_files) >= 2:
        compare_error_files(error_files[:5])

    # Ищем общие ошибки
    if len(error_files) >= 2:
        find_common_errors(error_files[:10], min_count=2)

    # Генерируем отчёт
    if error_files:
        report_file = log_dir / f"error_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        generate_error_report(error_files[:20], report_file)

    error_logger.info("\n" + "=" * 80)
    error_logger.info("АНАЛИЗ ЗАВЕРШЁН")
    error_logger.info("=" * 80)


if __name__ == "__main__":
    # Импортируем константы из format.py
    try:
        from format import max_description_length
    except ImportError:
        max_description_length = 100

    main()