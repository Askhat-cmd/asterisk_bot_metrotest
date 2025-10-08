"""
Основной файл приложения.
- WebSocket-сервер для общения с Voximplant
- API для просмотра логов
- Статика для UI логов
"""
import os, logging, uuid, json, asyncio, io, shutil, time, re
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status, UploadFile, File, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.backend.rag.agent import Agent
from app.backend.utils.text_normalizer import normalize as normalize_text
from app.backend.services.log_storage import insert_log, query_logs, to_csv, delete_all_logs
from scripts.create_embeddings import recreate_embeddings

# --- Инициализация ---
load_dotenv()

# --- Конфигурация логирования ---
# Создаем директорию для логов, если ее нет
os.makedirs("data/logs", exist_ok=True)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file = "data/logs/app.log"

# Настраиваем ротируемый файловый обработчик
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Получаем корневой логгер и ДОБАВЛЯЕМ наш обработчик, не удаляя существующие.
# Это предотвращает конфликты с логгерами Gunicorn/Uvicorn.
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)
root_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)


app = FastAPI()
app.mount("/logs-ui", StaticFiles(directory="app/frontend/logs-ui", html=True), name="logs-ui")


# --- Вспомогательные функции ---

def duplicate_headers_without_hashes(text: str) -> str:
    """
    Дублирует заголовки Markdown (от h1 до h6) в тексте,
    добавляя версию без хэшей в следующей строке.
    """
    def replacer(match):
        header_line = match.group(0)
        clean_header = header_line.lstrip('#').strip()
        return f"{header_line}\n{clean_header}"

    processed_text = re.sub(r"^(#{1,6}\s.+)", replacer, text, flags=re.MULTILINE)
    return processed_text


def _update_env_file(vars_to_set: Dict[str, str]) -> None:
    env_path = os.path.join(os.getcwd(), ".env")
    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    keys = set(vars_to_set.keys())
    new_lines: list[str] = []
    for line in lines:
        if not line or line.strip().startswith("#"):
            new_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in keys:
            new_lines.append(f"{key}={vars_to_set[key]}")
            keys.remove(key)
        else:
            new_lines.append(line)
    for k in keys:
        new_lines.append(f"{k}={vars_to_set[k]}")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")


# --- Модели данных (Pydantic) ---

class PromptsUpdatePayload(BaseModel):
    """Схема для валидации входящих данных при обновлении промптов."""
    greeting: str = Field(..., min_length=1, description="Приветственное сообщение бота.")
    contextualize_q_system_prompt: str = Field(..., min_length=1, description="Системный промпт для контекстуализации.")
    qa_system_prompt: str = Field(..., min_length=1, description="Основной системный промпт для ответов на вопросы.")

class SearchSettingsPayload(BaseModel):
    kb_top_k: int | None = Field(None, ge=1, le=20)
    kb_fallback_threshold: float | None = Field(None, ge=0.0, le=1.0)

class ModelSettingsPayload(BaseModel):
    llm_model_primary: str | None = Field(None, description="Имя основной модели, например 'gpt-4o-mini'")
    llm_model_fallback: str | None = Field(None, description="Имя запасной модели")
    llm_temperature: float | None = Field(None, ge=0.0, le=1.0, description="Температура выборки (0..1)")

class NormalizeRequest(BaseModel):
    text: str


# --- Безопасность ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key: str = Security(api_key_header)):
    """Проверяет API ключ из заголовка."""
    expected_api_key = os.getenv("API_SECRET_KEY")
    if not expected_api_key:
        logger.warning("API_SECRET_KEY не установлен на сервере, авторизация отключена. Это небезопасно для продакшена.")
        return # Разрешаем доступ, если ключ не задан на сервере
    if not api_key or api_key != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или отсутствующий API ключ",
        )
    return api_key


try:
    agent = Agent()
    logger.info("Агент 'Метротест' успешно инициализирован.")
except SystemExit as e:
    logger.critical(f"Приложение не может запуститься из-за критической ошибки: {e}")
    agent = None
except Exception as e:
    logger.error(f"Непредвиденная ошибка при инициализации агента 'Метротест': {e}", exc_info=True)
    agent = None

# --- Глобальное состояние для управления звонками ---
active_calls: Dict[str, Dict[str, Any]] = {}

# --- Роуты ---

@app.get("/")
async def root():
    return HTMLResponse(
        "<h3>Бэкенд 'Метротэст' активен.<br>"
        "• WebSocket — <code>/ws</code><br>"
        "• UI логов — <code>/logs-ui/</code><br>"
        "• Тест нормализации — <code>POST /api/normalize</code></h3>"
    )

# ... (остальные роуты для логов и CSV остаются без изменений) ...
@app.get("/logs")
async def get_logs(q: str | None = None,
                   date_from: str | None = None,
                   date_to: str | None = None,
                   status: str | None = None):
    rows = await query_logs({"from": date_from, "to": date_to, "status": status})
    if q:
        q_low = q.lower()
        filtered_rows = []
        for r in rows:
            if q_low in (r.get("callerId") or "").lower():
                filtered_rows.append(r)
                continue
            try:
                transcript = json.loads(r["transcript_json"])
                for turn in transcript:
                    if q_low in turn.get("text", "").lower():
                        filtered_rows.append(r)
                        break
            except (json.JSONDecodeError, AttributeError):
                continue
        rows = filtered_rows
    return JSONResponse(content=rows)

@app.delete("/logs", dependencies=[Depends(get_api_key)])
async def clear_logs():
    try:
        await delete_all_logs()
        logger.info("🗑️ Все логи были удалены.")
        return JSONResponse(content={"message": "Все логи удалены"}, status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении логов: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.get("/logs/csv")
async def get_logs_csv():
    rows = await query_logs({})
    csv_data_str = await to_csv(rows)
    response_bytes = csv_data_str.encode('utf-8-sig')
    return StreamingResponse(
        io.BytesIO(response_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="call_logs.csv"'}
    )

# --- API для Базы Знаний и Промптов ---

@app.get("/api/prompts")
async def get_prompts():
    prompts_file = os.getenv("PROMPTS_FILE_PATH")
    if not prompts_file:
        raise HTTPException(status_code=500, detail="Переменная окружения PROMPTS_FILE_PATH не установлена.")
    try:
        with open(prompts_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Не удалось прочитать файл промптов: {e}")

@app.post("/api/prompts", dependencies=[Depends(get_api_key)])
async def update_prompts(payload: PromptsUpdatePayload): # NEW: Используем Pydantic модель
    prompts_file = os.getenv("PROMPTS_FILE_PATH")
    if not prompts_file:
        raise HTTPException(status_code=500, detail="Переменная окружения PROMPTS_FILE_PATH не установлена.")
    try:
        # Pydantic автоматически преобразует модель в словарь
        with open(prompts_file, 'w', encoding='utf-8') as f:
            json.dump(payload.dict(), f, ensure_ascii=False, indent=2)

        # Перезагружаем агента, чтобы он подхватил новые промпты
        if agent and hasattr(agent, 'reload'):
            agent.reload()

        return JSONResponse(content={"message": "Промпты успешно обновлены."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить промпты: {e}")

@app.get("/api/settings")
async def get_search_settings():
    return {
        "kb_top_k": int(os.getenv("KB_TOP_K", "3")),
        "kb_fallback_threshold": float(os.getenv("KB_FALLBACK_THRESHOLD", "0.2")),
        "llm_model_primary": os.getenv("LLM_MODEL_PRIMARY", "gpt-4o-mini"),
        "llm_model_fallback": os.getenv("LLM_MODEL_FALLBACK", ""),
        "llm_temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
    }

@app.post("/api/settings", dependencies=[Depends(get_api_key)])
async def update_search_settings(payload: SearchSettingsPayload):
    try:
        to_set: Dict[str, str] = {}
        if payload.kb_top_k is not None:
            to_set["KB_TOP_K"] = str(payload.kb_top_k)
            os.environ["KB_TOP_K"] = str(payload.kb_top_k)
        if payload.kb_fallback_threshold is not None:
            to_set["KB_FALLBACK_THRESHOLD"] = str(payload.kb_fallback_threshold)
            os.environ["KB_FALLBACK_THRESHOLD"] = str(payload.kb_fallback_threshold)

        if to_set:
            _update_env_file(to_set)
            if agent and hasattr(agent, 'reload'):
                agent.reload()
        return JSONResponse(content={"message": "Настройки сохранены"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить настройки: {e}")


@app.post("/api/model-settings", dependencies=[Depends(get_api_key)])
async def update_model_settings(payload: ModelSettingsPayload):
    try:
        to_set: Dict[str, str] = {}
        if payload.llm_model_primary is not None:
            to_set["LLM_MODEL_PRIMARY"] = payload.llm_model_primary
            os.environ["LLM_MODEL_PRIMARY"] = payload.llm_model_primary
        if payload.llm_model_fallback is not None:
            to_set["LLM_MODEL_FALLBACK"] = payload.llm_model_fallback
            os.environ["LLM_MODEL_FALLBACK"] = payload.llm_model_fallback
        if payload.llm_temperature is not None:
            to_set["LLM_TEMPERATURE"] = str(payload.llm_temperature)
            os.environ["LLM_TEMPERATURE"] = str(payload.llm_temperature)

        if to_set:
            _update_env_file(to_set)
            if agent and hasattr(agent, 'reload'):
                agent.reload()
        return JSONResponse(content={"message": "Модельные настройки сохранены"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить модельные настройки: {e}")


@app.post("/api/normalize")
async def api_normalize(payload: NormalizeRequest):
    try:
        normalized = normalize_text(payload.text)
        return {"raw": payload.text, "normalized": normalized}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/kb")
async def get_knowledge_base():
    kb_path = os.getenv("KNOWLEDGE_BASE_PATH")
    if not kb_path:
        raise HTTPException(status_code=500, detail="Переменная окружения KNOWLEDGE_BASE_PATH не установлена.")
    try:
        with open(kb_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return JSONResponse(content={"text": content})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл базы знаний не найден")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/kb/upload", dependencies=[Depends(get_api_key)])
async def upload_kb(file: UploadFile = File(...)):
    kb_path = os.getenv("KNOWLEDGE_BASE_PATH")
    if not kb_path:
        raise HTTPException(status_code=500, detail="Переменная окружения KNOWLEDGE_BASE_PATH не установлена.")

    if not file.filename.endswith('.md'):
        raise HTTPException(status_code=400, detail="Ошибка: Пожалуйста, загрузите .md файл.")

    try:
        # Читаем содержимое файла
        content_bytes = await file.read()
        content_text = content_bytes.decode('utf-8')

        # Обогащаем текст, дублируя заголовки
        logger.info("Дублирование заголовков в загруженном файле...")
        enriched_content = duplicate_headers_without_hashes(content_text)
        logger.info("Заголовки успешно продублированы.")


        backup_dir = "kb/backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = os.path.join(backup_dir, f"knowledge_base_{timestamp}.md.bak")
        if os.path.exists(kb_path):
            shutil.copy(kb_path, backup_path)
            logger.info(f"💾 Создан бэкап базы знаний: {backup_path}")

        # Сохраняем обогащенный контент
        with open(kb_path, "w", encoding='utf-8') as buffer:
            buffer.write(enriched_content)

        logger.info(f"✅ Новый файл базы знаний '{file.filename}' сохранен с обогащенными заголовками.")

        asyncio.create_task(recreate_embeddings_and_reload_agent())

        return JSONResponse(status_code=202, content={"message": "Файл принят. Начался процесс обновления базы знаний. Это может занять несколько минут."})

    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке файла БЗ: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")

# --- База знаний (TECH) ---

@app.get("/kb2")
async def get_knowledge_base_tech():
    kb_path = os.getenv("KNOWLEDGE_BASE2_PATH")
    if not kb_path:
        raise HTTPException(status_code=500, detail="Переменная окружения KNOWLEDGE_BASE2_PATH не установлена.")
    try:
        with open(kb_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return JSONResponse(content={"text": content})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл технической базы знаний не найден")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/kb2/upload", dependencies=[Depends(get_api_key)])
async def upload_kb_tech(file: UploadFile = File(...)):
    kb_path = os.getenv("KNOWLEDGE_BASE2_PATH")
    if not kb_path:
        raise HTTPException(status_code=500, detail="Переменная окружения KNOWLEDGE_BASE2_PATH не установлена.")

    if not file.filename.endswith('.md'):
        raise HTTPException(status_code=400, detail="Ошибка: Пожалуйста, загрузите .md файл.")

    try:
        content_bytes = await file.read()
        content_text = content_bytes.decode('utf-8')

        logger.info("[TECH KB] Дублирование заголовков в загруженном файле...")
        enriched_content = duplicate_headers_without_hashes(content_text)
        logger.info("[TECH KB] Заголовки успешно продублированы.")

        backup_dir = "kb/backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = os.path.join(backup_dir, f"knowledge_base2_{timestamp}.md.bak")
        if os.path.exists(kb_path):
            shutil.copy(kb_path, backup_path)
            logger.info(f"💾 Создан бэкап ТЕХ БЗ: {backup_path}")

        with open(kb_path, "w", encoding='utf-8') as buffer:
            buffer.write(enriched_content)

        logger.info(f"✅ Новый файл ТЕХ БЗ '{file.filename}' сохранен с обогащенными заголовками.")

        asyncio.create_task(recreate_embeddings_and_reload_agent())

        return JSONResponse(status_code=202, content={"message": "Файл принят. Начался процесс обновления ТЕХ БЗ. Это может занять несколько минут."})

    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке ТЕХ БЗ: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {e}")

async def recreate_embeddings_and_reload_agent():
    logger.info("⏳ Начинаем пересоздание эмбеддингов в фоновом режиме...")
    loop = asyncio.get_event_loop()
    try:
        success = await loop.run_in_executor(None, recreate_embeddings)
        if success:
            logger.info("✅ Эмбеддинги успешно пересозданы.")
            if agent and hasattr(agent, 'reload'):
                agent.reload()
        else:
            logger.error("❌ Ошибка при пересоздании эмбеддингов. Подробности в логе выше.")

    except Exception as e:
        logger.error(f"❌ Исключение при пересоздании эмбеддингов: {e}", exc_info=True)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, callerId: str = Query(None)):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)

    active_calls[session_id] = {
        "callerId": callerId,
        "startTime": start_time.isoformat(),
        "transcript": [],
        "status": "Initiated"
    }
    logger.info(f"Новый звонок: Session ID: {session_id}, Caller ID: {callerId}")

    if not agent:
        await websocket.send_text("Ошибка инициализации агента.")
        await websocket.close()
        del active_calls[session_id]
        return

    try:
        # Загружаем приветствие из файла
        greeting = agent.prompts.get("greeting", "Здравствуйте, чем могу помочь?")
        active_calls[session_id]["transcript"].append(
            {"speaker": "bot", "text": greeting, "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        await websocket.send_text(greeting)

        while True:
            data = await websocket.receive_text()
            norm = normalize_text(data)
            logger.info(f"Получен вопрос ({session_id}) RAW='{data}' NORM='{norm}'")
            active_calls[session_id]["transcript"].append(
                {"speaker": "user", "text": norm, "raw": data, "timestamp": datetime.now(timezone.utc).isoformat()}
            )

            response_generator = agent.get_response_generator(norm, session_id=session_id)

            full_response = ""
            for chunk in response_generator:
                if chunk:
                    # Возвращаем прежнее поведение: нормализация только входа; выход шлём как есть
                    await websocket.send_text(chunk)
                    full_response += chunk

            logger.info(f"Полный ответ ({session_id}) отправлен.")
            kb_used = getattr(agent, 'last_kb', None)
            active_calls[session_id]["transcript"].append(
                {
                    "speaker": "bot",
                    "text": full_response,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "kb": kb_used,
                }
            )
            active_calls[session_id]["status"] = "InProgress"

    except WebSocketDisconnect:
        logger.info(f"Клиент ({session_id}) отключился.")
        active_calls[session_id]["status"] = "Completed"
    except Exception as e:
        logger.error(f"Ошибка WS ({session_id}): {e}", exc_info=True)
        active_calls[session_id]["status"] = "Failed"
    finally:
        # ... (логика сохранения лога без изменений) ...
        end_time = datetime.now(timezone.utc)
        call_log = active_calls.get(session_id)
        if call_log:
            log_record: Dict[str, Any] = {
                "id": session_id,
                "callerId": call_log["callerId"],
                "startTime": call_log["startTime"],
                "endTime": end_time.isoformat(),
                "status": call_log["status"],
                "transcript": call_log["transcript"],
            }
            try:
                await insert_log(log_record)
                logger.info(f"💾 Лог сохранён для Session {session_id}")
            except Exception as err:
                logger.error(f"❌ Ошибка insert_log: {err}", exc_info=True)

            del active_calls[session_id]

# --- Запуск сервера ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
