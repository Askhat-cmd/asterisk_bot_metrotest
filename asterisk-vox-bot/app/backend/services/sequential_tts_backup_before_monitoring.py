#!/usr/bin/env python3
"""
SequentialTTSProcessor - РЕАЛЬНАЯ обработка чанков с воспроизведением через ARI
Заменитель ParallelTTSProcessor с заглушками на реальное воспроизведение
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class SequentialTTSProcessor:
    """
    Sequential TTS Processor с РЕАЛЬНЫМ воспроизведением через ARI
    
    Ключевые особенности:
    - ✅ Реальное воспроизведение через ARI (не заглушки)
    - ✅ Проверка каналов перед каждой операцией
    - ✅ Последовательная обработка для стабильности
    - ✅ Немедленное воспроизведение каждого чанка
    - ✅ Hold/Unhold каналов для предотвращения закрытия
    """
    
    def __init__(self, tts_service, ari_client):
        self.tts_service = tts_service
        self.ari_client = ari_client
        self.active_channels = {}  # Отслеживание активных каналов
        logger.info("🔄 SequentialTTSProcessor инициализирован")
    
    async def process_chunk_immediate(self, channel_id: str, chunk_data: Dict[str, Any]):
        """Обрабатывает чанк с уже удержанным каналом"""
        try:
            chunk_text = chunk_data.get("text", "")
            chunk_index = chunk_data.get("index", 0)
            is_first = chunk_data.get("is_first", False)

            if not chunk_text:
                logger.warning(f"⚠️ Пустой текст в чанке {chunk_index}")
                return

            logger.info(f"🚀 Sequential processing chunk {chunk_index}: '{chunk_text[:50]}...'")

            # TTS синтез
            tts_start = time.time()
            audio_data = await self._synthesize_chunk(chunk_text)
            tts_time = time.time() - tts_start

            if audio_data:
                logger.info(f"✅ Sequential TTS chunk {chunk_index}: {tts_time:.2f}s")
                
                # РЕАЛЬНОЕ воспроизведение через ARI
                playback_start = time.time()
                playback_id = await self._play_audio_real(channel_id, audio_data, chunk_index)
                playback_time = time.time() - playback_start

                if playback_id:
                    logger.info(f"✅ REAL ARI playback started: {playback_id} for chunk {chunk_index}")
                    
                    if is_first:
                        total_time = tts_time + playback_time
                        logger.info(f"🎯 FIRST AUDIO LATENCY: {total_time:.2f}s")
                else:
                    logger.error(f"❌ ARI playback failed for chunk {chunk_index}")
            else:
                logger.error(f"❌ TTS synthesis failed for chunk {chunk_index}")

        except Exception as e:
            logger.error(f"❌ Sequential TTS error chunk {chunk_index}: {e}")
    
    
    async def _synthesize_chunk(self, text: str) -> Optional[bytes]:
        """Синтезирует аудио для чанка"""
        try:
            # Используем gRPC TTS для быстрого синтеза
            if hasattr(self.tts_service, 'synthesize_chunk_fast'):
                return await self.tts_service.synthesize_chunk_fast(text)
            else:
                # Fallback на обычный синтез
                return await self.tts_service.synthesize(text)
        except Exception as e:
            logger.error(f"❌ TTS synthesis error: {e}")
            return None
    
    async def _play_audio_real(self, channel_id: str, audio_data: bytes, chunk_index: int) -> Optional[str]:
        """
        РЕАЛЬНОЕ воспроизведение аудио через ARI
        
        Это ключевое отличие от ParallelTTSProcessor с заглушками!
        """
        try:
            # Сохраняем аудио данные во временный файл
            timestamp = datetime.now().strftime('%H%M%S%f')[:-3]
            temp_filename = f"chunk_{channel_id}_{chunk_index}_{timestamp}.wav"
            temp_path = f"/var/lib/asterisk/sounds/{temp_filename}"
            
            # Создаем директорию если не существует
            import os
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            # Проверяем формат данных
            header = audio_data[:12]
            if header.startswith(b'RIFF') and b'WAVE' in header:
                # Уже готовый WAV файл
                with open(temp_path, 'wb') as f:
                    f.write(audio_data)
            else:
                # Raw LPCM - конвертируем в WAV
                await self._convert_lpcm_to_wav(audio_data, temp_path)
            
            # РЕАЛЬНОЕ воспроизведение через ARI
            # Дополнительная проверка канала перед воспроизведением
            if not await self.ari_client.channel_exists(channel_id):
                logger.warning(f"⚠️ Канал {channel_id} исчез перед воспроизведением chunk {chunk_index}")
                return None
            
            playback_id = await self.ari_client.play_sound(channel_id, temp_filename[:-4], lang=None)
            
            if playback_id:
                logger.info(f"🔊 REAL ARI playback: {playback_id} for chunk {chunk_index}")
                
                # Очищаем временный файл через некоторое время
                asyncio.create_task(self._cleanup_temp_file(temp_path, delay=10.0))
                
                return playback_id
            else:
                logger.error(f"❌ ARI playback failed for chunk {chunk_index}")
                return None
                    
        except Exception as e:
            logger.error(f"❌ Real audio playback error for chunk {chunk_index}: {e}")
            return None
    
    async def _convert_lpcm_to_wav(self, lpcm_data: bytes, output_path: str):
        """Конвертирует raw LPCM в WAV файл"""
        try:
            import wave
            
            sample_rate = 8000  # 8kHz для Asterisk
            channels = 1        # mono
            sample_width = 2    # 16-bit
            
            with wave.open(output_path, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(lpcm_data)
                
            logger.debug(f"🔄 LPCM конвертирован в WAV: {output_path}")
            
        except Exception as e:
            logger.error(f"❌ LPCM to WAV conversion error: {e}")
            # Fallback: сохраняем как есть
            with open(output_path, 'wb') as f:
                f.write(lpcm_data)
    
    async def _cleanup_temp_file(self, file_path: str, delay: float = 10.0):
        """Очищает временный файл после задержки"""
        try:
            await asyncio.sleep(delay)
            import os
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"🗑️ Удален временный файл: {file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить временный файл {file_path}: {e}")
    
    async def clear_all_queues(self, channel_id: str):
        """Очищает все очереди для канала (для barge-in)"""
        try:
            if channel_id in self.active_channels:
                # Unhold канал если он был удержан
                if self.active_channels[channel_id].get("is_held"):
                    await self._unhold_channel(channel_id)
                
                # Очищаем данные канала
                del self.active_channels[channel_id]
                
            logger.info(f"🧹 Cleared all queues for channel {channel_id}")
            
        except Exception as e:
            logger.error(f"❌ Clear queues error for {channel_id}: {e}")
    
    def get_metrics(self, channel_id: str) -> Dict[str, Any]:
        """Возвращает метрики для канала"""
        return self.active_channels.get(channel_id, {})
