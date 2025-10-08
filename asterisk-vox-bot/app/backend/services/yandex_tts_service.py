"""
Yandex SpeechKit TTS Service с gRPC Streaming
Сверхбыстрая интеграция с Yandex Cloud для синтеза речи (1-1.5 сек)
"""

import os
import sys
import grpc
import subprocess
import hashlib
import logging
import asyncio
import wave
import io
from typing import Optional

# Добавляем путь к gRPC файлам
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from yandex.cloud.ai.tts.v3 import tts_service_pb2_grpc
    from yandex.cloud.ai.tts.v3 import tts_pb2
    # ИСПРАВЛЕНО: Все классы находятся в tts_pb2
    GRPC_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ gRPC модули для Yandex TTS загружены")
    logger.info(f"📋 Доступные классы: {[x for x in dir(tts_pb2) if 'utterance' in x.lower()]}")
except ImportError as e:
    GRPC_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ gRPC модули недоступны: {e}")
    logger.info("🔄 Будет использоваться HTTP API")
    # Fallback на HTTP API
    import requests

class YandexTTSService:
    def __init__(self):
        """Инициализация сверхбыстрого Yandex TTS с gRPC streaming"""
        self.oauth_token = os.getenv("OAUTH_TOKEN")  # Используем OAUTH_TOKEN из .env
        self.folder_id = os.getenv("YANDEX_FOLDER_ID")
        self.asterisk_sounds_dir = "/usr/share/asterisk/sounds/ru"
        
        # Кеш для коротких фраз (до 100 символов)
        self.tts_cache = {}
        
        # gRPC настройки
        self.grpc_channel = None
        self.tts_stub = None
        self.iam_token = None
        self.iam_token_expires = 0
        
        if not self.oauth_token or not self.folder_id:
            raise ValueError("Не найдены OAUTH_TOKEN или YANDEX_FOLDER_ID в .env")
        
        # Инициализируем gRPC соединение если доступно
        if GRPC_AVAILABLE:
            self._init_grpc_connection()
        
        logger.info("🚀 Yandex TTS Service с gRPC streaming инициализирован")
    
    def _create_wav_from_pcm(self, pcm_data: bytes, sample_rate: int = 8000, channels: int = 1, sample_width: int = 2) -> bytes:
        """
        Создание WAV файла из raw PCM данных
        
        Args:
            pcm_data: Raw PCM данные (LINEAR16_PCM)
            sample_rate: Частота дискретизации (8000 для Asterisk)
            channels: Количество каналов (1 = моно)
            sample_width: Ширина сэмпла в байтах (2 = 16 бит)
        
        Returns:
            bytes: WAV файл с заголовками
        """
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        
        wav_buffer.seek(0)
        return wav_buffer.read()
    
    def _init_grpc_connection(self):
        """Инициализация gRPC соединения для максимальной скорости"""
        try:
            # Создаем защищенное gRPC соединение с оптимизацией
            credentials = grpc.ssl_channel_credentials()
            self.grpc_channel = grpc.secure_channel(
                'tts.api.cloud.yandex.net:443', 
                credentials,
                options=[
                    ('grpc.keepalive_time_ms', 10000),
                    ('grpc.keepalive_timeout_ms', 5000),
                    ('grpc.keepalive_permit_without_calls', True),
                    ('grpc.http2.max_pings_without_data', 0),
                    ('grpc.http2.min_time_between_pings_ms', 10000),
                ]
            )
            self.tts_stub = tts_service_pb2_grpc.SynthesizerStub(self.grpc_channel)
            logger.info("✅ gRPC соединение с Yandex TTS установлено")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось установить gRPC соединение: {e}")
            logger.info("🔄 Будет использоваться HTTP API как fallback")
            self.grpc_channel = None
            self.tts_stub = None
    
    def _get_fresh_iam_token(self) -> str:
        """Получение свежего IAM токена из OAuth токена с кешированием"""
        import time
        import requests
        
        # Проверяем, не истек ли токен (12 часов = 43200 сек, обновляем за час до истечения)
        if self.iam_token and time.time() < (self.iam_token_expires - 3600):
            return self.iam_token
        
        url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
        headers = {"Content-Type": "application/json"}
        data = {"yandexPassportOauthToken": self.oauth_token}
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=5)
            response.raise_for_status()
            
            token_data = response.json()
            self.iam_token = token_data["iamToken"]
            
            # Токен действует 12 часов
            import time
            self.iam_token_expires = time.time() + 43200
            
            logger.info("🔑 IAM токен обновлен")
            return self.iam_token
        except Exception as e:
            logger.error(f"❌ Ошибка получения IAM токена: {e}")
            raise
    
    async def text_to_speech_grpc(self, text: str, filename_prefix: str = "tts") -> str:
        """
        Сверхбыстрый синтез речи через gRPC streaming (1-1.5 сек)
        """
        if not self.tts_stub:
            logger.warning("⚠️ gRPC недоступен, используем HTTP fallback")
            return await self.text_to_speech_http(text, filename_prefix)
        
        try:
            # Получаем свежий IAM токен
            iam_token = self._get_fresh_iam_token()
            
            # Создаем запрос для gRPC streaming с ПРАВИЛЬНЫМ форматом для Asterisk
            request = tts_pb2.UtteranceSynthesisRequest(
                text=text,
                output_audio_spec=tts_pb2.AudioFormatOptions(
                    # ✅ ИСПРАВЛЕНО: RawAudio с LINEAR16_PCM 8000Hz для Asterisk
                    raw_audio=tts_pb2.RawAudio(
                        audio_encoding=tts_pb2.RawAudio.AudioEncoding.LINEAR16_PCM,
                        sample_rate_hertz=8000  # КРИТИЧНО: 8kHz для телефонии
                    )
                ),
                hints=[
                    tts_pb2.Hints(
                        voice="jane",  # Быстрый голос
                        speed=1.2      # Ускоренная речь
                    )
                ],
                loudness_normalization_type=tts_pb2.UtteranceSynthesisRequest.LoudnessNormalizationType.LUFS
            )
            
            # Выполняем gRPC streaming запрос
            metadata = [
                ('authorization', f'Bearer {iam_token}'),
                ('x-folder-id', self.folder_id)  # ИСПРАВЛЕНО: добавляем folder_id
            ]
            
            logger.info(f"🚀 gRPC TTS запрос: {text[:50]}...")
            
            # Получаем поток raw PCM данных
            response_stream = self.tts_stub.UtteranceSynthesis(request, metadata=metadata)
            
            # Собираем raw PCM чанки
            pcm_chunks = []
            for response in response_stream:
                if response.audio_chunk.data:
                    pcm_chunks.append(response.audio_chunk.data)
            
            if not pcm_chunks:
                logger.error("❌ Пустой ответ от gRPC TTS")
                return None
            
            # Объединяем raw PCM данные
            raw_pcm = b''.join(pcm_chunks)
            
            # ✅ КРИТИЧНО: Конвертируем raw PCM в WAV для Asterisk
            audio_data = self._create_wav_from_pcm(raw_pcm, sample_rate=8000, channels=1, sample_width=2)
            
            # Сохраняем готовый WAV файл 8kHz
            cache_key = hashlib.md5(text.encode()).hexdigest()
            wav_filename = f"{filename_prefix}_{cache_key}.wav"
            wav_path = os.path.join(self.asterisk_sounds_dir, wav_filename)
            
            with open(wav_path, "wb") as f:
                f.write(audio_data)
            
            # Устанавливаем правильные права доступа для Asterisk
            subprocess.run(["chown", "asterisk:asterisk", wav_path], check=True, capture_output=True)
            subprocess.run(["chmod", "644", wav_path], check=True, capture_output=True)
            
            logger.info(f"⚡ gRPC TTS готов (8kHz WAV): {wav_filename}, размер={len(audio_data)} bytes")
            
            # Кеширование отключено для диагностики
            # if len(text) < 100:
            #     self.tts_cache[hashlib.md5(text.encode()).hexdigest()] = wav_path
            
            return wav_path
            
        except grpc.RpcError as e:
            logger.error(f"❌ gRPC ошибка: {e.code()}: {e.details()}")
            # Fallback на HTTP API
            return await self.text_to_speech_http(text, filename_prefix)
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка gRPC TTS: {e}")
            # Fallback на HTTP API
            return await self.text_to_speech_http(text, filename_prefix)
    
    async def text_to_speech_http(self, text: str, filename_prefix: str = "tts") -> str:
        """
        Fallback HTTP API для синтеза речи
        """
        import requests
        
        try:
            # Получаем свежий IAM токен
            iam_token = self._get_fresh_iam_token()
            
            # Настройки для оптимальной скорости
            url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
            headers = {"Authorization": f"Bearer {iam_token}"}
            
            data = {
                "text": text,
                "lang": "ru-RU",
                "folderId": self.folder_id,
                "voice": "jane",  # Быстрый голос
                "emotion": "neutral",
                "speed": "1.2",  # Ускоренная речь
                "format": "lpcm",
                "sampleRateHertz": "8000"
            }
            
            logger.info(f"🎤 HTTP TTS запрос: {text[:50]}...")
            
            # Выполняем запрос к TTS API
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            
            # Сохраняем raw LPCM данные
            cache_key = hashlib.md5(text.encode()).hexdigest()
            raw_filename = f"{filename_prefix}_{cache_key}.raw"
            raw_path = os.path.join("/tmp", raw_filename)
            
            with open(raw_path, "wb") as f:
                f.write(response.content)
            
            # ВОССТАНОВЛЕНО: Оригинальная sox конвертация из архивной версии
            wav_filename = f"{filename_prefix}_{cache_key}.wav"
            wav_path = os.path.join(self.asterisk_sounds_dir, wav_filename)
            
            # sox конвертация: raw LPCM -> 8kHz mono WAV
            sox_cmd = [
                "sox", "-t", "raw", "-r", "8000", "-e", "signed-integer", "-b", "16", "-c", "1",
                raw_path, "-t", "wav", wav_path
            ]
            
            subprocess.run(sox_cmd, check=True, capture_output=True)
            
            # Удаляем временный raw файл
            os.remove(raw_path)
            
            logger.info(f"✅ HTTP TTS готов: {wav_filename}")
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Отключаем кеширование для диагностики
            # Кешируем короткие фразы
            if False:  # Отключаем кеширование
                self.tts_cache[cache_key] = wav_path
            
            return wav_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка HTTP TTS: {e}")
            return None
    
    async def text_to_speech(self, text: str, filename: str) -> Optional[str]:
        """
        Основной метод синтеза речи - автоматически выбирает лучший способ
        Возвращает имя файла без расширения для совместимости с существующим кодом
        """
        if not text.strip():
            logger.warning("⚠️ Пустой текст для TTS")
            return None
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Отключаем кеширование для диагностики
        # Проверяем кеш для коротких фраз
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if False:  # Отключаем кеширование
            cached_path = self.tts_cache[cache_key]
            if os.path.exists(cached_path):
                logger.info(f"🎯 Используем кешированный TTS для: {text[:30]}...")
                # Возвращаем имя файла без расширения и пути
                return os.path.splitext(os.path.basename(cached_path))[0]
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Принудительно используем HTTP TTS (как было до оптимизаций)
        # Приоритет: HTTP API (рабочий) -> gRPC streaming (проблемный)
        if False:  # Отключаем gRPC для диагностики
            full_path = await self.text_to_speech_grpc(text, filename)
        else:
            full_path = await self.text_to_speech_http(text, filename)
        
        if full_path and os.path.exists(full_path):
            # Возвращаем имя файла без расширения и пути для совместимости
            # Поддерживаем как .wav, так и .gsm, .ulaw, .alaw расширения
            filename = os.path.basename(full_path)
            if filename.endswith('.gsm'):
                return filename[:-4]  # убираем .gsm
            elif filename.endswith('.ulaw'):
                return filename[:-5]  # убираем .ulaw
            elif filename.endswith('.alaw'):
                return filename[:-5]  # убираем .alaw
            elif filename.endswith('.wav'):
                return filename[:-4]  # убираем .wav
            else:
                return filename
        else:
            return None
    
    def __del__(self):
        """Закрываем gRPC соединение при уничтожении объекта"""
        if self.grpc_channel:
            self.grpc_channel.close()

# Глобальный экземпляр сервиса
_yandex_tts_service = None

def get_yandex_tts_service() -> YandexTTSService:
    """Фабрика для создания сверхбыстрого TTS сервиса"""
    global _yandex_tts_service
    if _yandex_tts_service is None:
        _yandex_tts_service = YandexTTSService()
    return _yandex_tts_service