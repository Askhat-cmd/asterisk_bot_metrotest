#!/usr/bin/env python3
"""
Filler Words TTS система для мгновенных психологических реакций
Цель: <150мс для создания ощущения "бот думает, скоро ответит"
"""

import asyncio
import time
import logging
import os
from typing import Dict, Optional
import io
import wave

logger = logging.getLogger(__name__)

class InstantFillerTTS:
    """
    Система мгновенных filler words для психологического эффекта
    
    Принцип работы:
    1. Предгенерируем популярные filler words в память
    2. Возвращаем мгновенно (<100мс) при запросе
    3. Контекстный выбор filler на основе типа вопроса
    """
    
    def __init__(self):
        self.cached_fillers: Dict[str, bytes] = {}
        self.initialized = False
        
        # Популярные filler words для русского языка
        self.filler_words = [
            "Хм,",
            "Так,",
            "Итак,",
            "Понятно,",
            "Сейчас,",
            "Хорошо,",
            "Отлично,",
            "Понял,"
        ]
        
        logger.info("🎵 InstantFillerTTS инициализирован")
    
    async def initialize(self, grpc_tts=None):
        """
        Инициализация с предгенерацией filler words
        
        Args:
            grpc_tts: Экземпляр YandexGrpcTTS для генерации реального аудио (опционально)
        """
        try:
            logger.info("🔄 Инициализация Filler TTS...")
            
            # Сохраняем ссылку на gRPC TTS для будущего использования
            self.grpc_tts = grpc_tts
            
            # Предгенерируем все filler words
            for filler in self.filler_words:
                audio = await self._synthesize_filler_grpc(filler)
                self.cached_fillers[filler] = audio
                logger.info(f"✅ Cached filler: '{filler}'")
            
            self.initialized = True
            logger.info("✅ Filler TTS initialized with cached responses")
            
        except Exception as e:
            logger.error(f"❌ Filler TTS init failed: {e}")
            self.initialized = False
    
    async def get_instant_filler(self, context: str = "") -> bytes:
        """
        Возвращает мгновенный filler word (<100мс).
        
        Args:
            context: Контекст вопроса для выбора подходящего filler
            
        Returns:
            bytes: Аудио данные filler word
        """
        start_time = time.time()
        
        try:
            # Контекстный выбор filler
            filler = self._select_contextual_filler(context)
            
            # Возвращаем кэшированный или генерируем
            if filler in self.cached_fillers:
                audio = self.cached_fillers[filler]
                elapsed = time.time() - start_time
                logger.info(f"⚡ Instant cached filler: '{filler}' ({elapsed:.3f}s)")
                return audio
            else:
                # Fallback - генерируем на лету через gRPC
                audio = await self._synthesize_filler_grpc(filler)
                elapsed = time.time() - start_time
                logger.info(f"⚡ Generated filler on-the-fly: '{filler}' ({elapsed:.3f}s)")
                return audio
                
        except Exception as e:
            logger.error(f"❌ Filler generation error: {e}")
            return b""  # Пустой при ошибке
    
    def _select_contextual_filler(self, context: str) -> str:
        """
        Выбирает подходящий filler на основе контекста
        
        Args:
            context: Контекст вопроса
            
        Returns:
            str: Выбранный filler word
        """
        context_lower = context.lower()
        
        # Технические вопросы → серьезный тон
        if any(word in context_lower for word in ["техн", "машин", "испытан", "стандарт", "iso", "астм"]):
            return "Итак,"
        
        # Ценовые вопросы → деловой тон
        elif any(word in context_lower for word in ["цена", "стоимость", "кп", "коммерческ", "договор"]):
            return "Сейчас,"
        
        # Вопросы о характеристиках → заинтересованный тон
        elif any(word in context_lower for word in ["характеристик", "параметр", "точность", "скорость"]):
            return "Хорошо,"
        
        # Общие вопросы → дружелюбный тон
        else:
            return "Хм,"  # Универсальный
    
    async def _synthesize_filler_grpc(self, text: str) -> bytes:
        """
        Синтез filler word через gRPC TTS (РЕАЛЬНЫЙ ЗВУК!)
        
        Args:
            text: Текст для синтеза (например "Хм,")
            
        Returns:
            bytes: Аудио данные (WAV формат, 8kHz)
        """
        try:
            # Если есть gRPC TTS - используем реальный синтез
            if self.grpc_tts:
                try:
                    audio_data = await self.grpc_tts.synthesize_chunk_fast(text)
                    logger.info(f"✅ Filler synthesized via gRPC: '{text}' ({len(audio_data)} bytes)")
                    return audio_data
                except Exception as grpc_error:
                    logger.warning(f"⚠️ gRPC filler failed for '{text}', fallback to silence: {grpc_error}")
                    return self._synthesize_filler_simple(text)
            else:
                # Fallback на тишину если gRPC недоступен
                logger.debug(f"ℹ️ gRPC TTS not available, using silence for filler")
                return self._synthesize_filler_simple(text)
            
        except Exception as e:
            logger.error(f"❌ Filler synthesis error: {e}")
            return self._synthesize_filler_simple(text)
    
    def _synthesize_filler_simple(self, text: str) -> bytes:
        """
        Fallback: Синтез filler word как тишина
        Используется только если gRPC TTS недоступен
        
        Args:
            text: Текст для синтеза
            
        Returns:
            bytes: Аудио данные (WAV с тишиной)
        """
        try:
            # Создаем 0.5 секунды тишины (16-bit, 8kHz, mono)
            sample_rate = 8000
            duration = 0.5  # 500мс
            samples = int(sample_rate * duration)
            
            # Генерируем тишину (нулевые значения)
            audio_data = b'\x00' * (samples * 2)  # 16-bit = 2 bytes per sample
            
            # Создаем WAV заголовок
            wav_header = self._create_wav_header(len(audio_data), sample_rate)
            
            # Объединяем заголовок и данные
            wav_data = wav_header + audio_data
            
            logger.debug(f"🎵 Generated silence filler: {len(wav_data)} bytes")
            return wav_data
            
        except Exception as e:
            logger.error(f"❌ Simple filler synthesis error: {e}")
            return b""
    
    def _create_wav_header(self, data_size: int, sample_rate: int) -> bytes:
        """
        Создает WAV заголовок для аудио данных
        
        Args:
            data_size: Размер аудио данных в байтах
            sample_rate: Частота дискретизации
            
        Returns:
            bytes: WAV заголовок
        """
        # WAV заголовок (44 байта)
        header = bytearray(44)
        
        # RIFF заголовок
        header[0:4] = b'RIFF'
        header[4:8] = (data_size + 36).to_bytes(4, 'little')  # Размер файла - 8
        header[8:12] = b'WAVE'
        
        # fmt chunk
        header[12:16] = b'fmt '
        header[16:20] = (16).to_bytes(4, 'little')  # Размер fmt chunk
        header[20:22] = (1).to_bytes(2, 'little')   # PCM format
        header[22:24] = (1).to_bytes(2, 'little')   # Mono
        header[24:28] = sample_rate.to_bytes(4, 'little')  # Sample rate
        header[28:32] = (sample_rate * 2).to_bytes(4, 'little')  # Byte rate
        header[32:34] = (2).to_bytes(2, 'little')   # Block align
        header[34:36] = (16).to_bytes(2, 'little')  # Bits per sample
        
        # data chunk
        header[36:40] = b'data'
        header[40:44] = data_size.to_bytes(4, 'little')  # Размер данных
        
        return bytes(header)
    
    def get_available_fillers(self) -> list:
        """Возвращает список доступных filler words"""
        return list(self.cached_fillers.keys())
    
    def is_initialized(self) -> bool:
        """Проверяет, инициализирован ли сервис"""
        return self.initialized

# Глобальный экземпляр для использования в других модулях
filler_tts_instance = InstantFillerTTS()

async def get_filler_tts() -> InstantFillerTTS:
    """Возвращает инициализированный экземпляр Filler TTS"""
    if not filler_tts_instance.is_initialized():
        await filler_tts_instance.initialize()
    return filler_tts_instance

