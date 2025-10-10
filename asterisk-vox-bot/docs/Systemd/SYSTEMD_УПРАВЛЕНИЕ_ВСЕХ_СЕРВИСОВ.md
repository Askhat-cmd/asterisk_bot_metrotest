# 🚀 Полное руководство по управлению всеми сервисами проекта через systemd

> 📅 **Обновлено**: 10.10.2025  
> 🎯 **Цель**: Управление 4 системными сервисами проекта "Метротэст"  
> 👤 **Для кого**: Администраторы и DevOps

---

## 📋 Содержание

1. [Обзор всех сервисов](#обзор-сервисов)
2. [Команды управления](#команды-управления)
3. [Мониторинг и логи](#мониторинг-и-логи)
4. [Автозапуск сервисов](#автозапуск)
5. [Горячая перезагрузка](#горячая-перезагрузка)
6. [Диагностика проблем](#диагностика)
7. [Полезные сценарии](#сценарии)

---

## 🎯 Обзор всех сервисов {#обзор-сервисов}

Проект использует **4 системных сервиса**, управляемых через **systemd**:

| # | Сервис | Назначение | Порт | Критичность |
|---|--------|------------|------|-------------|
| 1 | `asterisk.service` | 🎯 Asterisk PBX - телефония | 5038 (AMI), 8088 (ARI) | 🔴 Критичный |
| 2 | `redis-server.service` | 💾 Кеширование embeddings | 6379 | 🟡 Важный |
| 3 | `metrotech-bot.service` | 🤖 Обработчик звонков | - | 🔴 Критичный |
| 4 | `metrotech-fastapi.service` | 🌐 Админ-панель и API | 9000 | 🟢 Вспомогательный |

### 📊 Зависимости сервисов

```
┌─────────────────┐
│   Asterisk PBX  │ ← Принимает звонки
│   Порт: 5038,   │   (5038 - AMI, 8088 - ARI)
│         8088    │
└────────┬────────┘
         ↓
┌─────────────────┐
│ metrotech-bot   │ ← Обрабатывает звонки (зависит от Asterisk)
│ (stasis_handler)│
└────────┬────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
┌─────────┐ ┌──────────────────┐
│  Redis  │ │ metrotech-fastapi│
│  Cache  │ │  (admin panel)   │
│ 6379    │ │      9000        │
└─────────┘ └──────────────────┘
```

### 🌐 Порты и их назначение

| Порт | Сервис | Назначение | Доступ |
|------|--------|------------|--------|
| 5038 | Asterisk | AMI (Asterisk Manager Interface) | Внутренний |
| 8088 | Asterisk | ARI (Asterisk REST Interface) | Внутренний |
| 6379 | Redis | Кеширование embeddings | Внутренний |
| 9000 | FastAPI | Админ-панель и API | Доступен извне |

**Безопасность портов:**
- ✅ **Порт 9000** — единственный доступный из интернета (админ-панель)
- 🔒 **Порты 5038, 8088, 6379** — только для внутреннего использования
- 🔒 **SIP порт 5060** — управляется на уровне файрвола, не показан в systemd

**Зависимости сервисов:**
- ⚠️ `metrotech-bot` **не запустится** без `asterisk`
- ⚠️ `metrotech-fastapi` работает независимо
- ⚠️ `redis-server` желательно запустить **до** bot и fastapi

---

## ⚙️ Команды управления {#команды-управления}

### 🔍 Проверка статуса

#### Статус всех сервисов проекта:
```bash
sudo systemctl status asterisk redis-server metrotech-bot metrotech-fastapi
```

#### Краткий статус (только Active):
```bash
sudo systemctl status asterisk redis-server metrotech-bot metrotech-fastapi --no-pager | grep -E "(●|Active:)"
```

**Пример вывода:**
```
● asterisk.service - Asterisk PBX
     Active: active (running) since Fri 2025-10-10 06:38:15 UTC; 1h ago
● redis-server.service - Advanced key-value store
     Active: active (running) since Wed 2025-10-02 06:24:56 UTC; 1 week ago
● metrotech-bot.service - Metrotech Voice Bot (Asterisk ARI)
     Active: active (running) since Fri 2025-10-10 08:02:57 UTC; 30min ago
● metrotech-fastapi.service - Metrotech FastAPI Admin Panel & API
     Active: active (running) since Fri 2025-10-10 08:03:07 UTC; 29min ago
```

#### Статус отдельного сервиса:
```bash
# Asterisk PBX
sudo systemctl status asterisk

# Redis кеширование
sudo systemctl status redis-server

# Обработчик звонков
sudo systemctl status metrotech-bot

# Админ-панель
sudo systemctl status metrotech-fastapi
```

---

### 🔄 Перезапуск сервисов

#### Перезапуск отдельного сервиса:

```bash
# Asterisk (осторожно! прервет активные звонки)
sudo systemctl restart asterisk

# Redis (может сбросить кеш)
sudo systemctl restart redis-server

# Обработчик звонков (безопасно между звонками)
sudo systemctl restart metrotech-bot

# Админ-панель (безопасно всегда)
sudo systemctl restart metrotech-fastapi
```

#### Перезапуск всего проекта:

```bash
# Последовательный перезапуск (правильный порядок):
sudo systemctl restart asterisk
sleep 3
sudo systemctl restart redis-server
sleep 2
sudo systemctl restart metrotech-bot
sudo systemctl restart metrotech-fastapi
```

**Или одной командой (быстрее, но менее безопасно):**
```bash
sudo systemctl restart asterisk redis-server metrotech-bot metrotech-fastapi
```

---

### ⏹️ Остановка сервисов

#### Остановить отдельный сервис:
```bash
sudo systemctl stop metrotech-bot        # обработчик звонков
sudo systemctl stop metrotech-fastapi    # админ-панель
sudo systemctl stop redis-server         # кеширование
sudo systemctl stop asterisk             # телефония (осторожно!)
```

#### Остановить все сервисы проекта:
```bash
# В обратном порядке зависимостей:
sudo systemctl stop metrotech-fastapi
sudo systemctl stop metrotech-bot
sudo systemctl stop redis-server
sudo systemctl stop asterisk
```

---

### ▶️ Запуск сервисов

#### Запустить отдельный сервис:
```bash
sudo systemctl start asterisk            # телефония
sudo systemctl start redis-server        # кеширование
sudo systemctl start metrotech-bot       # обработчик звонков
sudo systemctl start metrotech-fastapi   # админ-панель
```

#### Запустить все сервисы (правильный порядок):
```bash
# 1. Сначала инфраструктура
sudo systemctl start asterisk
sudo systemctl start redis-server

# 2. Дать время на запуск
sleep 3

# 3. Затем приложения
sudo systemctl start metrotech-bot
sudo systemctl start metrotech-fastapi
```

---

### 🔁 Перезагрузка конфигурации

#### После изменения unit файлов:
```bash
# 1. Перезагрузить конфигурацию systemd
sudo systemctl daemon-reload

# 2. Перезапустить нужные сервисы
sudo systemctl restart metrotech-bot
sudo systemctl restart metrotech-fastapi
```

#### Пример (после изменения `/etc/systemd/system/metrotech-bot.service`):
```bash
sudo systemctl daemon-reload
sudo systemctl restart metrotech-bot
sudo systemctl status metrotech-bot
```

---

## 🔄 Автозапуск сервисов {#автозапуск}

### ✅ Проверка автозапуска

```bash
# Проверить статус автозапуска всех сервисов
systemctl is-enabled asterisk
systemctl is-enabled redis-server
systemctl is-enabled metrotech-bot
systemctl is-enabled metrotech-fastapi
```

**Вывод:**
- `enabled` — автозапуск **включен** ✅
- `disabled` — автозапуск **выключен** ❌

### 🟢 Включить автозапуск

```bash
# Включить для всех сервисов проекта
sudo systemctl enable asterisk
sudo systemctl enable redis-server
sudo systemctl enable metrotech-bot
sudo systemctl enable metrotech-fastapi
```

**Результат:** Сервисы запустятся автоматически после перезагрузки сервера.

### 🔴 Выключить автозапуск

```bash
# Отключить для конкретного сервиса
sudo systemctl disable metrotech-bot
sudo systemctl disable metrotech-fastapi
```

**Результат:** Сервисы НЕ запустятся после перезагрузки (нужно будет запускать вручную).

---

## 📊 Мониторинг и логи {#мониторинг-и-логи}

### 📝 Логи через journalctl (systemd)

#### Просмотр логов в реальном времени:

```bash
# Asterisk PBX
sudo journalctl -u asterisk -f

# Redis
sudo journalctl -u redis-server -f

# Обработчик звонков
sudo journalctl -u metrotech-bot -f

# Админ-панель
sudo journalctl -u metrotech-fastapi -f
```

#### Последние N строк:

```bash
# Последние 50 строк
sudo journalctl -u metrotech-bot -n 50

# Последние 100 строк с прокруткой
sudo journalctl -u metrotech-bot -n 100 -f
```

#### Логи за период:

```bash
# Логи за сегодня
sudo journalctl -u metrotech-bot --since today

# Логи за последний час
sudo journalctl -u metrotech-bot --since "1 hour ago"

# Логи между датами
sudo journalctl -u metrotech-bot --since "2025-10-10 00:00:00" --until "2025-10-10 23:59:59"
```

### 📁 Логи через файлы (централизованные)

#### Все логи в одном месте: `/var/log/metrotech/`

```bash
# Перейти в директорию логов
cd /var/log/metrotech/

# Просмотр всех логов
ls -la

# Мониторинг всех логов одновременно
tail -f *.log

# Мониторинг только приложений (без симлинков)
tail -f bot.log fastapi.log app-detailed.log
```

#### Структура логов:

| Файл | Описание | Команда просмотра |
|------|----------|-------------------|
| `bot.log` | Обработка звонков (stasis_handler) | `tail -f /var/log/metrotech/bot.log` |
| `fastapi.log` | Админ-панель и API | `tail -f /var/log/metrotech/fastapi.log` |
| `app-detailed.log` | Детальные логи FastAPI | `tail -f /var/log/metrotech/app-detailed.log` |
| `asterisk.log` | Asterisk PBX (симлинк) | `tail -f /var/log/metrotech/asterisk.log` |
| `redis.log` | Redis (симлинк) | `tail -f /var/log/metrotech/redis.log` |

### 🔍 Поиск в логах

#### Поиск ошибок:

```bash
# Ошибки в конкретном сервисе
sudo journalctl -u metrotech-bot | grep -i "error"

# Ошибки во всех логах проекта
grep -i "error" /var/log/metrotech/*.log

# Ошибки с контекстом (3 строки до/после)
grep -i "error" -A 3 -B 3 /var/log/metrotech/bot.log
```

#### Поиск по звонкам:

```bash
# Найти конкретный номер
grep "79581114700" /var/log/metrotech/bot.log

# Все завершенные звонки
grep "Звонок.*завершен" /var/log/metrotech/bot.log

# Последние 10 звонков
grep "Новый звонок" /var/log/metrotech/bot.log | tail -10
```

#### Поиск атак:

```bash
# Заблокированные попытки подключения
sudo journalctl -u asterisk | grep "No matching endpoint"

# Или в файле
tail -f /var/log/metrotech/asterisk.log | grep "No matching endpoint"
```

---

## 🔥 Горячая перезагрузка промптов {#горячая-перезагрузка}

### Что это?

**Горячая перезагрузка** — автоматическое применение изменений промптов **без перезапуска** сервисов.

### Как работает?

1. Вы изменяете промпты через админ-панель (`http://localhost:9000/logs-ui/`)
2. Промпты сохраняются в `config/prompts.json`
3. Оба процесса (`metrotech-bot` и `metrotech-fastapi`) **автоматически** замечают изменения
4. Промпты перезагружаются **в течение 5-10 секунд**

### Настройка (`.env`):

```bash
# Включить/выключить горячую перезагрузку
PROMPTS_HOT_RELOAD=true

# Интервал проверки изменений (секунды)
PROMPTS_RELOAD_INTERVAL_SEC=5
```

### Мониторинг горячей перезагрузки:

```bash
# Проверить, что горячая перезагрузка работает
grep "Горячая" /var/log/metrotech/bot.log | tail -5
grep "Горячая" /var/log/metrotech/fastapi.log | tail -5

# Мониторинг в реальном времени
tail -f /var/log/metrotech/bot.log | grep -E "(Горячая|Промпты|перезагружены)"
tail -f /var/log/metrotech/fastapi.log | grep -E "(Горячая|Промпты|перезагружены)"
```

**Пример вывода:**
```
2025-10-10 08:03:01,737 - __main__ - INFO - 🔥 Горячая перезагрузка промптов включена (интервал: 5с)
2025-10-10 08:15:23,456 - __main__ - INFO - 🔄 Обнаружено изменение файла промптов, перезагружаем...
2025-10-10 08:15:23,489 - __main__ - INFO - ✅ Промпты успешно перезагружены из файла
```

### Когда нужен перезапуск?

**НЕ нужен** перезапуск для:
- ✅ Изменения промптов (горячая перезагрузка)
- ✅ Изменения базы знаний (если перегенерировать embeddings)

**Нужен** перезапуск для:
- ⚠️ Изменения переменных окружения (`.env`)
- ⚠️ Изменения кода Python
- ⚠️ Изменения systemd конфигурации

---

## 🔧 Диагностика проблем {#диагностика}

### ❌ Сервис не запускается

#### 1. Проверить статус и ошибки:
```bash
sudo systemctl status metrotech-bot
```

**Если видите "failed" или "inactive":**

#### 2. Посмотреть детальные логи:
```bash
sudo journalctl -u metrotech-bot -n 50 --no-pager
```

#### 3. Проверить unit файл:
```bash
sudo systemctl cat metrotech-bot
```

#### 4. Проверить зависимости:
```bash
# Для metrotech-bot нужен asterisk
sudo systemctl status asterisk
```

#### 5. Попробовать запустить вручную:
```bash
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
python app/backend/asterisk/stasis_handler_optimized.py
```

### ⚠️ Сервис постоянно перезапускается

#### Проверить причину перезапусков:
```bash
sudo journalctl -u metrotech-bot | grep -E "(Started|Stopped|Failed)"
```

#### Проверить параметры перезапуска:
```bash
sudo systemctl show metrotech-bot | grep -E "Restart|RestartSec"
```

**Должно быть:**
```
Restart=always
RestartSec=10s
```

### 🔴 Asterisk не работает

#### Проверка основных компонентов:

```bash
# 1. Статус сервиса
sudo systemctl status asterisk

# 2. Подключение к CLI
sudo asterisk -rvvv

# 3. Проверка endpoints
sudo asterisk -rx "pjsip show endpoints"

# 4. Проверка ARI
curl -u asterisk:asterisk123 http://localhost:8088/ari/asterisk/info

# 5. Проверка Stasis приложения
sudo asterisk -rx "stasis show apps"
# Должно показать: asterisk-bot
```

### 🟡 Redis не работает

#### Проверка Redis:

```bash
# 1. Статус сервиса
sudo systemctl status redis-server

# 2. Подключение к Redis
redis-cli ping
# Должно вернуть: PONG

# 3. Проверка порта
sudo netstat -tulpn | grep 6379

# 4. Логи Redis
sudo journalctl -u redis-server -n 30
```

### 🤖 metrotech-bot не обрабатывает звонки

#### Чеклист диагностики:

```bash
# 1. Проверить статус
sudo systemctl status metrotech-bot

# 2. Проверить подключение к ARI
curl -u asterisk:asterisk123 http://localhost:8088/ari/asterisk/info

# 3. Проверить Stasis приложение
sudo asterisk -rx "stasis show apps"

# 4. Проверить логи бота
tail -50 /var/log/metrotech/bot.log

# 5. Проверить логи Asterisk
tail -50 /var/log/metrotech/asterisk.log

# 6. Перезапустить бота
sudo systemctl restart metrotech-bot

# 7. Мониторить в реальном времени
tail -f /var/log/metrotech/bot.log
```

### 🌐 Админ-панель недоступна

#### Проверка FastAPI:

```bash
# 1. Статус сервиса
sudo systemctl status metrotech-fastapi

# 2. Проверить порт 9000
sudo netstat -tulpn | grep 9000

# 3. Проверить доступность
curl http://localhost:9000/

# 4. Логи FastAPI
tail -50 /var/log/metrotech/fastapi.log

# 5. Перезапустить
sudo systemctl restart metrotech-fastapi
```

---

## 💡 Полезные сценарии {#сценарии}

### 🔄 Сценарий 1: Обновление кода

```bash
# 1. Остановить сервисы приложения (Asterisk оставить!)
sudo systemctl stop metrotech-bot metrotech-fastapi

# 2. Обновить код (git pull, изменения и т.д.)
cd /root/Asterisk_bot/asterisk-vox-bot
git pull

# 3. Обновить зависимости (если нужно)
source venv/bin/activate
pip install -r requirements.txt

# 4. Запустить сервисы обратно
sudo systemctl start metrotech-bot metrotech-fastapi

# 5. Проверить статус
sudo systemctl status metrotech-bot metrotech-fastapi
```

### 🔧 Сценарий 2: Изменение .env

```bash
# 1. Отредактировать .env
nano /root/Asterisk_bot/asterisk-vox-bot/.env

# 2. Перезапустить только затронутые сервисы
sudo systemctl restart metrotech-bot metrotech-fastapi

# 3. Проверить логи
tail -f /var/log/metrotech/bot.log
tail -f /var/log/metrotech/fastapi.log
```

### 🚨 Сценарий 3: Экстренный перезапуск всего

```bash
# Полный перезапуск всех компонентов проекта
sudo systemctl restart asterisk
sleep 5
sudo systemctl restart redis-server
sleep 2
sudo systemctl restart metrotech-bot
sudo systemctl restart metrotech-fastapi

# Проверить что все запустилось
sudo systemctl status asterisk redis-server metrotech-bot metrotech-fastapi --no-pager | grep -E "(●|Active:)"
```

### 📦 Сценарий 4: Перезагрузка сервера

```bash
# 1. Проверить что автозапуск включен для всех сервисов
systemctl is-enabled asterisk redis-server metrotech-bot metrotech-fastapi

# 2. Если не все enabled - включить
sudo systemctl enable asterisk redis-server metrotech-bot metrotech-fastapi

# 3. Перезагрузить сервер
sudo reboot

# 4. После перезагрузки - проверить статус
sudo systemctl status asterisk redis-server metrotech-bot metrotech-fastapi
```

### 🔍 Сценарий 5: Диагностика медленной работы

```bash
# 1. Проверить загрузку CPU и RAM
top

# 2. Проверить процессы Python
ps aux | grep python

# 3. Проверить логи на ошибки
grep -i "error\|timeout\|slow" /var/log/metrotech/*.log

# 4. Проверить подключения к внешним API
grep "OpenAI\|Yandex" /var/log/metrotech/bot.log | tail -20

# 5. Проверить Redis
redis-cli info stats

# 6. Проверить Asterisk каналы
sudo asterisk -rx "core show channels"
```

### 🧹 Сценарий 6: Очистка и обслуживание

```bash
# 1. Остановить сервисы (кроме Asterisk)
sudo systemctl stop metrotech-bot metrotech-fastapi

# 2. Очистить старые логи (осторожно!)
sudo truncate -s 0 /var/log/metrotech/bot.log
sudo truncate -s 0 /var/log/metrotech/fastapi.log

# 3. Очистить кеш Redis (если нужно)
redis-cli FLUSHALL

# 4. Перегенерировать embeddings (если нужно)
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
python scripts/create_embeddings.py

# 5. Запустить сервисы обратно
sudo systemctl start metrotech-bot metrotech-fastapi

# 6. Проверить
sudo systemctl status metrotech-bot metrotech-fastapi
```

---

## 📚 Дополнительные ресурсы

### Файлы конфигурации systemd:

```bash
# Просмотр unit файлов
sudo systemctl cat asterisk
sudo systemctl cat redis-server
sudo systemctl cat metrotech-bot
sudo systemctl cat metrotech-fastapi

# Редактирование (через override)
sudo systemctl edit metrotech-bot
sudo systemctl edit metrotech-fastapi
```

### Расположение файлов:

- **Unit файлы**: `/etc/systemd/system/metrotech-*.service`
- **Логи проекта**: `/var/log/metrotech/`
- **Логи systemd**: `journalctl -u <service>`
- **Конфигурация проекта**: `/root/Asterisk_bot/asterisk-vox-bot/.env`
- **Код проекта**: `/root/Asterisk_bot/asterisk-vox-bot/`

### Полезные команды systemd:

```bash
# Список всех сервисов проекта
systemctl list-units | grep -E "asterisk|redis|metrotech"

# Детальная информация о сервисе
systemctl show metrotech-bot

# Зависимости сервиса
systemctl list-dependencies metrotech-bot

# История перезапусков
systemctl list-timers
```

---

## ✅ Чеклист ежедневной проверки

### Утренняя проверка:

- [ ] Проверить статус всех 4 сервисов
- [ ] Посмотреть логи на ошибки за ночь
- [ ] Проверить наличие атак в Asterisk логах
- [ ] Убедиться что горячая перезагрузка работает
- [ ] Проверить размеры логов
- [ ] Проверить использование RAM/CPU

### Команды для чеклиста:

```bash
# 1. Статус сервисов
sudo systemctl status asterisk redis-server metrotech-bot metrotech-fastapi --no-pager | grep -E "(●|Active:)"

# 2. Ошибки за последние 12 часов
sudo journalctl --since "12 hours ago" | grep -i "error" | tail -20

# 3. Атаки
grep "No matching endpoint" /var/log/metrotech/asterisk.log | tail -10

# 4. Горячая перезагрузка
grep "Горячая\|перезагружены" /var/log/metrotech/bot.log | tail -3

# 5. Размеры логов
du -h /var/log/metrotech/

# 6. Ресурсы
free -h
top -bn1 | head -5
```

---

## 🆘 Когда нужна помощь

### Критические проблемы (требуют немедленного внимания):

1. **Asterisk не запускается** → Звонки не работают
2. **metrotech-bot падает** → Звонки не обрабатываются
3. **Высокая нагрузка CPU/RAM** → Система может упасть
4. **Ошибки "Out of memory"** → Критично!

### Где искать помощь:

- **Документация проекта**: `/root/Asterisk_bot/asterisk-vox-bot/docs/`
- **Логи systemd**: `sudo journalctl -xe`
- **Логи приложения**: `/var/log/metrotech/`
- **Основной README**: `/root/Asterisk_bot/asterisk-vox-bot/README.md`
- **Гайд по логированию**: `/root/Asterisk_bot/asterisk-vox-bot/docs/LOGGING_GUIDE.md`

---

**Дата создания**: 10.10.2025  
**Версия**: 1.0  
**Автор**: Системная документация проекта "Метротэст"

> 🚀 **Система готова к работе!** Все 4 сервиса под управлением systemd с автозапуском.

