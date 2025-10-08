# 🤖 АРХИТЕКТУРА PYTHON БОТА

## 🎯 ОБЗОР СИСТЕМЫ

Python бот - это сердце нашей AI-системы, которая обрабатывает голосовые звонки через Asterisk ARI. Система построена на асинхронной архитектуре для обеспечения высокой производительности.

### **Основные компоненты:**
```
Asterisk ARI ↔ StasisHandler ↔ [ASR → AI Agent → TTS] ↔ Audio Files
```

## 📁 СТРУКТУРА ПРОЕКТА

```
asterisk-vox-bot/
├── app/
│   └── backend/
│       ├── asterisk/
│       │   ├── stasis_handler_optimized.py    # Основной обработчик
│       │   └── ari_client.py                  # ARI клиент
│       ├── services/
│       │   ├── yandex_asr_service.py         # Распознавание речи
│       │   ├── yandex_tts_service.py         # Синтез речи HTTP
│       │   ├── yandex_grpc_tts.py            # Синтез речи gRPC
│       │   ├── tts_adapter.py                # Адаптер TTS
│       │   ├── sequential_tts.py             # Последовательный TTS
│       │   ├── simple_vad_service.py         # Детекция речи
│       │   └── smart_speech_detector.py      # Умная детекция
│       ├── rag/
│       │   └── agent.py                      # AI агент с RAG
│       └── main.py                           # Точка входа
├── .env                                      # Конфигурация
└── requirements.txt                          # Зависимости
```

## 🔧 КЛЮЧЕВЫЕ КОМПОНЕНТЫ

### **1. StasisHandler (`stasis_handler_optimized.py`)**

**Назначение**: Основной обработчик событий от Asterisk ARI

#### **Ключевые методы:**
```python
class StasisHandler:
    async def handle_stasis_start(event)      # Начало звонка
    async def handle_channel_destroyed(event) # Завершение звонка
    async def process_user_speech_optimized() # Обработка речи
    async def _play_audio_data()              # Воспроизведение звука
    async def _start_or_reset_call_timeout()  # Управление таймаутами
```

#### **Состояния звонка:**
```python
self.active_calls[channel_id] = {
    "status": "Active",           # Active, Processing, Completed
    "start_time": datetime,       # Время начала
    "bridge_id": str,            # ID моста для аудио
    "held": bool,                # Статус hold
    "is_recording": bool,        # Статус записи
    "processing_speech": bool,   # Обработка речи
    "timeout_task": Task,        # Задача таймаута
}
```

### **2. ARI Client (`ari_client.py`)**

**Назначение**: Интерфейс для взаимодействия с Asterisk REST API

#### **Основные методы:**
```python
class AsteriskARIClient:
    async def answer_channel(channel_id)           # Ответить на звонок
    async def start_recording(channel_id, filename) # Начать запись
    async def stop_recording(recording_id)         # Остановить запись
    async def play_sound(channel_id, sound_name)   # Воспроизвести звук
    async def hold_channel(channel_id)             # Поставить на hold
    async def unhold_channel(channel_id)           # Снять с hold
    async def ensure_mixing_bridge_for_call()      # Создать мост
```

#### **Конфигурация ARI:**
```python
ARI_HTTP_URL = "http://127.0.0.1:8088/ari"
ARI_USER = "asterisk"
ARI_PASSWORD = "asterisk123"
ARI_APP_NAME = "asterisk-bot"
```

### **3. TTS System (Text-to-Speech)**

#### **TTS Adapter (`tts_adapter.py`)**
- **Назначение**: Единый интерфейс для всех TTS сервисов
- **Поддерживает**: gRPC TTS (быстрый) + HTTP TTS (fallback)
- **Формат**: WAV 8kHz 16-bit mono

#### **Yandex gRPC TTS (`yandex_grpc_tts.py`)**
- **Скорость**: 0.14-0.33 секунды
- **Качество**: Высокое
- **Статус**: ✅ Работает стабильно

#### **Sequential TTS (`sequential_tts.py`)**
- **Назначение**: Последовательная обработка TTS запросов
- **Chunked processing**: Разбивка на части для быстрого ответа

### **4. ASR System (Automatic Speech Recognition)**

#### **Yandex ASR (`yandex_asr_service.py`)**
- **Формат входа**: WAV файлы от Asterisk
- **Язык**: Русский
- **Точность**: Высокая для телефонного качества

### **5. AI Agent (`agent.py`)**

#### **RAG System (Retrieval-Augmented Generation)**
- **База знаний**: Векторная база с embeddings
- **Поиск**: Семантический поиск по контексту
- **Генерация**: GPT-based ответы с контекстом

#### **Embeddings**:
- **Создание**: Yandex Text Embeddings API
- **Кеширование**: Redis для оптимизации
- **Статус**: ⚠️ Временно отключено для стабильности

### **6. VAD System (Voice Activity Detection)**

#### **Simple VAD (`simple_vad_service.py`)**
- **Назначение**: Детекция речи и тишины
- **Алгоритм**: Анализ энергии сигнала
- **Barge-in**: Поддержка прерывания бота

## ⚙️ КОНФИГУРАЦИЯ (.env)

### **Основные переменные:**
```bash
# ARI настройки
ARI_HTTP_URL=http://127.0.0.1:8088/ari
ARI_USER=asterisk
ARI_PASSWORD=asterisk123
ARI_APP_NAME=asterisk-bot

# Asterisk пути
ASTERISK_SOUNDS_DIR=/var/lib/asterisk/sounds
ASTERISK_LANG=ru

# Таймауты
CHANNEL_TIMEOUT=60
AI_PROCESSING_TIMEOUT=20
PLAYBACK_RETRY_COUNT=3

# TTS настройки
CHANNEL_HOLD_DURING_AI=true
TTS_DEBUG_KEEP_CHUNKS=true
TTS_DEBUG_DUMP_DIR=/var/lib/asterisk/sounds/stream_debug

# Yandex API
YANDEX_API_KEY=your_api_key
YANDEX_FOLDER_ID=your_folder_id
OAUTH_TOKEN=your_oauth_token

# RAG настройки
PROMPTS_FILE_PATH=path/to/prompts
PERSIST_DIRECTORY=path/to/vector_db
```

## 🔄 ПОТОК ОБРАБОТКИ ЗВОНКА

### **1. Инициализация звонка**
```
Asterisk → StasisStart → answer_channel() → create_bridge() → start_recording()
```

### **2. Обработка речи**
```
Recording → ASR → AI Agent → TTS → play_audio_data() → reset_timeout()
```

### **3. Завершение звонка**
```
ChannelDestroyed → cleanup_resources() → stop_recording() → remove_from_active_calls()
```

## 🚨 ТИПИЧНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### **ПРОБЛЕМА 1: Bot не подключается к ARI**

#### **Симптомы:**
- Нет логов от Python бота
- `stasis show apps` не показывает asterisk-bot
- Каналы остаются в Ring состоянии

#### **Диагностика:**
```bash
# Проверить ARI доступность
curl -u asterisk:asterisk123 http://localhost:8088/ari/asterisk/info

# Проверить .env переменные
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(f'ARI_URL: {os.getenv(\"ARI_HTTP_URL\")}')"
```

#### **Решение:**
1. **Проверить .env файл:**
   ```bash
   grep ARI /root/Asterisk_bot/asterisk-vox-bot/.env
   ```

2. **Перезапустить бот:**
   ```bash
   cd /root/Asterisk_bot/asterisk-vox-bot
   source venv/bin/activate
   python app/backend/asterisk/stasis_handler_optimized.py
   ```

### **ПРОБЛЕМА 2: TTS не работает**

#### **Симптомы:**
- AI отвечает, но звук не воспроизводится
- В логах: "❌ ARI playback не удался"
- Файлы не создаются в `/var/lib/asterisk/sounds/ru/`

#### **Диагностика:**
```bash
# Проверить создание файлов
ls -la /var/lib/asterisk/sounds/ru/stream_*

# Проверить права доступа
ls -la /var/lib/asterisk/sounds/

# Проверить TTS логи
grep -i "tts" /path/to/bot/logs
```

#### **Решение:**
1. **Проверить права доступа:**
   ```bash
   chown -R asterisk:asterisk /var/lib/asterisk/sounds/
   chmod -R 755 /var/lib/asterisk/sounds/
   ```

2. **Проверить Yandex API ключи:**
   ```bash
   grep YANDEX /root/Asterisk_bot/asterisk-vox-bot/.env
   ```

### **ПРОБЛЕМА 3: ASR не распознает речь**

#### **Симптомы:**
- Записи создаются, но текст не распознается
- AI не отвечает на вопросы
- В логах: ошибки ASR API

#### **Решение:**
1. **Проверить формат записей:**
   ```bash
   file /var/spool/asterisk/recording/user_*.wav
   ```

2. **Проверить Yandex ASR настройки:**
   ```bash
   grep -E "(YANDEX|ASR)" /root/Asterisk_bot/asterisk-vox-bot/.env
   ```

### **ПРОБЛЕМА 4: Каналы закрываются преждевременно**

#### **Симптомы:**
- Звонки обрываются через 30 секунд
- В логах: "Idle timeout: завершаем канал"
- `channel_exists -> 404`

#### **Решение:**
1. **Увеличить таймаут:**
   ```bash
   # В .env файле
   CHANNEL_TIMEOUT=120
   ```

2. **Проверить hold/unhold логику:**
   ```bash
   # В логах искать:
   # "⏰ Таймер завершения сброшен"
   # "🔒 Channel held during AI processing"
   ```

## 📊 МОНИТОРИНГ И ЛОГИ

### **Ключевые логи для мониторинга:**
```python
# Успешные операции
"✅ ARI playback: {playback_id}"
"🚀 Используем TTS Adapter с gRPC + HTTP fallback"
"📞 Новый звонок: {channel_id}"

# Ошибки
"❌ ARI playback не удался"
"⚠️ Канал {channel_id} не существует"
"🚨 МГНОВЕННАЯ ОЧИСТКА: Отменяем VAD-монитор"
```

### **Команды мониторинга:**
```bash
# Мониторинг Python процесса
ps aux | grep stasis_handler

# Мониторинг логов
tail -f /path/to/bot/logs | grep -E "(✅|❌|⚠️|🚨)"

# Проверка активных звонков
# В Python коде: len(self.active_calls)
```

## 🛠️ ПРОЦЕДУРА ПЕРЕЗАПУСКА

### **Полный перезапуск системы:**
```bash
# 1. Остановить Python бот
pkill -f stasis_handler

# 2. Перезапустить Asterisk
systemctl restart asterisk

# 3. Подождать 5 секунд
sleep 5

# 4. Запустить Python бот
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
nohup python app/backend/asterisk/stasis_handler_optimized.py > bot.log 2>&1 &

# 5. Проверить результат
asterisk -rx "stasis show apps"
```

### **Быстрый перезапуск бота:**
```bash
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate

# Остановить старый процесс
pkill -f stasis_handler

# Запустить новый
python app/backend/asterisk/stasis_handler_optimized.py
```

## 📞 ТЕСТИРОВАНИЕ СИСТЕМЫ

### **Базовый тест:**
1. Позвонить на `79581114700`
2. Дождаться ответа бота
3. Сказать что-то
4. Проверить, что бот отвечает

### **Диагностические команды:**
```bash
# Проверить активные каналы
asterisk -rx "core show channels"

# Проверить Stasis приложения
asterisk -rx "stasis show apps"

# Проверить Python процесс
ps aux | grep stasis_handler
```

---

**Дата создания**: 2025-09-26  
**Версия**: 1.0  
**Статус**: Система работает стабильно  
**Последнее обновление**: После исправления проблем с подключением
