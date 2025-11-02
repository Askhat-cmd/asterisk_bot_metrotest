
#!/usr/bin/env python3
"""
Оптимизированный StasisHandler с интеграцией всех компонентов оптимизации
Цель: 1.1 секунды от ASR до первого звука
"""

import asyncio
import json
import logging
import websockets
import uuid
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Добавляем путь для импорта модулей проекта
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.backend.asterisk.ari_client import AsteriskARIClient
from app.backend.rag.agent import Agent
from app.backend.services.yandex_tts_service import get_yandex_tts_service
from app.backend.services.asr_service import get_asr_service
from app.backend.utils.text_normalizer import normalize as normalize_text
from app.backend.services.log_storage import insert_log
from app.backend.config.settings import settings

# НОВЫЕ КОМПОНЕНТЫ ОПТМЗАЦ
from app.backend.services.yandex_grpc_tts import YandexGrpcTTS
from app.backend.services.tts_adapter import TTSAdapter
from app.backend.services.filler_tts import InstantFillerTTS
from app.backend.services.parallel_tts import ParallelTTSProcessor
from app.backend.services.smart_speech_detector import SmartSpeechDetector
from app.backend.services.speech_filter import SpeechFilter
from app.backend.services.simple_vad_service import get_vad_service
# Удален adaptive_recording - возвращаемся к простой логике

logger = logging.getLogger(__name__)

class OptimizedAsteriskAIHandler:
    """
    Оптимизированный обработчик Asterisk с интеграцией всех компонентов
    
    Компоненты:
    1. Yandex gRPC TTS - быстрый синтез речи
    2. Chunked Response Generator - streaming AI ответы
    3. Filler Words - мгновенные психологические реакции
    4. Parallel TTS Processor - параллельная обработка чанков
    """
    
    def __init__(self):
        # Формируем WebSocket URL из настроек
        ws_protocol = "wss" if settings.ari_http_url.startswith("https") else "ws"
        ws_host = settings.ari_http_url.replace("http://", "").replace("https://", "")
        self.ws_url = f"{ws_protocol}://{ws_host}/ari/events?app={settings.ari_app_name}&api_key={settings.ari_username}:{settings.ari_password}"
        
        # нициализируем AI Agent
        try:
            self.agent = Agent()
            logger.info("✅ AI Agent успешно инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AI Agent: {e}")
            self.agent = None
        
        # нициализируем ASR сервис
        try:
            self.asr = get_asr_service()
            logger.info("✅ ASR сервис инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации ASR: {e}")
            self.asr = None
        
        # НОВЫЕ КОМПОНЕНТЫ ОПТМЗАЦ
        self.grpc_tts = None
        self.tts_adapter = None
        self.filler_tts = None
        self.parallel_tts = None
        # Удален adaptive_recording - возвращаемся к простой логике
        
        # НОВЫЕ КОМПОНЕНТЫ УМНОЙ ДЕТЕКЦ РЕЧ
        self.speech_detector = None
        self.speech_filter = None
        self.smart_detection_enabled = settings.speech_detection_enabled
        self.speech_debug_logging = settings.speech_debug_logging
        
        # ✅ ОТСЛЕЖИВАНИЕ PLAYBACK СОБЫТИЙ (для filler оптимизации)
        self.playback_events = {}
        
        # VAD СЕРВС ДЛЯ УМЕНЬШЕНЯ ПАУЗЫ
        self.vad_service = None
        self.vad_enabled = settings.vad_enabled
        
        # Активные звонки с оптимизированными данными
        self.active_calls = {}
        self.bridge_to_channel = {}

        # Константы оптимизации
        self.SPEECH_END_TIMEOUT = settings.speech_end_timeout
        self.BARGE_IN_GUARD_MS = settings.barge_in_guard_ms  # Увеличено для Asterisk
        self.INPUT_DEBOUNCE_MS = settings.input_debounce_ms
        
        # Конфигурация умной детекции речи
        self.silence_timeout = settings.speech_silence_timeout
        self.min_speech_duration = settings.speech_min_duration
        self.max_recording_time = settings.speech_max_recording_time
        
        # Метрики производительности
        self.performance_metrics = {}
        
        # Мониторинг состояния каналов
        self.channel_monitor_task = None
        
        logger.info("🚀 OptimizedAsteriskAIHandler инициализирован")
    
    async def initialize_optimization_services(self):
        """нициализация всех сервисов оптимизации"""
        try:
            logger.info("🔄 нициализация сервисов оптимизации...")
            
            # 1. Yandex gRPC TTS
            self.grpc_tts = YandexGrpcTTS()
            await self.grpc_tts.initialize()
            
            # 2. TTS Adapter (gRPC + HTTP fallback)
            self.tts_adapter = TTSAdapter()
            await self.tts_adapter.initialize()
            
            # 3. Filler TTS (с передачей gRPC TTS для реального синтеза)
            self.filler_tts = InstantFillerTTS()
            await self.filler_tts.initialize(grpc_tts=self.grpc_tts)
            
            # 4. Parallel TTS Processor
            ari_client = AsteriskARIClient()
            # ✅ ИСПРАВЛЕНО: Используем уже инициализированный self.grpc_tts
            self.parallel_tts = ParallelTTSProcessor(self.grpc_tts, ari_client)
            # Колбэк: когда TTS полностью idle, пробуем запустить VAD
            async def _on_tts_idle(channel_id: str):
                try:
                    call_data = self.active_calls.get(channel_id)
                    if not call_data or call_data.get("is_recording", False):
                        return
                    # Повторная проверка занятости перед запуском VAD
                    active_tts = len(self.parallel_tts.tts_tasks.get(channel_id, []))
                    queued_chunks = len(self.parallel_tts.playback_queues.get(channel_id, []))
                    if active_tts == 0 and queued_chunks == 0:
                        logger.info(f"🎤 Idle detected → запускаем VAD для {channel_id}")
                        await self.start_user_recording(channel_id)
                except Exception as e:
                    logger.debug(f"on_tts_idle error for {channel_id}: {e}")
            self.parallel_tts.on_tts_idle = _on_tts_idle
            
            # 5. Умная детекция речи
            if self.smart_detection_enabled:
                self.speech_detector = SmartSpeechDetector(
                    silence_timeout=self.silence_timeout,
                    min_speech_duration=self.min_speech_duration
                )
                self.speech_filter = SpeechFilter()
                logger.info(f"✅ Умная детекция речи включена: timeout={self.silence_timeout}s, min_duration={self.min_speech_duration}s")
            else:
                logger.info("⚠️ Умная детекция речи отключена")
            
            # 6. VAD сервис для уменьшения паузы
            if self.vad_enabled:
                self.vad_service = get_vad_service()
                logger.info("✅ VAD сервис включен для уменьшения паузы после речи")
            else:
                logger.info("⚠️ VAD сервис отключен")
            
            logger.info("✅ Все сервисы оптимизации инициализированы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации сервисов оптимизации: {e}")
            # Fallback на старые сервисы
            self.tts = get_yandex_tts_service()
            logger.warning("⚠️ спользуем fallback TTS сервис")
    
    async def cleanup_hanging_channels(self):
        """Принудительно завершает все висящие каналы при запуске бота"""
        try:
            logger.info("🧹 Очистка висящих каналов...")
            
            async with AsteriskARIClient() as ari:
                # Получаем список всех активных каналов
                channels = await ari.get_channels()
                
                if not channels:
                    logger.info("✅ Висящих каналов не найдено")
                    return
                
                logger.info(f"🔍 Найдено {len(channels)} активных каналов")
                
                # Завершаем каждый канал
                for channel in channels:
                    channel_id = channel.get('id')
                    if channel_id:
                        try:
                            await ari.hangup_channel(channel_id)
                            logger.info(f"🔚 Канал {channel_id} принудительно завершен")
                        except Exception as e:
                            logger.warning(f"⚠️ Не удалось завершить канал {channel_id}: {e}")
                
                logger.info("✅ Очистка висящих каналов завершена")
                
        except Exception as e:
            logger.error(f"❌ Ошибка очистки висящих каналов: {e}")
    
    async def handle_stasis_start(self, event):
        """Обрабатывает начало звонка с оптимизированной инициализацией"""
        channel_id = event.get('channel', {}).get('id')
        caller_id = event.get('channel', {}).get('caller', {}).get('number', 'Unknown')
        
        logger.info(f"🔔 Новый звонок: Channel={channel_id}, Caller={caller_id}")
        
        # Создаем сессию звонка с оптимизированными данными
        session_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)

        self.active_calls[channel_id] = {
            "session_id": session_id,
            "caller_id": caller_id,
            "start_time": start_time.isoformat(),
            "transcript": [],
            "status": "InProgress",
            
            # Оптимизированные данные
            "response_buffer": "",
            "buffer_timer": None,
            "tts_queue": [],
            "is_recording": False,
            "tts_busy": False,
            "current_playback": None,
            "last_speak_started_at": 0,
            "is_speaking": False,
            "preload_cache": {},
            
            # Новые метрики производительности
            "performance_start": time.time(),
            "asr_complete_time": None,
            "first_chunk_time": None,
            "first_audio_time": None,
            "user_interrupted": False
        }
        
        # Канал уже принят в dialplan
        async with AsteriskARIClient() as ari:
            logger.info(f"✅ Звонок уже принят в dialplan: {channel_id}")
            
            # 🎯 КРТЧЕСКОЕ СПРАВЛЕНЕ: Принудительно отвечаем на канал для ARI playback
            try:
                await ari.answer_channel(channel_id)
                logger.info(f"✅ Канал {channel_id} отвечен для ARI playback")
                
                # Небольшая задержка для стабилизации канала
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ Ошибка ответа на канал {channel_id}: {e}")
                # Продолжаем работу даже если ответ не удался
            
            # Получаем приветствие от AI Agent
            if self.agent:
                greeting = self.agent.prompts.get("greeting", "Здравствуйте! Чем могу помочь?")
            else:
                greeting = "Здравствуйте! Система временно недоступна."

            # Добавляем в транскрипт
            self.active_calls[channel_id]["transcript"].append({
                "speaker": "bot",
                "text": greeting,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            # Оптимизированное приветствие через TTS Adapter
            if self.tts_adapter:
                await self.speak_optimized(channel_id, greeting)
            else:
                # Fallback на старый метод
                await self.speak_queued(channel_id, greeting)
            
            logger.info(f"🎤 Готов к приему речи от {caller_id}")

    async def process_user_speech_optimized(self, channel_id: str, audio_path: str):
        """
        ОПТМЗРОВАННАЯ обработка речи пользователя
        ЦЕЛЬ: 1.1 секунды от ASR до первого звука
        """
        if channel_id not in self.active_calls:
            logger.warning(f"Канал {channel_id} не найден в активных звонках")
            return

        call_data = self.active_calls[channel_id]
        session_id = call_data["session_id"]
        overall_start = time.time()

        # Проверяем, что канал еще активен
        if call_data.get("status") == "Completed":
            logger.info(f"🚫 Канал {channel_id} уже завершен, пропускаем обработку речи")
            return
        
        # Сбрасываем таймер завершения при новой активности
        if "timeout_task" in call_data:
            call_data["timeout_task"].cancel()
            logger.info(f"⏰ Таймер завершения сброшен для {channel_id} - новая активность")

        # Проверяем, не обрабатывается ли уже эта запись
        if call_data.get("processing_speech", False):
            logger.info(f"🎯 Запись для канала {channel_id} уже обрабатывается, пропускаем дублирование")
            return
        
        # Устанавливаем флаг обработки
        call_data["processing_speech"] = True

        try:
            logger.info("🎯 Оптимизированная обработка речи активирована")
            
            # ЭТАП 1.2: Проверка размера аудио файла перед ASR
            if not os.path.exists(audio_path):
                logger.warning(f"⚠️ Аудио файл не найден: {audio_path}")
                return
                
            file_size = os.path.getsize(audio_path)
            if file_size < 1000:  # Минимальный размер 1KB
                logger.warning(f"⚠️ Аудио файл слишком короткий: {file_size} bytes, пропускаем ASR")
                return
                
            logger.info(f"✅ Аудио файл проверен: {file_size} bytes")
            
            # 1. ASR: Преобразуем речь в текст
            if self.asr:
                logger.info(f"🎤 Запускаем ASR для файла: {audio_path}")
                user_text = await self.asr.speech_to_text(audio_path)
                normalized_text = normalize_text(user_text)
                
                asr_complete_time = time.time()
                call_data["asr_complete_time"] = asr_complete_time
                
                logger.info(f"🎤 Пользователь сказал: '{user_text}' → '{normalized_text}'")

                # Обновляем VAD активность при получении ASR результата
                if self.vad_enabled and self.vad_service:
                    await self.vad_service.update_activity(channel_id)

                # 🎯 КРТЧЕСКОЕ СПРАВЛЕНЕ: Проверяем на пустой результат ASR
                if not normalized_text or not normalized_text.strip():
                    logger.warning(f"⚠️ ASR вернул пустой результат, пропускаем обработку")
                    # Не завершаем звонок при пустом ASR - возможно пользователь еще говорит
                    return

                # 🧠 УМНАЯ ФЛЬТРАЦЯ: Проверяем информативность речи
                if self.smart_detection_enabled and self.speech_filter:
                    if self.speech_debug_logging:
                        analysis = self.speech_filter.get_detailed_analysis(normalized_text)
                        logger.info(f"🧠 Анализ речи: {analysis}")
                    
                    if not self.speech_filter.is_informative(normalized_text):
                        logger.info(f"🗑️ Речь неинформативна: '{normalized_text}' - пропускаем обработку")
                        
                        # Добавляем в транскрипт с пометкой
                        call_data["transcript"].append({
                            "speaker": "user",
                            "text": normalized_text,
                            "raw": user_text,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "filtered": True,
                            "filter_reason": "non_informative"
                        })
                        
                        # Запускаем новую запись после неинформативной фразы
                        await asyncio.sleep(0.5)  # Небольшая пауза
                        await self.start_user_recording(channel_id)
                        return
                    else:
                        logger.info(f"✅ Речь информативна: '{normalized_text}' - продолжаем обработку")

                # Добавляем в транскрипт
                call_data["transcript"].append({
                    "speaker": "user",
                    "text": normalized_text,
                    "raw": user_text,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            else:
                logger.warning("ASR сервис недоступен")
                normalized_text = "звините, система распознавания речи недоступна"

            # 2. Останавливаем TTS при barge-in
            await self.stop_tts_on_barge_in_optimized(channel_id, "UserSpeech")

            # 3. ОПТМЗРОВАННАЯ AI обработка с chunking
            if self.agent and normalized_text:
                logger.info(f"🤖 Запрашиваем ОПТМЗРОВАННЫЙ ответ от AI агента")
                
                try:
                    # ✅ ОПТИМИЗАЦИЯ: Запускаем filler word НЕМЕДЛЕННО!
                    filler_task = asyncio.create_task(
                        self._play_instant_filler(channel_id, normalized_text)
                    )
                    
                    # ✅ КРИТИЧНО: Даём filler ДОСТАТОЧНО времени начать воспроизведение (200мс)
                    # Это оптимальный баланс: достаточно для старта, но не слишком долго
                    await asyncio.sleep(0.20)
                    
                    # ✅ CHUNKED STREAMING ACTIVATED! (Психологический эффект)
                    logger.info("🚀 ОПТИМИЗАЦИЯ: Используем chunked streaming с разделителями |")
                    
                    # Получаем обычный response generator от AI Agent (с разделителями |)
                    # Теперь это запускается ПАРАЛЛЕЛЬНО с filler (который уже играется!)
                    response_generator = self.agent.get_response_generator(normalized_text, session_id)
                    
                    # Обрабатываем AI ответы через streaming с chunked TTS
                    await self.process_ai_response_streaming_with_chunked_tts(channel_id, response_generator)
                    
                    # НЕ ждем завершения filler - он уже сыгран параллельно!
                    # (Но на всякий случай проверяем что не осталось висеть)
                    if not filler_task.done():
                        await filler_task
                    
                    total_time = time.time() - overall_start
                    logger.info(f"✅ ОПТМЗРОВАННАЯ обработка завершена: {total_time:.2f}s")
                    
                    # Логируем метрики
                    self._log_performance_metrics(channel_id, total_time)
                    
                    # Добавляем ответ бота в транскрипт (если есть накопленный ответ)
                    if channel_id in self.active_calls:
                        call_data = self.active_calls[channel_id]
                        bot_response = call_data.get("bot_response", "")
                        if bot_response:
                            call_data["transcript"].append({
                                "speaker": "bot",
                                "text": bot_response,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                            # Очищаем накопленный ответ
                            call_data["bot_response"] = ""
                    
                    # Сохраняем лог после каждого ответа (так как ChannelDestroyed не приходит)
                    await self._save_call_log_forced(channel_id)
                    
                    # НЕ устанавливаем статус "Completed" после ответа - звонок продолжается
                    # Статус "Completed" будет установлен только при реальном завершении звонка
                    logger.info(f"✅ Ответ AI завершен, готов к следующему вопросу от {channel_id}")
                    
                    # Запускаем таймер для автоматического завершения звонка через 30 секунд бездействия
                    # Таймер будет сброшен при новом вопросе
                    await self._start_call_timeout(channel_id)
                    
                except Exception as ai_error:
                    logger.error(f"❌ Ошибка оптимизированного AI: {ai_error}", exc_info=True)
                    # Fallback на старую систему
                    await self._fallback_to_old_system(channel_id, normalized_text)
            else:
                logger.warning("AI Agent недоступен или текст пустой")
                await self.speak_optimized(channel_id, "звините, система  временно недоступна")

        except Exception as e:
            logger.error(f"❌ Ошибка оптимизированной обработки речи: {e}", exc_info=True)
        finally:
            # Сбрасываем флаг обработки
            if channel_id in self.active_calls:
                self.active_calls[channel_id]["processing_speech"] = False

    async def _play_instant_filler(self, channel_id: str, user_text: str) -> Optional[str]:
        """Воспроизводит мгновенный filler word и возвращает playback_id"""
        try:
            if not self.filler_tts:
                return None
                
            filler_start = time.time()
            
            # Получаем мгновенный filler
            filler_audio = await self.filler_tts.get_instant_filler(user_text)
            
            if filler_audio:
                # Воспроизводим немедленно
                playback_id = await self._play_audio_data(channel_id, filler_audio)
                
                filler_time = time.time() - filler_start
                logger.info(f"⚡ Filler played: {filler_time:.2f}s")
                
                # Логируем метрику
                call_data = self.active_calls.get(channel_id, {})
                call_data["filler_time"] = filler_time
                
                return playback_id
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Filler playback error: {e}")
            return None
    
    async def _wait_for_playback_start(self, playback_id: str, timeout: float = 0.5) -> bool:
        """
        ✅ ГИБРИДНАЯ ОПТИМИЗАЦИЯ: Ждёт пока playback реально начнётся (событие PlaybackStarted от ARI)
        
        Args:
            playback_id: ID воспроизведения от ARI
            timeout: Максимальное время ожидания в секундах (по умолчанию 500мс)
        
        Returns:
            True если playback начался, False если таймаут
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Проверяем зарегистрировано ли событие PlaybackStarted
            if playback_id in self.playback_events:
                if self.playback_events[playback_id].get('started'):
                    elapsed = time.time() - start_time
                    logger.info(f"✅ Playback {playback_id[:8]}... начался через {elapsed*1000:.0f}мс")
                    return True
            
            # Проверяем каждые 10мс
            await asyncio.sleep(0.01)
        
        logger.warning(f"⏰ Playback {playback_id[:8]}... не начался за {timeout*1000:.0f}мс")
        return False

    async def process_chunked_ai_response(self, channel_id: str, chunked_generator):
        """Обрабатывает chunked AI ответы через Parallel TTS Processor"""
        try:
            if not self.parallel_tts:
                logger.warning("Parallel TTS Processor недоступен")
                return
            
            # ✅ ИСПРАВЛЕНО: Итерируем sync generator с await для каждого чанка
            for chunk_data in chunked_generator:
                # Запускаем TTS каждого чанка НЕМЕДЛЕННО (параллельно)
                await self.parallel_tts.process_chunk_immediate(channel_id, chunk_data)
                
                # Логируем критическую метрику
                if chunk_data.get("is_first"):
                    first_chunk_time = time.time() - self.active_calls[channel_id]["performance_start"]
                    logger.info(f"🎯 FIRST CHUNK GENERATED: {first_chunk_time:.2f}s")
                    self.active_calls[channel_id]["first_chunk_time"] = first_chunk_time
                    
        except Exception as e:
            logger.error(f"❌ Chunked AI response error: {e}", exc_info=True)

    async def process_ai_response_streaming_with_chunked_tts(self, channel_id: str, response_generator):
        """✅ ОПТИМИЗИРОВАННАЯ потоковая обработка с chunked TTS + parallel processing"""
        import time
        stasis_start = time.time()
        logger.info(f"🚀 CHUNKED TTS: Начинаем обработку AI response для канала {channel_id}")
        
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        # Инициализируем накопление ответа бота
        if "bot_response" not in call_data:
            call_data["bot_response"] = ""
        
        # Накапливаем chunks от AI Agent
        first_chunk = True
        chunk_count = 0
        sentence_count = 0
        
        # ✅ КРИТИЧЕСКАЯ КОНСТАНТА: Максимальный размер чанка для принудительной сегментации
        MAX_CHUNK_SIZE = 75  # символов (оптимизировано: 75 симв = 3-5с аудио вместо 6-10с)
        
        for chunk in response_generator:
            # ✅ КРИТИЧНО: Даём квант времени event loop!
            # Это позволяет filler task выполниться НЕМЕДЛЕННО
            await asyncio.sleep(0)
            
            if first_chunk:
                first_chunk_time = time.time() - stasis_start
                logger.info(f"⚡ CHUNKED TTS: Первый токен получен через {first_chunk_time:.3f}с")
                first_chunk = False
            
            if chunk:
                chunk_count += 1
                call_data["response_buffer"] += chunk
                call_data["bot_response"] += chunk
                
                # ✅ ПРИОРИТЕТ 1: Проигрываем завершённые предложения по разделителю |
                while "|" in call_data["response_buffer"]:
                    idx = call_data["response_buffer"].index("|")
                    sentence = self.clean_text(call_data["response_buffer"][:idx])
                    call_data["response_buffer"] = call_data["response_buffer"][idx + 1:]
                    
                    if sentence and self.parallel_tts:
                        sentence_count += 1
                        chunk_data = {
                            "text": sentence,
                            "chunk_number": sentence_count,
                            "is_first": sentence_count == 1
                        }
                        await self.parallel_tts.process_chunk_immediate(channel_id, chunk_data)
                        logger.info(f"🔊 DELIMITER CHUNK {sentence_count}: '{sentence[:30]}...'")
                
                # ✅ ПРИОРИТЕТ 2: Принудительная сегментация при достижении MAX_CHUNK_SIZE
                # Ищем естественную точку разбиения (знак препинания)
                if len(call_data["response_buffer"]) >= MAX_CHUNK_SIZE:
                    best_split = -1
                    best_delim = None
                    
                    # Ищем ближайший знак препинания в диапазоне 45-95 символов (75±20)
                    for delim in ['. ', '! ', '? ', ', ', '; ']:
                        idx = call_data["response_buffer"].find(delim, 45, MAX_CHUNK_SIZE + 20)
                        if idx > 0:
                            best_split = idx + len(delim)
                            best_delim = delim
                            break
                    
                    # Если не нашли знак препинания - режем по MAX_CHUNK_SIZE
                    if best_split <= 0 and len(call_data["response_buffer"]) > MAX_CHUNK_SIZE + 25:
                        best_split = MAX_CHUNK_SIZE
                        logger.debug(f"⚠️ Forced hard split at {best_split} (no punctuation found)")
                    
                    if best_split > 0:
                        sentence = self.clean_text(call_data["response_buffer"][:best_split])
                        call_data["response_buffer"] = call_data["response_buffer"][best_split:]
                        
                        if sentence and self.parallel_tts:
                            sentence_count += 1
                            chunk_data = {
                                "text": sentence,
                                "chunk_number": sentence_count,
                                "is_first": sentence_count == 1
                            }
                            await self.parallel_tts.process_chunk_immediate(channel_id, chunk_data)
                            logger.info(f"🔊 FORCED CHUNK {sentence_count} ({len(sentence)} chars): '{sentence[:30]}...'")
                
                # Сбрасываем таймер для остатка
                if call_data["buffer_timer"]:
                    call_data["buffer_timer"].cancel()
                
                # Страховочный таймер для "хвоста" без |
                if call_data["response_buffer"].strip():
                    call_data["buffer_timer"] = asyncio.create_task(
                        self.flush_response_buffer_chunked(channel_id)
                    )
        
        total_stasis_time = time.time() - stasis_start
        logger.info(f"✅ CHUNKED TTS: Обработка AI response заняла {total_stasis_time:.3f}с, токенов: {chunk_count}, предложений: {sentence_count}")
    
    async def flush_response_buffer_chunked(self, channel_id: str):
        """Страховочный таймер для остатка без | с chunked TTS"""
        await asyncio.sleep(self.SPEECH_END_TIMEOUT)
        
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        if call_data["response_buffer"].strip():
            tail = self.clean_text(call_data["response_buffer"])
            call_data["response_buffer"] = ""
            call_data["buffer_timer"] = None
            
            if tail and self.parallel_tts:
                # Отправляем финальный чанк
                chunk_data = {
                    "text": tail,
                    "chunk_number": 999,  # Финальный
                    "is_first": False,
                    "is_final": True
                }
                await self.parallel_tts.process_chunk_immediate(channel_id, chunk_data)
                logger.info(f"🏁 CHUNKED TTS: Отправлен финальный чанк: '{tail[:30]}...'")

    async def process_ai_response_streaming(self, channel_id: str, response_generator):
        """Потоковая обработка ответа AI с разделителями | (СТАРАЯ ВЕРСИЯ - FALLBACK)."""
        import time
        stasis_start = time.time()
        logger.info(f"⏱️ ПРОФЛРОВАНЕ STASIS: Начинаем обработку AI response для канала {channel_id}")
        
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        # нициализируем накопление ответа бота
        if "bot_response" not in call_data:
            call_data["bot_response"] = ""
        
        # Накапливаем chunks от AI Agent
        first_chunk = True
        chunk_count = 0
        
        for chunk in response_generator:
            if first_chunk:
                first_chunk_time = time.time() - stasis_start
                logger.info(f"⏱️ ПРОФЛРОВАНЕ STASIS: Первый чанк получен через {first_chunk_time:.3f}с")
                first_chunk = False
            
            if chunk:
                chunk_count += 1
                call_data["response_buffer"] += chunk
                call_data["bot_response"] += chunk  # Накопляем полный ответ бота
                
                # Проигрываем каждое завершённое предложение по | (как в Voximplant)
                while "|" in call_data["response_buffer"]:
                    idx = call_data["response_buffer"].index("|")
                    sentence = self.clean_text(call_data["response_buffer"][:idx])
                    call_data["response_buffer"] = call_data["response_buffer"][idx + 1:]
                    
                    if sentence:
                        await self.speak_optimized(channel_id, sentence)
                
                # Сбрасываем таймер для остатка
                if call_data["buffer_timer"]:
                    call_data["buffer_timer"].cancel()
                
                # Страховочный таймер для "хвоста" без | (как в Voximplant)
                if call_data["response_buffer"].strip():
                    call_data["buffer_timer"] = asyncio.create_task(
                        self.flush_response_buffer(channel_id)
                    )
        
        total_stasis_time = time.time() - stasis_start
        logger.info(f"⏱️ ПРОФЛРОВАНЕ STASIS: Обработка AI response заняла {total_stasis_time:.3f}с, чанков: {chunk_count}")
    
    async def flush_response_buffer(self, channel_id: str):
        """Страховочный таймер для остатка без | (из оригинальной версии)."""
        await asyncio.sleep(self.SPEECH_END_TIMEOUT)
        
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        if call_data["response_buffer"].strip():
            tail = self.clean_text(call_data["response_buffer"])
            call_data["response_buffer"] = ""
            call_data["buffer_timer"] = None
            
            if tail:
                await self.speak_optimized(channel_id, tail)
    
    def clean_text(self, text: str) -> str:
        """Очищает текст от лишних символов (из оригинальной версии)."""
        if not text:
            return ""
        
        # Убираем лишние пробелы и переносы
        text = text.strip()
        text = " ".join(text.split())
        
        return text

    async def speak_optimized(self, channel_id: str, text: str):
        """Оптимизированное воспроизведение через исправленный gRPC TTS"""
        try:
            if not self.tts_adapter:
                # Fallback на старый метод
                await self.speak_queued(channel_id, text)
                return
            
            # ✅ ИСПРАВЛЕНО: Используем gRPC TTS с правильным форматом 8kHz
            logger.info("🚀 Используем исправленный gRPC TTS (8kHz)")
            
            # Используем исправленный TTS сервис с gRPC
            from app.backend.services.yandex_tts_service import get_yandex_tts_service
            tts_service = get_yandex_tts_service()
            
            # ✅ КРИТИЧНО: Используем gRPC метод напрямую!
            timestamp = datetime.now().strftime('%H%M%S%f')[:-3]
            audio_filename = f"stream_{channel_id}_{timestamp}"
            sound_filename = await tts_service.text_to_speech_grpc(text, audio_filename)
            
            if sound_filename:
                # ✅ КРИТИЧНО: Извлекаем только имя файла без пути и расширения для ARI
                import os
                basename = os.path.basename(sound_filename)  # stream_xxx.wav
                sound_name = os.path.splitext(basename)[0]   # stream_xxx (без .wav)
                
                # Воспроизводим через ARI с правильным форматом
                async with AsteriskARIClient() as ari:
                    playback_id = await ari.play_sound(channel_id, sound_name, lang="ru")
                    
                    if playback_id:
                        # Обновляем данные канала
                        if channel_id in self.active_calls:
                            call_data = self.active_calls[channel_id]
                            call_data["current_playback"] = playback_id
                            call_data["is_speaking"] = True
                            call_data["last_speak_started_at"] = int(time.time() * 1000)

                        if call_data.get("first_audio_time") is None:
                            asr_finished_at = call_data.get("asr_complete_time")
                            if asr_finished_at:
                                delay = time.time() - asr_finished_at
                                call_data["first_audio_time"] = delay
                                logger.info(f"🔊 FIRST AUDIO PLAYED: {delay:.3f}s after ASR")

                        
                        logger.info(f"✅ Аудио воспроизводится через ARI: {playback_id}")
                    else:
                        logger.warning("⚠️ ARI playback не удался")
            else:
                logger.warning("Оригинальный TTS не вернул имя файла")
                
        except Exception as e:
            logger.error(f"❌ Optimized speak error: {e}")
            # Fallback на старый метод
            await self.speak_queued(channel_id, text)

    async def _play_audio_data(self, channel_id: str, audio_data: bytes) -> Optional[str]:
        """ПРАВЛЬНАЯ обработка аудио данных от Yandex gRPC TTS, возвращает playback_id"""
        try:
            # Проверяем, что канал еще активен
            if channel_id not in self.active_calls:
                logger.warning(f"⚠️ Канал {channel_id} завершен, пропускаем воспроизведение")
                return None
                
            if not audio_data:
                logger.warning("⚠️ Пустые аудио данные")
                return None
            
            # Сохраняем аудио данные во временный файл
            timestamp = datetime.now().strftime('%H%M%S%f')[:-3]  # миллисекунды
            temp_filename = f"stream_{channel_id}_{timestamp}.wav"
            temp_path = f"/var/lib/asterisk/sounds/{temp_filename}"
            
            # Создаем директорию если не существует
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            # 🎯 КРТЧЕСКОЕ СПРАВЛЕНЕ: Проверяем формат данных
            header = audio_data[:12]
            
            if header.startswith(b'RIFF') and b'WAVE' in header:
                # ✅ Уже готовый WAV файл - сохраняем как есть
                logger.info("✅ WAV файл с заголовками - сохраняем как есть")
                with open(temp_path, 'wb') as f:
                    f.write(audio_data)
            else:
                # 🔄 Raw LPCM - добавляем WAV заголовки
                logger.info("🔄 Raw LPCM - конвертируем в WAV")
                await self._convert_lpcm_to_wav(audio_data, temp_path)
            
            logger.info(f"💾 Сохранен аудио файл: {temp_path} ({len(audio_data)} bytes)")
            
            # Воспроизводим через ARI (как в оригинальном коде)
            async with AsteriskARIClient() as ari:
                playback_id = await ari.play_sound(channel_id, temp_filename[:-4], lang=None)  # убираем .wav
                
                if playback_id:
                    # Обновляем данные канала
                    if channel_id in self.active_calls:
                        call_data = self.active_calls[channel_id]
                        call_data["current_playback"] = playback_id
                        call_data["is_speaking"] = True
                        call_data["last_speak_started_at"] = int(time.time() * 1000)

                        if call_data.get("first_audio_time") is None:
                            asr_finished_at = call_data.get("asr_complete_time")
                            if asr_finished_at:
                                delay = time.time() - asr_finished_at
                                call_data["first_audio_time"] = delay
                                logger.info(f"🔊 FIRST AUDIO PLAYED (dialplan): {delay:.3f}s after ASR")

                    
                    logger.info(f"✅ Аудио воспроизводится через ARI: {playback_id}")
                    return playback_id  # ✅ Возвращаем playback_id для отслеживания
                else:
                    logger.warning("⚠️ ARI playback не удался, пробуем fallback через dialplan")
                    # FALLBACK: спользуем dialplan Playback (как в оригинале)
                    fallback_success = await self.playback_via_dialplan(channel_id, temp_filename[:-4])
                    if fallback_success:
                        logger.info("✅ Аудио воспроизводится через dialplan fallback")
                        if channel_id in self.active_calls:
                            call_data = self.active_calls[channel_id]
                            fallback_id = f"dialplan_{temp_filename[:-4]}"
                            call_data["current_playback"] = fallback_id
                            call_data["is_speaking"] = True
                            call_data["last_speak_started_at"] = int(time.time() * 1000)
                        return fallback_id  # ✅ Возвращаем fallback ID
                    else:
                        logger.error("❌ Не удалось воспроизвести аудио ни через ARI, ни через dialplan")
                        return None
            
            # Очищаем временный файл после небольшой задержки
            # (даем время ARI прочитать файл)
            asyncio.create_task(self._cleanup_temp_file(temp_path, delay=5.0))
            return None  # На случай если что-то пошло не так
            
        except Exception as e:
            logger.error(f"❌ Audio playback error: {e}")
            return None
    
    async def _convert_lpcm_to_wav(self, lpcm_data: bytes, output_path: str):
        """Конвертирует raw LPCM в WAV файл с правильными заголовками для Asterisk"""
        try:
            import wave
            
            # Оптимальные параметры для Asterisk
            sample_rate = 8000  # 8kHz для лучшей совместимости
            channels = 1        # mono
            sample_width = 2    # 16-bit
            
            with wave.open(output_path, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(lpcm_data)
            
            logger.info(f"🔄 LPCM конвертирован в WAV: {output_path}")
            logger.info(f"📊 Параметры: {sample_rate}Hz, {channels}ch, {sample_width*8}bit")
            
        except Exception as e:
            logger.error(f"❌ LPCM to WAV conversion error: {e}")
            # Fallback: сохраняем как есть
            with open(output_path, 'wb') as f:
                f.write(lpcm_data)
    
    async def _cleanup_temp_file(self, file_path: str, delay: float = 5.0):
        """Очищает временный файл после задержки"""
        try:
            await asyncio.sleep(delay)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"🗑️ Удален временный файл: {file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить временный файл {file_path}: {e}")
    
    async def playback_via_dialplan(self, channel_id: str, filename: str) -> bool:
        """FALLBACK: Проигрывание через dialplan если ARI не работает."""
        try:
            async with AsteriskARIClient() as ari:
                # Отправляем канал в dialplan для проигрывания
                url = f"{ari.base_url}/channels/{channel_id}/continue"
                data = {
                    "context": "playback-context",
                    "extension": "play",
                    "priority": 1,
                    "variables": {
                        "SOUND_FILE": filename
                    }
                }
                
                async with ari.session.post(url, json=data) as response:
                    if response.status in (200, 201, 202):
                        logger.info(f"✅ Dialplan playback запущен для {filename}")
                        return True
                    else:
                        logger.error(f"❌ Dialplan playback failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ Dialplan playback error: {e}")
            return False

    async def stop_tts_on_barge_in_optimized(self, channel_id: str, event_name: str):
        """ОПТМЗРОВАННЫЙ barge-in с очисткой всех очередей"""
        call_data = self.active_calls.get(channel_id)
        if not call_data:
            return
        
        # Защита от ложного barge-in
        BARGE_IN_GUARD_MS = self.BARGE_IN_GUARD_MS
        since_start = int(time.time() * 1000) - call_data.get("last_speak_started_at", 0)
        
        if since_start < BARGE_IN_GUARD_MS:
            logger.debug(f"🔇 Ignoring barge-in - too early ({since_start}ms)")
            return
        
        logger.info(f"🚫 [OPTIMIZED BARGE-IN] {event_name} → stopping all TTS processing")
        
        # Останавливаем текущее воспроизведение
        if call_data.get("current_playback"):
            try:
                async with AsteriskARIClient() as ari:
                    await ari.stop_playback(call_data["current_playback"])
            except:
                pass
        
        # КРТЧНО: Очищаем все очереди параллельного TTS
        if self.parallel_tts:
            await self.parallel_tts.clear_all_queues(channel_id)
        
        # Отмечаем прерывание
        call_data["user_interrupted"] = True
        call_data["barge_in_time"] = time.time()
        
        logger.info("✅ Optimized barge-in processed - ready for new input")

    async def _fallback_to_old_system(self, channel_id: str, user_text: str):
        """Fallback на старую систему при ошибках оптимизации"""
        try:
            logger.warning("🔄 Falling back to old system")
            
            # спользуем старый метод обработки
            if self.agent:
                response_generator = self.agent.get_response_generator(user_text, self.active_calls[channel_id]["session_id"])
                await self.process_ai_response_streaming_old(channel_id, response_generator)
            else:
                error_text = "звините, произошла ошибка в системе"
                # Накопляем ответ бота
                if channel_id in self.active_calls:
                    self.active_calls[channel_id]["bot_response"] = error_text
                await self.speak_queued(channel_id, error_text)
                
        except Exception as e:
            logger.error(f"❌ Fallback system error: {e}")

    async def process_ai_response_streaming_old(self, channel_id: str, response_generator):
        """Старый метод потоковой обработки (fallback)"""
        # Копируем логику из оригинального StasisHandler
        # ... (код из оригинального метода)
        pass

    async def speak_queued(self, channel_id: str, text: str):
        """Старый метод воспроизведения (fallback)"""
        # Копируем логику из оригинального StasisHandler
        # ... (код из оригинального метода)
        pass

    def _log_performance_metrics(self, channel_id: str, total_time: float):
        """Логирует метрики производительности"""
        call_data = self.active_calls.get(channel_id, {})
        
        metrics = {
            "total_time": total_time,
            "asr_complete_time": call_data.get("asr_complete_time"),
            "first_chunk_time": call_data.get("first_chunk_time"),
            "first_audio_time": call_data.get("first_audio_time"),
            "filler_time": call_data.get("filler_time")
        }
        
        self.performance_metrics[channel_id] = metrics
        
        logger.info(f"📊 Performance metrics for {channel_id}: {metrics}")

    async def _start_call_timeout(self, channel_id):
        """Запускает таймер для автоматического завершения звонка через 30 секунд бездействия"""
        try:
            # Отменяем предыдущий таймер если есть
            if channel_id in self.active_calls and "timeout_task" in self.active_calls[channel_id]:
                self.active_calls[channel_id]["timeout_task"].cancel()
            
            # Создаем новый таймер
            timeout_task = asyncio.create_task(self._call_timeout_handler(channel_id))
            if channel_id in self.active_calls:
                self.active_calls[channel_id]["timeout_task"] = timeout_task
                logger.info(f"⏰ Таймер завершения звонка запущен для {channel_id} (30 сек)")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска таймера звонка: {e}")
    
    async def _call_timeout_handler(self, channel_id):
        """Обработчик таймаута звонка"""
        try:
            await asyncio.sleep(30)  # Ждем 30 секунд
            
            if channel_id in self.active_calls:
                call_data = self.active_calls[channel_id]
                if call_data.get("status") != "Completed":
                    logger.info(f"⏰ Таймаут звонка {channel_id} - завершаем автоматически")
                    call_data["status"] = "Completed"
                    
                    # Сохраняем финальный лог
                    await self._save_call_log_forced(channel_id)
                    
                    # Удаляем из активных звонков
                    del self.active_calls[channel_id]
                    if channel_id in self.performance_metrics:
                        del self.performance_metrics[channel_id]
                    
                    logger.info(f"✅ Звонок {channel_id} автоматически завершен по таймауту")
        except asyncio.CancelledError:
            logger.info(f"⏰ Таймер звонка {channel_id} отменен")
        except Exception as e:
            logger.error(f"❌ Ошибка в таймере звонка {channel_id}: {e}")

    async def _complete_all_active_calls(self):
        """Завершает все активные звонки при разрыве WebSocket соединения"""
        logger.info(f"📞 Завершаем {len(self.active_calls)} активных звонков")
        
        for channel_id, call_data in list(self.active_calls.items()):
            try:
                if call_data.get("status") != "Completed":
                    logger.info(f"✅ Завершаем звонок {channel_id} - клиент положил трубку")
                    call_data["status"] = "Completed"
                    
                    # Сохраняем финальный лог
                    await self._save_call_log_forced(channel_id)
                    
                    # Удаляем из активных звонков
                    del self.active_calls[channel_id]
                    if channel_id in self.performance_metrics:
                        del self.performance_metrics[channel_id]
                    
                    logger.info(f"✅ Звонок {channel_id} завершен - клиент положил трубку")
            except Exception as e:
                logger.error(f"❌ Ошибка завершения звонка {channel_id}: {e}")
        
        logger.info("✅ Все активные звонки завершены")

    async def _monitor_channels(self):
        """Мониторинг состояния каналов для детекции разрыва соединения"""
        while True:
            try:
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд
                
                if not self.active_calls:
                    continue
                
                # Проверяем состояние каждого активного канала
                for channel_id in list(self.active_calls.keys()):
                    try:
                        async with AsteriskARIClient() as ari:
                            # Получаем информацию о канале
                            channel_info = await ari.get_channel_info(channel_id)
                            
                            if not channel_info or channel_info.get('state') in ['Down', 'Ringing']:
                                # Канал недоступен или завершен
                                logger.info(f"📞 Канал {channel_id} недоступен - завершаем звонок")
                                await self._complete_single_call(channel_id, "channel_unavailable")
                                
                    except Exception as e:
                        # Если не можем получить информацию о канале, считаем что он завершен
                        logger.info(f"📞 Канал {channel_id} недоступен (ошибка: {e}) - завершаем звонок")
                        await self._complete_single_call(channel_id, "channel_error")
                        
            except asyncio.CancelledError:
                logger.info("🛑 Мониторинг каналов остановлен")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга каналов: {e}")
                await asyncio.sleep(10)  # Пауза при ошибке

    async def _complete_single_call(self, channel_id: str, reason: str):
        """Завершает один конкретный звонок"""
        if channel_id not in self.active_calls:
            return
            
        try:
            call_data = self.active_calls[channel_id]
            if call_data.get("status") != "Completed":
                logger.info(f"✅ Завершаем звонок {channel_id} - {reason}")
                call_data["status"] = "Completed"
                
                # Сохраняем финальный лог
                await self._save_call_log_forced(channel_id)
                
                # Удаляем из активных звонков
                del self.active_calls[channel_id]
                if channel_id in self.performance_metrics:
                    del self.performance_metrics[channel_id]
                
                logger.info(f"✅ Звонок {channel_id} завершен - {reason}")
        except Exception as e:
            logger.error(f"❌ Ошибка завершения звонка {channel_id}: {e}")

    async def _save_call_log_forced(self, channel_id):
        """Принудительно сохраняет лог звонка после каждого ответа AI (так как ChannelDestroyed не приходит)"""
        if channel_id not in self.active_calls:
            return
            
        call_data = self.active_calls[channel_id]
        end_time = datetime.now(timezone.utc)
        
        # Сохраняем текущий статус без изменения
        # Статус "Completed" будет установлен только при реальном завершении звонка
        current_status = call_data.get("status", "InProgress")
        logger.info(f"💾 Сохраняем лог со статусом: {current_status}")
        
        try:
            log_record = {
                "id": call_data["session_id"],
                "callerId": call_data["caller_id"],
                "startTime": call_data["start_time"],
                "endTime": end_time.isoformat(),
                "status": current_status,
                "transcript": call_data.get("transcript", []),
                "performance_metrics": self.performance_metrics.get(channel_id, {})
            }
            await insert_log(log_record)
            logger.info(f"💾 Лог сохранён для Session {call_data['session_id']}")
        except Exception as e:
            logger.error(f"❌ Ошибка insert_log: {e}", exc_info=True)
    
    # Остальные методы из оригинального StasisHandler...
    # (handle_channel_destroyed, clean_text, и т.д.)
    
    async def handle_channel_destroyed(self, event):
        """Обрабатывает завершение звонка с принудительным завершением"""
        channel_id = event.get('channel', {}).get('id')
        
        if channel_id in self.active_calls:
            call_data = self.active_calls[channel_id]
            call_data["status"] = "Completed"
            end_time = datetime.now(timezone.utc)
            
            logger.info(f"📞 Звонок завершен: {channel_id}")
            
            # Принудительно завершаем канал если он еще существует
            try:
                async with AsteriskARIClient() as ari:
                    await ari.hangup_channel(channel_id)
                    logger.info(f"🔚 Канал {channel_id} принудительно завершен")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось принудительно завершить канал {channel_id}: {e}")
            
            # Сохраняем лог звонка (как в старом проекте)
            try:
                log_record = {
                    "id": call_data["session_id"],
                    "callerId": call_data["caller_id"],
                    "startTime": call_data["start_time"],
                    "endTime": end_time.isoformat(),
                    "status": call_data["status"],
                    "transcript": call_data["transcript"],
                    "performance_metrics": self.performance_metrics.get(channel_id, {})
                }
                await insert_log(log_record)
                logger.info(f"💾 Лог сохранён для Session {call_data['session_id']}")
            except Exception as e:
                logger.error(f"❌ Ошибка insert_log: {e}", exc_info=True)
            
            # Удаляем из активных звонков
            del self.active_calls[channel_id]
            if channel_id in self.performance_metrics:
                del self.performance_metrics[channel_id]

    def clean_text(self, text: str) -> str:
        """Очистка текста от служебных символов"""
        import re
        text = str(text).replace("|", " ").replace("*", " ")
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    async def run(self):
        """Основной цикл обработки WebSocket событий от Asterisk"""
        try:
            async with websockets.connect(self.ws_url) as websocket:
                logger.info("✅ Подключен к Asterisk ARI WebSocket")
                
                # Запускаем мониторинг каналов
                self.channel_monitor_task = asyncio.create_task(self._monitor_channels())
                
                async for message in websocket:
                    try:
                        event = json.loads(message)
                        await self.handle_event(event)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Ошибка парсинга JSON: {e}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки события: {e}", exc_info=True)
                        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("🔌 WebSocket соединение закрыто - завершаем все активные звонки")
            await self._complete_all_active_calls()
        except Exception as e:
            logger.error(f"❌ Критическая ошибка WebSocket: {e}", exc_info=True)
            await self._complete_all_active_calls()
        finally:
            # Останавливаем мониторинг каналов
            if self.channel_monitor_task:
                self.channel_monitor_task.cancel()
                try:
                    await self.channel_monitor_task
                except asyncio.CancelledError:
                    pass
    
    async def handle_event(self, event):
        """Обрабатывает события от Asterisk ARI"""
        event_type = event.get('type')
        
        if event_type == 'StasisStart':
            await self.handle_stasis_start(event)
        elif event_type == 'ChannelDestroyed':
            await self.handle_channel_destroyed(event)
        elif event_type == 'PlaybackStarted':
            await self.handle_playback_started(event)
        elif event_type == 'PlaybackFinished':
            await self.handle_playback_finished(event)
        elif event_type == 'RecordingFinished':
            await self.handle_recording_finished(event)
        elif event_type == 'UserEvent':
            await self.handle_user_event(event)
        # Добавляем обработку других событий по необходимости
    
    async def _run_asterisk_cli(self, command: str, context: str = ""):
        """Выполняет команду `asterisk -rx` и пишет вывод в логи."""
        try:
            process = await asyncio.create_subprocess_exec(
                "asterisk",
                "-rx",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            label = context or command
            if stdout:
                stdout_text = stdout.decode("utf-8", errors="ignore").strip()
                if stdout_text:
                    logger.debug("🛠️ Asterisk CLI [%s] stdout: %s", label, stdout_text)
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="ignore").strip()
                if stderr_text:
                    logger.warning("⚠️ Asterisk CLI [%s] stderr: %s", label, stderr_text)
        except FileNotFoundError:
            logger.debug("Asterisk CLI недоступен: бинарь asterisk не найден")
        except Exception as cli_error:
            logger.warning("⚠️ Ошибка запуска Asterisk CLI '%s': %s", command, cli_error)
    async def handle_playback_started(self, event):
        """Handle ARI playback_started event."""
        playback = event.get('playback', {})
        playback_id = playback.get('id')
        target_uri = playback.get('target_uri', '')

        channel_id = None
        bridge_id = None
        if target_uri.startswith('channel:'):
            channel_id = target_uri.replace('channel:', '')
        elif target_uri.startswith('bridge:'):
            bridge_id = target_uri.replace('bridge:', '')
            channel_id = self.bridge_to_channel.get(bridge_id)

        if not channel_id:
            logger.debug("PlaybackStarted for unknown target %s", target_uri)
            return

        call_data = self.active_calls.get(channel_id)
        if not call_data:
            logger.debug("PlaybackStarted for inactive channel %s", channel_id)
            return

        call_data["current_playback"] = playback_id
        call_data["is_speaking"] = True
        call_data["last_speak_started_at"] = int(time.time() * 1000)
        
        # ✅ КРИТИЧНО: Регистрируем событие старта воспроизведения для filler оптимизации
        self.playback_events[playback_id] = {
            'started': True,
            'started_at': time.time(),
            'channel_id': channel_id
        }
        logger.info(f"📝 HYBRID: Registered playback start: {playback_id[:8]}... for channel {channel_id}")

        if bridge_id:
            logger.info("Playback started on bridge %s for channel %s: %s", bridge_id, channel_id, playback_id)
            await self._run_asterisk_cli(f"core show bridges like {bridge_id}", "playback-started-bridge")
        else:
            logger.info("Playback started for channel %s: %s", channel_id, playback_id)
        await self._run_asterisk_cli(f"core show channel {channel_id}", "playback-started")

        # if self.vad_enabled and self.vad_service:
        #     await self.vad_service.stop_monitoring(channel_id)
        #     logger.info("VAD monitoring stopped for %s (playback started)", channel_id)


    async def handle_playback_finished(self, event):
        """Handle ARI playback_finished event and resume user recording."""
        playback = event.get('playback', {})
        playback_id = playback.get('id')
        target_uri = playback.get('target_uri', '')

        channel_id = None
        bridge_id = None
        if target_uri.startswith('channel:'):
            channel_id = target_uri.replace('channel:', '')
        elif target_uri.startswith('bridge:'):
            bridge_id = target_uri.replace('bridge:', '')
            channel_id = self.bridge_to_channel.get(bridge_id)

        if not channel_id:
            logger.debug("PlaybackFinished for unknown target %s", target_uri)
            return

        call_data = self.active_calls.get(channel_id)
        if not call_data:
            logger.debug("PlaybackFinished for inactive channel %s", channel_id)
            return

        call_data["is_speaking"] = False
        call_data["current_playback"] = None

        if bridge_id:
            logger.info("Playback finished on bridge %s for channel %s: %s", bridge_id, channel_id, playback_id)
            await self._run_asterisk_cli(f"core show bridges like {bridge_id}", "playback-finished-bridge")
        else:
            logger.info("Playback finished for channel %s: %s", channel_id, playback_id)
        await self._run_asterisk_cli(f"core show channel {channel_id}", "playback-finished")

        if call_data.get("is_recording", False):
            logger.info("Recording already in progress for %s, skip restart", channel_id)
            return

        # ✅ КРИТИЧНО: Проверяем АКТИВНЫЕ TTS ЗАДАЧИ + ОЧЕРЕДЬ перед запуском VAD
        # Проблема: chunk может быть в процессе генерации, но еще не в очереди!
        if self.parallel_tts:
            active_tts = len(self.parallel_tts.tts_tasks.get(channel_id, []))
            queued_chunks = len(self.parallel_tts.playback_queues.get(channel_id, []))
            
            if active_tts > 0 or queued_chunks > 0:
                logger.info(f"⏳ ParallelTTS активен: {active_tts} TTS tasks + {queued_chunks} queued, VAD НЕ запускаем")
                return

        # ТОЛЬКО ЕСЛИ НЕТ АКТИВНЫХ TTS И ОЧЕРЕДЬ ПУСТА - запускаем VAD
        await self.start_user_recording(channel_id)


    async def start_user_recording(self, channel_id: str):
        """Запускает запись речи пользователя с умной детекцией окончания."""
        try:
            # Проверяем, что запись не запущена уже
            if channel_id in self.active_calls and self.active_calls[channel_id].get("is_recording"):
                logger.warning(f"⚠️ Запись уже запущена для канала {channel_id}")
                return
            
            # Создаем уникальное имя файла с UUID
            import uuid
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            unique_id = str(uuid.uuid4())[:8]
            recording_filename = f"user_{channel_id}_{timestamp}_{unique_id}"
            
            # Определяем длительность записи в зависимости от режима
            if self.vad_enabled and self.vad_service:
                # VAD режим - используем максимальное время как fallback, VAD остановит раньше
                recording_duration = self.max_recording_time
                logger.info(f"🎤 Запускаем VAD запись речи пользователя: {recording_filename}, max_duration={recording_duration}s")
            elif self.smart_detection_enabled:
                # Умный режим (старый) - используем короткую запись с детекцией окончания
                recording_duration = min(self.silence_timeout + 2.0, self.max_recording_time)
                logger.info(f"🎤 Запускаем УМНУЮ запись речи пользователя: {recording_filename}, duration={recording_duration}s")
            else:
                # В обычном режиме используем стандартную длительность
                recording_duration = self.max_recording_time
                logger.info(f"🎤 Запускаем запись речи пользователя: {recording_filename}, duration={recording_duration}s")
            
            async with AsteriskARIClient() as ari:
                recording_id = await ari.start_recording(channel_id, recording_filename, max_duration=int(recording_duration))
                
                # Status 201 означает успешный запуск записи
                if recording_id and channel_id in self.active_calls:
                    self.active_calls[channel_id]["current_recording"] = recording_id
                    self.active_calls[channel_id]["recording_filename"] = recording_filename
                    self.active_calls[channel_id]["is_recording"] = True
                    self.active_calls[channel_id]["smart_detection_active"] = self.smart_detection_enabled
                    self.active_calls[channel_id]["vad_processed"] = False  # Сбрасываем флаг для новой записи
                    self.active_calls[channel_id]["processing_speech"] = False  # Сбрасываем флаг обработки речи
                    
                    # Запускаем VAD мониторинг для уменьшения паузы
                    if self.vad_enabled and self.vad_service:
                        vad_success = await self.vad_service.start_monitoring(
                            channel_id, 
                            recording_id, 
                            self._on_vad_recording_finished
                        )
                        if vad_success:
                            logger.info(f"🎯 VAD мониторинг запущен для канала {channel_id}")
                        else:
                            logger.warning(f"⚠️ Не удалось запустить VAD мониторинг для {channel_id}")
                    
                    # нициализируем детектор речи для умного режима (старый)
                    if self.smart_detection_enabled and self.speech_detector:
                        self.speech_detector.reset()
                        self.active_calls[channel_id]["speech_detection_start"] = time.time()
                        logger.info(f"🧠 Умная детекция речи активирована для канала {channel_id}")
                    
                    logger.info(f"✅ Запись запущена: {recording_id}")
                else:
                    logger.warning(f"⚠️ Не удалось запустить запись для канала {channel_id}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка запуска записи: {e}", exc_info=True)
    
# Удален _on_adaptive_recording_finished - возвращаемся к простой логике
    
    async def handle_recording_finished(self, event):
        """Обрабатывает завершение записи."""
        recording = event.get('recording', {})
        recording_name = recording.get('name')
        
        logger.info(f"🎤 Запись завершена: {recording_name}")
        
        # щем канал по имени записи
        channel_id = None
        for cid, call_data in self.active_calls.items():
            if call_data.get("recording_filename") == recording_name:
                channel_id = cid
                logger.info(f"✅ Найден канал {channel_id} для записи {recording_name}")
                break
        
        if not channel_id:
            logger.warning(f"❌ Не найден канал для записи: {recording_name}")
            return
                
        if channel_id:
            # Проверяем, не обработана ли уже запись VAD
            if self.active_calls[channel_id].get("vad_processed", False):
                logger.info(f"🎯 Запись {recording_name} уже обработана VAD, пропускаем дублирование")
                return
            
            # Сбрасываем флаг записи
            self.active_calls[channel_id]["is_recording"] = False
            self.active_calls[channel_id]["current_recording"] = None
            logger.info(f"✅ Сброшен флаг записи для канала {channel_id}")
            
            # Путь к записанному файлу
            recording_path = f"/var/spool/asterisk/recording/{recording_name}.wav"
            
            # Проверяем существование файла перед обработкой
            if os.path.exists(recording_path):
                logger.info(f"✅ Файл записи найден: {recording_path}")
                # Обрабатываем речь пользователя
                await self.process_user_speech_optimized(channel_id, recording_path)
            else:
                logger.warning(f"⚠️ Файл записи не найден: {recording_path}")
        else:
            logger.warning(f"Не найден канал для записи: {recording_name}")
    
    async def handle_user_event(self, event):
        """Обрабатывает пользовательские события"""
        event_name = event.get('eventname')
        channel_id = event.get('channel', {}).get('id')
        
        if event_name == 'UserSpeech' and channel_id:
            # Обрабатываем речь пользователя
            audio_path = event.get('args', [{}])[0].get('audio_path')
            if audio_path:
                await self.process_user_speech_optimized(channel_id, audio_path)
    
    async def _on_vad_recording_finished(self, channel_id: str, recording_id: str, reason: str):
        """
        Callback для VAD - вызывается при окончании записи по детекции тишины.
        
        Args:
            channel_id: ID канала Asterisk
            recording_id: ID записи для остановки
            reason: Причина окончания записи
        """
        try:
            logger.info(f"🎯 VAD callback: {channel_id}, recording={recording_id}, reason={reason}")
            
            # Останавливаем запись через ARI
            async with AsteriskARIClient() as ari:
                await ari.stop_recording(recording_id)
                logger.info(f"✅ VAD остановил запись {recording_id} для канала {channel_id}")
            
            # Обновляем состояние канала
            if channel_id in self.active_calls:
                call_data = self.active_calls[channel_id]
                call_data["is_recording"] = False
                call_data["vad_finished"] = True
                call_data["vad_reason"] = reason
                call_data["vad_processed"] = True  # Флаг для предотвращения дублирования
                call_data["current_recording"] = None  # Сбрасываем текущую запись
                
                # Останавливаем VAD мониторинг
                if self.vad_service:
                    await self.vad_service.stop_monitoring(channel_id)
            
            # Обрабатываем записанную речь
            if channel_id in self.active_calls:
                call_data = self.active_calls[channel_id]
                recording_filename = call_data.get("recording_filename")
                if recording_filename:
                    # Формируем правильный путь к аудио файлу (запись сохраняется в /var/spool/asterisk/recording/)
                    audio_path = f"/var/spool/asterisk/recording/{recording_filename}.wav"
                    logger.info(f"🎯 VAD: Обрабатываем аудио файл: {audio_path}")
                    await self.process_user_speech_optimized(channel_id, audio_path)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в VAD callback для {channel_id}: {e}", exc_info=True)

async def main():
    """Основная функция запуска."""
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Загружаем переменные окружения
    from dotenv import load_dotenv
    load_dotenv()
    
    # Запускаем оптимизированный обработчик
    handler = OptimizedAsteriskAIHandler()
    
    # нициализируем сервисы оптимизации
    await handler.initialize_optimization_services()
    
    # Очищаем висящие каналы перед запуском
    await handler.cleanup_hanging_channels()
    
    # Запускаем основной цикл
    await handler.run()

if __name__ == "__main__":
    asyncio.run(main())

# 111111111111111111
