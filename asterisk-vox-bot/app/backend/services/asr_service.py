"""
ASR (Automatic Speech Recognition) сервис для распознавания речи.
Использует Yandex SpeechKit API для преобразования аудио в текст.
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ASRService:
    def __init__(self):
        self.model = os.getenv("ASR_MODEL", "general")
        self.language = os.getenv("ASR_LANGUAGE", "ru-RU")
        
        # Инициализируем Yandex ASR сервис
        try:
            from .yandex_asr_service import get_yandex_asr_service
            self.yandex_asr = get_yandex_asr_service()
            logger.info("✅ Yandex ASR сервис инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Yandex ASR: {e}")
            raise
        
        logger.info(f"ASR Service инициализирован: model={self.model}, language={self.language}")

    async def speech_to_text(self, audio_path: str, prompt: Optional[str] = None) -> str:
        """
        Преобразует аудио файл в текст используя Yandex SpeechKit.
        
        Args:
            audio_path: Путь к аудио файлу
            prompt: Дополнительный промпт для улучшения качества распознавания
            
        Returns:
            str: Распознанный текст
        """
        # Используем Yandex ASR сервис
        return await self.yandex_asr.speech_to_text(audio_path, prompt)

# Глобальный экземпляр сервиса
asr_service = None

def get_asr_service() -> ASRService:
    """Возвращает глобальный экземпляр ASR сервиса."""
    global asr_service
    if asr_service is None:
        asr_service = ASRService()
    return asr_service

# Тестирование
if __name__ == "__main__":
    import asyncio
    
    async def test_asr():
        service = ASRService()
        
        # Для тестирования нужен реальный аудио файл
        test_audio = "data/audio/test_greeting.wav"
        
        if os.path.exists(test_audio):
            try:
                text = await service.speech_to_text(test_audio)
                print(f"✅ Тест пройден! Распознанный текст: '{text}'")
            except Exception as e:
                print(f"❌ Тест не пройден: {e}")
        else:
            print(f"⚠️ Тестовый аудио файл не найден: {test_audio}")
    
    asyncio.run(test_asr())