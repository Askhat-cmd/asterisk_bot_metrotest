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
