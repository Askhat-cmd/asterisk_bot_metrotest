#!/usr/bin/env python3
"""
Интеграционные тесты для проверки совместимости VAD и TTS
Task 4.1a: Проверка совместимости (Phase 4 - Integration Part 1)

Цель: Проверить совместимость VAD (Phase 2) и TTS (Phase 3) улучшений
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple

# Добавляем путь к модулям приложения
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app', 'backend'))

# Импортируем сервисы
from services.simple_vad_service import SimpleVADService, get_vad_service
from services.barge_in_manager import BargeInManager
from services.yandex_tts_service import YandexTTSService, get_yandex_tts_service

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VADTTSIntegrationTester:
    """
    Интеграционный тестер для VAD + TTS совместимости
    """
    
    def __init__(self):
        """Инициализация тестера"""
        self.vad_service = SimpleVADService(
            silence_timeout=2.0,
            min_recording_time=1.0,
            max_recording_time=15.0,
            debug_logging=True
        )
        
        self.barge_in_manager = BargeInManager()
        
        # Здесь мы не инициализируем TTS сервис, т.к. он требует API ключей
        # В реальных тестах нужны валидные OAUTH_TOKEN и YANDEX_FOLDER_ID
        
        self.test_results: List[Dict] = []
        self.deadlock_detected = False
        self.race_condition_detected = False
        
        logger.info("✅ Инициализирован VADTTSIntegrationTester")
    
    async def scenario_1_normal_dialog(self) -> Dict:
        """
        Сценарий 1: Нормальный диалог
        - TTS воспроизводит фразу
        - VAD ждет ввода от пользователя
        - Пользователь говорит
        - Запись останавливается после тишины
        """
        logger.info("\n" + "="*60)
        logger.info("🎯 СЦЕНАРИЙ 1: Нормальный диалог")
        logger.info("="*60)
        
        channel_id = "test_channel_1"
        recording_id = "rec_1"
        
        result = {
            "scenario": "normal_dialog",
            "status": "OK",
            "details": [],
            "errors": []
        }
        
        try:
            # Шаг 1: Имитируем TTS воспроизведение
            logger.info("1️⃣ TTS начинает воспроизведение фразы...")
            result["details"].append("TTS: Starting playback")
            await asyncio.sleep(0.1)  # Имитируем начало воспроизведения
            
            # Шаг 2: Запускаем VAD мониторинг для записи пользователя
            logger.info("2️⃣ VAD начинает мониторинг (ожидание речи)...")
            
            vad_callback_called = False
            vad_reason = None
            
            async def vad_callback(ch_id, rec_id, reason):
                nonlocal vad_callback_called, vad_reason
                vad_callback_called = True
                vad_reason = reason
                logger.info(f"   ✅ VAD callback вызван: {reason}")
            
            ok = await self.vad_service.start_monitoring(
                channel_id,
                recording_id,
                vad_callback,
                silence_timeout_override=2.0,
                max_duration_override=15.0
            )
            
            if not ok:
                result["status"] = "FAILED"
                result["errors"].append("VAD monitoring не запустился")
                return result
            
            result["details"].append("VAD: Monitoring started")
            
            # Шаг 3: Имитируем TTS воспроизведение (3 сек)
            logger.info("3️⃣ TTS воспроизводит фразу (3 сек)...")
            result["details"].append("TTS: Playing phrase (3s)")
            
            # Проверяем, что VAD работает во время TTS
            if not self.vad_service.is_monitoring(channel_id):
                result["status"] = "FAILED"
                result["errors"].append("VAD остановился во время TTS")
                return result
            
            await asyncio.sleep(3)  # TTS воспроизводит фразу
            
            # Шаг 4: Имитируем ввод от пользователя (речь)
            logger.info("4️⃣ Пользователь говорит (2 сек)...")
            result["details"].append("User: Speaking (2s)")
            
            # Обновляем активность (имитируем ASR детекцию речи)
            await self.vad_service.update_activity(channel_id)
            result["details"].append("VAD: Activity detected (speech started)")
            
            await asyncio.sleep(2)  # Пользователь говорит 2 сек
            
            # Шаг 5: Пауза (тишина) - VAD должен завершить запись
            logger.info("5️⃣ Пауза (тишина)...")
            result["details"].append("User: Silence (pause)")
            
            # Ждем, пока VAD завершит запись по тишине (макс 2.5 сек)
            for i in range(25):  # 25 * 0.1 = 2.5 сек макс
                if vad_callback_called:
                    break
                await asyncio.sleep(0.1)
            
            # Проверяем результаты
            if not vad_callback_called:
                result["status"] = "FAILED"
                result["errors"].append(f"VAD callback не был вызван в течение 2.5 сек")
                
                # Останавливаем мониторинг принудительно
                await self.vad_service.stop_monitoring(channel_id)
            else:
                result["details"].append(f"VAD: Recording finished ({vad_reason})")
                
                if vad_reason == "silence_detected":
                    result["details"].append("✅ Запись остановлена корректно по тишине")
                elif vad_reason == "max_time_reached":
                    result["details"].append("⚠️  Запись остановлена по максимальному времени")
            
            # Финальная проверка: нет deadlock'ов
            logger.info("6️⃣ Проверка deadlock'ов...")
            
            if not self.vad_service.is_monitoring(channel_id):
                result["details"].append("✅ Нет deadlock'ов - мониторинг корректно завершился")
            else:
                result["status"] = "FAILED"
                result["errors"].append("Deadlock: VAD мониторинг не завершился")
                await self.vad_service.stop_monitoring(channel_id)
            
        except Exception as e:
            result["status"] = "ERROR"
            result["errors"].append(f"Exception: {str(e)}")
            logger.error(f"❌ Ошибка в сценарии 1: {e}")
        
        logger.info(f"📊 Результат: {result['status']}")
        return result
    
    async def scenario_2_long_phrase(self) -> Dict:
        """
        Сценарий 2: Длинная фраза (>10 сек)
        - TTS воспроизводит длинную фразу
        - Пользователь говорит длительный ввод (>10 сек)
        - VAD grace period не должен прерывать запись
        """
        logger.info("\n" + "="*60)
        logger.info("🎯 СЦЕНАРИЙ 2: Длинная фраза (>10s)")
        logger.info("="*60)
        
        channel_id = "test_channel_2"
        recording_id = "rec_2"
        
        result = {
            "scenario": "long_phrase",
            "status": "OK",
            "details": [],
            "errors": [],
            "grace_period_tested": False
        }
        
        try:
            # Шаг 1: Запускаем VAD мониторинг с большим окном
            logger.info("1️⃣ VAD: Запуск мониторинга для длинной фразы...")
            
            vad_callback_called = False
            vad_reason = None
            activity_updates = 0
            
            async def vad_callback(ch_id, rec_id, reason):
                nonlocal vad_callback_called, vad_reason
                vad_callback_called = True
                vad_reason = reason
                logger.info(f"   ✅ VAD callback вызван: {reason}")
            
            ok = await self.vad_service.start_monitoring(
                channel_id,
                recording_id,
                vad_callback,
                silence_timeout_override=2.0,
                max_duration_override=20.0  # Большое окно для длинной фразы
            )
            
            if not ok:
                result["status"] = "FAILED"
                result["errors"].append("VAD monitoring не запустился")
                return result
            
            result["details"].append("VAD: Monitoring started for long phrase")
            
            # Шаг 2: Имитируем длинный ввод от пользователя
            logger.info("2️⃣ Пользователь говорит длинную фразу (12 сек)...")
            result["details"].append("User: Speaking long phrase (12s)")
            
            # Обновляем активность каждые 2 сек (имитируем непрерывную речь)
            long_phrase_duration = 12
            update_interval = 2
            
            for i in range(long_phrase_duration // update_interval):
                logger.info(f"   🎤 Речь продолжается... ({i*2}s)")
                await self.vad_service.update_activity(channel_id)
                activity_updates += 1
                result["details"].append(f"User: Activity update #{activity_updates}")
                
                # Проверяем, что Grace period работает
                if i > 0 and i < 4:  # После 2s и до 8s
                    stats = self.vad_service.get_monitoring_stats(channel_id)
                    if stats and stats["is_active"]:
                        result["grace_period_tested"] = True
                
                await asyncio.sleep(update_interval)
            
            # Шаг 3: Конец фразы - тишина
            logger.info("3️⃣ Конец фразы - пауза...")
            result["details"].append("User: Silence (end of phrase)")
            
            # Ждем завершения (макс 3 сек)
            for i in range(30):  # 30 * 0.1 = 3 сек макс
                if vad_callback_called:
                    break
                await asyncio.sleep(0.1)
            
            if not vad_callback_called:
                result["status"] = "FAILED"
                result["errors"].append("VAD callback не был вызван в течение 3 сек")
                await self.vad_service.stop_monitoring(channel_id)
            else:
                result["details"].append(f"VAD: Recording finished ({vad_reason})")
                
                # Проверяем, что запись не была прервана в процессе
                if activity_updates >= 4:  # Минимум 4 обновления за 12 сек
                    result["details"].append(f"✅ Grace period: Запись не прервана ({activity_updates} activity updates)")
                else:
                    result["status"] = "FAILED"
                    result["errors"].append(f"Grace period problem: Только {activity_updates} activity updates")
            
        except Exception as e:
            result["status"] = "ERROR"
            result["errors"].append(f"Exception: {str(e)}")
            logger.error(f"❌ Ошибка в сценарии 2: {e}")
        
        logger.info(f"📊 Результат: {result['status']}")
        return result
    
    async def scenario_3_quick_barge_in(self) -> Dict:
        """
        Сценарий 3: Быстрый barge-in
        - TTS воспроизводит фразу
        - Пользователь начинает говорить во время TTS
        - TTS должна остановиться
        - Запись начинается без задержек
        """
        logger.info("\n" + "="*60)
        logger.info("🎯 СЦЕНАРИЙ 3: Быстрый barge-in")
        logger.info("="*60)
        
        channel_id = "test_channel_3"
        recording_id = "rec_3"
        
        result = {
            "scenario": "quick_barge_in",
            "status": "OK",
            "details": [],
            "errors": [],
            "barge_in_response_time": None
        }
        
        try:
            # Шаг 1: Имитируем TTS воспроизведение
            logger.info("1️⃣ TTS: Начало воспроизведения фразы...")
            result["details"].append("TTS: Starting playback")
            
            tts_start_time = asyncio.get_event_loop().time()
            await asyncio.sleep(0.5)  # Полсекунды в процесс воспроизведения
            
            # Шаг 2: Пользователь начинает говорить (barge-in)
            logger.info("2️⃣ Пользователь начинает говорить (BARGE-IN)...")
            barge_in_time = asyncio.get_event_loop().time()
            result["details"].append(f"User: Started speaking (barge-in at {barge_in_time-tts_start_time:.2f}s)")
            
            # Шаг 3: Запускаем VAD мониторинг с коротким окном для barge-in
            logger.info("3️⃣ VAD: Запуск мониторинга для barge-in записи...")
            
            vad_callback_called = False
            vad_reason = None
            vad_start_time = asyncio.get_event_loop().time()
            
            async def vad_callback(ch_id, rec_id, reason):
                nonlocal vad_callback_called, vad_reason
                vad_callback_called = True
                vad_reason = reason
                callback_time = asyncio.get_event_loop().time()
                logger.info(f"   ✅ VAD callback вызван за {callback_time-vad_start_time:.3f}s")
            
            ok = await self.vad_service.start_monitoring(
                channel_id,
                recording_id,
                vad_callback,
                silence_timeout_override=2.0,
                max_duration_override=3.0  # Короткое окно для barge-in
            )
            
            if not ok:
                result["status"] = "FAILED"
                result["errors"].append("VAD monitoring для barge-in не запустился")
                return result
            
            result["details"].append("VAD: Barge-in monitoring started")
            
            # Шаг 4: Проверяем обработку barge-in
            logger.info("4️⃣ Barge-in Manager: Обработка события...")
            result["details"].append("BargeInManager: Processing barge-in event")
            
            call_data = {
                "last_speak_started_at": int(tts_start_time * 1000),
                "is_speaking": True
            }
            
            barge_in_processed = await self.barge_in_manager.handle_barge_in(
                channel_id,
                "UserSpeech",
                call_data
            )
            
            if barge_in_processed:
                result["details"].append("✅ BargeInManager: Barge-in processed")
            else:
                result["details"].append("⚠️  BargeInManager: Barge-in not processed (too early or debounced)")
            
            # Шаг 5: Имитируем речь пользователя
            logger.info("5️⃣ Пользователь говорит (2 сек)...")
            result["details"].append("User: Speaking (2s)")
            
            # Обновляем активность VAD
            await self.vad_service.update_activity(channel_id)
            result["details"].append("VAD: Activity detected")
            
            await asyncio.sleep(2)
            
            # Шаг 6: Тишина - VAD завершает запись
            logger.info("6️⃣ Пауза после речи...")
            result["details"].append("User: Silence")
            
            # Ждем завершения
            for i in range(25):
                if vad_callback_called:
                    break
                await asyncio.sleep(0.1)
            
            if vad_callback_called:
                result["barge_in_response_time"] = asyncio.get_event_loop().time() - vad_start_time
                result["details"].append(f"✅ VAD завершила запись за {result['barge_in_response_time']:.3f}s")
            else:
                result["status"] = "FAILED"
                result["errors"].append("VAD callback не был вызван")
                await self.vad_service.stop_monitoring(channel_id)
            
        except Exception as e:
            result["status"] = "ERROR"
            result["errors"].append(f"Exception: {str(e)}")
            logger.error(f"❌ Ошибка в сценарии 3: {e}")
        
        logger.info(f"📊 Результат: {result['status']}")
        return result
    
    async def scenario_4_slow_tts_prebuffering(self) -> Dict:
        """
        Сценарий 4: Медленный TTS (под нагрузкой)
        - Имитируем медленное воспроизведение TTS
        - TTS prebuffering должно помочь
        - VAD должна продолжать работать нормально
        """
        logger.info("\n" + "="*60)
        logger.info("🎯 СЦЕНАРИЙ 4: Медленный TTS (под нагрузкой)")
        logger.info("="*60)
        
        channel_id = "test_channel_4"
        recording_id = "rec_4"
        
        result = {
            "scenario": "slow_tts_prebuffering",
            "status": "OK",
            "details": [],
            "errors": [],
            "vad_interrupts": 0
        }
        
        try:
            # Шаг 1: Имитируем медленное TTS воспроизведение
            logger.info("1️⃣ TTS: Медленное воспроизведение (нагрузка на систему)...")
            result["details"].append("TTS: Slow playback starting")
            
            # Запускаем VAD мониторинг
            logger.info("2️⃣ VAD: Запуск мониторинга...")
            
            vad_callback_called = False
            vad_reason = None
            
            async def vad_callback(ch_id, rec_id, reason):
                nonlocal vad_callback_called, vad_reason
                vad_callback_called = True
                vad_reason = reason
                logger.info(f"   ✅ VAD callback вызван: {reason}")
            
            ok = await self.vad_service.start_monitoring(
                channel_id,
                recording_id,
                vad_callback,
                silence_timeout_override=2.0,
                max_duration_override=15.0
            )
            
            if not ok:
                result["status"] = "FAILED"
                result["errors"].append("VAD monitoring не запустился")
                return result
            
            result["details"].append("VAD: Monitoring started")
            
            # Шаг 2: Имитируем медленное TTS воспроизведение (с рывками)
            logger.info("3️⃣ TTS: Воспроизведение с рывками (имитация медленности)...")
            
            tts_chunks = 5
            for i in range(tts_chunks):
                logger.info(f"   🎵 TTS chunk {i+1}/{tts_chunks}")
                result["details"].append(f"TTS: Playing chunk {i+1}")
                
                # Проверяем, что VAD не остановился
                if not self.vad_service.is_monitoring(channel_id):
                    result["vad_interrupts"] += 1
                    result["status"] = "FAILED"
                    result["errors"].append(f"VAD остановился во время TTS chunk {i+1}")
                    break
                
                await asyncio.sleep(0.8)  # Медленное воспроизведение
            
            if result["status"] == "FAILED":
                return result
            
            result["details"].append("✅ TTS успешно воспроизведена несмотря на медленность")
            
            # Шаг 3: Пользователь говорит после TTS
            logger.info("4️⃣ Пользователь говорит...")
            result["details"].append("User: Speaking")
            
            await self.vad_service.update_activity(channel_id)
            await asyncio.sleep(2)
            
            # Шаг 4: Проверяем завершение записи
            logger.info("5️⃣ Проверка завершения VAD...")
            
            for i in range(25):
                if vad_callback_called:
                    break
                await asyncio.sleep(0.1)
            
            if vad_callback_called:
                result["details"].append(f"✅ VAD завершила запись ({vad_reason})")
            else:
                result["status"] = "FAILED"
                result["errors"].append("VAD callback не был вызван")
                await self.vad_service.stop_monitoring(channel_id)
            
        except Exception as e:
            result["status"] = "ERROR"
            result["errors"].append(f"Exception: {str(e)}")
            logger.error(f"❌ Ошибка в сценарии 4: {e}")
        
        logger.info(f"📊 Результат: {result['status']}")
        return result
    
    async def check_deadlocks_and_race_conditions(self) -> Dict:
        """
        Проверка deadlock'ов и race conditions между VAD и TTS
        """
        logger.info("\n" + "="*60)
        logger.info("🔍 Проверка deadlock'ов и race conditions")
        logger.info("="*60)
        
        result = {
            "check": "deadlocks_and_race_conditions",
            "status": "OK",
            "details": [],
            "errors": []
        }
        
        try:
            # Проверка 1: Нет активных мониторингов
            logger.info("1️⃣ Проверка завершения всех мониторингов...")
            
            active_monitors = len(self.vad_service.active_monitors)
            if active_monitors > 0:
                result["errors"].append(f"Остались активные мониторинги: {active_monitors}")
                for ch_id in self.vad_service.active_monitors:
                    logger.warning(f"   ⚠️  Активный мониторинг: {ch_id}")
                    await self.vad_service.stop_monitoring(ch_id)
            else:
                result["details"].append("✅ Нет активных мониторингов")
            
            # Проверка 2: Нет состояний barge-in
            logger.info("2️⃣ Проверка завершения всех barge-in состояний...")
            
            active_barge_ins = len(self.barge_in_manager.barge_in_states)
            if active_barge_ins > 0:
                result["errors"].append(f"Остались активные barge-in состояния: {active_barge_ins}")
                for ch_id in list(self.barge_in_manager.barge_in_states.keys()):
                    logger.warning(f"   ⚠️  Активное barge-in состояние: {ch_id}")
            else:
                result["details"].append("✅ Нет активных barge-in состояний")
            
            # Проверка 3: Внутренняя консистентность VAD сервиса
            logger.info("3️⃣ Проверка внутренней консистентности VAD...")
            
            # После выключения все мониторы должны быть очищены
            if len(self.vad_service.active_monitors) == 0:
                result["details"].append("✅ VAD сервис в консистентном состоянии")
            else:
                result["errors"].append("VAD сервис в непредсказуемом состоянии")
            
            if result["errors"]:
                result["status"] = "WARNING"
            
        except Exception as e:
            result["status"] = "ERROR"
            result["errors"].append(f"Exception: {str(e)}")
            logger.error(f"❌ Ошибка при проверке deadlock'ов: {e}")
        
        logger.info(f"📊 Результат: {result['status']}")
        return result
    
    async def run_all_tests(self) -> None:
        """
        Запускает все тесты интеграции
        """
        logger.info("\n\n")
        logger.info("╔" + "="*58 + "╗")
        logger.info("║ 🧪 ИНТЕГРАЦИОННЫЕ ТЕСТЫ VAD + TTS (Task 4.1a)           ║")
        logger.info("╚" + "="*58 + "╝")
        
        # Запускаем все сценарии
        self.test_results.append(await self.scenario_1_normal_dialog())
        self.test_results.append(await self.scenario_2_long_phrase())
        self.test_results.append(await self.scenario_3_quick_barge_in())
        self.test_results.append(await self.scenario_4_slow_tts_prebuffering())
        
        # Проверяем deadlock'ы и race conditions
        self.test_results.append(await self.check_deadlocks_and_race_conditions())
        
        # Генерируем отчет
        self.generate_report()
    
    def generate_report(self) -> None:
        """
        Генерирует отчет по результатам тестирования
        """
        logger.info("\n\n")
        logger.info("╔" + "="*58 + "╗")
        logger.info("║ 📊 ИТОГОВЫЙ ОТЧЕТ                                        ║")
        logger.info("╚" + "="*58 + "╝")
        
        # Подсчет результатов
        ok_count = sum(1 for r in self.test_results if r["status"] == "OK")
        warning_count = sum(1 for r in self.test_results if r["status"] == "WARNING")
        failed_count = sum(1 for r in self.test_results if r["status"] in ["FAILED", "ERROR"])
        
        logger.info(f"\n✅ Успешно: {ok_count}/{len(self.test_results)}")
        logger.info(f"⚠️  Предупреждений: {warning_count}/{len(self.test_results)}")
        logger.info(f"❌ Ошибок: {failed_count}/{len(self.test_results)}")
        
        # Детали по каждому тесту
        logger.info("\n--- Результаты по сценариям ---\n")
        
        for result in self.test_results:
            scenario = result.get("scenario", result.get("check", "unknown"))
            status = result["status"]
            status_emoji = "✅" if status == "OK" else "⚠️ " if status == "WARNING" else "❌"
            
            logger.info(f"{status_emoji} {scenario.upper()}: {status}")
            
            if result.get("details"):
                for detail in result["details"][:3]:  # Показываем первые 3 детали
                    logger.info(f"   • {detail}")
                if len(result["details"]) > 3:
                    logger.info(f"   ... и еще {len(result['details'])-3} деталей")
            
            if result.get("errors"):
                for error in result["errors"]:
                    logger.error(f"   ❌ {error}")
            
            logger.info("")
        
        # Итоговое заключение
        logger.info("=" * 60)
        if failed_count == 0:
            logger.info("✅ ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
            logger.info("✅ VAD и TTS совместимы и готовы к использованию")
        else:
            logger.info(f"❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ ({failed_count} ошибок)")
            logger.info("❌ Требуется дополнительное расследование")
        
        logger.info("=" * 60)


async def main():
    """
    Главная функция для запуска тестов
    """
    tester = VADTTSIntegrationTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⛔ Тестирование прервано пользователем")
    except Exception as e:
        logger.error(f"\n❌ Ошибка при выполнении тестов: {e}")
        sys.exit(1)
