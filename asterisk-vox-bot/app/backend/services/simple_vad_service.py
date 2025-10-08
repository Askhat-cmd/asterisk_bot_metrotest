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
                             callback: Callable[[str, str], None]) -> bool:
        """
        Запускает мониторинг VAD для канала.
        
        Args:
            channel_id: ID канала Asterisk
            recording_id: ID записи для остановки
            callback: Функция обратного вызова при окончании речи
            
        Returns:
            True если мониторинг запущен успешно, False иначе
        """
        try:
            if channel_id in self.active_monitors:
                logger.warning(f"VAD мониторинг уже активен для канала {channel_id}")
                return False
            
            # Создаем данные мониторинга
            monitor_data = {
                "recording_id": recording_id,
                "callback": callback,
                "start_time": time.time(),
                "last_activity": time.time(),
                "is_active": True,
                "silence_start": None
            }
            
            self.active_monitors[channel_id] = monitor_data
            
            # Запускаем мониторинг в фоне
            asyncio.create_task(self._monitor_silence(channel_id))
            
            logger.info(f"✅ VAD мониторинг запущен для канала {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска VAD мониторинга для {channel_id}: {e}")
            return False
    
    async def stop_monitoring(self, channel_id: str) -> bool:
        """
        Останавливает мониторинг VAD для канала.
        
        Args:
            channel_id: ID канала Asterisk
            
        Returns:
            True если мониторинг остановлен успешно, False иначе
        """
        try:
            if channel_id not in self.active_monitors:
                logger.warning(f"VAD мониторинг не активен для канала {channel_id}")
                return False
            
            # Останавливаем мониторинг
            self.active_monitors[channel_id]["is_active"] = False
            del self.active_monitors[channel_id]
            
            logger.info(f"✅ VAD мониторинг остановлен для канала {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка остановки VAD мониторинга для {channel_id}: {e}")
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
                
                # Проверяем максимальное время записи (fallback)
                if recording_duration >= self.max_recording_time:
                    logger.info(f"VAD: Максимальное время записи достигнуто для {channel_id} ({recording_duration:.1f}s)")
                    await self._finish_recording(channel_id, "max_time_reached")
                    break
                
                # Проверяем минимальное время записи
                if recording_duration < self.min_recording_time:
                    await asyncio.sleep(0.1)  # Короткая пауза
                    continue
                
                # Проверяем тишину
                if time_since_activity >= self.silence_timeout:
                    if monitor_data["silence_start"] is None:
                        monitor_data["silence_start"] = current_time
                        logger.info(f"VAD: Тишина обнаружена для {channel_id} (длительность: {time_since_activity:.1f}s)")
                    else:
                        silence_duration = current_time - monitor_data["silence_start"]
                        if silence_duration >= self.silence_timeout:
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
