"""
TTS Adapter - Умный адаптер с автоматическим fallback
Архитектурное решение для достижения 1.1 секунды ответа
"""

import asyncio
import time
import logging
from typing import Optional, Dict, Any

from .yandex_grpc_tts import YandexGrpcTTS
from .yandex_tts_service import YandexTTSService

logger = logging.getLogger(__name__)

class TTSAdapter:
    """
    Умный TTS адаптер с автоматическим fallback
    - Primary: gRPC TTS (быстрый, <250мс)
    - Fallback: HTTP TTS (надежный, 700мс)
    """
    
    def __init__(self):
        self.grpc_tts = YandexGrpcTTS()
        self.http_tts = YandexTTSService()  # Существующий HTTP TTS
        self.grpc_healthy = True
        self.fallback_count = 0
        self.success_count = 0
        
        # Метрики для мониторинга
        self.metrics = {
            "grpc_success_count": 0,
            "grpc_error_count": 0,
            "http_fallback_count": 0,
            "grpc_latency_sum": 0,
            "grpc_latency_count": 0
        }
        
        logger.info("🚀 TTSAdapter инициализирован с gRPC + HTTP fallback")
        
    async def initialize(self):
        """Инициализация обоих TTS сервисов"""
        try:
            await self.grpc_tts.initialize()
            logger.info("✅ TTSAdapter initialized with gRPC + HTTP fallback")
        except Exception as e:
            logger.error(f"❌ gRPC TTS init failed: {e}")
            self.grpc_healthy = False
            logger.info("🔄 TTSAdapter будет использовать только HTTP TTS")
        
    async def synthesize(self, text: str) -> bytes:
        """
        Умный синтез с автоматическим fallback
        """
        if self.grpc_healthy:
            try:
                start_time = time.time()
                audio_data = await self.grpc_tts.synthesize_chunk_fast(text)
                elapsed = time.time() - start_time
                
                # Обновляем метрики
                self.metrics["grpc_success_count"] += 1
                self.metrics["grpc_latency_sum"] += elapsed
                self.metrics["grpc_latency_count"] += 1
                self.success_count += 1
                
                # Периодически проверяем здоровье gRPC
                if self.success_count % 10 == 0:
                    await self._check_grpc_health()
                
                logger.info(f"✅ gRPC TTS success: {elapsed:.2f}s")
                return audio_data
                
            except Exception as e:
                logger.warning(f"gRPC TTS failed: {e}, falling back to HTTP")
                self.grpc_healthy = False
                self.metrics["grpc_error_count"] += 1
                self.fallback_count += 1
                self.metrics["http_fallback_count"] += 1
                
                # Fallback на HTTP TTS
                return await self._http_fallback(text)
        else:
            # Используем HTTP TTS
            return await self._http_fallback(text)
    
    async def _http_fallback(self, text: str) -> bytes:
        """Fallback на HTTP TTS"""
        try:
            # Используем существующий HTTP TTS сервис
            # Создаем временный файл для получения аудио данных
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Генерируем аудио через HTTP TTS
            result = await self.http_tts.text_to_speech(text, "fallback")
            
            if result:
                # Читаем сгенерированный файл
                wav_path = os.path.join(self.http_tts.asterisk_sounds_dir, f"{result}.wav")
                if os.path.exists(wav_path):
                    with open(wav_path, 'rb') as f:
                        audio_data = f.read()
                    
                    # Удаляем временный файл
                    os.unlink(wav_path)
                    return audio_data
            
            logger.error("❌ HTTP TTS fallback failed")
            return b""
            
        except Exception as e:
            logger.error(f"❌ HTTP TTS fallback error: {e}")
            return b""
    
    async def _check_grpc_health(self):
        """Проверка здоровья gRPC соединения"""
        try:
            # Простой тест соединения
            test_audio = await self.grpc_tts.synthesize_chunk_fast("тест")
            if len(test_audio) > 0:
                self.grpc_healthy = True
                logger.info("✅ gRPC TTS health check passed")
        except Exception as e:
            logger.warning(f"gRPC TTS health check failed: {e}")
            self.grpc_healthy = False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получение метрик производительности"""
        total_requests = (self.metrics["grpc_success_count"] + 
                         self.metrics["grpc_error_count"] + 
                         self.metrics["http_fallback_count"])
        
        grpc_success_rate = (self.metrics["grpc_success_count"] / total_requests 
                           if total_requests > 0 else 0)
        
        avg_grpc_latency = (self.metrics["grpc_latency_sum"] / self.metrics["grpc_latency_count"] 
                          if self.metrics["grpc_latency_count"] > 0 else 0)
        
        fallback_rate = (self.metrics["http_fallback_count"] / total_requests 
                        if total_requests > 0 else 0)
        
        return {
            "grpc_success_rate": grpc_success_rate,
            "avg_grpc_latency": avg_grpc_latency,
            "fallback_rate": fallback_rate,
            "grpc_healthy": self.grpc_healthy,
            "total_requests": total_requests
        }
    
    async def synthesize_chunk_fast(self, text: str) -> Optional[bytes]:
        """
        Быстрый синтез для чанков с приоритетом на скорость
        Используется ParallelTTSProcessor для немедленной обработки
        """
        try:
            # Используем gRPC для максимальной скорости
            if self.grpc_healthy:
                start_time = time.time()
                audio_data = await self.grpc_tts.synthesize(text)
                latency = time.time() - start_time
                
                if audio_data:
                    self.metrics["grpc_success_count"] += 1
                    self.metrics["grpc_latency_sum"] += latency
                    self.metrics["grpc_latency_count"] += 1
                    
                    # Логируем быстрые чанки
                    if latency < 0.5:
                        logger.info(f"⚡ Fast chunk TTS: {latency:.3f}s for '{text[:30]}...'")
                    else:
                        logger.warning(f"🐌 Slow chunk TTS: {latency:.3f}s for '{text[:30]}...'")
                    
                    return audio_data
                else:
                    raise Exception("gRPC TTS returned None")
            else:
                raise Exception("gRPC TTS not healthy")
                
        except Exception as e:
            logger.error(f"❌ Chunk TTS error: {e}")
            self.metrics["grpc_error_count"] += 1
            
            # Fallback на HTTP TTS
            try:
                logger.info("🔄 Chunk TTS fallback to HTTP")
                audio_data = await self.http_tts.synthesize(text)
                self.metrics["http_fallback_count"] += 1
                return audio_data
            except Exception as e2:
                logger.error(f"❌ HTTP fallback also failed: {e2}")
                return None

    async def close(self):
        """Закрытие всех соединений"""
        if self.grpc_tts:
            await self.grpc_tts.close()
        logger.info("✅ TTSAdapter closed")

# Глобальный экземпляр адаптера
_tts_adapter = None

async def get_tts_adapter() -> TTSAdapter:
    """Фабрика для создания TTS адаптера"""
    global _tts_adapter
    if _tts_adapter is None:
        _tts_adapter = TTSAdapter()
        await _tts_adapter.initialize()
    return _tts_adapter

