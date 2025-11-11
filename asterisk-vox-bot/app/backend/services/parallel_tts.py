#!/usr/bin/env python3
"""
Parallel TTS Processor для параллельной обработки чанков
Цель: TTS каждого чанка запускается немедленно, параллельно с генерацией следующих
"""

import asyncio
import time
import logging
import os
from collections import defaultdict
from typing import Dict, List, Optional, Any
import json
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# ✅ CTO.NEW: Статистика underrun для мониторинга
class TTSUnderrunStats:
    """Статистика Buffer underrun для мониторинга качества воспроизведения"""
    def __init__(self):
        self.underrun_count = 0
        self.last_underrun_time = None
        self.total_playback_time = 0
    
    def record_underrun(self):
        """Записывает факт underrun и обновляет статистику"""
        self.underrun_count += 1
        self.last_underrun_time = time.time()
        underrun_percent = (self.underrun_count / max(1, self.total_playback_time)) * 100
        logger.warning(f"TTS: Underrun #{self.underrun_count} "
                       f"(frequency: {underrun_percent:.2f}% of playback time)")

class ParallelTTSProcessor:
    """
    Параллельный TTS процессор для обработки chunked ответов
    
    Принцип работы:
    1. TTS каждого чанка запускается немедленно (не ждем предыдущие)
    2. Готовые аудио складываются в очередь воспроизведения
    3. Воспроизведение происходит последовательно в правильном порядке
    4. Barge-in очищает все очереди и отменяет задачи
    """
    
    def __init__(self, grpc_tts, ari_client):
        """
        Инициализация параллельного TTS процессора
        
        Args:
            grpc_tts: Экземпляр YandexGrpcTTS для синтеза
            ari_client: Клиент ARI для воспроизведения
        """
        self.grpc_tts = grpc_tts
        self.ari_client = ari_client
        self._ari_session = None  # Будет инициализирована при первом использовании
        
        # Конфигурация из .env
        self.tts_workers = int(os.getenv("TTS_PARALLEL_WORKERS", "3"))
        self.audio_buffer_size = int(os.getenv("AUDIO_BUFFER_SIZE", "2"))
        
        # ThreadPoolExecutor для параллельных TTS запросов
        self.tts_pool = ThreadPoolExecutor(max_workers=self.tts_workers)
        
        # Управление очередями по каналам
        self.playback_queues: Dict[str, List[Dict]] = defaultdict(list)
        self.playback_busy: Dict[str, bool] = defaultdict(bool)
        self.tts_tasks: Dict[str, List[asyncio.Task]] = defaultdict(list)
        
        # Метрики производительности
        self.performance_metrics: Dict[str, Dict] = defaultdict(dict)
        # Опциональный колбэк: вызывается, когда для канала больше нет активных TTS задач и очередь пуста
        self.on_tts_idle: Optional[Any] = None
        
        # ✅ CTO.NEW: Инициализация статистики underrun
        self._underrun_stats = TTSUnderrunStats()
        # ✅ CTO.NEW: Флаги состояния воспроизведения для обработки underrun
        self.playback_paused: Dict[str, bool] = defaultdict(bool)
        
        logger.info(f"🔄 ParallelTTSProcessor инициализирован с {self.tts_workers} TTS workers")
    
    async def process_chunk_immediate(self, channel_id: str, chunk_data: Dict[str, Any]):
        """
        Обрабатывает чанк НЕМЕДЛЕННО, параллельно с генерацией следующих.
        
        Ключевая логика:
        1. Запускаем gRPC TTS сразу (не ждем)
        2. Добавляем в очередь воспроизведения  
        3. Воспроизводим последовательно готовые чанки
        
        Args:
            channel_id: ID канала для воспроизведения
            chunk_data: Данные чанка с текстом и метаданными
        """
        chunk_num = chunk_data.get("chunk_number", 0)
        text = chunk_data.get("text", "")
        is_first = chunk_data.get("is_first", False)
        
        logger.info(f"🚀 Processing chunk {chunk_num} immediately: '{text[:30]}...'")
        
        try:
            # Запускаем TTS ПАРАЛЛЕЛЬНО (не блокируем)
            tts_task = asyncio.create_task(
                self._synthesize_chunk_async(channel_id, chunk_num, text, is_first)
            )
            
            self.tts_tasks[channel_id].append(tts_task)

            # ✅ ВАЖНО: очищаем список активных задач по завершении
            # Иначе в stasis_handler будет казаться, что задачи ещё идут,
            # и VAD не запустится для следующего вопроса
            tts_task.add_done_callback(lambda t, cid=channel_id: self._on_tts_task_done(cid, t))
            
            # Не ждем завершения TTS - обрабатываем следующий чанк
            
        except Exception as e:
            logger.error(f"❌ Immediate processing error chunk {chunk_num}: {e}")

    def _on_tts_task_done(self, channel_id: str, task: asyncio.Task) -> None:
        """Удаляет завершившуюся TTS задачу из реестра и логирует остаток."""
        try:
            # Снимем результат, чтобы не оставлять скрытые исключения
            try:
                task.result()
            except Exception:
                # Ошибку уже залогировали в месте выполнения
                pass

            if channel_id in self.tts_tasks:
                before = len(self.tts_tasks[channel_id])
                # Удаляем конкретно этот task
                self.tts_tasks[channel_id] = [t for t in self.tts_tasks[channel_id] if t is not task]
                after = len(self.tts_tasks[channel_id])
                logger.info(f"🧹 TTS task cleanup: {before} → {after} active for {channel_id}")

                # Если канал стал idle (нет активных TTS задач и очередь пуста) — сообщаем верхнему уровню
                try:
                    if after == 0 and len(self.playback_queues.get(channel_id, [])) == 0 and not self.playback_busy.get(channel_id, False):
                        # Небольшая задержка, чтобы исключить гонки с окончанием playback
                        asyncio.create_task(self._notify_idle(channel_id))
                except Exception as notify_err:
                    logger.debug(f"idle notify error for {channel_id}: {notify_err}")
        except Exception as cleanup_error:
            logger.debug(f"⚠️ Cleanup tts task error for {channel_id}: {cleanup_error}")
    
    async def _synthesize_chunk_async(self, channel_id: str, chunk_num: int, text: str, is_first: bool):
        """Async TTS + добавление в очередь воспроизведения"""
        
        tts_start = time.time()
        
        try:
            # ✅ УБРАНА РАННЯЯ ПРОВЕРКА: gRPC TTS сразу!
            # Проверка канала будет в _play_audio_chunk перед воспроизведением
            
            # gRPC TTS (параллельно с другими чанками)
            audio_data = await self.grpc_tts.synthesize_chunk_fast(text)
            tts_time = time.time() - tts_start
            
            # ✅ ИСПРАВЛЕНО: НЕ проверяем канал здесь! Проверка будет в _play_audio_chunk()
            # Причина: во время TTS канал может быть занят (VAD recording), что вызывает ложное срабатывание
            
            logger.info(f"✅ TTS done for chunk {chunk_num}: {tts_time:.2f}s, size={len(audio_data)} bytes")
            
            # Добавляем готовый аудио в очередь воспроизведения
            playback_item = {
                "chunk_num": chunk_num,
                "audio_data": audio_data,
                "text": text,
                "tts_time": tts_time,
                "is_first": is_first,
                "ready_time": time.time()
            }
            
            await self._enqueue_playback(channel_id, playback_item)
            
        except Exception as e:
            logger.error(f"❌ Async TTS error chunk {chunk_num}: {e}")
    
    async def _enqueue_playback(self, channel_id: str, playback_item: Dict[str, Any]):
        """Добавляет готовый аудио в очередь воспроизведения"""
        
        self.playback_queues[channel_id].append(playback_item)
        
        # Сортируем по номеру чанка для правильного порядка
        self.playback_queues[channel_id].sort(key=lambda x: x["chunk_num"])
        
        logger.debug(f"📋 Playback queue for {channel_id}: {len(self.playback_queues[channel_id])} items")
        
        # Запускаем обработку очереди если не занят
        if not self.playback_busy[channel_id]:
            await self._process_playback_queue(channel_id)

    async def _notify_idle(self, channel_id: str) -> None:
        """Уведомляет колбэк on_tts_idle, если канал действительно idle после короткой паузы."""
        try:
            await asyncio.sleep(0.05)
            is_idle = (
                len(self.tts_tasks.get(channel_id, [])) == 0
                and len(self.playback_queues.get(channel_id, [])) == 0
                and not self.playback_busy.get(channel_id, False)
            )
            if is_idle and self.on_tts_idle is not None:
                logger.info(f"✅ ParallelTTS idle for {channel_id} — triggering VAD check")
                await self.on_tts_idle(channel_id)
        except Exception as e:
            logger.debug(f"_notify_idle error for {channel_id}: {e}")
    
    async def _process_playback_queue(self, channel_id: str):
        """Последовательно воспроизводит готовые чанки В ПРАВИЛЬНОМ ПОРЯДКЕ"""
        
        if self.playback_busy[channel_id]:
            return
            
        self.playback_busy[channel_id] = True
        next_expected_chunk = 1  # Начинаем с chunk 1
        
        try:
            while self.playback_queues[channel_id]:
                # Проверяем barge-in
                if self._check_barge_in(channel_id):
                    logger.info("🚫 Barge-in detected - clearing playback queue")
                    self.playback_queues[channel_id] = []
                    break
                
                # ✅ КРИТИЧНО: Ждем ИМЕННО нужный chunk по порядку!
                if not self.playback_queues[channel_id]:
                    break
                
                # Проверяем, готов ли следующий ожидаемый chunk
                next_item = self.playback_queues[channel_id][0]
                
                if next_item["chunk_num"] != next_expected_chunk:
                    # ✅ CTO.NEW: Детекция Buffer underrun - нужный chunk не готов
                    # Проверяем, есть ли активные TTS задачи
                    if len(self.tts_tasks.get(channel_id, [])) > 0:
                        # TTS задачи еще идут, возможен underrun
                        logger.warning(f"TTS: Potential buffer underrun - waiting for chunk {next_expected_chunk}, but have chunk {next_item['chunk_num']}")
                        # ✅ CTO.NEW: Вызываем обработчик underrun
                        await self._handle_buffer_underrun(channel_id)
                    else:
                        # Нужный chunk еще не готов - ЖДЕМ немного
                        await asyncio.sleep(0.05)
                    continue
                
                # Берем следующий готовый чанк В ПРАВИЛЬНОМ ПОРЯДКЕ
                item = self.playback_queues[channel_id].pop(0)
                next_expected_chunk += 1
                
                # Воспроизводим через ARI
                success = await self._play_audio_chunk(channel_id, item)
                
                # Логируем критическую метрику для первого чанка
                # ✅ КРИТИЧНО: Логируем ТОЛЬКО ОДИН РАЗ за весь ответ (не за каждый вопрос!)
                if item["is_first"]:
                    # Проверяем, не логировали ли мы уже для этого ответа
                    if channel_id not in self.performance_metrics or "first_audio_time" not in self.performance_metrics.get(channel_id, {}):
                        logger.info(f"🎯 FIRST AUDIO PLAYED for {channel_id}")
                        self._log_first_audio_metric(channel_id, item)
                
                if not success:
                    logger.warning("⚠️ Playback failed, stopping queue processing")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Playback queue error: {e}")
        finally:
            self.playback_busy[channel_id] = False
    
    async def _play_audio_chunk(self, channel_id: str, item: Dict[str, Any]) -> bool:
        """Воспроизводит аудио чанк через ARI"""
        
        try:
            # ✅ CTO.NEW: Проверяем, не на паузе ли воспроизведение
            while self.playback_paused.get(channel_id, False):
                logger.debug(f"TTS: Playback paused for {channel_id}, waiting...")
                await asyncio.sleep(0.05)
            
            play_start = time.time()
            
            # ✅ РЕАЛЬНОЕ ВОСПРОИЗВЕДЕНИЕ: Сохраняем WAV и играем через ARI
            audio_data = item["audio_data"]
            
            # Сохраняем в /usr/share/asterisk/sounds/ru/
            from datetime import datetime
            timestamp = datetime.now().strftime('%H%M%S%f')[:-3]
            sound_dir = os.getenv("ASTERISK_SOUNDS_DIR", "/usr/share/asterisk/sounds")
            lang = os.getenv("ASTERISK_LANG", "ru")
            
            filename = f"chunk_{channel_id}_{timestamp}_{item['chunk_num']}.wav"
            filepath = os.path.join(sound_dir, lang, filename)
            
            # Сохраняем WAV файл
            with open(filepath, 'wb') as f:
                f.write(audio_data)
            
            logger.info(f"💾 Saved chunk {item['chunk_num']}: {filepath} ({len(audio_data)} bytes)")
            
            # Извлекаем имя без расширения для ARI
            sound_name = os.path.splitext(filename)[0]
            
            # ✅ ИСПРАВЛЕНО: Инициализируем ARI сессию если еще не создана
            if not self.ari_client.session:
                import aiohttp
                self.ari_client.session = aiohttp.ClientSession(auth=self.ari_client.auth)
            
            logger.info(f"🎵 Воспроизводим chunk {item['chunk_num']}: {sound_name} (канал {channel_id})")
            playback_id = await self.ari_client.play_sound(channel_id, sound_name, lang=lang)
            
            play_time = time.time() - play_start
            
            if playback_id:
                logger.info(f"🔊 Played chunk {item['chunk_num']}: {play_time:.2f}s - '{item['text'][:30]}...'")
                
                # Ждем завершения воспроизведения (приблизительно 1с аудио = 0.2с TTS)
                # Для более точного ожидания можно парсить длину аудио из WAV
                estimated_duration = len(audio_data) / 16000  # Примерная оценка для 8kHz
                await asyncio.sleep(max(0.5, estimated_duration))
                
                return True
            else:
                logger.error(f"❌ Failed to play chunk {item['chunk_num']}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Audio playback error: {e}")
            return False
    
    def _check_barge_in(self, channel_id: str) -> bool:
        """
        Проверяет не прервал ли пользователь
        
        В реальной реализации здесь будет интеграция с системой active_calls
        """
        # ЗАГЛУШКА: Всегда возвращаем False для тестирования
        return False
    
    def _log_first_audio_metric(self, channel_id: str, item: Dict[str, Any]):
        """Логирует критическую метрику первого аудио"""
        
        if channel_id not in self.performance_metrics:
            self.performance_metrics[channel_id] = {}
        
        self.performance_metrics[channel_id]["first_audio_time"] = item["ready_time"]
        self.performance_metrics[channel_id]["first_chunk_tts_time"] = item["tts_time"]
        
        logger.info(f"📊 First audio metrics for {channel_id}: TTS={item['tts_time']:.2f}s")
    
    # ✅ CTO.NEW: Детекция underrun и автоматическая пауза
    async def _handle_buffer_underrun(self, channel_id: str):
        """
        Обработка Buffer underrun:
        1. Получить уведомление об underrun
        2. Пауза воспроизведения на 100-200ms
        3. Дождаться накопления буфера (минимум 2-3 чанка)
        4. Возобновить воспроизведение
        """
        
        logger.warning(f"TTS: Buffer underrun detected! Pausing playback to accumulate buffer...")
        
        # ✅ CTO.NEW: Записываем статистику underrun
        self._underrun_stats.record_underrun()
        
        # 1. Пауза воспроизведения
        try:
            await self._pause_playback(channel_id)
            logger.debug("TTS: Playback paused")
        except Exception as e:
            logger.error(f"TTS: Error pausing playback: {e}")
        
        # 2. Ждать накопления буфера (минимум 2-3 чанка)
        buffer_wait_time = 0.15  # 150ms для накопления буфера
        logger.debug(f"TTS: Waiting {buffer_wait_time}s for buffer accumulation...")
        await asyncio.sleep(buffer_wait_time)
        
        # 3. Проверить, достаточно ли в буфере
        current_buffer_size = await self._get_queue_size(channel_id)
        min_buffer_needed = 2  # Минимум 2 чанка в очереди
        
        if current_buffer_size >= min_buffer_needed:
            logger.info(f"TTS: Buffer accumulated ({current_buffer_size} chunks), resuming playback")
            try:
                await self._resume_playback(channel_id)
                logger.debug("TTS: Playback resumed")
            except Exception as e:
                logger.error(f"TTS: Error resuming playback: {e}")
        else:
            logger.warning(f"TTS: Buffer not enough ({current_buffer_size} chunks), waiting longer...")
            await asyncio.sleep(0.1)  # Дополнительное ожидание
            await self._resume_playback(channel_id)
    
    # ✅ CTO.NEW: Вспомогательные методы для управления воспроизведением
    async def _pause_playback(self, channel_id: str):
        """Пауза воспроизведения на канале"""
        self.playback_paused[channel_id] = True
        logger.debug(f"TTS: Playback paused for channel {channel_id}")
    
    async def _resume_playback(self, channel_id: str):
        """Возобновление воспроизведения на канале"""
        self.playback_paused[channel_id] = False
        logger.debug(f"TTS: Playback resumed for channel {channel_id}")
    
    async def _get_queue_size(self, channel_id: str) -> int:
        """Возвращает текущий размер очереди воспроизведения"""
        queue_size = len(self.playback_queues.get(channel_id, []))
        logger.debug(f"TTS: Current queue size for {channel_id}: {queue_size}")
        return queue_size
    
    async def clear_all_queues(self, channel_id: str):
        """
        Очищает все очереди и отменяет задачи для канала
        
        Используется при barge-in для полной остановки обработки
        """
        try:
            # Очищаем очередь воспроизведения
            self.playback_queues[channel_id] = []
            
            # Отменяем все активные TTS задачи
            for task in self.tts_tasks[channel_id]:
                if not task.done():
                    task.cancel()
            
            self.tts_tasks[channel_id] = []
            
            # Сбрасываем флаг занятости
            self.playback_busy[channel_id] = False
            
            # ✅ CTO.NEW: Сбрасываем флаг паузы при очистке
            self.playback_paused[channel_id] = False
            
            # ✅ КРИТИЧНО: Сбрасываем метрику first_audio для нового вопроса
            if channel_id in self.performance_metrics:
                if "first_audio_time" in self.performance_metrics[channel_id]:
                    del self.performance_metrics[channel_id]["first_audio_time"]
            
            logger.info(f"🧹 Cleared all queues for channel {channel_id}")
            
        except Exception as e:
            logger.error(f"❌ Error clearing queues for {channel_id}: {e}")
    
    def get_performance_metrics(self, channel_id: str) -> Dict[str, Any]:
        """Возвращает метрики производительности для канала"""
        return self.performance_metrics.get(channel_id, {})
    
    def get_queue_status(self, channel_id: str) -> Dict[str, Any]:
        """Возвращает статус очередей для канала"""
        return {
            "playback_queue_size": len(self.playback_queues[channel_id]),
            "active_tts_tasks": len(self.tts_tasks[channel_id]),
            "playback_busy": self.playback_busy[channel_id],
            "queued_chunks": [item["chunk_num"] for item in self.playback_queues[channel_id]]
        }
    
    # ✅ CTO.NEW: Метод для получения статистики underrun
    def get_underrun_stats(self) -> Dict[str, Any]:
        """Возвращает статистику Buffer underrun"""
        return {
            "underrun_count": self._underrun_stats.underrun_count,
            "last_underrun_time": self._underrun_stats.last_underrun_time,
            "total_playback_time": self._underrun_stats.total_playback_time
        }

