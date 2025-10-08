"""
TTS (Text-to-Speech) сервис для преобразования текста в аудио файлы.
Использует OpenAI TTS API для генерации речи.
"""
import os
import logging
import aiohttp
import aiofiles
import subprocess
import asyncio
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY не установлен в переменных окружения")
        
        self.voice = os.getenv("TTS_VOICE", "alloy")  # alloy, echo, fable, onyx, nova, shimmer
        self.model = os.getenv("TTS_MODEL", "tts-1")  # tts-1 или tts-1-hd
        self.audio_dir = os.getenv("TTS_AUDIO_DIR", "data/audio")
        # Используем стандартный путь Asterisk для звуков
        self.asterisk_sounds_dir = "/var/lib/asterisk/sounds/ru"
        
        # Создаем директории для аудио файлов
        os.makedirs(self.audio_dir, exist_ok=True)
        os.makedirs(self.asterisk_sounds_dir, exist_ok=True)
        
        logger.info(f"TTS Service инициализирован: voice={self.voice}, model={self.model}")

    async def text_to_speech(self, text: str, filename: Optional[str] = None) -> str:
        """
        Преобразует текст в речь, конвертирует для Asterisk и возвращает имя файла для ARI.
        
        Args:
            text: Текст для озвучивания
            filename: Имя файла (без расширения). Если не указано, генерируется автоматически
            
        Returns:
            str: Имя файла для использования в ARI (без расширения и пути)
        """
        if not text.strip():
            raise ValueError("Текст для озвучивания не может быть пустым")
        
        # Генерируем имя файла, если не указано
        if not filename:
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            filename = f"tts_{text_hash}"
        
        # Пути к файлам: создаем только WAV для Asterisk
        temp_audio_path = os.path.join(self.audio_dir, f"{filename}.wav")
        dest_wav_path = os.path.join(self.asterisk_sounds_dir, f"{filename}.wav")
        
        # Если файл уже существует в Asterisk, возвращаем имя
        if os.path.exists(dest_wav_path):
            logger.info(f"Аудио файл уже существует в Asterisk: {dest_wav_path}")
            return filename
        
        try:
            # 1. Генерируем речь через OpenAI TTS API
            url = "https://api.openai.com/v1/audio/speech"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": self.model,
                "input": text,
                "voice": self.voice,
                "response_format": "wav"
            }
            
            logger.info(f"Генерируем речь для текста: '{text[:50]}...'")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        # Сохраняем временный файл
                        async with aiofiles.open(temp_audio_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        
                        logger.info(f"✅ Временный аудио файл создан: {temp_audio_path}")
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка TTS API: {response.status} - {error_text}")
                        raise Exception(f"TTS API error: {response.status} - {error_text}")
            
            # 2. Конвертируем для Asterisk (WAV 8kHz mono)
            await self._convert_wav(temp_audio_path, dest_wav_path)
            
            logger.info(f"✅ Аудио готово для Asterisk: {filename}")
            return filename
                        
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации речи: {e}", exc_info=True)
            raise

    async def _convert_wav(self, input_path: str, output_path: str):
        """Конвертирует временный WAV в WAV 8kHz mono для Asterisk."""
        try:
            # Команда sox для конвертации в WAV 8kHz mono
            # Убираем лишние параметры - Asterisk сам разберется с форматом
            cmd = [
                "sox", input_path, 
                "-r", "8000",      # Sample rate 8kHz
                "-c", "1",         # Mono
                output_path
            ]
            
            logger.info(f"Конвертируем в WAV: {input_path} → {output_path}")
            
            # Запускаем sox асинхронно
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"✅ WAV готов: {output_path}")
                
                # Удаляем временный файл
                if os.path.exists(input_path):
                    os.remove(input_path)
                    
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"❌ Ошибка конвертации (WAV) sox: {error_msg}")
                raise Exception(f"Sox conversion failed (wav): {error_msg}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при конвертации WAV: {e}")
            raise

    async def cleanup_old_files(self, max_files: int = 100):
        """
        Удаляет старые аудио файлы, оставляя только max_files самых новых.
        """
        try:
            files = []
            for filename in os.listdir(self.audio_dir):
                if filename.endswith('.wav'):
                    filepath = os.path.join(self.audio_dir, filename)
                    mtime = os.path.getmtime(filepath)
                    files.append((filepath, mtime))
            
            # Сортируем по времени модификации (новые первыми)
            files.sort(key=lambda x: x[1], reverse=True)
            
            # Удаляем старые файлы
            for filepath, _ in files[max_files:]:
                os.remove(filepath)
                logger.info(f"🗑️ Удален старый аудио файл: {filepath}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке старых файлов: {e}")

# Глобальный экземпляр сервиса
tts_service = None

def get_tts_service() -> TTSService:
    """Возвращает глобальный экземпляр TTS сервиса."""
    global tts_service
    if tts_service is None:
        tts_service = TTSService()
    return tts_service

# Тестирование
if __name__ == "__main__":
    import asyncio
    
    async def test_tts():
        service = TTSService()
        
        test_text = "Привет! Это тестовое сообщение для проверки работы TTS сервиса."
        
        try:
            audio_path = await service.text_to_speech(test_text, "test_greeting")
            print(f"✅ Тест пройден! Аудио файл: {audio_path}")
        except Exception as e:
            print(f"❌ Тест не пройден: {e}")
    
    asyncio.run(test_tts())
