# 📊 Полный гайд по логированию проекта "Метротэст"

> 📅 **Обновлено**: 10.10.2025  
> 👤 **Для кого**: Новички и администраторы  
> 🎯 **Цель**: Понять, где и как хранятся логи, как их мониторить

---

## 📚 Содержание

1. [Что такое логи и зачем они нужны](#что-такое-логи)
2. [Где хранятся все логи](#где-хранятся-логи)
3. [Централизованное логирование](#централизованное-логирование)
4. [Типы логов в проекте](#типы-логов)
5. [Как читать логи](#как-читать-логи)
6. [Мониторинг в реальном времени](#мониторинг-в-реальном-времени)
7. [Поиск и фильтрация](#поиск-и-фильтрация)
8. [Ротация и очистка логов](#ротация-логов)
9. [Частые проблемы и решения](#частые-проблемы)
10. [Полезные команды](#полезные-команды)

---

## 🤔 Что такое логи и зачем они нужны? {#что-такое-логи}

**Логи** (logs) — это текстовые файлы, в которые программы записывают информацию о своей работе:
- Что происходит в данный момент
- Какие ошибки возникли
- Кто и когда звонил
- Как долго обрабатывался запрос

### Зачем нужны логи?
✅ **Диагностика** — понять, почему что-то не работает  
✅ **Мониторинг** — следить за работой системы в реальном времени  
✅ **Статистика** — сколько звонков было, сколько ошибок  
✅ **Безопасность** — кто пытался атаковать систему  
✅ **Аудит** — история всех действий

---

## 📁 Где хранятся все логи? {#где-хранятся-логи}

### 🎯 Главная директория (с 10.10.2025)

```
/var/log/metrotech/  ← ВСЕ ЛОГИ ЗДЕСЬ!
```

Все логи проекта собраны в **одном месте** для удобства.

### 📊 Структура директории

```
/var/log/metrotech/
├── bot.log                    # Логи обработки звонков (30KB)
├── fastapi.log                # Логи веб-интерфейса (2KB)
├── app-detailed.log           # Детальные логи приложения (2KB)
├── asterisk.log → /var/log/asterisk/messages.log  # Симлинк на Asterisk
├── redis.log → /var/log/redis/redis-server.log    # Симлинк на Redis
└── archive/                   # Архив старых логов
    ├── old-logs/              # Устаревшие логи
    └── *.service.backup       # Backup конфигураций
```

---

## 🎯 Централизованное логирование {#централизованное-логирование}

### Что это значит?

**До централизации** (до 10.10.2025):
```bash
# Логи были разбросаны по системе:
/root/Asterisk_bot/asterisk-vox-bot/bot.log           # Тут
/root/Asterisk_bot/asterisk-vox-bot/fastapi.log       # Там
/root/Asterisk_bot/asterisk-vox-bot/data/logs/app.log # Здесь
/var/log/asterisk/messages.log                        # А тут системные
/var/log/redis/redis-server.log                       # И еще Redis
```

**После централизации** (с 10.10.2025):
```bash
# Все логи в одном месте:
/var/log/metrotech/  ← ТОЛЬКО ТУТ!
```

### 🔗 Что такое симлинки?

**Симлинк** (symbolic link) — это как **ярлык** в Windows. Не копия файла, а указатель на него.

#### Зачем симлинки?

Asterisk и Redis — системные сервисы, их логи лежат в стандартных местах:
- `/var/log/asterisk/messages.log`
- `/var/log/redis/redis-server.log`

Мы **не можем** и **не должны** их перемещать. Поэтому создали симлинки:

```bash
/var/log/metrotech/asterisk.log → /var/log/asterisk/messages.log
/var/log/metrotech/redis.log → /var/log/redis/redis-server.log
```

#### Как работают симлинки?

```bash
# Когда вы читаете:
tail -f /var/log/metrotech/asterisk.log

# На самом деле читается:
tail -f /var/log/asterisk/messages.log
```

**Преимущества:**
- ✅ Все логи в одном месте
- ✅ Не занимают дополнительное место (это не копия!)
- ✅ Всегда актуальные данные
- ✅ Не ломаем системные сервисы

---

## 📝 Типы логов в проекте {#типы-логов}

### 1. **bot.log** — Обработка звонков (главный!)

**Путь**: `/var/log/metrotech/bot.log`  
**Кто пишет**: `stasis_handler_optimized.py`  
**Размер**: ~30KB (растет быстро!)

**Что внутри:**
```
2025-10-10 08:03:01,766 - __main__ - INFO - ✅ Подключен к Asterisk ARI WebSocket
2025-10-10 08:04:12,445 - __main__ - INFO - 📞 Новый звонок: 1760083438.270
2025-10-10 08:04:15,231 - __main__ - INFO - 🎤 ASR результат: "Здравствуйте"
2025-10-10 08:04:16,892 - __main__ - INFO - 🤖 AI ответ: "Добрый день!"
2025-10-10 08:04:18,123 - __main__ - INFO - 🔊 TTS завершен
2025-10-10 08:04:31,806 - __main__ - INFO - ✅ Звонок завершен
```

**Когда смотреть:**
- ✅ Проверить, обрабатываются ли звонки
- ✅ Узнать, что сказал пользователь (ASR)
- ✅ Увидеть ответ бота (AI)
- ✅ Найти ошибки в обработке звонков

### 2. **fastapi.log** — Веб-интерфейс

**Путь**: `/var/log/metrotech/fastapi.log`  
**Кто пишет**: `main.py` (FastAPI сервер)  
**Размер**: ~2KB (растет медленно)

**Что внутри:**
```
INFO:     Started server process [1305190]
INFO:     Uvicorn running on http://0.0.0.0:9000
INFO:     151.115.98.4:46825 - "GET /logs HTTP/1.1" 200 OK
INFO:     151.115.98.4:2963 - "POST /api/prompts HTTP/1.1" 200 OK
```

**Когда смотреть:**
- ✅ Проверить, работает ли админ-панель
- ✅ Увидеть HTTP запросы к API
- ✅ Найти ошибки веб-интерфейса

### 3. **app-detailed.log** — Детальные логи

**Путь**: `/var/log/metrotech/app-detailed.log`  
**Кто пишет**: `main.py` (Python logging)  
**Размер**: ~2KB (с автоматической ротацией)

**Что внутри:**
```
2025-10-10 08:03:10,007 - app.backend.rag.agent - INFO - --- Агент 'Метротест' успешно инициализирован ---
2025-10-10 08:03:10,007 - __main__ - INFO - Агент 'Метротест' успешно инициализирован.
```

**Когда смотреть:**
- ✅ Подробная информация о работе приложения
- ✅ Ошибки загрузки баз знаний
- ✅ Проблемы с AI агентом

**Особенность:** Автоматическая ротация (макс. 5MB, 5 backup файлов)

### 4. **asterisk.log** — Телефония (системный)

**Путь**: `/var/log/metrotech/asterisk.log` → `/var/log/asterisk/messages.log`  
**Кто пишет**: Asterisk PBX (система)  
**Размер**: ~961MB! (ОГРОМНЫЙ!)

**Что внутри:**
```
[Oct 10 08:16:00] NOTICE[1262652] res_pjsip/pjsip_distributor.c: Request 'INVITE' from '"default" <sip:default@31.207.75.71>' failed for '213.170.135.210:32952' - No matching endpoint found
[Oct 10 08:16:00] NOTICE[1262652] res_pjsip/pjsip_distributor.c: Request 'INVITE' from '"default" <sip:default@31.207.75.71>' failed for '213.170.135.210:32952' - Failed to authenticate
```

**Когда смотреть:**
- ✅ SIP атаки (No matching endpoint found)
- ✅ Проблемы с подключением к провайдеру
- ✅ Ошибки телефонии на низком уровне

⚠️ **ВНИМАНИЕ:** Файл очень большой! Нужна ротация.

### 5. **redis.log** — Кеширование (системный)

**Путь**: `/var/log/metrotech/redis.log` → `/var/log/redis/redis-server.log`  
**Кто пишет**: Redis (система)  
**Размер**: ~1MB

**Что внутри:**
```
939334:M 10 Oct 2025 06:55:23.133 * Background saving terminated with success
939334:M 10 Oct 2025 07:29:06.181 * 1 changes in 3600 seconds. Saving...
```

**Когда смотреть:**
- ✅ Проблемы с кешированием
- ✅ Ошибки подключения к Redis
- ✅ Статистика использования памяти

---

## 📖 Как читать логи? {#как-читать-логи}

### Базовые команды

#### 1. Просмотр последних строк
```bash
# Последние 10 строк
tail /var/log/metrotech/bot.log

# Последние 50 строк
tail -n 50 /var/log/metrotech/bot.log

# Последние 2 строки всех логов
tail -n 2 /var/log/metrotech/*.log
```

#### 2. Просмотр с начала файла
```bash
# Первые 20 строк
head -n 20 /var/log/metrotech/bot.log

# Весь файл (осторожно с большими!)
cat /var/log/metrotech/bot.log
```

#### 3. Постраничный просмотр
```bash
# С прокруткой (стрелки, пробел, q для выхода)
less /var/log/metrotech/bot.log

# Поиск внутри less: нажать /, ввести текст, Enter
```

---

## 📡 Мониторинг в реальном времени {#мониторинг-в-реальном-времени}

### 🔥 Самое важное!

#### Мониторинг всех логов сразу
```bash
# Перейти в директорию
cd /var/log/metrotech/

# Смотреть все логи в реальном времени
tail -f *.log
```

**Что произойдет:**
- Увидите ВСЕ логи (bot, fastapi, app-detailed, asterisk, redis)
- Новые строки будут появляться автоматически
- Выход: `Ctrl+C`

#### Мониторинг конкретного лога
```bash
# Только обработка звонков
tail -f /var/log/metrotech/bot.log

# Только веб-интерфейс
tail -f /var/log/metrotech/fastapi.log

# Только Asterisk (телефония)
tail -f /var/log/metrotech/asterisk.log
```

#### Мониторинг через systemd
```bash
# Логи systemd для бота
sudo journalctl -u metrotech-bot -f

# Логи systemd для админки
sudo journalctl -u metrotech-fastapi -f

# Показать последние 100 строк и следить
sudo journalctl -u metrotech-bot -n 100 -f
```

---

## 🔍 Поиск и фильтрация {#поиск-и-фильтрация}

### Поиск ошибок

#### Найти все ошибки
```bash
# Ошибки в bot.log
grep -i "error" /var/log/metrotech/bot.log

# Ошибки во ВСЕХ логах
grep -i "error" /var/log/metrotech/*.log

# Ошибки и предупреждения
grep -E "ERROR|WARN|Exception" /var/log/metrotech/*.log
```

#### С контекстом (строки до и после)
```bash
# Показать 3 строки до и после ошибки
grep -i "error" -A 3 -B 3 /var/log/metrotech/bot.log
```

### Поиск по звонкам

#### Конкретный номер телефона
```bash
grep "79581114700" /var/log/metrotech/bot.log
```

#### Все завершенные звонки
```bash
grep "Звонок.*завершен" /var/log/metrotech/bot.log
```

#### Последние 10 звонков
```bash
grep "Звонок.*завершен" /var/log/metrotech/bot.log | tail -10
```

### Поиск за период времени

#### Логи за сегодня
```bash
# Текущая дата в формате 2025-10-10
grep "2025-10-10" /var/log/metrotech/bot.log
```

#### Логи за последний час
```bash
# Найти файлы, измененные за последний час
find /var/log/metrotech/ -name "*.log" -mmin -60

# Или через grep с временем
grep "08:0[0-9]:" /var/log/metrotech/bot.log
```

### Статистика

#### Сколько ошибок?
```bash
grep -c "ERROR" /var/log/metrotech/bot.log
```

#### Сколько звонков?
```bash
grep -c "Новый звонок" /var/log/metrotech/bot.log
```

#### Топ-10 частых ошибок
```bash
grep "ERROR" /var/log/metrotech/bot.log | sort | uniq -c | sort -rn | head -10
```

---

## 🔄 Ротация и очистка логов {#ротация-логов}

### Что такое ротация?

**Ротация** — автоматическое архивирование старых логов, чтобы они не занимали много места.

### Наша настройка (с 10.10.2025)

**Файл конфигурации**: `/etc/logrotate.d/metrotech`

```bash
/var/log/metrotech/*.log {
    daily              # Каждый день
    rotate 7           # Хранить 7 дней
    compress           # Сжимать старые
    delaycompress      # Не сжимать последний
    missingok          # Не ругаться, если файл отсутствует
    notifempty         # Не ротировать пустые
    create 0644 root root  # Создать новый файл с правами
}
```

**Что происходит:**
1. Каждый день в 00:00 запускается ротация
2. Текущий лог переименовывается (например, `bot.log` → `bot.log.1`)
3. Старые логи сжимаются (`bot.log.2.gz`)
4. Логи старше 7 дней удаляются
5. Создается новый пустой файл

### Проверка ротации

```bash
# Проверить конфигурацию
cat /etc/logrotate.d/metrotech

# Принудительная ротация (тест)
sudo logrotate -f /etc/logrotate.d/metrotech

# Посмотреть архивные логи
ls -lh /var/log/metrotech/*.gz
```

### Ручная очистка (осторожно!)

```bash
# Очистить конкретный лог (НЕ удаляет файл!)
sudo truncate -s 0 /var/log/metrotech/bot.log

# Удалить старые архивы
sudo rm /var/log/metrotech/*.log.*.gz

# Проверить размеры перед очисткой
du -h /var/log/metrotech/
```

⚠️ **ВНИМАНИЕ:** Очистка логов **безвозвратна**! Сначала сделайте backup.

### Размеры логов

```bash
# Общий размер
du -sh /var/log/metrotech/

# По каждому файлу
du -h /var/log/metrotech/

# Отсортировать по размеру (большие сверху)
du -h /var/log/metrotech/ | sort -hr
```

---

## ❗ Частые проблемы и решения {#частые-проблемы}

### Проблема 1: "Логи не пишутся"

**Симптомы:**
```bash
tail -f /var/log/metrotech/bot.log
# Ничего не появляется
```

**Решение:**
```bash
# 1. Проверить, запущен ли сервис
sudo systemctl status metrotech-bot

# 2. Если не запущен - запустить
sudo systemctl start metrotech-bot

# 3. Проверить права на файл
ls -la /var/log/metrotech/bot.log

# 4. Посмотреть systemd логи
sudo journalctl -u metrotech-bot -n 50
```

### Проблема 2: "Файл слишком большой"

**Симптомы:**
```bash
du -h /var/log/metrotech/asterisk.log
# 961M  /var/log/metrotech/asterisk.log
```

**Решение:**
```bash
# 1. Это симлинк, нужно ротировать оригинал
sudo logrotate -f /etc/logrotate.d/asterisk

# 2. Или вручную (ОСТОРОЖНО!)
sudo truncate -s 0 /var/log/asterisk/messages.log

# 3. Или посмотреть только последние строки
tail -n 100 /var/log/metrotech/asterisk.log
```

### Проблема 3: "Permission denied"

**Симптомы:**
```bash
cat /var/log/metrotech/bot.log
# bash: /var/log/metrotech/bot.log: Permission denied
```

**Решение:**
```bash
# Использовать sudo
sudo cat /var/log/metrotech/bot.log

# Или tail (обычно работает без sudo)
tail /var/log/metrotech/bot.log
```

### Проблема 4: "Битый симлинк"

**Симптомы:**
```bash
ls -la /var/log/metrotech/asterisk.log
# lrwxrwxrwx 1 root root 30 Oct 10 08:01 asterisk.log -> /var/log/asterisk/messages.log (красный цвет!)
```

**Решение:**
```bash
# 1. Проверить, существует ли оригинал
ls -la /var/log/asterisk/messages.log

# 2. Если нет - пересоздать симлинк
sudo rm /var/log/metrotech/asterisk.log
sudo ln -s /var/log/asterisk/messages.log /var/log/metrotech/asterisk.log
```

### Проблема 5: "Горячая перезагрузка промптов не работает"

**Решение:**
```bash
# Проверить логи на наличие сообщений о перезагрузке
grep "Промпты" /var/log/metrotech/bot.log | tail -5
grep "Промпты" /var/log/metrotech/fastapi.log | tail -5

# Должны быть строки вида:
# "🔥 Горячая перезагрузка промптов включена"
# "🔄 Обнаружено изменение файла промптов"
# "✅ Промпты успешно перезагружены"
```

---

## 🛠️ Полезные команды {#полезные-команды}

### Быстрый мониторинг

```bash
# Перейти в директорию логов
cd /var/log/metrotech/

# Все логи в реальном времени
tail -f *.log

# Только логи приложений (без системных)
tail -f bot.log fastapi.log app-detailed.log

# С цветным выделением ошибок
tail -f bot.log | grep --color=auto -E "ERROR|WARN|$"
```

### Статус сервисов

```bash
# Все сервисы проекта
sudo systemctl status metrotech-bot metrotech-fastapi asterisk redis-server

# Краткий статус (только Active)
sudo systemctl status metrotech-bot metrotech-fastapi asterisk redis-server --no-pager | grep -E "(●|Active:)"

# Перезапустить все сервисы проекта
sudo systemctl restart metrotech-bot metrotech-fastapi
```

### Анализ логов

```bash
# Последние ошибки
grep -i "error" /var/log/metrotech/*.log | tail -20

# Статистика звонков за сегодня
grep "$(date +%Y-%m-%d)" /var/log/metrotech/bot.log | grep "Новый звонок" | wc -l

# Средняя длительность обработки (если есть метрики)
grep "Звонок.*завершен" /var/log/metrotech/bot.log | tail -10

# Поиск атак
grep "No matching endpoint" /var/log/metrotech/asterisk.log | tail -20
```

### Backup и восстановление

```bash
# Создать backup всех логов
sudo tar -czf /root/logs_backup_$(date +%Y%m%d_%H%M%S).tar.gz /var/log/metrotech/

# Восстановить из backup
sudo tar -xzf /root/logs_backup_20251010_120000.tar.gz -C /

# Backup только за сегодня
sudo tar -czf /root/logs_today_$(date +%Y%m%d).tar.gz /var/log/metrotech/*.log

# Посмотреть содержимое backup
tar -tzf /root/logs_backup_20251010_120000.tar.gz
```

### Экспорт для анализа

```bash
# Экспортировать ошибки в файл
grep -i "error" /var/log/metrotech/*.log > ~/errors_$(date +%Y%m%d).txt

# Экспортировать звонки за сегодня
grep "$(date +%Y-%m-%d)" /var/log/metrotech/bot.log > ~/calls_today.txt

# Статистика в CSV
echo "Date,Calls,Errors" > ~/stats.csv
for day in {01..10}; do
  date="2025-10-$day"
  calls=$(grep "$date" /var/log/metrotech/bot.log 2>/dev/null | grep -c "Новый звонок")
  errors=$(grep "$date" /var/log/metrotech/bot.log 2>/dev/null | grep -c "ERROR")
  echo "$date,$calls,$errors" >> ~/stats.csv
done
```

---

## 📚 Дополнительные ресурсы

### Документация проекта
- **Основной README**: `/root/Asterisk_bot/asterisk-vox-bot/README.md`
- **Документация**: `/root/Asterisk_bot/asterisk-vox-bot/docs/`
- **Systemd сервисы**: `/etc/systemd/system/metrotech-*.service`

### Конфигурация логирования
- **Ротация**: `/etc/logrotate.d/metrotech`
- **Python logging**: `/root/Asterisk_bot/asterisk-vox-bot/app/backend/main.py`
- **Asterisk логи**: `/etc/asterisk/logger.conf`
- **Redis логи**: `/etc/redis/redis.conf`

### Системные пути
- **Логи проекта**: `/var/log/metrotech/`
- **Asterisk логи**: `/var/log/asterisk/`
- **Redis логи**: `/var/log/redis/`
- **Systemd журналы**: `journalctl -u <service>`

---

## ✅ Чеклист для новичка

### Первое знакомство с логами

- [ ] Перейти в `/var/log/metrotech/`
- [ ] Посмотреть структуру: `ls -la`
- [ ] Прочитать последние строки: `tail bot.log`
- [ ] Запустить мониторинг: `tail -f bot.log`
- [ ] Найти ошибки: `grep -i "error" *.log`
- [ ] Проверить размеры: `du -h`
- [ ] Проверить статус сервисов: `sudo systemctl status metrotech-bot`

### Ежедневный мониторинг

- [ ] Проверить статус всех сервисов
- [ ] Посмотреть последние ошибки
- [ ] Проверить размеры логов
- [ ] Убедиться, что звонки обрабатываются
- [ ] Проверить, нет ли атак в `asterisk.log`

### При возникновении проблемы

- [ ] Проверить `bot.log` на ошибки
- [ ] Проверить `fastapi.log` на ошибки
- [ ] Посмотреть `systemd` логи: `journalctl -u metrotech-bot -n 50`
- [ ] Проверить статус сервисов
- [ ] Перезапустить проблемный сервис: `sudo systemctl restart metrotech-bot`
- [ ] Проверить, помогло ли

---

## 🎓 Заключение

Теперь вы знаете:
- ✅ Где находятся все логи (`/var/log/metrotech/`)
- ✅ Что такое симлинки и зачем они нужны
- ✅ Как читать и мониторить логи в реальном времени
- ✅ Как искать ошибки и анализировать проблемы
- ✅ Как работает ротация логов
- ✅ Как решать частые проблемы

**Главное правило:** Если что-то не работает — **первым делом смотрите в логи!**

```bash
# Ваша главная команда:
cd /var/log/metrotech/ && tail -f *.log
```

---

**Удачи в работе с логами!** 🚀

> 📞 **Проект**: Голосовой AI-ассистент "Метротэст"  
> 📅 **Обновлено**: 10.10.2025  
> 📊 **Версия гайда**: 1.0

