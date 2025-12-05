#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Настройки и конфигурация приложения
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class LogLevel(str, Enum):
    """Уровни логирования"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class OutputFormat(str, Enum):
    """Форматы вывода"""
    CONSOLE = "console"
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass
class LoggingConfig:
    """Конфигурация логирования"""

    # Основные настройки
    level: LogLevel = LogLevel.INFO
    format: str = "detailed"
    enable_file_logging: bool = True
    enable_console_logging: bool = True

    # Настройки файлов
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    max_file_size_mb: int = 5
    backup_count: int = 10
    error_log_retention_days: int = 14

    # Дополнительные функции
    enable_performance_logging: bool = True
    enable_statistics_logging: bool = True
    enable_error_tracking: bool = True
    enable_json_logging: bool = True

    # Внешние интеграции (заглушки для будущего расширения)
    enable_telegram_notifications: bool = False
    enable_email_notifications: bool = False
    enable_slack_notifications: bool = False

    # Метрики и мониторинг
    metrics_enabled: bool = True
    metrics_interval_seconds: int = 60

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Создаёт конфигурацию из переменных окружения"""
        return cls(
            level=LogLevel(os.getenv("LOG_LEVEL", "INFO")),
            format=os.getenv("LOG_FORMAT", "detailed"),
            enable_file_logging=os.getenv("ENABLE_FILE_LOGGING", "true").lower() == "true",
            enable_console_logging=os.getenv("ENABLE_CONSOLE_LOGGING", "true").lower() == "true",
            log_dir=Path(os.getenv("LOG_DIR", "logs")),
            max_file_size_mb=int(os.getenv("MAX_LOG_SIZE_MB", "5")),
            backup_count=int(os.getenv("LOG_BACKUP_COUNT", "10")),
            error_log_retention_days=int(os.getenv("ERROR_LOG_RETENTION_DAYS", "14")),
            enable_performance_logging=os.getenv("ENABLE_PERFORMANCE_LOGGING", "true").lower() == "true",
            enable_statistics_logging=os.getenv("ENABLE_STATISTICS_LOGGING", "true").lower() == "true",
            enable_error_tracking=os.getenv("ENABLE_ERROR_TRACKING", "true").lower() == "true",
            enable_json_logging=os.getenv("ENABLE_JSON_LOGGING", "true").lower() == "true",
        )

    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует конфигурацию в словарь"""
        return {
            "level": self.level.value,
            "format": self.format,
            "enable_file_logging": self.enable_file_logging,
            "enable_console_logging": self.enable_console_logging,
            "log_dir": str(self.log_dir),
            "max_file_size_mb": self.max_file_size_mb,
            "backup_count": self.backup_count,
            "error_log_retention_days": self.error_log_retention_days,
            "enable_performance_logging": self.enable_performance_logging,
            "enable_statistics_logging": self.enable_statistics_logging,
            "enable_error_tracking": self.enable_error_tracking,
            "enable_json_logging": self.enable_json_logging,
        }


@dataclass
class ValidationConfig:
    """Конфигурация валидации"""

    # Основные ограничения
    max_description_length: int = 100
    min_entries_per_category: int = 3
    min_description_length: int = 20  # для предупреждений

    # Настройки проверок
    check_alphabetical_order: bool = True
    check_index_consistency: bool = True
    check_category_structure: bool = True
    check_entry_formatting: bool = True

    # Строгие проверки
    strict_mode: bool = False  # Если True, предупреждения считаются ошибками
    fail_on_warnings: bool = False

    @classmethod
    def from_env(cls) -> "ValidationConfig":
        """Создаёт конфигурацию из переменных окружения"""
        return cls(
            max_description_length=int(os.getenv("MAX_DESCRIPTION_LENGTH", "100")),
            min_entries_per_category=int(os.getenv("MIN_ENTRIES_PER_CATEGORY", "3")),
            min_description_length=int(os.getenv("MIN_DESCRIPTION_LENGTH", "20")),
            check_alphabetical_order=os.getenv("CHECK_ALPHABETICAL_ORDER", "true").lower() == "true",
            check_index_consistency=os.getenv("CHECK_INDEX_CONSISTENCY", "true").lower() == "true",
            check_category_structure=os.getenv("CHECK_CATEGORY_STRUCTURE", "true").lower() == "true",
            check_entry_formatting=os.getenv("CHECK_ENTRY_FORMATTING", "true").lower() == "true",
            strict_mode=os.getenv("STRICT_MODE", "false").lower() == "true",
            fail_on_warnings=os.getenv("FAIL_ON_WARNINGS", "false").lower() == "true",
        )


@dataclass
class AppConfig:
    """Основная конфигурация приложения"""

    # Настройки приложения
    app_name: str = "API Format Checker"
    app_version: str = "1.0.0"
    app_description: str = "Проверка формата Markdown файлов с API"

    # Конфигурации компонентов
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)

    # Пути
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    config_dir: Path = field(default_factory=lambda: Path(__file__).parent)
    test_files_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "test_files")

    # Настройки производительности
    max_file_size_bytes: int = 10 * 1024 * 1024  # 10MB
    max_lines_to_process: Optional[int] = None  # None = без ограничений
    processing_timeout_seconds: int = 30

    @classmethod
    def load(cls) -> "AppConfig":
        """Загружает конфигурацию приложения"""
        config = cls()

        # Переопределяем из переменных окружения
        if os.getenv("APP_CONFIG_LOADED") != "true":
            config.logging = LoggingConfig.from_env()
            config.validation = ValidationConfig.from_env()

            # Дополнительные настройки из env
            config.app_name = os.getenv("APP_NAME", config.app_name)
            config.max_file_size_bytes = int(os.getenv("MAX_FILE_SIZE_BYTES", str(config.max_file_size_bytes)))
            config.processing_timeout_seconds = int(
                os.getenv("PROCESSING_TIMEOUT_SECONDS", str(config.processing_timeout_seconds)))

        return config

    def validate(self) -> bool:
        """Проверяет корректность конфигурации"""
        try:
            # Проверяем пути
            self.base_dir.mkdir(exist_ok=True)
            self.config_dir.mkdir(exist_ok=True)
            self.logging.log_dir.mkdir(exist_ok=True)

            # Проверяем значения
            if self.max_file_size_bytes <= 0:
                raise ValueError("max_file_size_bytes должен быть положительным")

            if self.logging.max_file_size_mb <= 0:
                raise ValueError("max_file_size_mb должен быть положительным")

            if self.validation.max_description_length <= 0:
                raise ValueError("max_description_length должен быть положительным")

            return True
        except Exception as e:
            print(f"Ошибка конфигурации: {e}")
            return False

    def save_to_file(self, filepath: Path) -> bool:
        """Сохраняет конфигурацию в файл"""
        import yaml

        try:
            data = {
                "app": {
                    "name": self.app_name,
                    "version": self.app_version,
                    "description": self.app_description,
                },
                "logging": self.logging.to_dict(),
                "validation": {
                    "max_description_length": self.validation.max_description_length,
                    "min_entries_per_category": self.validation.min_entries_per_category,
                    "min_description_length": self.validation.min_description_length,
                    "check_alphabetical_order": self.validation.check_alphabetical_order,
                    "check_index_consistency": self.validation.check_index_consistency,
                    "check_category_structure": self.validation.check_category_structure,
                    "check_entry_formatting": self.validation.check_entry_formatting,
                    "strict_mode": self.validation.strict_mode,
                    "fail_on_warnings": self.validation.fail_on_warnings,
                },
                "paths": {
                    "base_dir": str(self.base_dir),
                    "config_dir": str(self.config_dir),
                    "test_files_dir": str(self.test_files_dir),
                },
                "performance": {
                    "max_file_size_bytes": self.max_file_size_bytes,
                    "max_lines_to_process": self.max_lines_to_process,
                    "processing_timeout_seconds": self.processing_timeout_seconds,
                }
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

            return True
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")
            return False


# Глобальная конфигурация
config = AppConfig.load()