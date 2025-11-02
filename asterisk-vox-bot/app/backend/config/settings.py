"""
Централизованная конфигурация приложения.

Использует Pydantic BaseSettings для загрузки и валидации настроек из .env файла.
Все настройки должны загружаться через этот модуль для централизованного управления.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Центральные настройки приложения."""
    
    # ==========================================
    # ASTERISK ARI НАСТРОЙКИ
    # ==========================================
    ari_http_url: str = Field(
        default="http://localhost:8088",
        description="HTTP URL для подключения к Asterisk ARI"
    )
    ari_username: str = Field(
        default="asterisk",
        description="Имя пользователя для ARI"
    )
    ari_password: str = Field(
        default="asterisk123",
        description="Пароль для ARI"
    )
    ari_app_name: str = Field(
        default="asterisk-bot",
        description="Имя приложения Stasis в Asterisk"
    )
    
    # ==========================================
    # REDIS НАСТРОЙКИ
    # ==========================================
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="URL для подключения к Redis"
    )
    
    # ==========================================
    # ТАЙМАУТЫ И ПОРОГИ
    # ==========================================
    speech_end_timeout: float = Field(
        default=0.2,
        ge=0.1,
        le=5.0,
        description="Таймаут окончания речи в секундах (для определения конца фразы пользователя)"
    )
    max_silence_duration: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Максимальная длительность тишины в секундах перед автоматическим завершением"
    )
    barge_in_guard_ms: int = Field(
        default=400,
        ge=0,
        le=5000,
        description="Защитный интервал в миллисекундах для предотвращения прерывания речи бота"
    )
    input_debounce_ms: int = Field(
        default=1200,
        ge=0,
        le=5000,
        description="Интервал подавления дребезга входящих сигналов в миллисекундах"
    )
    
    # ==========================================
    # НАСТРОЙКИ ДЕТЕКЦИИ РЕЧИ
    # ==========================================
    speech_silence_timeout: float = Field(
        default=1.2,
        ge=0.1,
        le=10.0,
        description="Таймаут тишины для определения конца речи в секундах"
    )
    speech_min_duration: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description="Минимальная длительность речи в секундах для обработки"
    )
    speech_max_recording_time: float = Field(
        default=15.0,
        ge=1.0,
        le=60.0,
        description="Максимальное время записи речи в секундах"
    )
    speech_detection_enabled: bool = Field(
        default=False,
        description="Включить умную детекцию речи"
    )
    speech_debug_logging: bool = Field(
        default=False,
        description="Включить отладочное логирование детекции речи"
    )
    
    # ==========================================
    # НАСТРОЙКИ VAD (Voice Activity Detection)
    # ==========================================
    vad_enabled: bool = Field(
        default=False,
        description="Включить VAD для уменьшения паузы после речи"
    )
    
    # ==========================================
    # ВАЛИДАТОРЫ
    # ==========================================
    
    @field_validator('ari_http_url')
    @classmethod
    def validate_ari_url(cls, v: str) -> str:
        """Проверяет, что ARI URL начинается с http:// или https://."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('ari_http_url должен начинаться с http:// или https://')
        return v
    
    @field_validator('redis_url')
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Проверяет, что Redis URL имеет корректный формат."""
        if not v.startswith('redis://'):
            raise ValueError('redis_url должен начинаться с redis://')
        return v
    
    class Config:
        """Настройки Pydantic."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # Разрешаем дополнительные поля для постепенной миграции


# Создаем глобальный экземпляр настроек
# Этот экземпляр будет загружен один раз при импорте модуля
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Получить экземпляр настроек (Singleton паттерн).
    
    Настройки загружаются один раз при первом вызове функции.
    Все последующие вызовы возвращают тот же экземпляр.
    
    Returns:
        Settings: Экземпляр настроек приложения
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Принудительно перезагрузить настройки из .env файла.
    
    Используется в случаях, когда .env файл был изменен во время работы приложения.
    
    Returns:
        Settings: Новый экземпляр настроек приложения
    """
    global _settings
    _settings = Settings()
    return _settings


# Для удобного импорта: from app.backend.config.settings import settings
settings = get_settings()
