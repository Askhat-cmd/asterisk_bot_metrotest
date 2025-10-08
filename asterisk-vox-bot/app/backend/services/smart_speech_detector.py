"""
Умный детектор окончания речи для уменьшения паузы в голосовом ассистенте.
Основан на анализе тишины и длительности речи.

Вдохновлено решением из scenario_barge-in_2.js
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SmartSpeechDetector:
    """
    Умный детектор окончания речи, который определяет, когда пользователь закончил говорить.
    Использует таймаут тишины и минимальную длительность речи для предотвращения ложных срабатываний.
    """
    
    def __init__(self, silence_timeout: float = 1.2, min_speech_duration: float = 0.5):
        """
        Инициализация детектора.
        
        Args:
            silence_timeout: Время тишины в секундах для определения окончания речи
            min_speech_duration: Минимальная длительность речи в секундах
        """
        self.silence_timeout = silence_timeout
        self.min_speech_duration = min_speech_duration
        self.speech_start_time: Optional[float] = None
        self.last_speech_time: Optional[float] = None
        self.is_speech_active = False
        self.speech_buffer = ""
        
        logger.info(f"SmartSpeechDetector инициализирован: silence_timeout={silence_timeout}s, min_speech_duration={min_speech_duration}s")
    
    def on_speech_detected(self, text: str = "") -> None:
        """
        Вызывается при обнаружении речи.
        
        Args:
            text: Распознанный текст (может быть пустым)
        """
        current_time = time.time()
        
        if not self.is_speech_active:
            # Начало новой речи
            self.is_speech_active = True
            self.speech_start_time = current_time
            logger.debug("Начало речи обнаружено")
        
        # Обновляем время последней речи
        self.last_speech_time = current_time
        
        # Добавляем текст в буфер
        if text.strip():
            self.speech_buffer = text  # Обновляем буфер последним результатом
            logger.debug(f"Обновлен буфер речи: '{text[:50]}...'")
    
    def on_silence_detected(self) -> bool:
        """
        Вызывается при обнаружении тишины.
        
        Returns:
            True, если речь считается завершенной, иначе False
        """
        if not self.is_speech_active:
            return False
        
        current_time = time.time()
        
        # Проверяем, достаточно ли долго длится тишина
        if self.last_speech_time and (current_time - self.last_speech_time) >= self.silence_timeout:
            # Проверяем, достаточно ли долго длилась речь
            speech_duration = self.last_speech_time - self.speech_start_time
            if speech_duration >= self.min_speech_duration:
                logger.info(f"Речь завершена. Длительность: {speech_duration:.2f}s, буфер: '{self.speech_buffer[:50]}...'")
                return True
            else:
                # Речь была слишком короткой, считаем это шумом
                logger.debug(f"Речь слишком короткая ({speech_duration:.2f}s), сброс")
                self.reset()
                return False
        
        return False
    
    def get_speech_text(self) -> str:
        """
        Возвращает накопленный текст речи.
        
        Returns:
            Текст речи из буфера
        """
        return self.speech_buffer.strip()
    
    def reset(self) -> None:
        """
        Сбрасывает состояние детектора.
        """
        self.is_speech_active = False
        self.speech_start_time = None
        self.last_speech_time = None
        self.speech_buffer = ""
        logger.debug("Детектор речи сброшен")
    
    def is_active(self) -> bool:
        """
        Проверяет, активен ли детектор (идет ли речь).
        
        Returns:
            True, если речь активна, иначе False
        """
        return self.is_speech_active
    
    def get_speech_duration(self) -> float:
        """
        Возвращает длительность текущей речи.
        
        Returns:
            Длительность речи в секундах или 0.0, если речь не активна
        """
        if not self.is_speech_active or not self.speech_start_time:
            return 0.0
        
        end_time = self.last_speech_time or time.time()
        return end_time - self.speech_start_time
