from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_chroma import Chroma
from dotenv import load_dotenv
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
import logging
import json
import os
import redis
import hashlib
import time
from typing import List

class CachedOpenAIEmbeddings(OpenAIEmbeddings):
    """Кешированные OpenAI Embeddings для ускорения повторных запросов"""
    
    def __init__(self, redis_client, **kwargs):
        super().__init__(**kwargs)
        # Используем объект для хранения кеш-данных
        self._cache_data = {
            'redis_client': redis_client,
            'cache_prefix': "embedding_cache:",
            'cache_ttl': 3600 * 24 * 7  # 7 дней
        }
        
    def _get_cache_key(self, text: str) -> str:
        """Генерирует ключ кеша для текста"""
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return f"{self._cache_data['cache_prefix']}{text_hash}"
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Кешированное создание embeddings для документов"""
        results = []
        texts_to_embed = []
        text_indices = []
        
        # Проверяем кеш для каждого текста
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached_embedding = self._cache_data['redis_client'].get(cache_key)
            
            if cached_embedding:
                # Восстанавливаем embedding из кеша
                embedding = json.loads(cached_embedding)
                results.append(embedding)
                logger.debug(f"✅ Embedding из кеша для текста {i}")
            else:
                # Добавляем в список для создания embedding
                texts_to_embed.append(text)
                text_indices.append(i)
                results.append(None)  # Заглушка
        
        # Создаем embeddings для текстов, которых нет в кеше
        if texts_to_embed:
            logger.info(f"🔄 Создаем {len(texts_to_embed)} новых embeddings")
            new_embeddings = super().embed_documents(texts_to_embed)
            
            # Сохраняем в кеш и заполняем результаты
            for i, (text, embedding) in enumerate(zip(texts_to_embed, new_embeddings)):
                cache_key = self._get_cache_key(text)
                self._cache_data['redis_client'].setex(cache_key, self._cache_data['cache_ttl'], json.dumps(embedding))
                
                # Заполняем результат
                original_index = text_indices[i]
                results[original_index] = embedding
                logger.debug(f"💾 Сохранен в кеш embedding для текста {original_index}")
        
        return results
    
    def embed_query(self, text: str) -> List[float]:
        """
        🚀 КРИТИЧЕСКАЯ ОПТИМИЗАЦИЯ: Агрессивное кеширование query embeddings
        Цель: Избежать OpenAI API вызовов при каждом запросе (экономия 0.7-0.9с)
        """
        cache_key = self._get_cache_key(text)
        cached_embedding = self._cache_data['redis_client'].get(cache_key)
        
        if cached_embedding:
            logger.info(f"⚡ ОПТИМИЗАЦИЯ: Embedding запроса из кеша (экономия ~0.8с)")
            return json.loads(cached_embedding)
        
        # Создаем новый embedding ТОЛЬКО если его нет в кеше
        logger.warning(f"🔄 МЕДЛЕННО: Создаем новый embedding для запроса (OpenAI API ~0.8с)")
        start_time = time.time()
        embedding = super().embed_query(text)
        elapsed = time.time() - start_time
        
        # Сохраняем в кеш с длительным TTL
        self._cache_data['redis_client'].setex(cache_key, self._cache_data['cache_ttl'], json.dumps(embedding))
        logger.info(f"💾 Сохранен в кеш embedding запроса (заняло {elapsed:.3f}с)")
        
        return embedding

load_dotenv()

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self) -> None:
        logger.info("--- Инициализация Агента 'Метротест' ---")
        # Текущая LLM и ленивый fallback
        self.llm = self._create_llm_from_env(primary=True)
        self.fallback_llm = None
        self._fallback_chains_built = False
        self.store = {}
        self.last_kb = "general"
        
        # НОВОЕ: Redis кеширование для embeddings
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
            self.redis_client.ping()  # проверяем соединение
            self.cache_enabled = True
            logger.info("✅ Redis кеширование включено")
        except Exception as e:
            self.redis_client = None
            self.cache_enabled = False
            logger.warning(f"⚠️ Redis недоступен, кеширование отключено: {e}")
        try:
            self.prompts = self.load_prompts()
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
            logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать агента из-за проблемы с конфигурацией промптов. {e}", exc_info=True)
            # Прерываем выполнение, чтобы предотвратить запуск с неверной конфигурацией
            raise SystemExit(f"Остановка приложения: {e}")

        self._initialize_rag_chain()
        
        # 🚀 ОПТИМИЗАЦИЯ: Pre-warm кеш для популярных вопросов
        self._prewarm_embedding_cache()
        
        logger.info("--- Агент 'Метротест' успешно инициализирован ---")

    def _prewarm_embedding_cache(self):
        """
        🚀 ОПТИМИЗАЦИЯ: Предзагрузка embeddings для популярных вопросов
        Запускается при старте агента, чтобы первые звонки были быстрыми
        """
        if not self.cache_enabled:
            logger.info("⚠️ Кеш отключен, pre-warming пропущен")
            return
        
        # Список популярных вопросов для pre-warming
        common_questions = [
            "твердомер",
            "разрывная машина",
            "испытательный пресс",
            "цена",
            "характеристики",
            "доставка",
            "У вас есть пресс испытательный",
            "Какие есть твердомеры",
            "Сколько стоит разрывная машина",
            "Какие характеристики у РЭМ",
            "Есть ли гарантия",
            "Как оформить заказ"
        ]
        
        logger.info(f"🔥 Pre-warming кеша для {len(common_questions)} популярных вопросов...")
        
        # Используем embeddings напрямую для pre-warming
        if isinstance(self.db._embedding_function, CachedOpenAIEmbeddings):
            warmed = 0
            for question in common_questions:
                try:
                    # Проверяем, есть ли уже в кеше
                    cache_key = self.db._embedding_function._get_cache_key(question)
                    if not self.redis_client.get(cache_key):
                        # Создаем embedding (он автоматически сохранится в кеш)
                        self.db._embedding_function.embed_query(question)
                        warmed += 1
                except Exception as e:
                    logger.debug(f"Ошибка pre-warming для '{question}': {e}")
            
            logger.info(f"✅ Pre-warming завершен: {warmed} новых, {len(common_questions) - warmed} уже в кеше")
        else:
            logger.warning("⚠️ Embeddings не поддерживают кеширование, pre-warming пропущен")
    
    def _get_cache_key(self, text: str, kb: str) -> str:
        """Генерирует ключ кеша для embedding запроса."""
        combined = f"{text}:{kb}:{self.last_kb}"
        return f"emb:{hashlib.md5(combined.encode()).hexdigest()}"
    
    def _get_cached_documents(self, text: str, kb: str):
        """Получает кешированные документы из Redis."""
        if not self.cache_enabled:
            return None
        
        cache_key = self._get_cache_key(text, kb)
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                logger.info(f"🎯 КЕШИРОВАНИЕ: Используем кешированный поиск для: {text[:30]}...")
                return json.loads(cached)
        except Exception as e:
            logger.debug(f"Ошибка чтения кеша: {e}")
        return None
    
    def _cache_documents(self, text: str, kb: str, documents):
        """Кеширует результаты поиска в Redis."""
        if not self.cache_enabled or not documents:
            return
            
        cache_key = self._get_cache_key(text, kb)
        try:
            # Кешируем на 1 час
            doc_contents = [{"content": doc.page_content, "metadata": doc.metadata} for doc in documents]
            self.redis_client.setex(
                cache_key, 
                3600,  # 1 час TTL
                json.dumps(doc_contents)
            )
            logger.debug(f"📦 КЕШИРОВАНИЕ: Сохранили {len(documents)} документов в кеш")
        except Exception as e:
            logger.debug(f"Ошибка записи в кеш: {e}")

    def _create_llm_from_env(self, primary: bool) -> ChatOpenAI:
        """Создаёт LLM на основе переменных окружения.
        primary=True → LLM_MODEL_PRIMARY, иначе LLM_MODEL_FALLBACK.
        """
        model_env_key = "LLM_MODEL_PRIMARY" if primary else "LLM_MODEL_FALLBACK"
        model_name = os.getenv(model_env_key, os.getenv("LLM_MODEL_PRIMARY", "gpt-4o-mini"))
        try:
            temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        except ValueError:
            temperature = 0.2
        logger.info(f"LLM конфигурация: {'PRIMARY' if primary else 'FALLBACK'} model='{model_name}', temperature={temperature}")
        # ОПТИМИЗАЦИЯ: ограничиваем длину ответа и таймаут
        try:
            max_tokens = int(os.getenv("LLM_MAX_TOKENS", "128"))
        except ValueError:
            max_tokens = 128

        return ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            streaming=True,
            request_timeout=12,  # короче для быстрого отказа
            max_retries=1,
            max_tokens=max_tokens
        )

    def load_prompts(self):
        prompts_file = os.getenv("PROMPTS_FILE_PATH")
        if not prompts_file:
            raise ValueError("Переменная окружения PROMPTS_FILE_PATH не установлена.")

        logger.info(f"Загрузка промптов из файла: '{prompts_file}'")
        try:
            with open(prompts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Файл промптов не найден по пути: {prompts_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON в файле {prompts_file}: {e}")
            raise

    def _initialize_rag_chain(self):
        """Инициализирует/перезагружает векторное хранилище и RAG-цепочки для текущей LLM."""
        logger.info("Инициализация или перезагрузка RAG-цепочки...")

        persist_directory = os.getenv("PERSIST_DIRECTORY")
        if not persist_directory:
            raise ValueError("Переменная окружения PERSIST_DIRECTORY не установлена.")

        logger.info(f"Подключение к векторной базе в '{persist_directory}'...")
        
        # ОПТИМИЗАЦИЯ: Создаем кешированные embeddings
        if self.cache_enabled:
            embeddings = CachedOpenAIEmbeddings(
                redis_client=self.redis_client,
                chunk_size=1000
            )
            logger.info("✅ Используем кешированные embeddings")
        else:
            embeddings = OpenAIEmbeddings(chunk_size=1000)
            logger.info("⚠️ Используем обычные embeddings (кеширование недоступно)")
            
        self.db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        # ОПТИМИЗАЦИЯ: уменьшаем количество документов для контекста
        kb_k = int(os.getenv("KB_TOP_K", "1"))
        self.retriever_general = self.db.as_retriever(
            search_type="similarity", search_kwargs={"k": kb_k, "filter": {"kb": "general"}}
        )
        self.retriever_tech = self.db.as_retriever(
            search_type="similarity", search_kwargs={"k": kb_k, "filter": {"kb": "tech"}}
        )
        logger.info("Подключение к базе данных успешно.")

        # Строим цепочки для текущей LLM
        self._build_chains_for_llm(self.llm)
        # Сбросим кэш фолбэка
        self._fallback_chains_built = False
        self.fallback_llm = None
        logger.info("--- RAG-цепочка успешно создана/обновлена ---")

    def _build_chains_for_llm(self, llm: ChatOpenAI):
        """Строит и сохраняет цепочки для указанной LLM."""
        # ОПТИМИЗАЦИЯ: Убираем history_aware_retriever для ускорения
        # Вместо дополнительного LLM запроса для контекстуализации, используем простые retriever'ы
        logger.info("🚀 ОПТИМИЗАЦИЯ: Используем простые retriever'ы без history_aware для ускорения")
        
        qa_prompt = ChatPromptTemplate.from_messages(
            [("system", self.prompts["qa_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
        )
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

        # Используем простые retriever'ы вместо history_aware
        rag_chain_general = create_retrieval_chain(self.retriever_general, question_answer_chain)
        rag_chain_tech = create_retrieval_chain(self.retriever_tech, question_answer_chain)

        self.conversational_rag_chain_general = RunnableWithMessageHistory(
            rag_chain_general,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )
        self.conversational_rag_chain_tech = RunnableWithMessageHistory(
            rag_chain_tech,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )

    def _route_kb(self, text: str) -> str:
        """Простая и быстрая маршрутизация: general | tech.
        Выбираем 'tech', если обнаружены технические маркеры; иначе 'general'."""
        if not text:
            return "general"
        t = text.lower()
        tech_markers = [
            "техн", "характерист", "параметр", "диапазон", "класс точности", "нагруз", "датчик",
            "тензо", "разрывн", "машин", "усилие", "кн", "мпа", "ньютон", "мм", "гост", "iso",
            "сертиф", "модуль", "частота", "вибро", "сопротивл", "протокол", "datasheet", "spec"
        ]
        general_markers = ["цена", "стоимость", "контакт", "гарант", "доставка", "оплата", "адрес"]
        if any(m in t for m in tech_markers) and not any(m in t for m in general_markers):
            return "tech"
        return "general"

# УДАЛЕНА МЕДЛЕННАЯ ФУНКЦИЯ _max_relevance() - она тратила 6.4 секунды!
    # Эта функция отсутствовала в быстрой Voximplant версии

    def reload(self):
        """Перезагружает промпты, векторную базу данных и RAG-цепочку."""
        logger.info("🔃 Получена команда на перезагрузку агента...")
        try:
            self.prompts = self.load_prompts()
            # Обновим конфигурацию моделей
            self.llm = self._create_llm_from_env(primary=True)
            self._initialize_rag_chain()
            logger.info("✅ Агент успешно перезагружен с новой базой знаний и промптами.")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при перезагрузке агента: {e}", exc_info=True)
            return False

    def get_session_history(self, session_id: str):
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
        return self.store[session_id]

    def get_response_generator(self, user_question: str, session_id: str):
        import time
        start_time = time.time()
        logger.info(f"🕐 ПРОФИЛИРОВАНИЕ: Начало get_response_generator для вопроса: '{user_question[:50]}...'")
        
        # УПРОЩЕННАЯ маршрутизация (как в Voximplant версии)
        route_start = time.time()
        target = self._route_kb(user_question)
        route_time = time.time() - route_start
        logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Маршрутизация заняла {route_time:.3f}с")
        
        # УБИРАЕМ МЕДЛЕННУЮ ОЦЕНКУ РЕЛЕВАНТНОСТИ!
        # Была: max_score = self._max_relevance() - 6.4 секунды!
        # Теперь: просто используем результат маршрутизации
        
        self.last_kb = target
        logger.info(f"Маршрутизация вопроса в БЗ: {target}")
        
        setup_time = time.time() - start_time
        logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Общая подготовка заняла {setup_time:.3f}с")
        def _stream_with_chain(use_fallback: bool):
            import time
            stream_start = time.time()
            logger.info(f"🔄 ПРОФИЛИРОВАНИЕ: Начинаем streaming с {'FALLBACK' if use_fallback else 'PRIMARY'} моделью")
            
            chain_local = (
                self.conversational_rag_chain_tech if target == "tech" else self.conversational_rag_chain_general
            )
            
            chain_setup_time = time.time() - stream_start
            logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Подготовка цепочки заняла {chain_setup_time:.3f}с")
            
            stream_call_start = time.time()
            stream_local = chain_local.stream(
                {"input": user_question},
                config={"configurable": {"session_id": session_id}},
            )
            stream_call_time = time.time() - stream_call_start
            logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Вызов stream() занял {stream_call_time:.3f}с")
            
            first_chunk = True
            chunk_count = 0
            for chunk in stream_local:
                if first_chunk:
                    first_chunk_time = time.time() - stream_start
                    logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Первый чанк получен через {first_chunk_time:.3f}с")
                    first_chunk = False
                
                if 'answer' in chunk:
                    chunk_count += 1
                    yield chunk['answer']
            
            total_stream_time = time.time() - stream_start
            logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Весь streaming занял {total_stream_time:.3f}с, чанков: {chunk_count}")

        def _invoke_non_streaming_with_llm(model_name: str):
            """Локально построить НЕстриминговые цепочки под указанный model_name и вернуть полный ответ одной строкой."""
            try:
                temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
            except ValueError:
                temperature = 0.2
            llm_local = ChatOpenAI(model_name=model_name, temperature=temperature, streaming=False)

            contextualize_q_prompt = ChatPromptTemplate.from_messages(
                [("system", self.prompts["contextualize_q_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
            )
            history_aware_retriever_general = create_history_aware_retriever(llm_local, self.retriever_general, contextualize_q_prompt)
            history_aware_retriever_tech = create_history_aware_retriever(llm_local, self.retriever_tech, contextualize_q_prompt)

            qa_prompt = ChatPromptTemplate.from_messages(
                [("system", self.prompts["qa_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
            )
            question_answer_chain = create_stuff_documents_chain(llm_local, qa_prompt)

            rag_chain_local = create_retrieval_chain(
                history_aware_retriever_tech if target == "tech" else history_aware_retriever_general,
                question_answer_chain,
            )
            runnable = RunnableWithMessageHistory(
                rag_chain_local,
                self.get_session_history,
                input_messages_key="input",
                history_messages_key="chat_history",
                output_messages_key="answer",
            )
            result = runnable.invoke(
                {"input": user_question},
                config={"configurable": {"session_id": session_id}},
            )
            text = result.get("answer", "")
            if text:
                yield text

        # Попробуем основной пайплайн; при ошибке — один раз фолбэк на запасную модель
        try:
            yield from _stream_with_chain(use_fallback=False)
        except Exception as e:
            fb_model = os.getenv("LLM_MODEL_FALLBACK")
            primary_model = os.getenv("LLM_MODEL_PRIMARY", "gpt-4o-mini")
            err_text = str(e).lower()
            # Если стрим запрещён организацией/моделью — попробуем НЕстриминговый режим на основной модели
            if "unsupported_value" in err_text or "verify organization" in err_text or "param': 'stream" in err_text:
                logger.warning("Стриминг недоступен для текущей организации/модели → переключаемся на НЕстриминговый режим (PRIMARY)")
                try:
                    yield from _invoke_non_streaming_with_llm(primary_model)
                    return
                except Exception as e_ns:
                    logger.error(f"Не удалось выполнить нестриминговый режим на PRIMARY: {e_ns}", exc_info=True)
            # Если фолбэк определён — попробуем его (стрим), затем НЕстримингово
            if not fb_model or fb_model == primary_model:
                logger.error(f"Ошибка генерации (без фолбэка): {e}", exc_info=True)
                return
            logger.warning(f"Основная модель упала: {e}. Пытаемся переключиться на FALLBACK '{fb_model}'…")
            # Построим цепочки для fallback один раз
            try:
                if not self._fallback_chains_built:
                    self.fallback_llm = self._create_llm_from_env(primary=False)
                    self._build_chains_for_llm(self.fallback_llm)
                    self._fallback_chains_built = True
                try:
                    yield from _stream_with_chain(use_fallback=True)
                    return
                except Exception as e_fb_stream:
                    logger.warning(f"Фолбэк в стриминговом режиме не удался: {e_fb_stream}. Пробуем НЕстримингово…")
                    yield from _invoke_non_streaming_with_llm(fb_model)
            except Exception as e2:
                logger.error(f"Фолбэк модель также не справилась: {e2}", exc_info=True)
                return

    def _is_sentence_complete(self, text: str, min_length: int = 50, max_length: int = 200) -> bool:
        """
        Определяет завершенность предложения для chunking.
        Учитывает ваши маркеры сегментации "|" и естественные границы предложений.
        """
        if not text or len(text) < min_length:
            return False
            
        # Принудительная отправка при превышении максимальной длины
        if len(text) >= max_length:
            return True
            
        # Проверяем маркеры сегментации "|"
        if text.endswith(('.|', '?|', '!|')):
            return True
            
        # Проверяем естественные границы предложений
        if text.endswith(('.', '?', '!', ':', ';')):
            # Дополнительная проверка: не слишком короткое предложение
            if len(text) >= min_length:
                return True
                
        # Проверяем переходы на новую строку (могут быть в markdown)
        if '\n' in text and len(text) >= min_length:
            return True
            
        return False

    def get_chunked_response_generator(self, user_question: str, session_id: str):
        """
        ЯДРО СИСТЕМЫ: Генерирует чанки ответа с умной сегментацией для немедленного TTS.
        Основан на существующем get_response_generator, но буферизует до завершения предложений.
        
        ЦЕЛЬ: Первый чанк через 0.6-0.8с от начала AI генерации.
        """
        import time
        
        # Конфигурация из .env
        chunk_min_length = int(os.getenv("CHUNK_MIN_LENGTH", "50"))
        chunk_max_length = int(os.getenv("CHUNK_MAX_LENGTH", "200"))
        
        # Используем существующий streaming generator
        response_stream = self.get_response_generator(user_question, session_id)
        
        buffer = ""
        chunk_count = 0
        start_time = time.time()
        
        logger.info(f"🤖 Начало chunked генерации для: '{user_question[:50]}...'")
        
        try:
            for token in response_stream:
                buffer += token
                
                # УМНАЯ СЕГМЕНТАЦИЯ: Проверяем завершенность предложений
                if self._is_sentence_complete(buffer, chunk_min_length, chunk_max_length):
                    sentence = buffer.strip()
                    buffer = ""
                    
                    if sentence:  # Не отправляем пустые чанки
                        chunk_count += 1
                        elapsed = time.time() - start_time
                        
                        logger.info(f"⚡ Chunk {chunk_count} ready in {elapsed:.2f}s: '{sentence[:30]}...'")
                        
                        # ПЕРВЫЙ ЧАНК - критическая метрика
                        if chunk_count == 1:
                            logger.info(f"🎯 FIRST CHUNK TIME: {elapsed:.2f}s (target: <0.8s)")
                        
                        yield {
                            "text": sentence,
                            "chunk_number": chunk_count,
                            "elapsed_time": elapsed,
                            "kb": self.last_kb,
                            "is_first": chunk_count == 1
                        }
            
            # Отправляем остаток буфера (страховка)
            if buffer.strip():
                chunk_count += 1
                elapsed = time.time() - start_time
                logger.info(f"🏁 Final chunk {chunk_count}: '{buffer.strip()[:30]}...'")
                
                yield {
                    "text": buffer.strip(),
                    "chunk_number": chunk_count,
                    "elapsed_time": elapsed,
                    "kb": self.last_kb,
                    "is_final": True
                }
                
        except Exception as e:
            logger.error(f"❌ Chunked generator error: {e}", exc_info=True)
            # Критично: fallback на обычный генератор
            logger.warning("🔄 Falling back to regular generator")
            full_response = ""
            for token in self.get_response_generator(user_question, session_id):
                full_response += token
            yield {
                "text": full_response,
                "chunk_number": 1,
                "elapsed_time": time.time() - start_time,
                "kb": self.last_kb,
                "fallback": True
            }
