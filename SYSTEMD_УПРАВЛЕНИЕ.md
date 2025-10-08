# 🚀 Управление ботом через systemd

> Бот запущен как системный сервис и работает в фоновом режиме

---

## ✅ Бот уже настроен и запущен!

Сервис: **`metrotech-bot`**  
Статус: 🟢 **Работает автоматически**  
Автозапуск: ✅ **Включен** (запустится после перезагрузки сервера)

---

## 📋 Основные команды управления

### **Проверить статус бота:**
```bash
sudo systemctl status metrotech-bot
```

### **Перезапустить бота (после изменений кода/конфига):**
```bash
sudo systemctl restart metrotech-bot
```

### **Остановить бота:**
```bash
sudo systemctl stop metrotech-bot
```

### **Запустить бота:**
```bash
sudo systemctl start metrotech-bot
```

### **Отключить автозапуск (если не нужен):**
```bash
sudo systemctl disable metrotech-bot
```

### **Включить автозапуск обратно:**
```bash
sudo systemctl enable metrotech-bot
```

---

## 📊 Мониторинг и логи

### **Посмотреть последние логи в реальном времени:**
```bash
sudo journalctl -u metrotech-bot -f
```

### **Посмотреть последние 50 строк логов:**
```bash
sudo journalctl -u metrotech-bot -n 50
```

### **Логи бота (наш файл):**
```bash
tail -f /root/Asterisk_bot/asterisk-vox-bot/bot.log
```

### **Последние 100 строк лога:**
```bash
tail -n 100 /root/Asterisk_bot/asterisk-vox-bot/bot.log
```

### **Поиск ошибок в логах:**
```bash
tail -n 200 /root/Asterisk_bot/asterisk-vox-bot/bot.log | grep -E "(ERROR|❌|CRITICAL)"
```

---

## 🔄 Типичные сценарии использования

### **Сценарий 1: Изменили код или .env**
```bash
# 1. Остановить бота
sudo systemctl stop metrotech-bot

# 2. Сделать изменения (например, отредактировать .env)
nano /root/Asterisk_bot/asterisk-vox-bot/.env

# 3. Запустить бота
sudo systemctl start metrotech-bot

# 4. Проверить что всё работает
sudo systemctl status metrotech-bot
```

**Или короче (одной командой):**
```bash
sudo systemctl restart metrotech-bot && sudo systemctl status metrotech-bot
```

---

### **Сценарий 2: Бот упал (проверка и перезапуск)**
```bash
# Проверить статус
sudo systemctl status metrotech-bot

# Если "failed" - посмотреть логи
sudo journalctl -u metrotech-bot -n 50

# Перезапустить
sudo systemctl restart metrotech-bot
```

**Примечание:** Бот настроен на **автоматический перезапуск** (Restart=always), поэтому даже если упадёт - запустится сам через 10 секунд.

---

### **Сценарий 3: Обновили код из Git**
```bash
# 1. Перейти в директорию проекта
cd /root/Asterisk_bot

# 2. Получить изменения
git pull

# 3. Перезапустить бота
sudo systemctl restart metrotech-bot

# 4. Проверить логи
tail -f /root/Asterisk_bot/asterisk-vox-bot/bot.log
```

---

### **Сценарий 4: Перезагрузка сервера**
```bash
# Просто перезагрузите - бот запустится автоматически!
sudo reboot

# После перезагрузки проверьте:
sudo systemctl status metrotech-bot
```

---

## 🛠️ Конфигурация сервиса

**Файл сервиса:** `/etc/systemd/system/metrotech-bot.service`

### Что настроено:

| Параметр | Значение | Описание |
|----------|----------|----------|
| **Type** | simple | Простой сервис |
| **User** | root | Запуск от root |
| **WorkingDirectory** | `/root/Asterisk_bot/asterisk-vox-bot` | Рабочая директория |
| **ExecStart** | `venv/bin/python app/backend/asterisk/stasis_handler_optimized.py` | Команда запуска |
| **Restart** | always | Автоперезапуск при падении |
| **RestartSec** | 10 | Пауза перед перезапуском (10 сек) |
| **StandardOutput** | `bot.log` | Логи stdout |
| **StandardError** | `bot.log` | Логи stderr |
| **After** | asterisk.service | Запуск ПОСЛЕ Asterisk |
| **Wants** | asterisk.service | Зависимость от Asterisk |

---

## 📝 Если нужно изменить конфигурацию сервиса

```bash
# 1. Отредактировать файл
sudo nano /etc/systemd/system/metrotech-bot.service

# 2. Перезагрузить конфигурацию systemd
sudo systemctl daemon-reload

# 3. Перезапустить сервис
sudo systemctl restart metrotech-bot
```

---

## 🚨 Решение проблем

### **Проблема: Сервис не запускается**

```bash
# Проверить детальный статус
sudo systemctl status metrotech-bot -l

# Посмотреть логи
sudo journalctl -u metrotech-bot -n 100

# Проверить что venv существует
ls -la /root/Asterisk_bot/asterisk-vox-bot/venv/bin/python

# Запустить бота вручную для отладки
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
python app/backend/asterisk/stasis_handler_optimized.py
```

---

### **Проблема: Бот постоянно перезапускается (loop)**

```bash
# Посмотреть последние перезапуски
sudo journalctl -u metrotech-bot | grep "Started\|stopped"

# Временно отключить автоперезапуск для отладки
sudo systemctl stop metrotech-bot
# ... запустить вручную для отладки ...
```

---

### **Проблема: Логи не пишутся**

```bash
# Проверить права на файл лога
ls -la /root/Asterisk_bot/asterisk-vox-bot/bot.log

# Создать файл если не существует
touch /root/Asterisk_bot/asterisk-vox-bot/bot.log
chmod 644 /root/Asterisk_bot/asterisk-vox-bot/bot.log
```

---

## ✅ Проверка что всё работает правильно

```bash
# 1. Статус сервиса (должно быть "active (running)")
sudo systemctl status metrotech-bot

# 2. Процесс запущен
ps aux | grep stasis_handler_optimized

# 3. Подключение к Asterisk ARI
sudo asterisk -rx "stasis show apps"
# Должно показать: asterisk-bot

# 4. Последние логи без ошибок
tail -n 30 /root/Asterisk_bot/asterisk-vox-bot/bot.log | grep "✅"
```

---

## 🎯 Преимущества systemd

✅ **Автозапуск** - бот запустится после перезагрузки сервера  
✅ **Автоперезапуск** - если бот упадёт, он перезапустится автоматически  
✅ **Логирование** - все логи собираются в journald и `bot.log`  
✅ **Управление через sudo** - стандартные команды `start/stop/restart`  
✅ **Зависимости** - бот запустится ПОСЛЕ Asterisk  
✅ **Мониторинг** - легко проверить статус через `systemctl status`

---

**Дата создания:** 08.10.2025  
**Статус:** ✅ Настроено и работает  
**Автор:** Claude (Anthropic)

