<!-- a542025b-e1a2-4844-9474-370c9770d469 201a36fa-7f87-45b2-b33e-f738d4e1e03e -->
# Горячая перезагрузка промптов для фонового режима

## Описание проблемы

FastAPI (main.py) и stasis_handler работают в отдельных процессах. При изменении промптов через админ-панель, FastAPI сохраняет файл и перезагружает свой агент, но stasis_handler продолжает работать со старыми промптами из памяти.

## Решение

Добавить фоновый поток в класс `Agent`, который будет периодически проверять время модификации файла `prompts.json` и автоматически перезагружать промпты при обнаружении изменений.

## Шаги реализации

### 1. Добавить переменные окружения в `.env`

Файл: `/root/Asterisk_bot/asterisk-vox-bot/.env`

Добавить в конец файла новую секцию:

```bash
# HOT RELOAD настройки
#__________________________________________________________________
# PROMPTS_HOT_RELOAD — включить/выключить автоматическую перезагрузку промптов
PROMPTS_HOT_RELOAD=true
# PROMPTS_RELOAD_INTERVAL_SEC — интервал проверки изменений файла промптов (в секундах)
PROMPTS_RELOAD_INTERVAL_SEC=5
```

**Важно:** Используем секунды вместо миллисекунд для простоты, и увеличенный интервал (5 секунд по умолчанию) для снижения нагрузки.

### 2. Модифицировать класс `Agent` 

Файл: `/root/Asterisk_bot/asterisk-vox-bot/app/backend/rag/agent.py`

#### 2.1. Добавить импорты

В начало файла (после существующих импортов):

```python
import threading
```

#### 2.2. Обновить метод `__init__`

После инициализации промптов (`self.prompts = self.load_prompts()`), добавить:

```python
# Горячая перезагрузка промптов (для кросс-процессной синхронизации)
self.prompts_file_path = os.getenv("PROMPTS_FILE_PATH")
self._prompts_mtime = self._get_file_mtime(self.prompts_file_path) if self.prompts_file_path else -1.0
self._hot_reload_enabled = os.getenv("PROMPTS_HOT_RELOAD", "true").lower() == "true"
self._reload_interval = float(os.getenv("PROMPTS_RELOAD_INTERVAL_SEC", "5"))

if self._hot_reload_enabled and self.prompts_file_path:
    logger.info(f"🔥 Горячая перезагрузка промптов включена (интервал: {self._reload_interval}с)")
    reload_thread = threading.Thread(target=self._watch_prompts_file, daemon=True, name="PromptsWatcher")
    reload_thread.start()
else:
    logger.info("ℹ️  Горячая перезагрузка промптов отключена")
```

#### 2.3. Добавить вспомогательные методы

В конец класса `Agent` добавить:

```python
def _get_file_mtime(self, file_path: str) -> float:
    """Получает время последней модификации файла."""
    try:
        return os.path.getmtime(file_path)
    except Exception as e:
        logger.debug(f"Не удалось получить mtime для {file_path}: {e}")
        return -1.0

def _watch_prompts_file(self):
    """
    Фоновый поток: следит за изменениями файла промптов.
    При обнаружении изменений вызывает reload_prompts().
    """
    logger.info(f"🔍 Запущен мониторинг файла промптов: {self.prompts_file_path}")
    
    while True:
        try:
            time.sleep(self._reload_interval)
            
            current_mtime = self._get_file_mtime(self.prompts_file_path)
            
            if current_mtime > 0 and current_mtime != self._prompts_mtime:
                logger.info(f"🔄 Обнаружено изменение файла промптов, перезагружаем...")
                self.reload_prompts()
                self._prompts_mtime = current_mtime
                logger.info("✅ Промпты успешно перезагружены из файла")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в потоке мониторинга промптов: {e}", exc_info=True)

def reload_prompts(self):
    """
    Явная перезагрузка только промптов без полной перезагрузки агента.
    Вызывается из фонового потока или FastAPI.
    """
    try:
        old_prompts = self.prompts.copy() if self.prompts else {}
        self.prompts = self.load_prompts()
        
        # Проверяем, действительно ли промпты изменились
        if old_prompts != self.prompts:
            logger.info("📝 Промпты обновлены в памяти агента")
            return True
        else:
            logger.debug("ℹ️  Промпты не изменились")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при перезагрузке промптов: {e}", exc_info=True)
        return False
```

#### 2.4. Обновить существующий метод `reload()`

Заменить прямое присваивание `self.prompts = self.load_prompts()` на вызов нового метода:

```python
def reload(self):
    """Перезагружает промпты, векторную базу данных и RAG-цепочку."""
    logger.info("🔃 Получена команда на перезагрузку агента...")
    try:
        self.reload_prompts()  # используем новый метод вместо прямого load_prompts()
        # Обновим конфигурацию моделей
        self.llm = self._create_llm_from_env(primary=True)
        self._initialize_rag_chain()
        logger.info("✅ Агент успешно перезагружен с новой базой знаний и промптами.")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при перезагрузке агента: {e}", exc_info=True)
        return False
```

### 3. Улучшить атомарную запись в FastAPI (опционально, но рекомендуется)

Файл: `/root/Asterisk_bot/asterisk-vox-bot/app/backend/main.py`

Добавить импорт:

```python
import tempfile
```

Обновить endpoint `/api/prompts`:

```python
@app.post("/api/prompts", dependencies=[Depends(get_api_key)])
async def update_prompts(payload: PromptsUpdatePayload):
    prompts_file = os.getenv("PROMPTS_FILE_PATH")
    if not prompts_file:
        raise HTTPException(status_code=500, detail="Переменная окружения PROMPTS_FILE_PATH не установлена.")
    try:
        data = payload.dict()
        
        # Атомарная запись: temp file + rename
        dir_path = os.path.dirname(prompts_file) or "."
        os.makedirs(dir_path, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(
            mode='w', 
            delete=False, 
            dir=dir_path, 
            prefix=".prompts_", 
            suffix=".tmp", 
            encoding='utf-8'
        ) as tf:
            json.dump(data, tf, ensure_ascii=False, indent=2)
            tf.flush()
            os.fsync(tf.fileno())
            tmp_path = tf.name
        
        # Атомарный rename
        os.replace(tmp_path, prompts_file)
        
        # Локальный агент FastAPI может перезагрузиться немедленно
        if agent and hasattr(agent, 'reload_prompts'):
            agent.reload_prompts()

        return JSONResponse(content={"message": "Промпты успешно обновлены."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить промпты: {e}")
```

### 4. Тестирование

После применения изменений:

1. Перезапустить systemd сервис один раз для загрузки нового кода:
   ```bash
   sudo systemctl restart metrotech-bot
   ```

2. Проверить логи, что мониторинг запущен:
   ```bash
   sudo journalctl -u metrotech-bot -f | grep -E "(Горячая|мониторинг)"
   ```

3. Изменить промпты через админ-панель

4. В течение 5 секунд проверить логи на наличие сообщения о перезагрузке:
   ```bash
   sudo journalctl -u metrotech-bot -f | grep "перезагружаем"
   ```

5. Позвонить боту и убедиться, что он использует новые промпты

## Преимущества решения

- Не требует изменения архитектуры проекта
- Работает автономно в каждом процессе
- Не требует Redis или других внешних механизмов синхронизации
- Можно отключить через `.env` переменную
- Настраиваемый интервал проверки
- Безопасная атомарная запись файла
- Минимальная нагрузка на систему

## Риски и меры безопасности

- Фоновый поток работает как daemon, автоматически завершится при остановке процесса
- Все ошибки логируются, но не останавливают работу агента
- При ошибке чтения файла старые промпты остаются в памяти
- Атомарная запись предотвращает чтение поврежденного файла

### To-dos

- [ ] Добавить переменные PROMPTS_HOT_RELOAD и PROMPTS_RELOAD_INTERVAL_SEC в .env файл
- [ ] Добавить импорт threading в agent.py
- [ ] Добавить инициализацию горячей перезагрузки в метод __init__ класса Agent
- [ ] Добавить методы _get_file_mtime, _watch_prompts_file и reload_prompts в класс Agent
- [ ] Обновить существующий метод reload() для использования нового reload_prompts()
- [ ] Улучшить атомарную запись файла в FastAPI endpoint /api/prompts
- [ ] Перезапустить systemd сервис и протестировать горячую перезагрузку