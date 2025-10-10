# 🔧 РУКОВОДСТВО ПО УСТРАНЕНИЮ НЕИСПРАВНОСТЕЙ

**Версия**: 2.0 | **Дата обновления**: 01.10.2025  
**⚠️ ВАЖНО**: Система теперь использует PJSIP Identify вместо anonymous endpoint!

---

## 🚨 ЭКСТРЕННОЕ ВОССТАНОВЛЕНИЕ

### **Если система полностью не работает:**

#### **Шаг 1: Быстрая диагностика (2 минуты)**
```bash
# Проверить статус Asterisk
sudo systemctl status asterisk

# Проверить Python бот
ps aux | grep stasis_handler

# ⭐ ВАЖНО: Проверить identify правила
sudo asterisk -rx "pjsip show identifies"
# Должно показать: 37.139.38.224/32 и 37.139.38.56/32

# Проверить endpoints
sudo asterisk -rx "pjsip show endpoints" | grep novofon

# ⚠️ Проверить что anonymous УДАЛЕН
sudo asterisk -rx "pjsip show endpoint anonymous"
# Должно: "Unable to find object anonymous"

# Проверить активные каналы
sudo asterisk -rx "core show channels"
```

#### **Шаг 2: Экстренный перезапуск (3 минуты)**
```bash
# 1. Перезапустить Asterisk
sudo systemctl restart asterisk
sleep 10

# 2. Проверить что конфигурация загрузилась
sudo asterisk -rx "pjsip show identifies"

# 3. Перезапустить Python бот
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
pkill -f stasis_handler
nohup python app/backend/asterisk/stasis_handler_optimized.py > bot.log 2>&1 &

# 4. Проверить результат
sudo asterisk -rx "stasis show apps"
sudo asterisk -rx "pjsip show endpoints" | grep novofon
```

#### **Шаг 3: Тестовый звонок**
- Позвонить на `79581114700` **с любого номера**
- Проверить, что бот отвечает

---

## 📋 ДИАГНОСТИЧЕСКАЯ МАТРИЦА

| Симптом | Возможная причина | Команда диагностики | Решение |
|---------|-------------------|---------------------|---------|
| "Абонент занят" | Identify правила не работают | `pjsip show identifies` | Восстановить identify правила |
| Звонки не проходят | Dialplan проблема | `dialplan show from-novofon` | Перезагрузить dialplan |
| Каналы не создаются | Asterisk не работает | `systemctl status asterisk` | Перезапустить Asterisk |
| Бот не отвечает | Python процесс упал | `ps aux \| grep stasis` | Перезапустить Python бот |
| Нет звука | TTS проблема | Проверить `/var/lib/asterisk/sounds/ru/` | Проверить права доступа |
| ASR не работает | API ключи | Проверить `.env` файл | Обновить Yandex ключи |
| ⚠️ Anonymous endpoint есть | Критическая уязвимость | `pjsip show endpoint anonymous` | НЕМЕДЛЕННО удалить! |

---

## 🔍 ПОДРОБНАЯ ДИАГНОСТИКА

### **ПРОБЛЕМА: "Абонент занят" (busy signal)**

#### **Диагностика:**
```bash
# 1. ⭐ ГЛАВНОЕ: Проверить identify правила
sudo asterisk -rx "pjsip show identifies"
# Ожидаемый результат:
# Identify: novofon-identify/novofon-incoming
#     Match: 37.139.38.224/32
#     Match: 37.139.38.56/32

# 2. Проверить endpoint novofon-incoming
sudo asterisk -rx "pjsip show endpoint novofon-incoming"
# Статус "Unavailable" - это НОРМАЛЬНО (нет активных звонков)

# 3. ⚠️ Убедиться что anonymous УДАЛЕН
sudo asterisk -rx "pjsip show endpoint anonymous"
# Должно: "Unable to find object anonymous"

# 4. Проверить dialplan
sudo asterisk -rx "dialplan show 79581114700@from-novofon"
# Должен показать маршрут к Stasis(asterisk-bot)
```

#### **Решение по приоритету:**

1. **Если identify правила отсутствуют (КРИТИЧНО!):**
   ```bash
   # Проверить /etc/asterisk/pjsip.conf
   sudo grep -A 10 "novofon-identify" /etc/asterisk/pjsip.conf
   
   # Если нет - восстановить из бэкапа
   sudo cp /root/backup-asterisk/LATEST/asterisk/pjsip.conf /etc/asterisk/
   
   # ИЛИ добавить вручную
   sudo nano /etc/asterisk/pjsip.conf
   ```

   Добавить в конец файла:
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

   Применить:
   ```bash
   sudo asterisk -rx "pjsip reload"
   sudo asterisk -rx "pjsip show identifies"
   ```

2. **Если Python бот не запущен:**
   ```bash
   cd /root/Asterisk_bot/asterisk-vox-bot
   source venv/bin/activate
   python app/backend/asterisk/stasis_handler_optimized.py
   ```

3. **Если dialplan неправильный:**
   ```bash
   sudo asterisk -rx "dialplan reload"
   ```

---

### **ПРОБЛЕМА: Python бот не подключается к ARI**

#### **Диагностика:**
```bash
# 1. Проверить процесс
ps aux | grep stasis_handler

# 2. Проверить ARI доступность
curl -u asterisk:asterisk123 http://localhost:8088/ari/asterisk/info

# 3. Проверить Stasis приложения
sudo asterisk -rx "stasis show apps"
# Должно показать: asterisk-bot

# 4. Проверить .env переменные
cd /root/Asterisk_bot/asterisk-vox-bot
grep ARI .env
```

#### **Решение:**

1. **Если процесс не запущен:**
   ```bash
   cd /root/Asterisk_bot/asterisk-vox-bot
   source venv/bin/activate
   python app/backend/asterisk/stasis_handler_optimized.py
   ```

2. **Если ARI недоступен:**
   ```bash
   # Проверить /etc/asterisk/http.conf
   sudo grep -A 5 "^\[general\]" /etc/asterisk/http.conf
   
   # Должно быть:
   # [general]
   # enabled = yes
   # bindaddr = 127.0.0.1
   # bindport = 8088
   
   # Если неправильно - исправить и перезагрузить
   sudo asterisk -rx "module reload http.so"
   ```

3. **Если .env неправильный:**
   ```bash
   # Проверить и исправить:
   nano /root/Asterisk_bot/asterisk-vox-bot/.env
   
   # Должно быть:
   # ARI_HTTP_URL=http://127.0.0.1:8088/ari
   # ARI_USER=asterisk
   # ARI_PASSWORD=asterisk123
   # ARI_APP_NAME=asterisk-bot
   ```

---

### **ПРОБЛЕМА: Звук не доходит до абонента**

#### **Диагностика:**
```bash
# 1. Проверить создание файлов
ls -la /var/lib/asterisk/sounds/ru/stream_*

# 2. Проверить права доступа
ls -la /var/lib/asterisk/sounds/

# 3. Проверить формат файлов
file /var/lib/asterisk/sounds/ru/stream_*.wav

# 4. Проверить логи TTS в Python боте
# Искать: "✅ ARI playback" или "❌ ARI playback не удался"
```

#### **Решение:**

1. **Если файлы не создаются:**
   ```bash
   # Проверить TTS настройки в .env
   grep TTS /root/Asterisk_bot/asterisk-vox-bot/.env
   
   # Проверить Yandex API ключи
   grep YANDEX /root/Asterisk_bot/asterisk-vox-bot/.env
   ```

2. **Если файлы создаются, но не воспроизводятся:**
   ```bash
   # Исправить права доступа
   sudo chown -R asterisk:asterisk /var/lib/asterisk/sounds/
   sudo chmod -R 755 /var/lib/asterisk/sounds/
   ```

3. **Если формат файлов неправильный:**
   ```bash
   # Должен быть: WAV 8kHz 16-bit mono
   # Проверить настройки TTS в .env
   ```

---

### **ПРОБЛЕМА: Атаки от SIP-сканеров проходят**

#### **Симптомы:**
- В логах Python бота видны звонки с мусорных номеров (7005, 2600, 84957285000)
- Звонки с неизвестных IP проходят
- В логах нет блокировок "No matching endpoint found"

#### **Диагностика:**
```bash
# 1. ⚠️ КРИТИЧНО: Проверить что anonymous УДАЛЕН
sudo asterisk -rx "pjsip show endpoint anonymous"
# Должно: "Unable to find object anonymous"

# 2. Проверить identify правила
sudo asterisk -rx "pjsip show identifies"
# Должно показать правила для 37.139.38.224 и 37.139.38.56

# 3. Проверить dialplan правило _X.
sudo asterisk -rx "dialplan show from-novofon" | grep "_X."
# Должно быть: NoOp + Hangup БЕЗ Answer()

# 4. Проверить логи на атаки
sudo tail -50 /var/log/asterisk/messages.log | grep "No matching endpoint"
# Должны быть блокировки от сканеров
```

#### **Решение:**

1. **⚠️ Если anonymous endpoint присутствует (КРИТИЧНО!):**
   ```bash
   # НЕМЕДЛЕННО удалить из /etc/asterisk/pjsip.conf
   sudo nano /etc/asterisk/pjsip.conf
   
   # Найти и ПОЛНОСТЬЮ УДАЛИТЬ секцию:
   # [anonymous]
   # type=endpoint
   # ... (все строки с anonymous)
   
   # Сохранить и перезагрузить
   sudo asterisk -rx "pjsip reload"
   
   # Проверить что удален
   sudo asterisk -rx "pjsip show endpoint anonymous"
   # Должно: "Unable to find object anonymous" ✅
   ```

2. **Если identify правила отсутствуют:**
   ```bash
   # Добавить в /etc/asterisk/pjsip.conf (см. выше в решении "Абонент занят")
   sudo asterisk -rx "pjsip reload"
   ```

3. **Если _X. отвечает на звонки (содержит Answer()):**
   ```bash
   # Исправить в /etc/asterisk/extensions.conf
   sudo nano /etc/asterisk/extensions.conf
   
   # Правило должно быть:
   # exten => _X.,1,NoOp(БЛОКИРОВКА неизвестного DID: ${EXTEN} от ${CALLERID(num)})
   # exten => _X.,n,Hangup()
   # БЕЗ Answer()!
   
   # Применить
   sudo asterisk -rx "dialplan reload"
   ```

---

### **ПРОБЛЕМА: Каналы закрываются преждевременно**

#### **Диагностика:**
```bash
# 1. Проверить активные каналы
sudo asterisk -rx "core show channels"

# 2. Проверить время жизни каналов
# В логах Python бота искать: "Idle timeout: завершаем канал"

# 3. Проверить таймауты в .env
grep TIMEOUT /root/Asterisk_bot/asterisk-vox-bot/.env
```

#### **Решение:**

1. **Увеличить таймаут:**
   ```bash
   # В .env файле:
   nano /root/Asterisk_bot/asterisk-vox-bot/.env
   
   # Добавить/изменить:
   CHANNEL_TIMEOUT=120
   AI_PROCESSING_TIMEOUT=30
   ```

2. **Проверить hold/unhold логику:**
   ```bash
   # В логах Python бота должно быть:
   # "🔒 Channel held during AI processing"
   # "🔓 Channel unhold before playback"
   ```

---

## 🔄 ПРОЦЕДУРЫ ВОССТАНОВЛЕНИЯ

### **Процедура 1: Мягкий перезапуск (без потери звонков)**
```bash
# 1. Перезапустить только Python бот
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
pkill -f stasis_handler
python app/backend/asterisk/stasis_handler_optimized.py

# 2. Проверить результат
sudo asterisk -rx "stasis show apps"
```

### **Процедура 2: Полный перезапуск (с потерей активных звонков)**
```bash
# 1. Остановить все
pkill -f stasis_handler
sudo systemctl stop asterisk

# 2. Подождать 5 секунд
sleep 5

# 3. Запустить все
sudo systemctl start asterisk
sleep 10

cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
nohup python app/backend/asterisk/stasis_handler_optimized.py > bot.log 2>&1 &

# 4. Проверить результат
sudo asterisk -rx "pjsip show endpoints" | grep novofon
sudo asterisk -rx "pjsip show identifies"
sudo asterisk -rx "stasis show apps"
```

### **Процедура 3: Восстановление из бэкапа (ОБНОВЛЕНО!)**

⚠️ **ВАЖНО**: После восстановления проверьте что anonymous endpoint УДАЛЕН!

```bash
# 1. Остановить систему
sudo systemctl stop asterisk
pkill -f stasis_handler

# 2. Восстановить конфигурацию
sudo cp /root/backup-asterisk/LATEST/asterisk/pjsip.conf /etc/asterisk/
sudo cp /root/backup-asterisk/LATEST/asterisk/extensions.conf /etc/asterisk/

# 3. ⚠️ КРИТИЧНО: Проверить что нет anonymous
grep -A 15 "\[anonymous\]" /etc/asterisk/pjsip.conf

# Если anonymous есть - УДАЛИТЬ его!
sudo nano /etc/asterisk/pjsip.conf
# Удалить все строки с [anonymous]

# 4. Проверить identify правила
grep -A 10 "novofon-identify" /etc/asterisk/pjsip.conf
# Должны быть IP: 37.139.38.224 и 37.139.38.56

# 5. Запустить систему
sudo systemctl start asterisk
sleep 10

cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
python app/backend/asterisk/stasis_handler_optimized.py

# 6. Проверить безопасность
sudo asterisk -rx "pjsip show endpoint anonymous"
# Должно: "Unable to find object anonymous" ✅

sudo asterisk -rx "pjsip show identifies"
# Должны быть правила для Novofon IP ✅
```

---

## 📊 МОНИТОРИНГ И АЛЕРТЫ

### **Ключевые метрики для мониторинга:**
```bash
# 1. Активные каналы
sudo asterisk -rx "core show channels"

# 2. Endpoint статус
sudo asterisk -rx "pjsip show endpoints" | grep novofon

# 3. ⭐ Identify правила (ВАЖНО!)
sudo asterisk -rx "pjsip show identifies"

# 4. ⚠️ Anonymous отсутствует (БЕЗОПАСНОСТЬ!)
sudo asterisk -rx "pjsip show endpoint anonymous"

# 5. Stasis приложения
sudo asterisk -rx "stasis show apps"

# 6. Python процесс
ps aux | grep stasis_handler

# 7. Атаки (блокировки)
sudo tail -20 /var/log/asterisk/messages.log | grep "No matching endpoint"
```

### **Скрипт автоматического мониторинга:**
```bash
#!/bin/bash
# /root/Asterisk_bot/scripts/health_check.sh

# Проверить Asterisk
if ! systemctl is-active --quiet asterisk; then
    echo "ALERT: Asterisk не работает"
    systemctl restart asterisk
fi

# Проверить Python бот
if ! pgrep -f stasis_handler > /dev/null; then
    echo "ALERT: Python бот не работает"
    cd /root/Asterisk_bot/asterisk-vox-bot
    source venv/bin/activate
    nohup python app/backend/asterisk/stasis_handler_optimized.py > bot.log 2>&1 &
fi

# ⚠️ КРИТИЧНО: Проверить что anonymous УДАЛЕН
if sudo asterisk -rx "pjsip show endpoint anonymous" | grep -q "type=endpoint"; then
    echo "CRITICAL ALERT: Anonymous endpoint обнаружен! Критическая уязвимость!"
    # Можно добавить отправку уведомления
fi

# Проверить identify правила
if ! sudo asterisk -rx "pjsip show identifies" | grep -q "novofon-identify"; then
    echo "ALERT: Identify правила отсутствуют!"
    sudo asterisk -rx "pjsip reload"
fi

# Проверить ARI на localhost
if ! sudo asterisk -rx "http show status" | grep -q "127.0.0.1:8088"; then
    echo "ALERT: ARI не на localhost - уязвимость безопасности!"
fi
```

### **Настройка cron для автоматической проверки:**
```bash
# Добавить в crontab:
# */5 * * * * /root/Asterisk_bot/scripts/health_check.sh >> /var/log/asterisk_health.log 2>&1
```

---

## 🆘 ЭКСТРЕННЫЕ КОНТАКТЫ

### **Важные файлы для бэкапа:**
- `/etc/asterisk/pjsip.conf` ⭐ (самый важный!)
- `/etc/asterisk/extensions.conf`
- `/etc/asterisk/ari.conf`
- `/etc/asterisk/http.conf`
- `/root/Asterisk_bot/asterisk-vox-bot/.env`

### **Команды для создания бэкапа:**
```bash
# Создать бэкап конфигурации
sudo tar -czf /root/asterisk_config_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    /etc/asterisk/pjsip.conf \
    /etc/asterisk/extensions.conf \
    /etc/asterisk/ari.conf \
    /etc/asterisk/http.conf \
    /root/Asterisk_bot/asterisk-vox-bot/.env
```

### **Логи для анализа:**
- **Asterisk**: `/var/log/asterisk/messages.log` ⭐ (атаки видны здесь)
- **Python бот**: `/root/Asterisk_bot/asterisk-vox-bot/bot.log`
- **System**: `journalctl -u asterisk`

---

## ✅ ЧЕКЛИСТ ПОСЛЕ ВОССТАНОВЛЕНИЯ

После любого восстановления **ОБЯЗАТЕЛЬНО** проверить:

```bash
# 1. ⚠️ Anonymous УДАЛЕН?
sudo asterisk -rx "pjsip show endpoint anonymous"
# Должно: "Unable to find object anonymous" ✅

# 2. Identify правила есть?
sudo asterisk -rx "pjsip show identifies"
# Должны быть: 37.139.38.224/32 и 37.139.38.56/32 ✅

# 3. ARI на localhost?
sudo asterisk -rx "http show status"
# Должно: "Bound to 127.0.0.1:8088" ✅

# 4. Python бот работает?
ps aux | grep stasis_handler
sudo asterisk -rx "stasis show apps"
# Должно показать: asterisk-bot ✅

# 5. Атаки блокируются?
sudo tail -20 /var/log/asterisk/messages.log | grep "No matching endpoint"
# Должны быть блокировки ✅
```

Если все пункты ✅ - система безопасна и работает корректно!

---

**Дата создания**: 2025-09-26  
**Версия**: 2.0  
**Последнее обновление**: 2025-10-01 (Обновлено после исправлений безопасности)  
**Статус**: Проверено на защищенной системе
