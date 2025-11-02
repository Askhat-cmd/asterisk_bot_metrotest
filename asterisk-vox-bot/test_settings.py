#!/usr/bin/env python3
"""
Простой тест для проверки загрузки настроек.
Запустите: python test_settings.py
"""

import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_settings():
    """Тестирует загрузку и валидацию настроек."""
    print("=" * 70)
    print("ТЕСТ ЗАГРУЗКИ ЦЕНТРАЛИЗОВАННЫХ НАСТРОЕК")
    print("=" * 70)
    
    try:
        from app.backend.config.settings import settings
        
        print("\n✅ Настройки успешно загружены!\n")
        
        print("📋 ASTERISK ARI:")
        print(f"  • URL:      {settings.ari_http_url}")
        print(f"  • Username: {settings.ari_username}")
        print(f"  • Password: {'*' * len(settings.ari_password)}")
        print(f"  • App Name: {settings.ari_app_name}")
        
        print("\n📋 REDIS:")
        print(f"  • URL: {settings.redis_url}")
        
        print("\n📋 ТАЙМАУТЫ:")
        print(f"  • Speech end timeout:   {settings.speech_end_timeout}s")
        print(f"  • Max silence duration: {settings.max_silence_duration}s")
        
        print("\n" + "=" * 70)
        print("✅ ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО")
        print("=" * 70)
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        print("\n💡 Подсказка:")
        print("  1. Убедитесь, что установлен pydantic-settings:")
        print("     pip install pydantic-settings")
        print("  2. Создайте .env файл на основе .env.example:")
        print("     cp .env.example .env")
        print("=" * 70)
        return False

if __name__ == "__main__":
    success = test_settings()
    sys.exit(0 if success else 1)
