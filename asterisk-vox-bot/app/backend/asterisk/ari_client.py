import aiohttp
import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AsteriskARIClient:
    def __init__(self, host="localhost", port=8088, username="asterisk", password="asterisk123"):
        self.base_url = f"http://{host}:{port}/ari"
        self.auth = aiohttp.BasicAuth(username, password)
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(auth=self.auth)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def answer_channel(self, channel_id):
        """Отвечает на канал для корректной работы ARI playback"""
        try:
            url = f"{self.base_url}/channels/{channel_id}/answer"
            async with self.session.post(url) as response:
                if response.status == 204:
                    logger.info(f"✅ Канал {channel_id} успешно отвечен")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка ответа на канал: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"❌ Ошибка ответа на канал {channel_id}: {e}")
            return False
    
    async def play_sound(self, channel_id, sound_id, lang="ru"):
        """
        Проигрывает звуковой файл на канале.
        
        Args:
            channel_id: ID канала
            sound_id: Имя звукового файла (без расширения)
            lang: Язык (папка в sounds/)
        """
        # ✅ ИСПРАВЛЕНО: НЕ проверяем channel_exists() здесь!
        # Причина: ARI возвращает False когда канал занят (VAD recording)
        # Пусть ARI сам вернет ошибку, если канал действительно не существует
            
        try:
            url = f"{self.base_url}/channels/{channel_id}/play"
            # ИСПРАВЛЕНО: Убираем подпапку ru/ - Asterisk сам найдет файл по имени
            media = f"sound:{sound_id}"
            data = {"media": media}
            
            logger.info(f"Проигрываем звук: {media} на канале {channel_id}")
            
            async with self.session.post(url, json=data) as response:
                # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ: Логируем полный ответ ARI для диагностики
                response_text = await response.text()
                logger.info(f"🔍 ARI Response: status={response.status}, body={response_text}")
                
                # ARI может возвращать 200 OK или 201 Created/202 Accepted при успешном создании playback
                if response.status in (200, 201, 202):
                    try:
                        result = json.loads(response_text)
                        playback_id = result.get('id')
                        logger.info(f"✅ Проигрывание принято ARI (status={response.status}), playback_id={playback_id}")
                        return playback_id or True
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось распарсить JSON ответ: {e}, raw: {response_text}")
                        return True  # Возвращаем True если статус OK
                else:
                    logger.error(f"❌ Ошибка проигрывания: {response.status} - {response_text}")
                    logger.warning(
                        "ARI play_sound: status=%s body=%s",
                        response.status,
                        await response.text()
                    )
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка при проигрывании звука: {e}")
            return None

    async def start_recording(self, channel_id, filename, max_duration=15):
        """
        Запускает запись с канала.
        
        Args:
            channel_id: ID канала
            filename: Имя файла для записи (без расширения)
            max_duration: Максимальная длительность в секундах
        """
        # 🎯 ЭТАП 2.3: Проверка существования канала перед записью
        if not await self.channel_exists(channel_id):
            logger.warning(f"⚠️ Канал {channel_id} не существует, пропускаем запись")
            return False
            
        try:
            url = f"{self.base_url}/channels/{channel_id}/record"
            data = {
                "name": filename,
                "format": "wav",
                "maxDurationSeconds": max_duration,
                "beep": False,
                "terminateOn": "#",  # Завершить запись по нажатию #
                "ifExists": "overwrite"
            }
            
            logger.info(f"Запускаем запись: {filename} на канале {channel_id}")
            
            async with self.session.post(url, json=data) as response:
                # ARI может возвращать 200 OK или 201 Created при успешном создании записи
                if response.status in (200, 201):
                    result = await response.json()
                    recording_id = result.get('name')
                    logger.info(f"✅ Запись запущена: {recording_id}")
                    return recording_id
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка запуска записи: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске записи: {e}")
            return None

    async def stop_recording(self, recording_id):
        """Останавливает запись."""
        try:
            url = f"{self.base_url}/recordings/live/{recording_id}/stop"
            async with self.session.post(url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"❌ Ошибка остановки записи: {e}")
            return False

    async def hold_channel(self, channel_id):
        """
        КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Убираем проверку существования
        Asterisk может показывать канал как "несуществующий" но hold все равно работает
        """
        try:
            url = f"{self.base_url}/channels/{channel_id}/hold"
            async with self.session.post(url) as response:
                if response.status in (200, 201, 204):
                    logger.info(f"🔒 Канал {channel_id} поставлен на hold")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"⚠️ Hold failed {channel_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"❌ Hold error {channel_id}: {e}")
            return False

    async def unhold_channel(self, channel_id):
        """КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Убираем проверку существования"""
        try:
            url = f"{self.base_url}/channels/{channel_id}/unhold"
            async with self.session.delete(url) as response:
                if response.status in (200, 201, 204):
                    logger.info(f"🔓 Канал {channel_id} снят с hold")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"⚠️ Unhold failed {channel_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"❌ Unhold error {channel_id}: {e}")
            return False

    async def hangup_channel(self, channel_id):
        """Завершает звонок."""
        # 🎯 ЭТАП 2.3: Проверка существования канала перед завершением
        if not await self.channel_exists(channel_id):
            logger.warning(f"⚠️ Канал {channel_id} не существует, пропускаем завершение")
            return False
            
        try:
            url = f"{self.base_url}/channels/{channel_id}"
            async with self.session.delete(url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"❌ Ошибка завершения звонка: {e}")
            return False
    
    async def get_channels(self):
        """Получает список всех активных каналов."""
        try:
            url = f"{self.base_url}/channels"
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"⚠️ Не удалось получить список каналов: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка каналов: {e}")
            return []
    
    async def channel_exists(self, channel_id):
        """Проверяет, существует ли канал в Asterisk."""
        try:
            url = f"{self.base_url}/channels/{channel_id}"
            async with self.session.get(url) as response:
                return response.status == 200
        except Exception as e:
            logger.debug(f"Канал {channel_id} не найден: {e}")
            return False
    
    async def get_channel_info(self, channel_id):
        """Получает информацию о канале."""
        try:
            url = f"{self.base_url}/channels/{channel_id}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
        except Exception as e:
            logger.debug(f"Ошибка получения информации о канале {channel_id}: {e}")
            return None
    
    async def hold_channel(self, channel_id):
        """Принудительно удерживает канал для обработки"""
        try:
            url = f"{self.base_url}/channels/{channel_id}/hold"
            async with self.session.post(url) as response:
                if response.status == 204:
                    logger.info(f"🔒 Канал {channel_id} успешно удержан")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"⚠️ Не удалось удержать канал {channel_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.warning(f"⚠️ Ошибка удержания канала {channel_id}: {e}")
            return False
    
    async def unhold_channel(self, channel_id):
        """Снимает удержание канала"""
        try:
            url = f"{self.base_url}/channels/{channel_id}/unhold"
            async with self.session.post(url) as response:
                if response.status == 204:
                    logger.info(f"🔓 Канал {channel_id} успешно разблокирован")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"⚠️ Не удалось разблокировать канал {channel_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.warning(f"⚠️ Ошибка разблокировки канала {channel_id}: {e}")
            return False

if __name__ == "__main__":
    async def test():
        async with AsteriskARIClient() as ari:
            url = f"{ari.base_url}/asterisk/info"
            async with ari.session.get(url) as response:
                if response.status == 200:
                    print("ARI connection successful!")
                else:
                    print(f"ARI connection failed: {response.status}")
    
    asyncio.run(test())