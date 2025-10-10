<!-- a542025b-e1a2-4844-9474-370c9770d469 201a36fa-7f87-45b2-b33e-f738d4e1e03e -->
# Централизация логирования проекта

## Цель

Собрать все логи проекта в одну директорию `/var/log/metrotech/` для удобного мониторинга и управления.

## Текущее состояние логов

### Логи внутри проекта:

- `/root/Asterisk_bot/asterisk-vox-bot/bot.log` (425KB) - stasis_handler
- `/root/Asterisk_bot/asterisk-vox-bot/fastapi.log` (16KB) - FastAPI админ-панель
- `/root/Asterisk_bot/asterisk-vox-bot/data/logs/app.log` (247KB) - детальные логи FastAPI
- `/root/Asterisk_bot/asterisk-vox-bot/stasis.log` (8.9KB) - устаревший
- `/root/Asterisk_bot/asterisk-vox-bot/data/logs/stasis_handler.out` (2.6KB) - устаревший

### Системные логи:

- `/var/log/asterisk/messages.log` (961MB!) - Asterisk PBX
- `/var/log/redis/redis-server.log` - Redis

## Целевая структура

```
/var/log/metrotech/
├── bot.log                    # stasis_handler (симлинк или прямая запись)
├── fastapi.log                # FastAPI API (симлинк или прямая запись)
├── asterisk.log               # симлинк на /var/log/asterisk/messages.log
├── redis.log                  # симлинк на /var/log/redis/redis-server.log
└── archive/                   # архив старых логов
    └── 2025-10/
```

## Преимущества

- ✅ Все логи в одном месте
- ✅ Легко настроить мониторинг
- ✅ Удобно для backup
- ✅ Стандартизированная структура
- ✅ Не требует изменения кода

## Шаги реализации

### Шаг 1: Создать директорию для централизованных логов

```bash
sudo mkdir -p /var/log/metrotech/archive
sudo chown root:root /var/log/metrotech
sudo chmod 755 /var/log/metrotech
```

### Шаг 2: Обновить systemd сервисы для записи в новое место

**Обновить `metrotech-bot.service`:**

- Изменить `StandardOutput` и `StandardError` на `/var/log/metrotech/bot.log`

**Обновить `metrotech-fastapi.service`:**

- Изменить `StandardOutput` и `StandardError` на `/var/log/metrotech/fastapi.log`

### Шаг 3: Создать симлинки на системные логи

```bash
ln -s /var/log/asterisk/messages.log /var/log/metrotech/asterisk.log
ln -s /var/log/redis/redis-server.log /var/log/metrotech/redis.log
```

### Шаг 4: Обновить конфигурацию Python логирования (app.log)

Изменить в `main.py`:

```python
# Было:
log_file = "data/logs/app.log"

# Станет:
log_file = "/var/log/metrotech/app-detailed.log"
```

### Шаг 5: Настроить ротацию логов

Создать файл `/etc/logrotate.d/metrotech`:

```
/var/log/metrotech/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        systemctl reload metrotech-bot metrotech-fastapi > /dev/null 2>&1 || true
    endscript
}
```

### Шаг 6: Перезапустить сервисы с новыми настройками

```bash
sudo systemctl daemon-reload
sudo systemctl restart metrotech-bot
sudo systemctl restart metrotech-fastapi
```

### Шаг 7: Очистить устаревшие логи

```bash
# Переместить устаревшие логи в архив
mkdir -p /var/log/metrotech/archive/old-logs
mv /root/Asterisk_bot/asterisk-vox-bot/stasis.log /var/log/metrotech/archive/old-logs/
mv /root/Asterisk_bot/asterisk-vox-bot/data/logs/stasis_handler.out /var/log/metrotech/archive/old-logs/
```

### Шаг 8: Обновить README с новыми путями логов

## Проверка после внедрения

```bash
# Проверить структуру
ls -la /var/log/metrotech/

# Проверить, что логи пишутся
tail -f /var/log/metrotech/bot.log
tail -f /var/log/metrotech/fastapi.log

# Проверить симлинки
ls -la /var/log/metrotech/*.log

# Проверить работу сервисов
sudo systemctl status metrotech-bot metrotech-fastapi
```

## Команды мониторинга после централизации

```bash
# Просмотр всех логов из одного места
cd /var/log/metrotech/

# Мониторинг всех логов одновременно
tail -f *.log

# Поиск по всем логам
grep "ERROR" /var/log/metrotech/*.log

# Размеры логов
du -h /var/log/metrotech/

# Логи за последний час
find /var/log/metrotech/ -name "*.log" -mmin -60
```

## Риски и меры безопасности

### 🛡️ Что НЕ будет затронуто:

- ✅ Asterisk продолжит работать
- ✅ Redis продолжит работать
- ✅ Текущие звонки НЕ прервутся
- ✅ Старые логи останутся доступны

### 🔄 Что изменится:

- Новые логи будут писаться в `/var/log/metrotech/`
- Systemd сервисы перезапустятся (5-10 секунд простоя админ-панели)
- Старые файлы логов переместятся в архив

### ↩️ Возможность отката:

Если что-то пойдет не так:

```bash
# Откатить systemd конфигурацию
sudo cp /var/log/metrotech/archive/metrotech-bot.service.backup /etc/systemd/system/metrotech-bot.service
sudo cp /var/log/metrotech/archive/metrotech-fastapi.service.backup /etc/systemd/system/metrotech-fastapi.service
sudo systemctl daemon-reload
sudo systemctl restart metrotech-bot metrotech-fastapi
```

## Время выполнения

- Подготовка: 5 минут
- Реализация: 10 минут
- Проверка: 5 минут
- **Общее время: ~20 минут**

## Время простоя

- **Asterisk:** 0 секунд
- **Redis:** 0 секунд
- **Stasis Handler (звонки):** 5-10 секунд (перезапуск)
- **FastAPI (админ-панель):** 5-10 секунд (перезапуск)

### To-dos

- [ ] Добавить переменные PROMPTS_HOT_RELOAD и PROMPTS_RELOAD_INTERVAL_SEC в .env файл
- [ ] Добавить импорт threading в agent.py
- [ ] Добавить инициализацию горячей перезагрузки в метод __init__ класса Agent
- [ ] Добавить методы _get_file_mtime, _watch_prompts_file и reload_prompts в класс Agent
- [ ] Обновить существующий метод reload() для использования нового reload_prompts()
- [ ] Улучшить атомарную запись файла в FastAPI endpoint /api/prompts
- [ ] Перезапустить systemd сервис и протестировать горячую перезагрузку