#!/usr/bin/env python3
"""
Error Handler для обработки ошибок и fallback механизмов
Цель: отказоустойчивость и graceful degradation
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Уровни серьезности ошибок"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Категории ошибок"""
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    SERVICE_UNAVAILABLE = "service_unavailable"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    INTERNAL = "internal"

@dataclass
class ErrorInfo:
    """Информация об ошибке"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    channel_id: Optional[str] = None
    retry_count: int = 0
    resolved: bool = False

class FallbackStrategy:
    """Стратегия fallback для различных типов ошибок"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0, 
                 fallback_action: Optional[Callable] = None):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.fallback_action = fallback_action

class ErrorHandler:
    """
    Обработчик ошибок с fallback механизмами
    
    Функции:
    1. Классификация ошибок по категориям и серьезности
    2. Автоматические retry с экспоненциальным backoff
    3. Fallback стратегии для различных компонентов
    4. Логирование и мониторинг ошибок
    5. Graceful degradation при критических ошибках
    """
    
    def __init__(self):
        # Ошибки по каналам
        self.channel_errors: Dict[str, List[ErrorInfo]] = {}
        
        # Fallback стратегии
        self.fallback_strategies = {
            ErrorCategory.NETWORK: FallbackStrategy(max_retries=3, retry_delay=1.0),
            ErrorCategory.AUTHENTICATION: FallbackStrategy(max_retries=1, retry_delay=0.5),
            ErrorCategory.RATE_LIMIT: FallbackStrategy(max_retries=2, retry_delay=2.0),
            ErrorCategory.SERVICE_UNAVAILABLE: FallbackStrategy(max_retries=2, retry_delay=1.5),
            ErrorCategory.TIMEOUT: FallbackStrategy(max_retries=2, retry_delay=1.0),
            ErrorCategory.VALIDATION: FallbackStrategy(max_retries=0, retry_delay=0.0),
            ErrorCategory.INTERNAL: FallbackStrategy(max_retries=1, retry_delay=0.5)
        }
        
        # Статистика ошибок
        self.error_stats = {
            "total_errors": 0,
            "errors_by_category": {category.value: 0 for category in ErrorCategory},
            "errors_by_severity": {severity.value: 0 for severity in ErrorSeverity},
            "retry_success_rate": 0.0,
            "fallback_usage_rate": 0.0
        }
        
        logger.info("🛡️ ErrorHandler инициализирован")
    
    async def handle_error(self, error: Exception, channel_id: Optional[str] = None, 
                          context: Optional[Dict] = None) -> ErrorInfo:
        """
        Обрабатывает ошибку с автоматическим retry и fallback
        
        Args:
            error: Исключение
            channel_id: ID канала (если применимо)
            context: Дополнительный контекст
            
        Returns:
            ErrorInfo: Информация об обработанной ошибке
        """
        try:
            # Классифицируем ошибку
            error_info = self._classify_error(error, channel_id, context)
            
            # Логируем ошибку
            self._log_error(error_info)
            
            # Обновляем статистику
            self._update_error_stats(error_info)
            
            # Добавляем в историю канала
            if channel_id:
                if channel_id not in self.channel_errors:
                    self.channel_errors[channel_id] = []
                self.channel_errors[channel_id].append(error_info)
            
            # Определяем стратегию обработки
            strategy = self.fallback_strategies.get(error_info.category)
            
            if strategy and strategy.max_retries > 0:
                # Пытаемся retry
                success = await self._retry_with_backoff(error_info, strategy)
                if success:
                    error_info.resolved = True
                    return error_info
            
            # Если retry не помог, используем fallback
            if strategy and strategy.fallback_action:
                await self._execute_fallback(error_info, strategy)
            
            return error_info
            
        except Exception as e:
            logger.error(f"❌ Error handling failed: {e}")
            # Создаем критическую ошибку для самой системы обработки ошибок
            critical_error = ErrorInfo(
                error_id=f"critical_{int(time.time() * 1000)}",
                category=ErrorCategory.INTERNAL,
                severity=ErrorSeverity.CRITICAL,
                message=f"Error handler failed: {str(e)}",
                details={"original_error": str(error)},
                timestamp=datetime.now(timezone.utc),
                channel_id=channel_id
            )
            return critical_error
    
    def _classify_error(self, error: Exception, channel_id: Optional[str], 
                       context: Optional[Dict]) -> ErrorInfo:
        """Классифицирует ошибку по категории и серьезности"""
        try:
            error_id = f"error_{int(time.time() * 1000)}"
            error_message = str(error)
            error_type = type(error).__name__
            
            # Определяем категорию
            category = self._determine_category(error, context)
            
            # Определяем серьезность
            severity = self._determine_severity(error, category, context)
            
            # Собираем детали
            details = {
                "error_type": error_type,
                "error_message": error_message,
                "context": context or {},
                "channel_id": channel_id
            }
            
            return ErrorInfo(
                error_id=error_id,
                category=category,
                severity=severity,
                message=error_message,
                details=details,
                timestamp=datetime.now(timezone.utc),
                channel_id=channel_id
            )
            
        except Exception as e:
            logger.error(f"❌ Error classification failed: {e}")
            # Возвращаем базовую классификацию
            return ErrorInfo(
                error_id=f"classification_failed_{int(time.time() * 1000)}",
                category=ErrorCategory.INTERNAL,
                severity=ErrorSeverity.HIGH,
                message=f"Error classification failed: {str(e)}",
                details={"original_error": str(error)},
                timestamp=datetime.now(timezone.utc),
                channel_id=channel_id
            )
    
    def _determine_category(self, error: Exception, context: Optional[Dict]) -> ErrorCategory:
        """Определяет категорию ошибки"""
        error_message = str(error).lower()
        error_type = type(error).__name__
        
        # Сетевые ошибки
        if any(keyword in error_message for keyword in ["connection", "network", "timeout", "unreachable"]):
            return ErrorCategory.NETWORK
        
        # Ошибки аутентификации
        if any(keyword in error_message for keyword in ["auth", "token", "credential", "unauthorized"]):
            return ErrorCategory.AUTHENTICATION
        
        # Rate limiting
        if any(keyword in error_message for keyword in ["rate limit", "too many requests", "quota"]):
            return ErrorCategory.RATE_LIMIT
        
        # Сервис недоступен
        if any(keyword in error_message for keyword in ["service unavailable", "503", "502", "500"]):
            return ErrorCategory.SERVICE_UNAVAILABLE
        
        # Timeout
        if "timeout" in error_message or "TimeoutError" in error_type:
            return ErrorCategory.TIMEOUT
        
        # Валидация
        if any(keyword in error_message for keyword in ["validation", "invalid", "bad request", "400"]):
            return ErrorCategory.VALIDATION
        
        # По умолчанию - внутренняя ошибка
        return ErrorCategory.INTERNAL
    
    def _determine_severity(self, error: Exception, category: ErrorCategory, 
                           context: Optional[Dict]) -> ErrorSeverity:
        """Определяет серьезность ошибки"""
        # Критические ошибки
        if category in [ErrorCategory.AUTHENTICATION, ErrorCategory.SERVICE_UNAVAILABLE]:
            return ErrorSeverity.CRITICAL
        
        # Высокие ошибки
        if category in [ErrorCategory.NETWORK, ErrorCategory.TIMEOUT]:
            return ErrorSeverity.HIGH
        
        # Средние ошибки
        if category in [ErrorCategory.RATE_LIMIT, ErrorCategory.INTERNAL]:
            return ErrorSeverity.MEDIUM
        
        # Низкие ошибки
        if category == ErrorCategory.VALIDATION:
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM
    
    def _log_error(self, error_info: ErrorInfo):
        """Логирует ошибку"""
        try:
            log_message = f"🚨 {error_info.severity.value.upper()} ERROR [{error_info.category.value}]: {error_info.message}"
            
            if error_info.channel_id:
                log_message += f" (Channel: {error_info.channel_id})"
            
            if error_info.severity == ErrorSeverity.CRITICAL:
                logger.error(log_message, extra={"error_info": error_info})
            elif error_info.severity == ErrorSeverity.HIGH:
                logger.error(log_message)
            elif error_info.severity == ErrorSeverity.MEDIUM:
                logger.warning(log_message)
            else:
                logger.info(log_message)
                
        except Exception as e:
            logger.error(f"❌ Error logging failed: {e}")
    
    def _update_error_stats(self, error_info: ErrorInfo):
        """Обновляет статистику ошибок"""
        try:
            self.error_stats["total_errors"] += 1
            self.error_stats["errors_by_category"][error_info.category.value] += 1
            self.error_stats["errors_by_severity"][error_info.severity.value] += 1
        except Exception as e:
            logger.error(f"❌ Update error stats failed: {e}")
    
    async def _retry_with_backoff(self, error_info: ErrorInfo, strategy: FallbackStrategy) -> bool:
        """Пытается повторить операцию с экспоненциальным backoff"""
        try:
            for attempt in range(strategy.max_retries):
                error_info.retry_count += 1
                
                # Экспоненциальный backoff
                delay = strategy.retry_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                
                logger.info(f"🔄 Retry attempt {attempt + 1}/{strategy.max_retries} for {error_info.error_id}")
                
                # В реальной реализации здесь будет повторный вызов операции
                # success = await self._retry_operation(error_info)
                # if success:
                #     logger.info(f"✅ Retry successful for {error_info.error_id}")
                #     return True
            
            logger.warning(f"⚠️ All retry attempts failed for {error_info.error_id}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Retry with backoff failed: {e}")
            return False
    
    async def _execute_fallback(self, error_info: ErrorInfo, strategy: FallbackStrategy):
        """Выполняет fallback действие"""
        try:
            if strategy.fallback_action:
                logger.info(f"🔄 Executing fallback for {error_info.error_id}")
                await strategy.fallback_action(error_info)
                logger.info(f"✅ Fallback executed for {error_info.error_id}")
            else:
                logger.warning(f"⚠️ No fallback action defined for {error_info.category.value}")
                
        except Exception as e:
            logger.error(f"❌ Fallback execution failed: {e}")
    
    def get_channel_errors(self, channel_id: str) -> List[ErrorInfo]:
        """Возвращает ошибки для канала"""
        return self.channel_errors.get(channel_id, [])
    
    def get_error_stats(self) -> Dict:
        """Возвращает статистику ошибок"""
        return self.error_stats.copy()
    
    def clear_channel_errors(self, channel_id: str):
        """Очищает ошибки канала"""
        if channel_id in self.channel_errors:
            del self.channel_errors[channel_id]
            logger.debug(f"🧹 Cleared errors for {channel_id}")
    
    def get_health_status(self) -> Dict:
        """Возвращает статус здоровья системы"""
        try:
            total_errors = self.error_stats["total_requests"]
            critical_errors = self.error_stats["errors_by_severity"][ErrorSeverity.CRITICAL.value]
            high_errors = self.error_stats["errors_by_severity"][ErrorSeverity.HIGH.value]
            
            # Определяем статус здоровья
            if critical_errors > 0:
                health_status = "critical"
            elif high_errors > 5:
                health_status = "degraded"
            elif high_errors > 0:
                health_status = "warning"
            else:
                health_status = "healthy"
            
            return {
                "status": health_status,
                "total_errors": total_errors,
                "critical_errors": critical_errors,
                "high_errors": high_errors,
                "error_rate": (total_errors / max(total_errors, 1)) * 100,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Get health status failed: {e}")
            return {"status": "unknown", "error": str(e)}

# Глобальный экземпляр для использования в других модулях
error_handler = ErrorHandler()

def get_error_handler() -> ErrorHandler:
    """Возвращает глобальный экземпляр ErrorHandler"""
    return error_handler

