# 💾 Мониторинг дискового пространства

> 📅 **Создано**: 15.10.2025  
> 🎯 **Цель**: Найти большие файлы и мониторить рост диска  
> ⚠️ **Проблема**: Диск заполняется в пассивном состоянии

---

## 📊 Текущая ситуация

### Быстрая проверка:
```bash
# Общее использование диска
df -h /

# Топ-10 самых больших директорий в проекте
du -sh /root/Asterisk_bot/* | sort -hr | head -10

# Найти большие файлы (>100MB)
find /root/Asterisk_bot -type f -size +100M -exec ls -lh {} \;
```

---

## 🚨 КРИТИЧЕСКАЯ ПРОБЛЕМА: Asterisk логи!

### ⚠️ Asterisk `messages.log` растет ОЧЕНЬ быстро!

**Проблема:**
- Файл `/var/log/asterisk/messages.log` может вырасти до **нескольких гигабайт**
- Растет даже без звонков (из-за SIP-атак и проверок)
- По умолчанию **НЕТ автоматической ротации**

**Как проверить:**
```bash
ls -lh /var/log/asterisk/messages.log
```

**Типичная ситуация:**
```
-rw-r--r-- 1 asterisk asterisk 4.6G Oct 15 09:12 /var/log/asterisk/messages.log
```

### 🔧 Решение: Настроить ротацию Asterisk логов

#### **1. Создать конфигурацию logrotate:**

```bash
sudo nano /etc/logrotate.d/asterisk
```

**Содержимое файла:**
```
/var/log/asterisk/messages.log {
    daily
    rotate 7
    missingok
    notifempty
    compress
    delaycompress
    sharedscripts
    postrotate
        /usr/sbin/asterisk -rx 'logger reload' > /dev/null 2>&1 || true
    endscript
    create 0640 asterisk asterisk
}

/var/log/asterisk/*.log {
    weekly
    rotate 4
    missingok
    notifempty
    compress
    delaycompress
    sharedscripts
    postrotate
        /usr/sbin/asterisk -rx 'logger reload' > /dev/null 2>&1 || true
    endscript
    create 0640 asterisk asterisk
}
```

#### **2. Принудительная ротация (сейчас):**

```bash
# Ротировать логи Asterisk прямо сейчас
sudo logrotate -f /etc/logrotate.d/asterisk

# Проверить результат
ls -lh /var/log/asterisk/
```

#### **3. Экстренная очистка (если диск переполнен):**

⚠️ **ОСТОРОЖНО! Удаляет логи безвозвратно!**

```bash
# Сделать backup (на всякий случай)
sudo cp /var/log/asterisk/messages.log /tmp/asterisk_messages_backup.log

# Очистить файл (НЕ удалять!)
sudo truncate -s 0 /var/log/asterisk/messages.log

# Перезагрузить логгер Asterisk
sudo asterisk -rx 'logger reload'

# Проверить
ls -lh /var/log/asterisk/messages.log
```

---

## 🔄 Что такое ротация логов?

**Простыми словами:** Это автоматическая система, которая **переименовывает, сжимает и удаляет** старые логи, чтобы они не заполняли весь диск.

### Как это работает:

1. **День 1**: Asterisk пишет в `messages.log` (текущий лог)
2. **День 2** (00:00): 
   - `messages.log` → `messages.log.1` (вчерашний)
   - Создается новый пустой `messages.log`
3. **День 3** (00:00):
   - `messages.log` → `messages.log.1`
   - `messages.log.1` → `messages.log.2.gz` (сжимается)
4. **День 8** (00:00):
   - Самый старый лог (7 дней назад) **удаляется**

**Итого**: У вас всегда:
- 1 текущий лог (сегодня)
- 1 вчерашний (несжатый, для быстрого доступа)
- 5 старых (сжатых `.gz`)
- **Хранится 7 дней**, старое автоматически удаляется

### Ваша конфигурация:

**Asterisk** (`/etc/logrotate.d/asterisk`):
```
messages.log   → Ежедневно, 7 дней, сжатие
queue_log      → Еженедельно, 4 недели, сжатие
```

**Metrotech** (`/etc/logrotate.d/metrotech`):
```
bot.log, fastapi.log, app-detailed.log → Ежедневно, 7 дней, сжатие
```

### Запуск ротации:

**Автоматически:**
- Каждый день в 00:00 (полночь) через cron

**Вручную (принудительно):**
```bash
# Ротация всех логов
sudo logrotate -f /etc/logrotate.conf

# Только Asterisk
sudo logrotate -f /etc/logrotate.d/asterisk

# Только Metrotech
sudo logrotate -f /etc/logrotate.d/metrotech
```

---

## 🔍 Автоматический скрипт мониторинга

Создан скрипт **`disk_check.sh`** для автоматического мониторинга.

### Использование:

```bash
# Перейти в директорию
cd /root/Asterisk_bot/CHECK_DISK

# Запустить проверку
./disk_check.sh

# Запустить с сохранением истории
./disk_check.sh --save

# Сравнить с предыдущей проверкой
./disk_check.sh --compare
```

### Что показывает скрипт:

1. **Общее использование диска**
2. **Топ-10 самых больших директорий**
3. **Топ-10 самых больших файлов**
4. **Большие логи (>50MB)**
5. **Рост с предыдущей проверки** (если есть история)
6. **Рекомендации по очистке**

---

## 📁 Что обычно занимает место

### 1. **Логи Asterisk** (🔴 ГЛАВНАЯ ПРОБЛЕМА!)

| Файл | Типичный размер | Критичность |
|------|----------------|-------------|
| `/var/log/asterisk/messages.log` | **100MB - 10GB!** | 🔴 Очень высокая |
| `/var/log/asterisk/queue_log` | 1-10MB | 🟡 Средняя |

**Решение:**
- Настроить ротацию (см. выше)
- Мониторить еженедельно

### 2. **Записи звонков**

| Директория | Типичный размер | Критичность |
|-----------|----------------|-------------|
| `/var/spool/asterisk/recording/` | 10-100MB | 🟡 Средняя |
| `/var/lib/asterisk/sounds/stream_*.wav` | 5-50MB | 🟢 Низкая |

**Решение:**
- Очищать старые записи раз в месяц
- Настроить автоудаление через cron

### 3. **Backups проекта**

| Директория | Типичный размер | Критичность |
|-----------|----------------|-------------|
| `/root/Asterisk_bot/project_backup/` | 500MB - 1GB | 🟡 Средняя |
| `/root/Asterisk_bot/АРХИВ/` | 1-50MB | 🟢 Низкая |

**Решение:**
- Хранить только последние 3 backup
- Старые перемещать на внешнее хранилище

### 4. **ChromaDB (векторное хранилище)**

| Директория | Типичный размер | Критичность |
|-----------|----------------|-------------|
| `asterisk-vox-bot/data/chroma/` | 10-100MB | 🟢 Низкая |

**Решение:**
- Обычно не проблема
- Растет только при добавлении новых знаний

### 5. **Python кеш**

| Директория | Типичный размер | Критичность |
|-----------|----------------|-------------|
| `**/__pycache__/` | 5-20MB | 🟢 Низкая |
| `venv/` | 200-500MB | 🟢 Низкая (не удалять!) |

**Решение:**
- Можно очистить `__pycache__` (пересоздастся)
- `venv/` НЕ удалять!

---

## 🧹 Команды очистки

### Безопасные (можно использовать):

```bash
# 1. Очистить Python кеш
find /root/Asterisk_bot -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# 2. Очистить старые записи звонков (старше 30 дней)
find /var/spool/asterisk/recording/ -name "*.wav" -mtime +30 -delete

# 3. Очистить временные TTS файлы (старше 7 дней)
find /var/lib/asterisk/sounds/ -name "stream_*.wav" -mtime +7 -delete

# 4. Очистить старые логи проекта (если есть)
find /var/log/metrotech/archive/ -name "*.log.*" -mtime +30 -delete
```

### Осторожные (требуют проверки):

```bash
# 5. Удалить старые backups (оставить последние 3)
cd /root/Asterisk_bot/project_backup/
ls -t | tail -n +4 | xargs rm -rf

# 6. Очистить Redis dump (если не используется постоянное хранилище)
# ВНИМАНИЕ: Удалит кеш!
redis-cli FLUSHALL

# 7. Ротация логов Asterisk
sudo logrotate -f /etc/logrotate.d/asterisk
```

### ОПАСНЫЕ (использовать только в крайнем случае):

```bash
# ⚠️ Очистка всех логов Asterisk
sudo truncate -s 0 /var/log/asterisk/messages.log
sudo asterisk -rx 'logger reload'

# ⚠️ Удаление всех записей звонков
rm -rf /var/spool/asterisk/recording/*

# ⚠️ Удаление всех TTS файлов
rm -rf /var/lib/asterisk/sounds/stream_*.wav
```

---

## 📊 Регулярный мониторинг

### Ежедневно (автоматически через cron):

```bash
# Добавить в crontab
crontab -e

# Запускать проверку каждый день в 3:00
0 3 * * * /root/Asterisk_bot/CHECK_DISK/disk_check.sh --save >> /var/log/disk_check.log 2>&1

# Очистка старых записей каждый день в 4:00
0 4 * * * find /var/spool/asterisk/recording/ -name "*.wav" -mtime +30 -delete

# Очистка TTS файлов каждый день в 4:30
30 4 * * * find /var/lib/asterisk/sounds/ -name "stream_*.wav" -mtime +7 -delete
```

### Еженедельно (вручную):

```bash
# Каждый понедельник утром
cd /root/Asterisk_bot/CHECK_DISK && ./disk_check.sh --compare

# Проверить размер Asterisk логов
ls -lh /var/log/asterisk/messages.log

# Если больше 1GB - ротировать
sudo logrotate -f /etc/logrotate.d/asterisk
```

### Ежемесячно (вручную):

```bash
# Проверить backups
du -sh /root/Asterisk_bot/project_backup/

# Удалить старые (оставить последние 3)
cd /root/Asterisk_bot/project_backup/
ls -t | tail -n +4 | xargs rm -rf
```

---

## 🚨 Алерты и пороги

### Критические уровни:

| Использование диска | Статус | Действие |
|---------------------|--------|----------|
| < 70% | 🟢 OK | Ничего не делать |
| 70-85% | 🟡 Внимание | Проверить большие файлы |
| 85-95% | 🟠 Предупреждение | Очистить логи и backups |
| > 95% | 🔴 КРИТИЧНО | Экстренная очистка! |

### Команды проверки:

```bash
# Текущее использование
df -h / | awk 'NR==2 {print $5}' | sed 's/%//'

# Алерт если > 85%
USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $USAGE -gt 85 ]; then
    echo "⚠️ ВНИМАНИЕ! Диск заполнен на $USAGE%"
    echo "Запустите: sudo logrotate -f /etc/logrotate.d/asterisk"
fi
```

---

## 📝 История изменений

### 15.10.2025 - v1.1:
- ✅ **Исправлена ротация логов** - освобождено 10GB (83% → 47%)
- ✅ **Уменьшен уровень логирования** - рост логов замедлен в 10 раз
- ✅ **Исправлена конфигурация Metrotech** - добавлен copytruncate
- ✅ **Создан полный backup** конфигураций в `backup_configs/`
- ✅ **Добавлен CHANGELOG.md** с детальной историей

### 15.10.2025 - v1.0:
- ✅ Обнаружена проблема с Asterisk логами (4.6GB)
- ✅ Создана конфигурация logrotate для Asterisk
- ✅ Создан скрипт мониторинга `disk_check.sh`
- ✅ Настроены рекомендации по очистке

> 📄 Полная история изменений в `CHANGELOG.md`

---

## 🔗 Связанные документы

- **Гайд по логированию**: `docs/LOGGING_GUIDE.md`
- **Systemd управление**: `docs/Systemd/SYSTEMD_УПРАВЛЕНИЕ_ВСЕХ_СЕРВИСОВ.md`
- **Основной README**: `asterisk-vox-bot/README.md`

---

## 💡 Полезные команды (шпаргалка)

```bash
# === ПРОВЕРКА ===
df -h /                                    # Общее использование диска
du -sh /root/Asterisk_bot/*                # Размеры директорий проекта
ls -lh /var/log/asterisk/messages.log      # Размер главного лога Asterisk
./disk_check.sh --compare                  # Запустить скрипт мониторинга

# === ОЧИСТКА ===
sudo logrotate -f /etc/logrotate.d/asterisk           # Ротация логов Asterisk
find /var/spool/asterisk/recording/ -mtime +30 -delete  # Удалить старые записи
find /var/lib/asterisk/sounds/ -name "stream_*.wav" -mtime +7 -delete  # Удалить TTS

# === ЭКСТРЕННАЯ ПОМОЩЬ (диск > 95%) ===
sudo truncate -s 0 /var/log/asterisk/messages.log     # Очистить Asterisk лог
sudo asterisk -rx 'logger reload'                     # Перезагрузить логгер
rm -rf /var/spool/asterisk/recording/*.wav            # Удалить все записи
```

---

**Дата создания**: 15.10.2025  
**Версия**: 1.0  
**Автор**: Системная документация проекта "Метротэст"

> 💾 **Следите за дисковым пространством!** Запускайте `disk_check.sh` раз в неделю.

