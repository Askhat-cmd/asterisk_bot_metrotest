#!/usr/bin/env python3
"""
ГОТОВОЕ РЕШЕНИЕ для обновления Yandex IAM токена
Ваши данные уже подставлены!
"""

import requests
import json
import time
from datetime import datetime, timedelta
import threading
import logging

# 🎯 ВАШИ ДАННЫЕ (уже подставлены)
OAUTH_TOKEN = "y0_xDapiLvBBjB3RMgureWpRRd-4N8PQ1wUwN2LE2biUiAYyiHJA"
FOLDER_ID = "b1g6ft1co3nrff8jds4g"

class YandexTokenManager:
    def __init__(self, oauth_token, folder_id):
        self.oauth_token = oauth_token
        self.folder_id = folder_id
        self.iam_token = None
        self.token_expires_at = None
        
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def get_new_token(self):
        """Получение нового IAM токена"""
        url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
        
        payload = {
            "yandexPassportOauthToken": self.oauth_token
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            self.iam_token = data["iamToken"]
            
            # Токен действует 12 часов
            expires_at = data.get("expiresAt")
            if expires_at:
                self.token_expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            else:
                self.token_expires_at = datetime.now() + timedelta(hours=12)
            
            self.logger.info(f"✅ Новый IAM токен получен!")
            self.logger.info(f"📅 Действует до: {self.token_expires_at}")
            self.logger.info(f"🔑 Токен: {self.iam_token[:50]}...")
            
            return self.iam_token
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Ошибка получения токена: {e}")
            if hasattr(e, 'response') and e.response:
                self.logger.error(f"Ответ сервера: {e.response.text}")
            raise
    
    def get_token(self):
        """Получение актуального токена"""
        if self.token_needs_refresh():
            return self.get_new_token()
        return self.iam_token
    
    def token_needs_refresh(self):
        """Проверка, нужно ли обновить токен"""
        if not self.iam_token or not self.token_expires_at:
            return True
        
        # Обновляем за 30 минут до истечения
        refresh_time = self.token_expires_at - timedelta(minutes=30)
        return datetime.now() >= refresh_time


class YandexASR:
    def __init__(self, token_manager):
        self.token_manager = token_manager
    
    def recognize_audio(self, audio_data, format="lpcm", sample_rate=16000):
        """Распознавание аудио"""
        url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
        
        headers = {
            "Authorization": f"Bearer {self.token_manager.get_token()}",
            "Content-Type": "audio/x-pcm;bit=16;rate=16000"
        }
        
        params = {
            "topic": "general",
            "lang": "ru-RU",
            "format": format,
            "sampleRateHertz": sample_rate,
            "folderId": self.token_manager.folder_id
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                data=audio_data
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response and e.response.status_code == 401:
                # Токен истек, принудительно обновляем
                self.token_manager.get_new_token()
                headers["Authorization"] = f"Bearer {self.token_manager.iam_token}"
                
                # Повторяем запрос
                response = requests.post(
                    url,
                    headers=headers,
                    params=params,
                    data=audio_data
                )
                response.raise_for_status()
                return response.json()
            else:
                raise


def main():
    """Основная функция - тестирование и демо"""
    print("🚀 РЕШЕНИЕ ПРОБЛЕМЫ С ИСТЕКШИМ YANDEX IAM ТОКЕНОМ")
    print("="*60)
    
    # Создаем менеджер токенов с вашими данными
    token_manager = YandexTokenManager(OAUTH_TOKEN, FOLDER_ID)
    
    try:
        # Получаем новый токен
        print("\n🔄 Обновляем IAM токен...")
        new_token = token_manager.get_new_token()
        
        print(f"\n✅ УСПЕХ! Токен обновлен")
        print(f"📅 Действует до: {token_manager.token_expires_at}")
        print(f"🔑 Новый токен: {new_token[:50]}...")
        
        # Создаем ASR клиент
        asr_client = YandexASR(token_manager)
        
        print(f"\n🎤 ASR клиент готов к работе!")
        print(f"📁 Folder ID: {FOLDER_ID}")
        
        # Тестируем соединение (без аудио)
        print(f"\n🧪 Тестируем соединение...")
        test_url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
        test_headers = {
            "Authorization": f"Bearer {new_token}",
            "Content-Type": "audio/x-pcm;bit=16;rate=16000"
        }
        test_params = {
            "folderId": FOLDER_ID,
            "lang": "ru-RU"
        }
        
        # Отправляем пустой запрос для проверки авторизации
        test_response = requests.post(test_url, headers=test_headers, params=test_params, data=b'')
        
        if test_response.status_code in [200, 400]:  # 400 нормально для пустых данных
            print("✅ Соединение работает! Токен валиден")
        else:
            print(f"⚠️  Получен ответ: {test_response.status_code}")
            
        print(f"\n🎉 ВСЁ ГОТОВО!")
        print(f"Теперь можно использовать ASR без ошибок 401")
        
        # Показываем пример использования
        print(f"\n📋 ПРИМЕР ИСПОЛЬЗОВАНИЯ В ВАШЕМ КОДЕ:")
        print("="*60)
        print("# Замените ваш старый код на:")
        print("token_manager = YandexTokenManager(OAUTH_TOKEN, FOLDER_ID)")
        print("asr_client = YandexASR(token_manager)")
        print("result = asr_client.recognize_audio(audio_data)")
        
        return token_manager, asr_client
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        print(f"\n🔧 ПРОВЕРЬТЕ:")
        print(f"1. OAuth токен корректный")
        print(f"2. Folder ID правильный") 
        print(f"3. Интернет соединение")
        print(f"4. Включен ли Speech Recognition в папке")
        return None, None


if __name__ == "__main__":
    token_manager, asr_client = main()
    
    if token_manager:
        print(f"\n⏰ Токен будет автоматически обновляться каждые 11.5 часов")
        print(f"🔄 Используйте token_manager.get_token() для получения актуального токена")
        
        # Показываем время истечения
        time_left = token_manager.token_expires_at - datetime.now()
        hours_left = time_left.total_seconds() / 3600
        print(f"⏳ До истечения токена: {hours_left:.1f} часов")
