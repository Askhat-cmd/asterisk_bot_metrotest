"""
Скрипт для создания векторной базы данных ChromaDB
из текстового файла базы знаний.
"""
import os
import re
import shutil
import logging
from dotenv import load_dotenv

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Загрузка переменных окружения ---
load_dotenv()

# --- Константы из .env ---
KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", os.path.join(os.getcwd(), "kb", "general.md"))
KNOWLEDGE_BASE2_PATH = os.getenv("KNOWLEDGE_BASE2_PATH", os.path.join(os.getcwd(), "kb", "tech.md"))
PERSIST_DIRECTORY = os.getenv("PERSIST_DIRECTORY", os.path.join(os.getcwd(), "data", "chroma"))
TMP_DIRECTORY = f"{PERSIST_DIRECTORY}_tmp"
OLD_DIRECTORY = f"{PERSIST_DIRECTORY}_old"

# Санитизация ключа на случай переносов строк/пробелов
sanitized_key = (os.getenv("OPENAI_API_KEY") or "").strip()
if sanitized_key:
    os.environ["OPENAI_API_KEY"] = sanitized_key
OPENAI_API_KEY = sanitized_key

if not OPENAI_API_KEY:
    logging.error("Не найден ключ OPENAI_API_KEY в .env файле.")
    exit()

def duplicate_headers_without_hashes(text: str) -> str:
    """
    Дублирует заголовки Markdown (от h1 до h6) в тексте,
    добавляя версию без хэшей в следующей строке.
    Это обогащает контекст для каждого чанка.
    """
    def replacer(match):
        header_line = match.group(0)
        # Убираем хэши и лишние пробелы, чтобы получить чистый заголовок
        clean_header = header_line.lstrip('#').strip()
        # Возвращаем исходный заголовок и чистый заголовок на новой строке
        return f"{header_line}\n{clean_header}"

    # Используем re.MULTILINE для обработки каждой строки
    processed_text = re.sub(r"^(#{1,6}\s.+)", replacer, text, flags=re.MULTILINE)
    return processed_text

def _load_text(file_path: str) -> str:
    if not os.path.exists(file_path):
        logging.warning(f"Файл не найден: {file_path}")
        return ""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logging.error(f"Ошибка при чтении файла {file_path}: {e}")
        return ""


def create_embeddings():
    """
    Создаёт объединённую векторную базу для двух БЗ с пометками метаданных:
    - kb = "general" для `knowledge_base.md`
    - kb = "tech"    для `knowledge_base_2.md`
    """
    full_text_general = _load_text(KNOWLEDGE_BASE_PATH)
    full_text_tech = _load_text(KNOWLEDGE_BASE2_PATH)

    if not full_text_general and not full_text_tech:
        logging.error("Нет данных для индексирования: обе БЗ отсутствуют или пустые.")
        return False

    documents_all = []

    if full_text_general:
        logging.info("Обогащение (general): дублирование заголовков...")
        enriched_general = duplicate_headers_without_hashes(full_text_general)
        logging.info("Разделение (general) по '<<->>'...")
        splitter_general = RecursiveCharacterTextSplitter(
            separators=["<<->>"],
            chunk_size=4000,
            chunk_overlap=200,
            add_start_index=True,
        )
        docs_general = splitter_general.create_documents([enriched_general], metadatas=[{"kb": "general"}])
        documents_all.extend(docs_general)

    if full_text_tech:
        logging.info("Обогащение (tech): дублирование заголовков...")
        enriched_tech = duplicate_headers_without_hashes(full_text_tech)
        logging.info("Разделение (tech) по '<<->>'...")
        splitter_tech = RecursiveCharacterTextSplitter(
            separators=["<<->>"],
            chunk_size=4000,
            chunk_overlap=200,
            add_start_index=True,
        )
        docs_tech = splitter_tech.create_documents([enriched_tech], metadatas=[{"kb": "tech"}])
        documents_all.extend(docs_tech)

    if not documents_all:
        logging.warning("Не удалось создать ни одного чанка. Проверьте наличие разделителей '<<->>' в файлах.")
        return False

    logging.info(f"Всего подготовлено чанков: {len(documents_all)}")

    # --- Создание и сохранение эмбеддингов ---
    logging.info(f"Инициализация OpenAI Embeddings...")
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

    # Атомарная пересборка:
    # 1) строим новую БД в TMP_DIRECTORY
    # 2) переименовываем старую в OLD_DIRECTORY
    # 3) переименовываем TMP_DIRECTORY -> PERSIST_DIRECTORY (атомарно на одном FS)
    # 4) удаляем OLD_DIRECTORY

    # Чистим возможные артефакты прошлых запусков
    if os.path.exists(TMP_DIRECTORY):
        logging.info(f"Удаление прежней временной директории: {TMP_DIRECTORY}")
        shutil.rmtree(TMP_DIRECTORY, ignore_errors=True)
    if os.path.exists(OLD_DIRECTORY):
        logging.info(f"Удаление старого бэкапа директории: {OLD_DIRECTORY}")
        shutil.rmtree(OLD_DIRECTORY, ignore_errors=True)

    logging.info(f"Создание новой векторной базы данных во временной директории {TMP_DIRECTORY}...")
    db = Chroma.from_documents(
        documents=documents_all,
        embedding=embeddings,
        persist_directory=TMP_DIRECTORY
    )
    # Явно фиксируем на диск перед свопом
    try:
        db.persist()
    except Exception:
        # некоторые версии уже делают persist() внутри
        pass

    # Своп директорий
    if os.path.exists(PERSIST_DIRECTORY):
        logging.info(f"Переименование текущей БД → бэкап: {PERSIST_DIRECTORY} → {OLD_DIRECTORY}")
        os.replace(PERSIST_DIRECTORY, OLD_DIRECTORY)
    logging.info(f"Атомарная подмена новой БД: {TMP_DIRECTORY} → {PERSIST_DIRECTORY}")
    os.replace(TMP_DIRECTORY, PERSIST_DIRECTORY)
    # Удаляем бэкап (если хотим хранить — можно закомментировать)
    if os.path.exists(OLD_DIRECTORY):
        logging.info(f"Удаление бэкапа старой БД: {OLD_DIRECTORY}")
        shutil.rmtree(OLD_DIRECTORY, ignore_errors=True)

    logging.info("Векторная база данных успешно создана и атомарно подменена.")
    return True


def recreate_embeddings():
    """Функция-обертка для вызова из других модулей."""
    logging.info("Запрошено пересоздание эмбеддингов...")
    return create_embeddings()

if __name__ == "__main__":
    create_embeddings()
