<!-- a542025b-e1a2-4844-9474-370c9770d469 201a36fa-7f87-45b2-b33e-f738d4e1e03e -->
# Добавление FastAPI в systemd

## Цель

Добавить FastAPI (админ-панель) под управление systemd для автозапуска и единообразного управления всеми компонентами проекта.

## Текущее состояние

- ✅ Asterisk - управляется systemd
- ✅ Redis - управляется systemd  
- ✅ Stasis Handler - управляется systemd (`metrotech-bot.service`)
- ❌ FastAPI - запущен вручную, НЕ перезапускается автоматически

## Риски и меры безопасности

### 🛡️ Что НЕ будет затронуто:

- ✅ Asterisk продолжит работать
- ✅ Stasis Handler продолжит работать
- ✅ Redis продолжит работать
- ✅ Текущие звонки НЕ прервутся
- ✅ Существующий процесс FastAPI продолжит работать до его остановки

### 🔄 Что будет изменено:

- Создан новый файл `/etc/systemd/system/metrotech-fastapi.service`
- FastAPI будет остановлен и перезапущен через systemd
- После этого FastAPI будет автоматически запускаться при перезагрузке

### ↩️ Возможность отката:

Если что-то пойдет не так, можно быстро вернуться:

```bash
# Остановить новый сервис
sudo systemctl stop metrotech-fastapi
# Запустить FastAPI вручную как раньше
cd /root/Asterisk_bot/asterisk-vox-bot && source venv/bin/activate && nohup python app/backend/main.py > /dev/null 2>&1 &
```

## Шаги реализации

### Шаг 1: Создать резервную копию (на всякий случай)

Создадим backup текущего состояния для возможности быстрого отката:

```bash
cd /root/Asterisk_bot
tar -czf project_backup/fastapi_systemd_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
  /etc/systemd/system/metrotech-bot.service \
  asterisk-vox-bot/.env 2>/dev/null || true
```

### Шаг 2: Проверить текущий процесс FastAPI

Запишем PID текущего процесса, чтобы знать, что останавливать:

```bash
ps aux | grep "python app/backend/main.py" | grep -v grep
```

### Шаг 3: Создать systemd unit файл для FastAPI

Файл: `/etc/systemd/system/metrotech-fastapi.service`

```ini
[Unit]
Description=Metrotech FastAPI Admin Panel & API
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/Asterisk_bot/asterisk-vox-bot
Environment="PATH=/root/Asterisk_bot/asterisk-vox-bot/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONDONTWRITEBYTECODE=1"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/bin/bash -lc 'source /root/Asterisk_bot/asterisk-vox-bot/venv/bin/activate && exec python /root/Asterisk_bot/asterisk-vox-bot/app/backend/main.py'
Restart=always
RestartSec=10
StandardOutput=append:/root/Asterisk_bot/asterisk-vox-bot/fastapi.log
StandardError=append:/root/Asterisk_bot/asterisk-vox-bot/fastapi.log

[Install]
WantedBy=multi-user.target
```

**Особенности конфигурации:**

- `After=redis-server.service` - запуск после Redis (FastAPI нужен Redis для кеширования)
- `Restart=always` - автоматический перезапуск при сбое
- `RestartSec=10` - пауза 10 секунд перед перезапуском
- Отдельный лог файл `fastapi.log` (не путается с `bot.log`)

### Шаг 4: Перезагрузить конфигурацию systemd

```bash
sudo systemctl daemon-reload
```

**Безопасно:** Только перечитывает конфигурацию, ничего не останавливает.

### Шаг 5: Включить автозапуск

```bash
sudo systemctl enable metrotech-fastapi
```

**Безопасно:** Только добавляет симлинк для автозапуска, не запускает сервис.

### Шаг 6: Остановить старый процесс FastAPI

```bash
# Найти PID процесса main.py
PID=$(ps aux | grep "python app/backend/main.py" | grep -v grep | awk '{print $2}')
# Мягко остановить (SIGTERM)
kill $PID
# Подождать 2 секунды
sleep 2
```

**Влияние:** Админ-панель будет недоступна 2-5 секунд. Звонки продолжат работать.

### Шаг 7: Запустить FastAPI через systemd

```bash
sudo systemctl start metrotech-fastapi
```

### Шаг 8: Проверить статус

```bash
sudo systemctl status metrotech-fastapi --no-pager
```

### Шаг 9: Проверить логи горячей перезагрузки

```bash
tail -50 /root/Asterisk_bot/asterisk-vox-bot/fastapi.log | grep -E "(Горячая|мониторинг|Агент)"
```

Должны увидеть:

```
🔥 Горячая перезагрузка промптов включена (интервал: 5.0с)
🔍 Запущен мониторинг файла промптов: config/prompts.json
```

### Шаг 10: Проверить доступность админ-панели

```bash
curl -s http://localhost:8000/api/prompts | head -20
```

Должен вернуть JSON с промптами.

## Проверка после внедрения

### Тест 1: Все сервисы запущены

```bash
sudo systemctl status asterisk metrotech-bot metrotech-fastapi redis-server --no-pager
```

Все должны быть `active (running)`.

### Тест 2: Админ-панель доступна

Открыть в браузере админ-панель и проверить:

- Логи звонков отображаются
- Можно изменить промпты
- Можно загрузить базу знаний

### Тест 3: Горячая перезагрузка работает

1. Изменить промпт через админ-панель
2. Подождать 5-10 секунд
3. Проверить логи: `tail -f /root/Asterisk_bot/asterisk-vox-bot/bot.log | grep "Промпты обновлены"`

### Тест 4: Звонки работают

Позвонить боту и убедиться, что он отвечает.

## Итоговые команды управления

После внедрения все сервисы будут управляться единообразно:

```bash
# Статус всех компонентов
sudo systemctl status asterisk redis-server metrotech-bot metrotech-fastapi

# Перезапуск отдельного компонента
sudo systemctl restart metrotech-fastapi

# Перезапуск всего проекта (если нужно)
sudo systemctl restart asterisk redis-server metrotech-bot metrotech-fastapi

# Логи конкретного сервиса
sudo journalctl -u metrotech-fastapi -f
# или
tail -f /root/Asterisk_bot/asterisk-vox-bot/fastapi.log

# Остановка/запуск
sudo systemctl stop metrotech-fastapi
sudo systemctl start metrotech-fastapi
```

## План отката (если что-то пошло не так)

Если возникнут проблемы:

```bash
# 1. Остановить новый сервис
sudo systemctl stop metrotech-fastapi
sudo systemctl disable metrotech-fastapi

# 2. Удалить unit файл
sudo rm /etc/systemd/system/metrotech-fastapi.service
sudo systemctl daemon-reload

# 3. Запустить FastAPI вручную как раньше
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
nohup python app/backend/main.py > /dev/null 2>&1 &

# 4. Проверить, что FastAPI работает
ps aux | grep "main.py"
curl http://localhost:8000/api/prompts
```

## Преимущества после внедрения

1. ✅ **Автозапуск** - FastAPI запустится автоматически после перезагрузки сервера
2. ✅ **Автоперезапуск** - при сбое FastAPI перезапустится автоматически через 10 секунд
3. ✅ **Единообразное управление** - все компоненты через systemctl
4. ✅ **Отдельные логи** - логи FastAPI в `fastapi.log`, не путаются с логами звонков
5. ✅ **Горячая перезагрузка** - работает автоматически в обоих процессах
6. ✅ **Мониторинг** - можно использовать стандартные инструменты systemd для мониторинга

## Время простоя

- **Asterisk:** 0 секунд (не затрагивается)
- **Stasis Handler:** 0 секунд (не затрагивается)  
- **Redis:** 0 секунд (не затрагивается)
- **FastAPI (админ-панель):** 2-5 секунд (время перезапуска)
- **Звонки:** 0 секунд простоя (продолжают обрабатываться)

### To-dos

- [ ] Добавить переменные PROMPTS_HOT_RELOAD и PROMPTS_RELOAD_INTERVAL_SEC в .env файл
- [ ] Добавить импорт threading в agent.py
- [ ] Добавить инициализацию горячей перезагрузки в метод __init__ класса Agent
- [ ] Добавить методы _get_file_mtime, _watch_prompts_file и reload_prompts в класс Agent
- [ ] Обновить существующий метод reload() для использования нового reload_prompts()
- [ ] Улучшить атомарную запись файла в FastAPI endpoint /api/prompts
- [ ] Перезапустить systemd сервис и протестировать горячую перезагрузку