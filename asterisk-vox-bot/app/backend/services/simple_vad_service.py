#!/usr/bin/env python3
"""
Простая система VAD (Voice Activity Detection) для уменьшения паузы после ответа клиента.
Цель: остановка записи через 2-3 секунды после окончания речи вместо фиксированных 15 секунд.

Принципы безопасности:
- Максимальная простота - один класс, 3-4 метода
- Дополнение, не замена - работает поверх существующей системы
- Обязательный fallback - при ошибке возвращается к стандартной записи
- Минимальные изменения - не трогает существующий код
"""

import asyncio
import logging
import time
import os
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SimpleVADService:
    """
    Простая система VAD для детекции окончания речи.
    
    Принцип работы:
    1. Запускает мониторинг тишины после начала записи
    2. Детектирует окончание речи через настраиваемый таймаут тишины
    3. Останавливает запись и вызывает callback
    4. Имеет fallback на максимальное время записи
    """
    
    def __init__(self, 
                 silence_timeout: float = 2.0,
                 min_recording_time: float = 1.0,
                 max_recording_time: float = 15.0,
                 debug_logging: bool = False):
        """
        Инициализация VAD сервиса.
        
        Args:
            silence_timeout: Время тишины в секундах для определения окончания речи
            min_recording_time: Минимальное время записи в секундах (защита от шума)
            max_recording_time: Максимальное время записи в секундах (fallback)
            debug_logging: Включение детального логирования
        """
        self.silence_timeout = silence_timeout
        self.min_recording_time = min_recording_time
        self.max_recording_time = max_recording_time
        self.debug_logging = debug_logging
        
        # Активные мониторинги по channel_id
        self.active_monitors: Dict[str, Dict] = {}
        
        logger.info(f"SimpleVADService инициализирован: silence_timeout={silence_timeout}s, "
                   f"min_recording_time={min_recording_time}s, max_recording_time={max_recording_time}s")
    
    async def start_monitoring(self, 
                             channel_id: str, 
                             recording_id: str,
                             callback: Callable[[str, str], None],
                             silence_timeout_override: float = None,
                             max_duration_override: float = None) -> bool:
        """
        Запускает мониторинг VAD для канала.
        
        Args:
            channel_id: ID канала Asterisk
            recording_id: ID записи для остановки
            callback: Функция обратного вызова при окончании речи
            silence_timeout_override: Кастомный timeout тишины (опционально, для barge-in)
            max_duration_override: Кастомное максимальное время записи (опционально, для barge-in)
            
        Returns:
            True если мониторинг запущен успешно, False иначе
        """
        try:
            if channel_id in self.active_monitors:
                logger.warning(f"VAD мониторинг уже активен для канала {channel_id}")
                return False
            
            # Используем кастомный timeout если передан, иначе дефолтный
            custom_silence_timeout = silence_timeout_override if silence_timeout_override is not None else self.silence_timeout
            # Используем кастомное max_duration если передан, иначе дефолтное
            custom_max_duration = max_duration_override if max_duration_override is not None else self.max_recording_time
            
            # Создаем данные мониторинга
            monitor_data = {
                "recording_id": recording_id,
                "callback": callback,
                "start_time": time.time(),
                "last_activity": time.time(),
                "is_active": True,
                "silence_start": None,
                "silence_timeout": custom_silence_timeout,  # Кастомный timeout для этого мониторинга
                "max_duration": custom_max_duration,  # Кастомное max_duration для этого мониторинга
                "finished_future": asyncio.get_event_loop().create_future(),  # Для ожидания завершения VAD снаружи
                "finish_reason": None,
                "activity_updates": [],  # ✅ CTO.NEW: Сохраняем историю обновлений активности для адаптивного таймаута (Experiment 3)
                "last_timeout_mode": None  # ✅ CTO.NEW: Запоминаем последний режим таймаута для контроля логирования (Experiment 3)
            }
            
            self.active_monitors[channel_id] = monitor_data
            
            # Запускаем мониторинг в фоне
            asyncio.create_task(self._monitor_silence(channel_id))
            
            logger.info(f"✅ VAD мониторинг запущен для канала {channel_id} (silence_timeout={custom_silence_timeout}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска VAD мониторинга для {channel_id}: {e}")
            return False
    
    async def stop_monitoring(self, channel_id: str) -> bool:
        """
        Останавливает мониторинг VAD для канала.
        Идемпотентный метод - можно вызывать несколько раз безопасно.
        
        Args:
            channel_id: ID канала Asterisk
            
        Returns:
            True если мониторинг остановлен успешно, False если не был активен
        """
        try:
            if channel_id not in self.active_monitors:
                # Идемпотентность: если мониторинг уже остановлен, это нормально
                logger.debug(f"VAD мониторинг не активен для канала {channel_id} (уже остановлен или не был запущен)")
                return True  # Возвращаем True, т.к. результат достигнут (мониторинг не активен)
            
            # Останавливаем мониторинг
            self.active_monitors[channel_id]["is_active"] = False
            del self.active_monitors[channel_id]
            
            logger.debug(f"✅ VAD мониторинг остановлен для канала {channel_id}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка остановки VAD мониторинга для {channel_id}: {e}")
            # Пытаемся удалить из словаря, даже если была ошибка
            if channel_id in self.active_monitors:
                try:
                    del self.active_monitors[channel_id]
                except:
                    pass
            return False
    
    async def update_activity(self, channel_id: str) -> None:
        """
        Обновляет время последней активности для канала.
        Вызывается при получении аудио данных или ASR результатов.
        
        Args:
            channel_id: ID канала Asterisk
        """
        if channel_id not in self.active_monitors:
            return
        
        monitor_data = self.active_monitors[channel_id]
        if not monitor_data["is_active"]:
            return
        
        current_time = time.time()
        monitor_data["last_activity"] = current_time
        monitor_data["silence_start"] = None  # Сбрасываем начало тишины
        activity_updates = monitor_data.get("activity_updates")  # ✅ CTO.NEW: Получаем историю активности для адаптивного анализа (Experiment 3)
        if activity_updates is not None:  # ✅ CTO.NEW: Проверяем наличие буфера активности (Experiment 3)
            activity_updates.append(current_time)  # ✅ CTO.NEW: Фиксируем момент активности для расчета частоты (Experiment 3)
            if len(activity_updates) > 50:  # ✅ CTO.NEW: Ограничиваем объем буфера, чтобы избегать роста памяти (Experiment 3)
                del activity_updates[:-50]  # ✅ CTO.NEW: Храним только последние 50 обновлений для анализа (Experiment 3)
        
        if self.debug_logging:
            logger.debug(f"VAD: Активность обновлена для канала {channel_id}")
    
    async def _monitor_silence(self, channel_id: str) -> None:
        """
        Основной цикл мониторинга тишины.
        
        Args:
            channel_id: ID канала Asterisk
        """
        try:
            while channel_id in self.active_monitors:
                monitor_data = self.active_monitors[channel_id]
                
                if not monitor_data["is_active"]:
                    break
                
                current_time = time.time()
                recording_duration = current_time - monitor_data["start_time"]
                time_since_activity = current_time - monitor_data["last_activity"]
                
                # ✅ КРИТИЧНО: Используем кастомное max_duration из monitor_data, если установлено
                # Это позволяет использовать разные max_duration для разных записей (например, 2.0s для barge-in)
                max_duration = monitor_data.get("max_duration", self.max_recording_time)
                
                # Проверяем максимальное время записи (fallback)
                if recording_duration >= max_duration:
                    logger.info(f"VAD: Максимальное время записи достигнуто для {channel_id} ({recording_duration:.1f}s >= {max_duration:.1f}s)")
                    await self._finish_recording(channel_id, "max_time_reached")
                    break
                
                # Проверяем минимальное время записи (даем время пользователю начать говорить)
                if recording_duration < self.min_recording_time:
                    await asyncio.sleep(0.1)  # Короткая пауза
                    continue
                
                # Используем кастомный timeout из monitor_data, если есть, иначе дефолтный
                silence_timeout = monitor_data.get("silence_timeout", self.silence_timeout)
                activity_updates = monitor_data.setdefault("activity_updates", [])  # ✅ CTO.NEW: Храним таймстампы активности для частотного анализа (Experiment 3)
                adaptive_timeout = max(2.0, silence_timeout)  # ✅ CTO.NEW: Базовый таймаут учитывает исходное значение и минимальную границу из Experiment 3
                avg_interval = None  # ✅ CTO.NEW: Средний интервал между обновлениями активности для адаптивной логики (Experiment 3)
                if len(activity_updates) >= 2:  # ✅ CTO.NEW: Рассчитываем частоту только при наличии достаточного количества наблюдений (Experiment 3)
                    intervals = [activity_updates[i] - activity_updates[i - 1] for i in range(1, len(activity_updates))]  # ✅ CTO.NEW: Интервалы между обновлениями активности (Experiment 3)
                    if intervals:  # ✅ CTO.NEW: Проверка на возможность вычисления среднего интервала (Experiment 3)
                        avg_interval = sum(intervals) / len(intervals)  # ✅ CTO.NEW: Средний интервал помогает определить режим речи (Experiment 3)
                timeout_mode = "default"  # ✅ CTO.NEW: Режим адаптивного таймаута по умолчанию (Experiment 3)
                if avg_interval is not None and avg_interval < 2.0 and recording_duration > 3.0:  # ✅ CTO.NEW: Непрерывная речь с высокой частотой обновлений → увеличиваем таймаут до 3.5s (Experiment 3)
                    adaptive_timeout = 3.5  # ✅ CTO.NEW: Таймаут для непрерывной речи согласно Experiment 3
                    timeout_mode = "continuous_speech"  # ✅ CTO.NEW: Фиксируем режим непрерывной речи (Experiment 3)
                elif recording_duration > 8.0:  # ✅ CTO.NEW: Очень длинная фраза требует большего окна ожидания (Experiment 3)
                    adaptive_timeout = 4.0  # ✅ CTO.NEW: Таймаут для длинных фраз согласно Experiment 3
                    timeout_mode = "long_phrase"  # ✅ CTO.NEW: Фиксируем режим длинной фразы (Experiment 3)
                else:
                    adaptive_timeout = max(2.0, silence_timeout)  # ✅ CTO.NEW: Обычный режим использует стандартный таймаут 2s или больше (Experiment 3)
                    timeout_mode = "default"  # ✅ CTO.NEW: Подтверждаем стандартный режим (Experiment 3)
                should_debug_log = self.debug_logging and logger.isEnabledFor(logging.DEBUG)  # ✅ CTO.NEW: Логируем параметры только при активном DEBUG-режиме (Experiment 3)
                if should_debug_log and monitor_data.get("last_timeout_mode") != timeout_mode:  # ✅ CTO.NEW: Сообщаем о смене режима таймаута при изменении (Experiment 3)
                    if timeout_mode == "continuous_speech":  # ✅ CTO.NEW: Сообщаем о выборе режима непрерывной речи (Experiment 3)
                        logger.debug(f"VAD: Непрерывная речь, timeout={adaptive_timeout}s, avg_interval={(avg_interval if avg_interval is not None else float('nan')):.2f}s")  # ✅ CTO.NEW: Логирование параметров для отладки (Experiment 3)
                    elif timeout_mode == "long_phrase":  # ✅ CTO.NEW: Сообщаем о выборе режима длинной фразы (Experiment 3)
                        logger.debug("VAD: Очень длинная фраза (>8s), timeout=4.0s")  # ✅ CTO.NEW: Логирование параметров для отладки (Experiment 3)
                    else:
                        logger.debug(f"VAD: Обычный режим, timeout={adaptive_timeout:.1f}s")  # ✅ CTO.NEW: Логирование параметров для отладки (Experiment 3)
                monitor_data["last_timeout_mode"] = timeout_mode  # ✅ CTO.NEW: Обновляем актуальный режим независимо от логирования (Experiment 3)
                if should_debug_log:  # ✅ CTO.NEW: Логируем статистику адаптивного таймаута в режиме DEBUG (Experiment 3)
                    avg_interval_for_log = avg_interval if avg_interval is not None else float("nan")  # ✅ CTO.NEW: Значение для итоговой статистики адаптивного VAD (Experiment 3)
                    logger.debug(f"VAD stats: recording_duration={recording_duration:.2f}s, activity_updates={len(activity_updates)}, avg_interval={avg_interval_for_log:.2f}s, adaptive_timeout={adaptive_timeout:.2f}s")  # ✅ CTO.NEW: Детальное логирование статистики адаптивного VAD (Experiment 3)
                
                # ✅ ЗАЩИТА: Используем отношение к ТЕКУЩЕМУ max_duration (например, 5s для soft-window)
                # Это избегает слишком большого порога для коротких окон (иначе silence_timeout * 1.5 > max_duration)
                if recording_duration < max_duration / 3:
                    silence_timeout_threshold = adaptive_timeout * 1.5
                else:
                    silence_timeout_threshold = adaptive_timeout
                
                # Проверяем тишину
                if time_since_activity >= silence_timeout_threshold:
                    if monitor_data["silence_start"] is None:
                        monitor_data["silence_start"] = current_time
                        logger.info(f"VAD: Тишина обнаружена для {channel_id} (длительность: {time_since_activity:.1f}s, timeout={adaptive_timeout}s)")
                    else:
                        silence_duration = current_time - monitor_data["silence_start"]
                        # ✅ CTO.NEW: Для завершения используем адаптивный таймаут, как предписано Experiment 3
                        required_silence = min(adaptive_timeout, silence_timeout_threshold)
                        # Также страхуемся от выхода за предел max_duration
                        if silence_duration >= required_silence or (recording_duration + silence_duration) >= max_duration:
                            logger.info(f"VAD: Окончание речи детектировано для {channel_id} "
                                      f"(тишина: {silence_duration:.1f}s, общая запись: {recording_duration:.1f}s)")
                            await self._finish_recording(channel_id, "silence_detected")
                            break
                else:
                    # Сбрасываем начало тишины если есть активность
                    monitor_data["silence_start"] = None
                
                await asyncio.sleep(0.1)  # Проверяем каждые 100мс
                
        except Exception as e:
            logger.error(f"❌ Ошибка в VAD мониторинге для {channel_id}: {e}")
            # При ошибке останавливаем мониторинг
            if channel_id in self.active_monitors:
                del self.active_monitors[channel_id]
    
    async def _finish_recording(self, channel_id: str, reason: str) -> None:
        """
        Завершает запись и вызывает callback.
        
        Args:
            channel_id: ID канала Asterisk
            reason: Причина завершения записи
        """
        try:
            if channel_id not in self.active_monitors:
                return
            
            monitor_data = self.active_monitors[channel_id]
            recording_id = monitor_data["recording_id"]
            callback = monitor_data["callback"]
            
            # Останавливаем мониторинг
            monitor_data["is_active"] = False
            del self.active_monitors[channel_id]
            
            # Вызываем callback
            if callback:
                try:
                    await callback(channel_id, recording_id, reason)
                except Exception as e:
                    logger.error(f"❌ Ошибка в VAD callback для {channel_id}: {e}")
            
            logger.info(f"✅ VAD запись завершена для {channel_id}: {reason}")
            # Сигнализируем ожидающим корутинам
            try:
                fut = monitor_data.get("finished_future")
                if fut and not fut.done():
                    fut.set_result((recording_id, reason))
            except Exception:
                pass
            
        except Exception as e:
            logger.error(f"❌ Ошибка завершения VAD записи для {channel_id}: {e}")
    
    def is_monitoring(self, channel_id: str) -> bool:
        """
        Проверяет, активен ли мониторинг для канала.
        
        Args:
            channel_id: ID канала Asterisk
            
        Returns:
            True если мониторинг активен, False иначе
        """
        return (channel_id in self.active_monitors and 
                self.active_monitors[channel_id]["is_active"])
    
    def get_monitoring_stats(self, channel_id: str) -> Optional[Dict]:
        """
        Возвращает статистику мониторинга для канала.
        
        Args:
            channel_id: ID канала Asterisk
            
        Returns:
            Словарь со статистикой или None если мониторинг не активен
        """
        if channel_id not in self.active_monitors:
            return None
        
        monitor_data = self.active_monitors[channel_id]
        current_time = time.time()
        
        return {
            "recording_id": monitor_data["recording_id"],
            "start_time": monitor_data["start_time"],
            "duration": current_time - monitor_data["start_time"],
            "last_activity": monitor_data["last_activity"],
            "time_since_activity": current_time - monitor_data["last_activity"],
            "silence_start": monitor_data["silence_start"],
            "is_active": monitor_data["is_active"]
        }

    async def record_until_silence_with_soft_window(
        self,
        channel_id: str,
        start_segment_fn: Callable[[float], asyncio.Future],
        window_seconds: float = 5.0,
        max_total_seconds: float = 60.0,
        silence_timeout_override: Optional[float] = None,
        on_chunk: Optional[Callable[[str, str, str], asyncio.Future]] = None,
        on_final: Optional[Callable[[str, str, str], asyncio.Future]] = None,
        channel_check_fn: Optional[Callable[[str], asyncio.Future]] = None,
    ) -> None:
        """
        Квазистрим: последовательно пишет короткие сегменты фиксированной длины, пока не будет тишина.
        Для каждого сегмента вызывает on_chunk (если закончился по таймауту окна), а при тишине — on_final.

        Args:
            channel_id: Канал Asterisk
            start_segment_fn: async-функция, запускающая запись сегмента и возвращающая (recording_id, recording_filename)
            window_seconds: Длина окна сегмента (сек)
            max_total_seconds: Максимальная суммарная длительность (сек)
            silence_timeout_override: Кастомный таймаут тишины для VAD
            on_chunk: async-функция (channel_id, recording_filename, reason)
            on_final: async-функция (channel_id, recording_filename, reason)
            channel_check_fn: async-функция для проверки существования канала
        """
        started_at = time.time()
        while time.time() - started_at < max_total_seconds:
            # ✅ НОВОЕ: Проверяем что канал еще существует перед новым сегментом
            if channel_check_fn and not await channel_check_fn(channel_id):
                logger.info(f"soft-window: канал {channel_id} больше не существует, останавливаем запись")
                break
            
            # 1) Запускаем сегмент записи через переданную функцию
            recording_id, recording_filename = await start_segment_fn(window_seconds)
            
            # ✅ НОВОЕ: Если запись не удалась (канал разорван), останавливаем
            if not recording_id or not recording_filename:
                logger.info(f"soft-window: не удалось запустить запись для {channel_id}, останавливаем")
                break

            # 2) Запускаем мониторинг для сегмента c ограничением по окну
            ok = await self.start_monitoring(
                channel_id,
                recording_id,
                callback=None,  # будем ждать future ниже
                silence_timeout_override=silence_timeout_override,
                max_duration_override=window_seconds,
            )
            if not ok:
                logger.warning(f"soft-window: не удалось запустить мониторинг для {channel_id}")
                return

            # 3) Ждем завершения сегмента (тишина или достижение окна)
            fut = self.active_monitors.get(channel_id, {}).get("finished_future")
            if not fut:
                # Если по какой-то причине нет future — fallback ожидание окна
                await asyncio.sleep(window_seconds)
                reason = "max_time_reached"
            else:
                _rec_id, reason = await fut

            # В этот момент _finish_recording уже вызван и мониторинг остановлен

            # 4) Вызываем колбэки
            try:
                if reason == "max_time_reached":
                    if on_chunk:
                        await on_chunk(channel_id, recording_filename, reason)
                    # Продолжаем следующий сегмент
                    continue
                else:
                    if on_final:
                        await on_final(channel_id, recording_filename, reason)
                    break
            except Exception as e:
                logger.warning(f"soft-window: ошибка в колбэке: {e}")
                break


# Глобальный экземпляр сервиса
_vad_service: Optional[SimpleVADService] = None

def get_vad_service() -> SimpleVADService:
    """
    Возвращает глобальный экземпляр VAD сервиса.
    
    Returns:
        Экземпляр SimpleVADService
    """
    global _vad_service
    
    if _vad_service is None:
        # Загружаем конфигурацию из .env
        silence_timeout = float(os.getenv("VAD_SILENCE_TIMEOUT", "2.0"))
        min_recording_time = float(os.getenv("VAD_MIN_RECORDING_TIME", "1.0"))
        max_recording_time = float(os.getenv("VAD_MAX_RECORDING_TIME", "15.0"))
        debug_logging = os.getenv("VAD_DEBUG_LOGGING", "false").lower() == "true"
        
        _vad_service = SimpleVADService(
            silence_timeout=silence_timeout,
            min_recording_time=min_recording_time,
            max_recording_time=max_recording_time,
            debug_logging=debug_logging
        )
        
        logger.info("✅ SimpleVADService создан с конфигурацией из .env")
    
    return _vad_service
