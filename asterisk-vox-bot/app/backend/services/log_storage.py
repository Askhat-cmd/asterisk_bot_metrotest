"""
SQLite‑хранилище логов звонков.
"""
import aiosqlite, csv, io, json, os
from datetime import datetime, timezone
from typing import List, Dict, Any

DB_PATH = os.getenv("DB_PATH", os.path.join(os.getcwd(), "data", "db", "log_db.sqlite"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS logs (
    id TEXT PRIMARY KEY,
    callerId TEXT,
    startTime TEXT,
    endTime   TEXT,
    status    TEXT,
    transcript_json TEXT
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SQL)
        await db.commit()

async def insert_log(log: Dict[str, Any]):
    """
    log = {
        "id": "...", "callerId": "...",
        "startTime": ISO, "endTime": ISO,
        "status": "...",
        "transcript": [ {speaker:"user"|"bot",text:"..."} ]
    }
    """
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO logs VALUES (?,?,?,?,?,?)",
            (
                log["id"], log.get("callerId"),
                log["startTime"], log["endTime"],
                log["status"], json.dumps(log["transcript"])
            )
        )
        await db.commit()

async def query_logs(filters: Dict[str, str]) -> List[Dict[str, Any]]:
    # Гарантируем, что таблица существует перед выборкой
    await init_db()
    parts = ["SELECT * FROM logs WHERE 1=1"]
    params = []
    
    # Используем .get() для безопасного доступа к ключам, которых может не быть
    if filters.get("from"):
        parts.append("AND startTime >= ?")
        params.append(filters["from"])
    if filters.get("to"):
        parts.append("AND startTime <= ?")
        params.append(filters["to"])
    if filters.get("status"):
        parts.append("AND status = ?")
        params.append(filters["status"])
    
    parts.append("ORDER BY startTime DESC") # Сортируем по убыванию даты
    
    query = " ".join(parts)
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(query, params)
        return [dict(r) for r in rows]

async def to_csv(rows: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["ID", "Номер", "Начало", "Конец", "Статус", "Диалог"])
    for r in rows:
        try:
            # Форматируем JSON-диалог в одну строку
            transcript_list = json.loads(r["transcript_json"])
            formatted_transcript = "\n".join([
                f"[{t['speaker'].upper()}] {t['text']}" for t in transcript_list
            ])
        except (json.JSONDecodeError, TypeError):
            formatted_transcript = r["transcript_json"] # оставляем как есть, если не JSON

        w.writerow([
            r["id"], r.get("callerId", "—"), r["startTime"], r["endTime"],
            r["status"], formatted_transcript
        ])
    return output.getvalue()

async def delete_all_logs():
    """
    Удаляет все записи из таблицы логов.
    """
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM logs")
        await db.commit()
