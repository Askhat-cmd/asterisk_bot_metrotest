# 📞 ПОЛНОЕ РУКОВОДСТВО ПО СИСТЕМЕ ASTERISK

**Дата обновления**: 2025-10-01  
**Версия**: 2.0  
**Статус**: ✅ Система работает стабильно, защищена от атак

---

## 🎯 ОБЗОР СИСТЕМЫ

### Что это за система?

Это **голосовой AI-бот** на базе Asterisk, который:
- ✅ Принимает входящие звонки на номер **79581114700** (Novofon)
- ✅ Использует **AI-агента** для ответов на вопросы
- ✅ Распознает речь через **Yandex SpeechKit ASR**
- ✅ Синтезирует речь через **Yandex SpeechKit TTS**
- ✅ Защищен от **SIP-атак** и поддельных звонков

### Архитектура системы:

```
┌─────────────────┐
│  Реальный звонок│
│  (Клиент)       │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Провайдер      │
│  Novofon        │
│  (SIP trunk)    │
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────────────────┐
│           ВАШ СЕРВЕР                        │
│  ┌──────────────────────────────────────┐   │
│  │  ASTERISK (PBX)                      │   │
│  │  ┌─────────────┐    ┌──────────────┐│   │
│  │  │   PJSIP     │ →  │   Dialplan   ││   │
│  │  │ (SIP Stack) │    │  (Routing)   ││   │
│  │  └─────────────┘    └──────┬───────┘│   │
│  │                             ↓        │   │
│  │                      ┌──────────────┐│   │
│  │                      │  Stasis App  ││   │
│  │                      │ (asterisk-bot)│   │
│  │                      └──────┬───────┘│   │
│  └─────────────────────────────┼────────┘   │
│                                 │            │
│                                 ↓            │
│  ┌──────────────────────────────────────┐   │
│  │  PYTHON BOT                          │   │
│  │  ┌──────────┐  ┌─────────┐  ┌─────┐ │   │
│  │  │ AI Agent │  │ Yandex  │  │ ARI │ │   │
│  │  │  (RAG)   │  │ASR/TTS  │  │ API │ │   │
│  │  └──────────┘  └─────────┘  └─────┘ │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
         │
         ↓
    Ответ боту
```

---

## 📜 ИСТОРИЯ: ЧТО БЫЛО И ЧТО ИСПРАВИЛИ

### ⚠️ Проблема #1: Атака поддельных номеров (Сентябрь 2025)

**Что случилось:**
- Дешевая AI-модель в Cursor неправильно настроила Asterisk
- Начали приходить звонки с **поддельных номеров**: 7005, 2600, 84957285000, default
- Система отвечала на все звонки, включая мусорные

**Причины:**
1. **Включен `anonymous` endpoint** в PJSIP → Asterisk принимал звонки от ЛЮБОГО IP из интернета
2. **Правило `_X.` с Answer()** в dialplan → Любой номер отвечался и шел в бота
3. **ARI открыт на `0.0.0.0:8088`** → API был доступен из интернета

**Решение (Октябрь 2025):**
1. ✅ **Удалили `anonymous` endpoint** - теперь звонки только от провайдера
2. ✅ **Настроили PJSIP identify** - фильтрация по IP провайдера Novofon
3. ✅ **Исправили dialplan** - только реальные номера идут в бота, остальное Hangup() БЕЗ Answer()
4. ✅ **Закрыли ARI на localhost** - доступен только с сервера
5. ✅ **Убрали фильтр по CallerID** - теперь ЛЮБОЙ может звонить на ваш номер

**Результат:**
- ✅ Поддельные номера больше НЕ проходят
- ✅ Реальные клиенты могут звонить с любых номеров
- ✅ SIP-сканеры блокируются автоматически
- ✅ Система защищена и работает стабильно

---

## 🔧 ТЕКУЩАЯ КОНФИГУРАЦИЯ (ОКТЯБРЬ 2025)

### 1. PJSIP Configuration (`/etc/asterisk/pjsip.conf`)

#### Transport (UDP)
```ini
[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060
external_media_address=31.207.75.71
external_signaling_address=31.207.75.71
```

**Что это:**
- Слушает SIP на порту **5060 UDP**
- Внешний IP: `31.207.75.71` (IP вашего сервера)

---

#### Voximplant Endpoint (для других интеграций)
```ini
[voxi_in]
type=auth
auth_type=userpass
username=voxi_in
password=8ldWQAaqRs/MPcTV+gxoq+bSP0z4aaq/

[voxi_in]
type=aor
max_contacts=1

[voxi_in]
type=endpoint
context=from-voximplant
disallow=all
allow=alaw,ulaw
aors=voxi_in
auth=voxi_in
dtmf_mode=rfc4733
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
direct_media=no
language=ru
```

**Что это:**
- Endpoint для Voximplant (не используется для основных звонков)
- Требует аутентификацию

---

#### Novofon Outbound Trunk (исходящие звонки)
```ini
[novofon-trunk]
type=endpoint
transport=transport-udp
context=novofon-outbound
disallow=all
allow=alaw,ulaw,g722
outbound_auth=novofon-auth
aors=novofon-aor
dtmf_mode=rfc4733
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
direct_media=no

[novofon-auth]
type=auth
auth_type=userpass
username=asterisk01
password=dummy

[novofon-aor]
type=aor
contact=sip:sip.novofon.ru
```

**Что это:**
- Для **исходящих** звонков через Novofon
- Сейчас не используется (бот только принимает звонки)

---

#### ⭐ Novofon Incoming (ГЛАВНЫЙ - для входящих звонков)
```ini
[novofon-incoming]
type=endpoint
transport=transport-udp
context=from-novofon
disallow=all
allow=alaw,ulaw,g722
dtmf_mode=rfc4733
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
direct_media=no
timers=yes
timers_sess_expires=360

[novofon-identify]
type=identify
endpoint=novofon-incoming
match=37.139.38.224
match=37.139.38.56

[novofon-identify-2]
type=identify
endpoint=novofon-incoming
match=37.139.38.56/32
```

**⭐ ЭТО САМОЕ ВАЖНОЕ! ⭐**

**Что это делает:**
1. **`novofon-incoming`** - endpoint для ВСЕХ входящих звонков от Novofon
2. **`novofon-identify`** - фильтр по IP-адресам провайдера:
   - `37.139.38.224` - старый IP Novofon (sip.novofon.ru)
   - `37.139.38.56` - новый IP Novofon (pbx.novofon.com)
3. **`context=from-novofon`** - все звонки идут в контекст `from-novofon` (см. dialplan)

**Как это защищает:**
- ❌ Если звонок приходит с IP `185.243.5.195` (сканер) → **НЕ совпадает** с identify → Asterisk отклоняет
- ✅ Если звонок приходит с IP `37.139.38.56` (Novofon) → **совпадает** с identify → Asterisk принимает

---

### 2. Dialplan Configuration (`/etc/asterisk/extensions.conf`)

```ini
[general]
static=yes
writeprotect=no

[from-novofon]
; ⭐ ОСНОВНОЙ НОМЕР - главная точка входа
exten => 79581114700,1,NoOp(Main number to AI Handler)
exten => 79581114700,n,Answer()
exten => 79581114700,n,Set(CHANNEL(language)=ru)
exten => 79581114700,n,Stasis(asterisk-bot)
exten => 79581114700,n,Hangup()

; Алиас для основного номера (без 7)
exten => 9581114700,1,Goto(79581114700,1)

; Внутренний номер
exten => 04912,1,NoOp(Internal number to AI Handler)
exten => 04912,n,Answer()
exten => 04912,n,Set(CHANNEL(language)=ru)
exten => 04912,n,Stasis(asterisk-bot)
exten => 04912,n,Hangup()

; Тестовый номер
exten => 0011,1,NoOp(Test number to AI Handler)
exten => 0011,n,Answer()
exten => 0011,n,Set(CHANNEL(language)=ru)
exten => 0011,n,Stasis(asterisk-bot)
exten => 0011,n,Hangup()

; Алиас для тестового номера
exten => 11,1,Goto(0011,1)

; ⭐ ЗАЩИТА: Все остальные номера блокируются
exten => _X.,1,NoOp(БЛОКИРОВКА неизвестного DID: ${EXTEN} от ${CALLERID(num)})
exten => _X.,n,Hangup()

[from-voximplant]
; Для Voximplant (не используется)
exten => _X.,1,NoOp(Voximplant call to AI Handler: ${EXTEN})
exten => _X.,n,Answer()
exten => _X.,n,Set(CHANNEL(language)=ru)
exten => _X.,n,Stasis(asterisk-bot)
exten => _X.,n,Wait(60)
exten => _X.,n,Hangup()

[novofon-outbound]
; Для исходящих звонков (не используется)
exten => 8888,1,Dial(PJSIP/8888@novofon-trunk,30)
exten => 8888,n,Hangup()

exten => test,1,Dial(PJSIP/8888@novofon-trunk,30)
exten => test,n,Hangup()

[playback-context]
; Резервный контекст для воспроизведения звуков
exten => play,1,NoOp(Fallback playback: ${PLAYBACK_FILE})
exten => play,n,Playback(${PLAYBACK_FILE})
exten => play,n,Return()
```

**⭐ Как это работает:**

1. **Входящий звонок на 79581114700:**
   - Провайдер Novofon отправляет INVITE с DID (набранный номер) = `79581114700`
   - Asterisk проверяет IP отправителя → совпадает с `novofon-identify` → принимает
   - Ищет правило в контексте `from-novofon` для extension `79581114700`
   - Находит → Answer() → Stasis(asterisk-bot) → передает в Python бот

2. **Входящий звонок на мусорный номер (7005):**
   - Провайдер НЕ отправит такой звонок (это было раньше через anonymous)
   - Но если бы отправил → ищет правило для `7005`
   - Не находит конкретное правило → попадает на `_X.` (любой паттерн)
   - `NoOp(БЛОКИРОВКА...)` → `Hangup()` **БЕЗ Answer()** → звонок не считается "отвеченным"

3. **Звонок с любого номера клиента:**
   - Клиент звонит на 79581114700 → звонок идет через Novofon → Novofon отправляет INVITE на ваш Asterisk
   - CallerID (номер звонящего) может быть ЛЮБОЙ
   - Важен только **набранный номер** (DID) = 79581114700
   - Звонок проходит ✅

---

### 3. ARI Configuration (`/etc/asterisk/ari.conf`)

```ini
[general]
enabled = yes
pretty = yes

[asterisk]
type = user
read_only = no
password = asterisk123
```

**Что это:**
- **ARI (Asterisk REST Interface)** - HTTP API для управления звонками
- Python бот подключается к ARI для ответа на звонки и воспроизведения аудио

---

### 4. HTTP Configuration (`/etc/asterisk/http.conf`)

```ini
[general]
enabled = yes
bindaddr = 127.0.0.1
bindport = 8088
```

**⭐ ВАЖНО:**
- **`bindaddr = 127.0.0.1`** - ARI доступен **ТОЛЬКО с localhost**
- Python бот работает на том же сервере → может подключиться ✅
- Хакеры из интернета → НЕ могут подключиться ❌

**Как проверить:**
```bash
sudo asterisk -rx "http show status"
# Должно быть: Server Enabled and Bound to 127.0.0.1:8088
```

---

## 🛡️ КАК РАБОТАЕТ ЗАЩИТА

### Уровень 1: PJSIP Identify (Фильтрация по IP)

```
Звонок → Asterisk проверяет IP отправителя
         ↓
    Совпадает с identify?
         ↓
    ДА → Принимает
         ↓
    НЕТ → Отклоняет ("No matching endpoint found")
```

**Примеры:**
- IP `37.139.38.56` (Novofon) → ✅ Принимается
- IP `185.243.5.195` (сканер) → ❌ Отклоняется

**Логи при атаке:**
```
Request 'REGISTER' from '"9007" <sip:9007@31.207.75.71>' 
failed for '185.243.5.195:5350' 
- No matching endpoint found
```

---

### Уровень 2: Dialplan (Фильтрация по DID)

```
Звонок прошел PJSIP → Dialplan проверяет набранный номер (DID)
         ↓
    DID = 79581114700?
         ↓
    ДА → Answer() → В бота
         ↓
    НЕТ → Hangup() БЕЗ Answer()
```

**Примеры:**
- DID `79581114700` → ✅ В бота
- DID `7005` → ❌ Hangup() (мгновенно)

---

### Уровень 3: ARI на localhost

```
Запрос к ARI → Asterisk проверяет откуда запрос
         ↓
    С localhost (127.0.0.1)?
         ↓
    ДА → Разрешает
         ↓
    НЕТ → Отклоняет
```

---

## 🔍 КОМАНДЫ ДЛЯ ДИАГНОСТИКИ И МОНИТОРИНГА

### Проверка статуса Asterisk

```bash
# Статус сервиса
sudo systemctl status asterisk

# Версия Asterisk
sudo asterisk -rx "core show version"

# Время работы и нагрузка
sudo asterisk -rx "core show uptime"
```

---

### Проверка PJSIP

```bash
# Показать все endpoints
sudo asterisk -rx "pjsip show endpoints"

# Показать identify правила
sudo asterisk -rx "pjsip show identifies"

# Показать конкретный endpoint
sudo asterisk -rx "pjsip show endpoint novofon-incoming"

# Показать transports
sudo asterisk -rx "pjsip show transports"
```

**Что искать:**
```
 Endpoint:  novofon-incoming       Unavailable   0 of inf
   Identify:  novofon-identify/novofon-incoming
        Match: 37.139.38.224/32
        Match: 37.139.38.56/32
```

- ✅ **Unavailable** - нормально (нет активных звонков)
- ✅ **Identify правила присутствуют** - защита работает

---

### Проверка Dialplan

```bash
# Показать весь dialplan
sudo asterisk -rx "dialplan show"

# Показать контекст from-novofon
sudo asterisk -rx "dialplan show from-novofon"

# Проверить конкретный номер
sudo asterisk -rx "dialplan show 79581114700@from-novofon"
```

**Что искать:**
```
'79581114700' =>  1. NoOp(Main number to AI Handler)
                  2. Answer()
                  3. Set(CHANNEL(language)=ru)
                  4. Stasis(asterisk-bot)
                  5. Hangup()

'_X.' =>          1. NoOp(БЛОКИРОВКА неизвестного DID: ${EXTEN} от ${CALLERID(num)})
                  2. Hangup()
```

- ✅ Основной номер идет в Stasis
- ✅ `_X.` блокирует без Answer()

---

### Проверка активных звонков

```bash
# Показать активные каналы
sudo asterisk -rx "core show channels"

# Показать количество звонков
sudo asterisk -rx "core show calls"

# Показать Stasis приложения
sudo asterisk -rx "stasis show apps"
```

**Что искать:**
```
Name                   Debug          Subscriptions
asterisk-bot           No             Channel: 0
                                      Bridge: 0
                                      Endpoint: 0
```

- ✅ **asterisk-bot** присутствует - Python бот подключен

---

### Проверка ARI

```bash
# Статус HTTP/ARI
sudo asterisk -rx "http show status"

# Тест ARI с сервера
curl -u asterisk:asterisk123 http://localhost:8088/ari/asterisk/info

# Показать Stasis приложения
sudo asterisk -rx "stasis show apps"
```

**Что искать:**
```
Server Enabled and Bound to 127.0.0.1:8088
```

- ✅ Привязан к **127.0.0.1** (localhost)

---

### Проверка Python бота

```bash
# Проверить запущен ли процесс
ps aux | grep stasis_handler_optimized.py

# Проверить логи бота (если запущен в tmux/screen)
# или смотреть вывод в терминале где запущен

# Запустить бота (если не запущен)
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
python app/backend/asterisk/stasis_handler_optimized.py
```

**Что искать в логах:**
```
✅ Подключен к Asterisk ARI WebSocket
🔔 Новый звонок: Channel=..., Caller=...
✅ Аудио воспроизводится через ARI
```

---

### Мониторинг логов

```bash
# Логи Asterisk (общие)
sudo tail -f /var/log/asterisk/messages.log

# Логи PJSIP (детальные - включить отдельно)
sudo asterisk -rx "pjsip set logger on"
sudo tail -f /var/log/asterisk/messages.log | grep PJSIP

# Фильтр только INVITE запросы
sudo tail -f /var/log/asterisk/messages.log | grep INVITE

# Фильтр атаки (No matching endpoint)
sudo tail -f /var/log/asterisk/messages.log | grep "No matching endpoint"

# Фильтр блокировки в dialplan
sudo tail -f /var/log/asterisk/messages.log | grep "БЛОКИРОВКА"
```

---

### Мониторинг в реальном времени

```bash
# Обновлять каналы каждые 5 секунд
watch -n 5 'sudo asterisk -rx "core show channels"'

# Обновлять endpoints каждые 10 секунд
watch -n 10 'sudo asterisk -rx "pjsip show endpoints"'

# Считать атаки в реальном времени
watch -n 5 'sudo grep "No matching endpoint" /var/log/asterisk/messages.log | tail -20'
```

---

## 🛠️ КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ

### Перезагрузка компонентов

```bash
# Полная перезагрузка Asterisk (остановит все звонки!)
sudo systemctl restart asterisk

# Перезагрузить PJSIP (применить изменения в pjsip.conf)
sudo asterisk -rx "pjsip reload"

# Перезагрузить Dialplan (применить изменения в extensions.conf)
sudo asterisk -rx "dialplan reload"

# Перезагрузить HTTP/ARI (применить изменения в http.conf)
sudo asterisk -rx "module reload http.so"

# Полная перезагрузка конфигурации (без остановки звонков)
sudo asterisk -rx "core reload"
```

---

### Отладка

```bash
# Включить PJSIP логирование (очень детальное!)
sudo asterisk -rx "pjsip set logger on"

# Выключить PJSIP логирование
sudo asterisk -rx "pjsip set logger off"

# Увеличить уровень отладки
sudo asterisk -rx "core set verbose 5"
sudo asterisk -rx "core set debug 5"

# Вернуть обычный уровень
sudo asterisk -rx "core set verbose 0"
sudo asterisk -rx "core set debug 0"
```

---

### Управление звонками

```bash
# Показать активные каналы
sudo asterisk -rx "core show channels"

# Завершить конкретный канал
sudo asterisk -rx "channel request hangup PJSIP/novofon-incoming-00000123"

# Завершить ВСЕ активные каналы (осторожно!)
sudo asterisk -rx "core stop gracefully"
```

---

## 🚨 ТИПИЧНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### Проблема 1: Звонки не проходят ("Абонент занят")

**Симптомы:**
- Звонок не проходит, "busy signal"
- В логах Python бота нет входящих звонков

**Диагностика:**
```bash
# 1. Проверить endpoints
sudo asterisk -rx "pjsip show endpoints"

# 2. Проверить identify
sudo asterisk -rx "pjsip show identifies"

# 3. Проверить dialplan
sudo asterisk -rx "dialplan show from-novofon"

# 4. Проверить Python бот
ps aux | grep stasis_handler
```

**Решения:**

1. **Если identify правила отсутствуют:**
   ```bash
   # Проверить /etc/asterisk/pjsip.conf
   sudo grep -A 5 "novofon-identify" /etc/asterisk/pjsip.conf
   
   # Если нет - добавить вручную или восстановить из бэкапа
   # Затем перезагрузить
   sudo asterisk -rx "pjsip reload"
   ```

2. **Если Python бот не запущен:**
   ```bash
   cd /root/Asterisk_bot/asterisk-vox-bot
   source venv/bin/activate
   python app/backend/asterisk/stasis_handler_optimized.py
   ```

3. **Если dialplan неправильный:**
   ```bash
   # Проверить /etc/asterisk/extensions.conf
   sudo nano /etc/asterisk/extensions.conf
   
   # Перезагрузить dialplan
   sudo asterisk -rx "dialplan reload"
   ```

---

### Проблема 2: Python бот не подключается к ARI

**Симптомы:**
- Python бот выдает ошибку подключения к ARI
- В логах: Connection refused или Timeout

**Диагностика:**
```bash
# 1. Проверить HTTP/ARI статус
sudo asterisk -rx "http show status"

# 2. Попробовать подключиться вручную
curl -u asterisk:asterisk123 http://localhost:8088/ari/asterisk/info

# 3. Проверить .env файл бота
cat /root/Asterisk_bot/asterisk-vox-bot/.env | grep ARI
```

**Решения:**

1. **Если HTTP не запущен:**
   ```bash
   # Проверить /etc/asterisk/http.conf
   sudo nano /etc/asterisk/http.conf
   
   # Должно быть:
   # [general]
   # enabled = yes
   # bindaddr = 127.0.0.1
   # bindport = 8088
   
   # Перезагрузить
   sudo asterisk -rx "module reload http.so"
   ```

2. **Если неправильные credentials:**
   ```bash
   # Проверить /etc/asterisk/ari.conf
   sudo cat /etc/asterisk/ari.conf
   
   # Должно совпадать с .env файлом бота
   # ARI_USERNAME=asterisk
   # ARI_PASSWORD=asterisk123
   ```

---

### Проблема 3: Бот не отвечает или не слышен звук

**Симптомы:**
- Звонок проходит, но бот молчит
- В логах: "ARI playback не удался"

**Диагностика:**
```bash
# 1. Проверить права на звуковые файлы
ls -la /var/lib/asterisk/sounds/

# 2. Проверить логи Python бота
# Ищите "✅ ARI playback" или "❌ ARI playback не удался"

# 3. Проверить активные playback
sudo asterisk -rx "core show channels"
```

**Решения:**

1. **Если проблема с правами:**
   ```bash
   sudo chown -R asterisk:asterisk /var/lib/asterisk/sounds/
   sudo chmod -R 755 /var/lib/asterisk/sounds/
   ```

2. **Если файлы не создаются:**
   ```bash
   # Проверить переменные окружения для Yandex TTS
   cat /root/Asterisk_bot/asterisk-vox-bot/.env | grep YANDEX
   
   # Проверить квоту Yandex SpeechKit
   ```

---

### Проблема 4: Атаки продолжаются (мусорные номера проходят)

**Симптомы:**
- В логах Python бота видны звонки с номеров типа 7005, 2600
- Звонки с неизвестных IP проходят

**Диагностика:**
```bash
# 1. Проверить identify правила
sudo asterisk -rx "pjsip show identifies"

# 2. Проверить нет ли anonymous endpoint
sudo asterisk -rx "pjsip show endpoint anonymous"

# 3. Проверить dialplan правило _X.
sudo asterisk -rx "dialplan show from-novofon" | grep "_X."
```

**Решения:**

1. **Если anonymous endpoint присутствует:**
   ```bash
   # Удалить из /etc/asterisk/pjsip.conf
   sudo nano /etc/asterisk/pjsip.conf
   # Закомментировать все строки с [anonymous]
   
   # Перезагрузить
   sudo asterisk -rx "pjsip reload"
   
   # Проверить
   sudo asterisk -rx "pjsip show endpoint anonymous"
   # Должно: Unable to find object anonymous
   ```

2. **Если _X. отвечает на звонки:**
   ```bash
   # Проверить что _X. НЕ содержит Answer()
   sudo asterisk -rx "dialplan show from-novofon" | grep -A 3 "_X."
   
   # Должно быть:
   # '_X.' => 1. NoOp(БЛОКИРОВКА...)
   #          2. Hangup()
   # БЕЗ Answer()!
   ```

---

## 📊 РЕГУЛЯРНОЕ ОБСЛУЖИВАНИЕ

### Еженедельные проверки

```bash
# 1. Проверить что система работает
sudo asterisk -rx "pjsip show endpoints"
sudo asterisk -rx "stasis show apps"

# 2. Проверить количество атак
sudo grep "No matching endpoint" /var/log/asterisk/messages.log | wc -l

# 3. Проверить место на диске
df -h

# 4. Проверить логи на ошибки
sudo tail -100 /var/log/asterisk/messages.log | grep ERROR
```

---

### Ежемесячные проверки

```bash
# 1. Обновить систему
sudo apt update && sudo apt upgrade

# 2. Создать бэкап конфигурации
sudo mkdir -p /root/backup-asterisk/$(date +%Y-%m)
sudo tar -czf /root/backup-asterisk/$(date +%Y-%m)/asterisk-$(date +%F).tgz /etc/asterisk

# 3. Проверить логи на аномалии
sudo grep -i "attack\|hack\|unauthorized" /var/log/asterisk/messages.log

# 4. Проверить IP провайдера (если изменился)
sudo asterisk -rx "pjsip show identifies"
```

---

## 📞 СПРАВОЧНАЯ ИНФОРМАЦИЯ

### Важные файлы и каталоги

| Путь | Описание |
|------|----------|
| `/etc/asterisk/pjsip.conf` | Конфигурация PJSIP (endpoints, identify) |
| `/etc/asterisk/extensions.conf` | Dialplan (маршрутизация звонков) |
| `/etc/asterisk/ari.conf` | Конфигурация ARI |
| `/etc/asterisk/http.conf` | Конфигурация HTTP/ARI сервера |
| `/var/log/asterisk/messages.log` | Основные логи Asterisk |
| `/var/log/asterisk/full` | Полные логи (если включены) |
| `/var/lib/asterisk/sounds/` | Звуковые файлы (TTS) |
| `/var/spool/asterisk/recording/` | Записи разговоров (ASR) |
| `/root/Asterisk_bot/asterisk-vox-bot/` | Python бот |

---

### Контакты провайдеров

**Novofon:**
- Сайт: https://novofon.com/
- Основной номер: **79581114700**
- SIP-серверы:
  - `sip.novofon.ru` (37.139.38.224)
  - `pbx.novofon.com` (37.139.38.56)

---

### Полезные ссылки

- **Asterisk Documentation**: https://docs.asterisk.org/
- **PJSIP Configuration**: https://wiki.asterisk.org/wiki/display/AST/Configuring+res_pjsip
- **ARI Documentation**: https://docs.asterisk.org/Asterisk_REST_Interface/
- **Yandex SpeechKit**: https://cloud.yandex.ru/docs/speechkit/

---

## ✅ ЧЕКЛИСТ БЫСТРОЙ ПРОВЕРКИ

Используйте этот чеклист для быстрой проверки системы:

```bash
# 1. Asterisk запущен?
sudo systemctl status asterisk
# ✅ Должно: active (running)

# 2. Endpoints настроены?
sudo asterisk -rx "pjsip show endpoints" | grep novofon-incoming
# ✅ Должно: novofon-incoming   Unavailable   0 of inf

# 3. Identify правила есть?
sudo asterisk -rx "pjsip show identifies"
# ✅ Должно: Match: 37.139.38.224/32 и 37.139.38.56/32

# 4. Anonymous endpoint удален?
sudo asterisk -rx "pjsip show endpoint anonymous"
# ✅ Должно: Unable to find object anonymous

# 5. Dialplan правильный?
sudo asterisk -rx "dialplan show 79581114700@from-novofon"
# ✅ Должно: показать маршрут с Stasis(asterisk-bot)

# 6. ARI на localhost?
sudo asterisk -rx "http show status"
# ✅ Должно: Bound to 127.0.0.1:8088

# 7. Python бот подключен?
sudo asterisk -rx "stasis show apps"
# ✅ Должно: asterisk-bot

# 8. Атаки блокируются?
sudo tail -20 /var/log/asterisk/messages.log | grep "No matching endpoint"
# ✅ Должно: видеть блокировки от сканеров
```

Если все пункты ✅ - система настроена правильно!

---

**Последнее обновление**: 01.10.2025  
**Автор документации**: AI Cursor Assistant  
**Версия Asterisk**: 20.6.0
