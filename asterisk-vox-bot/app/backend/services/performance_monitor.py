#!/usr/bin/env python3
"""
Performance Monitor для отслеживания метрик оптимизации
Цель: мониторинг производительности и алерты для DevOps
"""

import asyncio
import time
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
import statistics

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """
    Монитор производительности для оптимизированной системы
    
    Отслеживает:
    1. Время до первого звука (главная метрика)
    2. Распределение времени по компонентам
    3. Показатели качества
    4. Алерты для DevOps
    """
    
    def __init__(self):
        # Метрики по каналам
        self.channel_metrics: Dict[str, Dict] = defaultdict(dict)
        
        # Агрегированные метрики
        self.aggregated_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0,
            "avg_first_chunk_time": 0.0,
            "avg_filler_time": 0.0,
            "avg_grpc_tts_time": 0.0,
            "barge_in_rate": 0.0,
            "fallback_rate": 0.0
        }
        
        # Скользящие окна для метрик
        self.response_times = deque(maxlen=100)  # Последние 100 запросов
        self.first_chunk_times = deque(maxlen=100)
        self.filler_times = deque(maxlen=100)
        self.grpc_tts_times = deque(maxlen=100)
        
        # Пороги для алертов
        self.alert_thresholds = {
            "response_time_critical": 3.0,  # Критично: >3 секунд
            "response_time_warning": 2.0,   # Предупреждение: >2 секунд
            "first_chunk_critical": 1.5,    # Критично: >1.5 секунд
            "first_chunk_warning": 1.0,     # Предупреждение: >1 секунд
            "grpc_tts_critical": 0.5,       # Критично: >0.5 секунд
            "grpc_tts_warning": 0.3,        # Предупреждение: >0.3 секунд
            "fallback_rate_critical": 0.1,  # Критично: >10% fallback
            "fallback_rate_warning": 0.05   # Предупреждение: >5% fallback
        }
        
        # Алерты
        self.active_alerts: List[Dict] = []
        self.alert_history: List[Dict] = []
        
        logger.info("📊 PerformanceMonitor инициализирован")
    
    def start_request(self, channel_id: str, user_text: str) -> str:
        """
        Начинает отслеживание запроса
        
        Args:
            channel_id: ID канала
            user_text: Текст пользователя
            
        Returns:
            str: ID запроса для отслеживания
        """
        request_id = f"{channel_id}_{int(time.time() * 1000)}"
        
        self.channel_metrics[channel_id] = {
            "request_id": request_id,
            "user_text": user_text,
            "start_time": time.time(),
            "asr_complete_time": None,
            "first_chunk_time": None,
            "first_audio_time": None,
            "filler_time": None,
            "grpc_tts_time": None,
            "total_time": None,
            "barge_in_count": 0,
            "fallback_used": False,
            "status": "processing"
        }
        
        logger.info(f"📊 Started monitoring request {request_id} for {channel_id}")
        return request_id
    
    def log_asr_complete(self, channel_id: str, asr_time: float):
        """Логирует завершение ASR"""
        if channel_id in self.channel_metrics:
            self.channel_metrics[channel_id]["asr_complete_time"] = asr_time
            logger.debug(f"📊 ASR complete for {channel_id}: {asr_time:.2f}s")
    
    def log_first_chunk(self, channel_id: str, chunk_time: float):
        """Логирует время первого чанка"""
        if channel_id in self.channel_metrics:
            self.channel_metrics[channel_id]["first_chunk_time"] = chunk_time
            self.first_chunk_times.append(chunk_time)
            logger.debug(f"📊 First chunk for {channel_id}: {chunk_time:.2f}s")
            
            # Проверяем алерты
            self._check_first_chunk_alerts(channel_id, chunk_time)
    
    def log_first_audio(self, channel_id: str, audio_time: float):
        """Логирует время первого аудио"""
        if channel_id in self.channel_metrics:
            self.channel_metrics[channel_id]["first_audio_time"] = audio_time
            logger.debug(f"📊 First audio for {channel_id}: {audio_time:.2f}s")
    
    def log_filler_time(self, channel_id: str, filler_time: float):
        """Логирует время filler"""
        if channel_id in self.channel_metrics:
            self.channel_metrics[channel_id]["filler_time"] = filler_time
            self.filler_times.append(filler_time)
            logger.debug(f"📊 Filler time for {channel_id}: {filler_time:.2f}s")
    
    def log_grpc_tts_time(self, channel_id: str, tts_time: float):
        """Логирует время gRPC TTS"""
        if channel_id in self.channel_metrics:
            self.channel_metrics[channel_id]["grpc_tts_time"] = tts_time
            self.grpc_tts_times.append(tts_time)
            logger.debug(f"📊 gRPC TTS time for {channel_id}: {tts_time:.2f}s")
            
            # Проверяем алерты
            self._check_grpc_tts_alerts(channel_id, tts_time)
    
    def log_barge_in(self, channel_id: str):
        """Логирует barge-in"""
        if channel_id in self.channel_metrics:
            self.channel_metrics[channel_id]["barge_in_count"] += 1
            logger.debug(f"📊 Barge-in for {channel_id}")
    
    def log_fallback(self, channel_id: str):
        """Логирует использование fallback"""
        if channel_id in self.channel_metrics:
            self.channel_metrics[channel_id]["fallback_used"] = True
            logger.debug(f"📊 Fallback used for {channel_id}")
    
    def complete_request(self, channel_id: str, success: bool = True):
        """
        Завершает отслеживание запроса
        
        Args:
            channel_id: ID канала
            success: Успешность запроса
        """
        if channel_id not in self.channel_metrics:
            return
        
        metrics = self.channel_metrics[channel_id]
        metrics["total_time"] = time.time() - metrics["start_time"]
        metrics["status"] = "completed" if success else "failed"
        
        # Добавляем в агрегированные метрики
        self.response_times.append(metrics["total_time"])
        self.aggregated_metrics["total_requests"] += 1
        
        if success:
            self.aggregated_metrics["successful_requests"] += 1
        else:
            self.aggregated_metrics["failed_requests"] += 1
        
        # Обновляем средние значения
        self._update_aggregated_metrics()
        
        # Проверяем алерты
        self._check_response_time_alerts(channel_id, metrics["total_time"])
        
        logger.info(f"📊 Completed monitoring for {channel_id}: {metrics['total_time']:.2f}s")
    
    def _update_aggregated_metrics(self):
        """Обновляет агрегированные метрики"""
        try:
            if self.response_times:
                self.aggregated_metrics["avg_response_time"] = statistics.mean(self.response_times)
            
            if self.first_chunk_times:
                self.aggregated_metrics["avg_first_chunk_time"] = statistics.mean(self.first_chunk_times)
            
            if self.filler_times:
                self.aggregated_metrics["avg_filler_time"] = statistics.mean(self.filler_times)
            
            if self.grpc_tts_times:
                self.aggregated_metrics["avg_grpc_tts_time"] = statistics.mean(self.grpc_tts_times)
            
            # Barge-in rate
            total_requests = self.aggregated_metrics["total_requests"]
            if total_requests > 0:
                barge_in_count = sum(1 for metrics in self.channel_metrics.values() 
                                   if metrics.get("barge_in_count", 0) > 0)
                self.aggregated_metrics["barge_in_rate"] = barge_in_count / total_requests
                
                # Fallback rate
                fallback_count = sum(1 for metrics in self.channel_metrics.values() 
                                   if metrics.get("fallback_used", False))
                self.aggregated_metrics["fallback_rate"] = fallback_count / total_requests
                
        except Exception as e:
            logger.error(f"❌ Update aggregated metrics error: {e}")
    
    def _check_response_time_alerts(self, channel_id: str, response_time: float):
        """Проверяет алерты по времени ответа"""
        try:
            if response_time > self.alert_thresholds["response_time_critical"]:
                self._create_alert("CRITICAL", "response_time", 
                                 f"Response time {response_time:.2f}s > {self.alert_thresholds['response_time_critical']}s",
                                 channel_id, response_time)
            elif response_time > self.alert_thresholds["response_time_warning"]:
                self._create_alert("WARNING", "response_time",
                                 f"Response time {response_time:.2f}s > {self.alert_thresholds['response_time_warning']}s",
                                 channel_id, response_time)
        except Exception as e:
            logger.error(f"❌ Response time alert check error: {e}")
    
    def _check_first_chunk_alerts(self, channel_id: str, chunk_time: float):
        """Проверяет алерты по времени первого чанка"""
        try:
            if chunk_time > self.alert_thresholds["first_chunk_critical"]:
                self._create_alert("CRITICAL", "first_chunk",
                                 f"First chunk time {chunk_time:.2f}s > {self.alert_thresholds['first_chunk_critical']}s",
                                 channel_id, chunk_time)
            elif chunk_time > self.alert_thresholds["first_chunk_warning"]:
                self._create_alert("WARNING", "first_chunk",
                                 f"First chunk time {chunk_time:.2f}s > {self.alert_thresholds['first_chunk_warning']}s",
                                 channel_id, chunk_time)
        except Exception as e:
            logger.error(f"❌ First chunk alert check error: {e}")
    
    def _check_grpc_tts_alerts(self, channel_id: str, tts_time: float):
        """Проверяет алерты по времени gRPC TTS"""
        try:
            if tts_time > self.alert_thresholds["grpc_tts_critical"]:
                self._create_alert("CRITICAL", "grpc_tts",
                                 f"gRPC TTS time {tts_time:.2f}s > {self.alert_thresholds['grpc_tts_critical']}s",
                                 channel_id, tts_time)
            elif tts_time > self.alert_thresholds["grpc_tts_warning"]:
                self._create_alert("WARNING", "grpc_tts",
                                 f"gRPC TTS time {tts_time:.2f}s > {self.alert_thresholds['grpc_tts_warning']}s",
                                 channel_id, tts_time)
        except Exception as e:
            logger.error(f"❌ gRPC TTS alert check error: {e}")
    
    def _create_alert(self, level: str, alert_type: str, message: str, channel_id: str, value: float):
        """Создает алерт"""
        try:
            alert = {
                "id": f"{alert_type}_{int(time.time() * 1000)}",
                "level": level,
                "type": alert_type,
                "message": message,
                "channel_id": channel_id,
                "value": value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "resolved": False
            }
            
            self.active_alerts.append(alert)
            self.alert_history.append(alert)
            
            # Логируем алерт
            if level == "CRITICAL":
                logger.error(f"🚨 CRITICAL ALERT: {message}")
            else:
                logger.warning(f"⚠️ WARNING ALERT: {message}")
            
            # В реальной реализации здесь будет отправка в систему мониторинга
            # await self._send_alert_to_monitoring_system(alert)
            
        except Exception as e:
            logger.error(f"❌ Create alert error: {e}")
    
    def get_channel_metrics(self, channel_id: str) -> Optional[Dict]:
        """Возвращает метрики для канала"""
        return self.channel_metrics.get(channel_id)
    
    def get_aggregated_metrics(self) -> Dict:
        """Возвращает агрегированные метрики"""
        return self.aggregated_metrics.copy()
    
    def get_active_alerts(self) -> List[Dict]:
        """Возвращает активные алерты"""
        return self.active_alerts.copy()
    
    def get_alert_history(self, limit: int = 100) -> List[Dict]:
        """Возвращает историю алертов"""
        return self.alert_history[-limit:]
    
    def resolve_alert(self, alert_id: str):
        """Разрешает алерт"""
        try:
            for alert in self.active_alerts:
                if alert["id"] == alert_id:
                    alert["resolved"] = True
                    alert["resolved_at"] = datetime.now(timezone.utc).isoformat()
                    self.active_alerts.remove(alert)
                    logger.info(f"✅ Resolved alert: {alert_id}")
                    break
        except Exception as e:
            logger.error(f"❌ Resolve alert error: {e}")
    
    def clear_channel_metrics(self, channel_id: str):
        """Очищает метрики канала"""
        if channel_id in self.channel_metrics:
            del self.channel_metrics[channel_id]
            logger.debug(f"🧹 Cleared metrics for {channel_id}")
    
    def get_dashboard_data(self) -> Dict:
        """Возвращает данные для dashboard"""
        try:
            return {
                "aggregated_metrics": self.get_aggregated_metrics(),
                "active_alerts": self.get_active_alerts(),
                "recent_alerts": self.get_alert_history(10),
                "performance_summary": {
                    "avg_response_time": self.aggregated_metrics["avg_response_time"],
                    "avg_first_chunk_time": self.aggregated_metrics["avg_first_chunk_time"],
                    "avg_filler_time": self.aggregated_metrics["avg_filler_time"],
                    "avg_grpc_tts_time": self.aggregated_metrics["avg_grpc_tts_time"],
                    "success_rate": (self.aggregated_metrics["successful_requests"] / 
                                   max(self.aggregated_metrics["total_requests"], 1)) * 100,
                    "barge_in_rate": self.aggregated_metrics["barge_in_rate"] * 100,
                    "fallback_rate": self.aggregated_metrics["fallback_rate"] * 100
                }
            }
        except Exception as e:
            logger.error(f"❌ Get dashboard data error: {e}")
            return {}

# Глобальный экземпляр для использования в других модулях
performance_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """Возвращает глобальный экземпляр PerformanceMonitor"""
    return performance_monitor

