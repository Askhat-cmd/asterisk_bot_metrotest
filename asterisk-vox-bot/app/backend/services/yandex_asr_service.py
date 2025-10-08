"""
Yandex SpeechKit ASR (Automatic Speech Recognition) сервис для распознавания речи.
Использует Yandex SpeechKit API для преобразования аудио в текст.
"""
import os
import logging
import aiohttp
import aiofiles
import json
from typing import Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class YandexASRService:
    def __init__(self):
        self.oauth_token = os.getenv("OAUTH_TOKEN")
        self.folder_id = os.getenv("YANDEX_FOLDER_ID")
        self.iam_token = None
        self.token_expires_at = None
        
        if not self.oauth_token:
            raise ValueError("OAUTH_TOKEN не установлен в переменных окружения")
        if not self.folder_id:
            raise ValueError("YANDEX_FOLDER_ID не установлен в переменных окружения")
        
        self.language = os.getenv("ASR_LANGUAGE", "ru-RU")
        self.model = os.getenv("ASR_MODEL", "general")
        self.base_url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
        
        logger.info(f"Yandex ASR Service инициализирован: language={self.language}, model={self.model}")
        logger.info("🔄 IAM токен будет обновляться автоматически каждые 12 часов")

    async def _get_iam_token(self):
        """Получает актуальный IAM токен, обновляя его при необходимости"""
        if self.token_needs_refresh():
            await self._refresh_iam_token()
        return self.iam_token

    def token_needs_refresh(self):
        """Проверяет, нужно ли обновить IAM токен"""
        if not self.iam_token or not self.token_expires_at:
            return True
        
        # Обновляем за 30 минут до истечения
        refresh_time = self.token_expires_at - timedelta(minutes=30)
        
        # Приводим к одному часовому поясу для сравнения
        now = datetime.now()
        if self.token_expires_at.tzinfo is not None:
            # Если токен с часовым поясом, приводим текущее время к UTC
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        
        return now >= refresh_time

    async def _refresh_iam_token(self):
        """Обновляет IAM токен из OAuth токена"""
        try:
            url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
            payload = {"yandexPassportOauthToken": self.oauth_token}
            headers = {"Content-Type": "application/json"}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.iam_token = data["iamToken"]
                        
                        # Токен действует 12 часов
                        expires_at = data.get("expiresAt")
                        if expires_at:
                            self.token_expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        else:
                            self.token_expires_at = datetime.now() + timedelta(hours=12)
                        
                        logger.info(f"✅ IAM токен обновлен! Действует до: {self.token_expires_at}")
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка обновления IAM токена: {response.status} - {error_text}")
                        raise Exception(f"IAM token refresh failed: {response.status}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка обновления IAM токена: {e}")
            raise

    async def speech_to_text(self, audio_path: str, prompt: Optional[str] = None) -> str:
        """
        Преобразует аудио файл в текст используя Yandex SpeechKit.
        
        Args:
            audio_path: Путь к аудио файлу
            prompt: Дополнительный промпт для улучшения качества распознавания
            
        Returns:
            str: Распознанный текст
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Аудио файл не найден: {audio_path}")
        
        try:
            # Получаем актуальный IAM токен (с автоматическим обновлением)
            iam_token = await self._get_iam_token()
            
            # Yandex SpeechKit STT API endpoint
            url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
            
            # Подготавливаем заголовки
            headers = {
                "Authorization": f"Bearer {iam_token}",
                "x-folder-id": self.folder_id,
                "Content-Type": "audio/x-pcm;bit=16;rate=8000"
            }
            
            # Подготавливаем параметры
            params = {
                "lang": self.language,
                "format": "lpcm",
                "sampleRateHertz": "8000",
                "encoding": "LINEAR16_PCM",
                "folderId": self.folder_id
            }
            
            if prompt:
                params["profanityFilter"] = "true"
                params["literateText"] = "true"
            
            # Читаем аудио файл
            async with aiofiles.open(audio_path, 'rb') as f:
                audio_data = await f.read()
            
            logger.info(f"🎤 Yandex ASR запрос: {len(audio_data)} bytes, language={self.language}")
            
            # Отправляем запрос к Yandex SpeechKit
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    params=params,
                    data=audio_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        recognized_text = result.get("result", "").strip()
                        
                        if recognized_text:
                            logger.info(f"✅ Yandex ASR распознано: '{recognized_text}'")
                            return recognized_text
                        else:
                            logger.warning("⚠️ Yandex ASR вернул пустой результат")
                            return ""
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Yandex ASR ошибка {response.status}: {error_text}")
                        raise Exception(f"Yandex ASR API error: {response.status} - {error_text}")
                        
        except aiohttp.ClientError as e:
            logger.error(f"❌ Ошибка HTTP запроса к Yandex ASR: {e}")
            raise Exception(f"Yandex ASR HTTP error: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка Yandex ASR: {e}")
            raise Exception(f"Yandex ASR error: {e}")

    async def test_connection(self) -> bool:
        """
        Тестирует соединение с Yandex SpeechKit.
        
        Returns:
            bool: True если соединение работает
        """
        try:
            # Создаем тестовый аудио файл (1 секунда тишины)
            test_audio_path = "/tmp/test_yandex_asr.wav"
            
            # Создаем минимальный WAV файл с заголовками
            wav_header = self._create_wav_header(8000, 8000, 1, 16)  # 1 секунда, 8kHz, моно, 16-bit
            silence_data = b'\x00' * 8000  # 1 секунда тишины
            
            async with aiofiles.open(test_audio_path, 'wb') as f:
                await f.write(wav_header + silence_data)
            
            # Тестируем распознавание
            result = await self.speech_to_text(test_audio_path)
            
            # Очищаем тестовый файл
            if os.path.exists(test_audio_path):
                os.remove(test_audio_path)
            
            logger.info(f"✅ Yandex ASR соединение работает, результат: '{result}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Yandex ASR соединение не работает: {e}")
            return False

    def _create_wav_header(self, sample_rate: int, data_size: int, channels: int, bits_per_sample: int) -> bytes:
        """Создает WAV заголовок для аудио файла."""
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        
        header = b'RIFF'
        header += (data_size + 36).to_bytes(4, 'little')  # ChunkSize
        header += b'WAVE'
        header += b'fmt '
        header += (16).to_bytes(4, 'little')  # Subchunk1Size
        header += (1).to_bytes(2, 'little')   # AudioFormat (PCM)
        header += channels.to_bytes(2, 'little')
        header += sample_rate.to_bytes(4, 'little')
        header += byte_rate.to_bytes(4, 'little')
        header += block_align.to_bytes(2, 'little')
        header += bits_per_sample.to_bytes(2, 'little')
        header += b'data'
        header += data_size.to_bytes(4, 'little')
        
        return header

# Глобальный экземпляр сервиса
yandex_asr_service = None

def get_yandex_asr_service() -> YandexASRService:
    """Возвращает глобальный экземпляр Yandex ASR сервиса."""
    global yandex_asr_service
    if yandex_asr_service is None:
        yandex_asr_service = YandexASRService()
    return yandex_asr_service

# Тестирование
if __name__ == "__main__":
    import asyncio
    
    async def test_yandex_asr():
        service = YandexASRService()
        
        # Тестируем соединение
        if await service.test_connection():
            print("✅ Yandex ASR соединение работает")
        else:
            print("❌ Yandex ASR соединение не работает")
    
    asyncio.run(test_yandex_asr())
