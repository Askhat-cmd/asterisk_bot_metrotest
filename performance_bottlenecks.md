# Анализ задержек ответа голосового бота

## Наблюдаемый таймлайн
По журнальному файлу видно, что после окончания распознавания речи (`ASR`) в 05:35:48 бот получает текст, но первый токен ответа из модели появляется лишь через ~3.0 с. Дополнительно перед запросом к LLM выполняется генерация embedding-а, что занимает ещё ~0.65 с.【F:../Логи_работы_бота.txt†L24-L79】

## 1. Холодные запросы к embedding API
* При отсутствии записи в Redis агент вызывает `OpenAIEmbeddings.embed_query`, о чём прямо сигнализирует лог "Создаем новый embedding"; продолжительность такого вызова ~0.8 с.【F:../Логи_работы_бота.txt†L65-L69】
* Логика `CachedOpenAIEmbeddings.embed_query` действительно обращается к внешнему API, если ключ отсутствует в кеше.【F:app/backend/rag/agent.py†L73-L95】
* В результате каждый новый формулированный вопрос (не входящий в список pre-warm) добавляет ~0.6‑0.8 с к времени ответа.

**Что можно сделать:**

1. **Автопрогрев кеша**. Добавьте cron-скрипт, который прогоняет последние обращения клиентов через API и складывает результат в Redis заранее. Минимальный пример:

   ```bash
   #!/usr/bin/env bash
   source /opt/bot-env/bin/activate
   python scripts/prewarm_embeddings.py \
       --questions-file data/real_calls/latest_questions.jsonl \
       --batch-size 20
   ```

   ```python
   # scripts/prewarm_embeddings.py
   import json
   from pathlib import Path

   from app.backend.rag.agent import CachedOpenAIEmbeddings

   def main(path: str, batch_size: int = 20) -> None:
       embeddings = CachedOpenAIEmbeddings()
       questions = [json.loads(line)["question"] for line in Path(path).read_text().splitlines()]
       for idx in range(0, len(questions), batch_size):
           chunk = questions[idx : idx + batch_size]
           # ключи появятся в Redis даже без обращений бота
           embeddings.embed_documents(chunk)
           print(f"prefetched {idx + len(chunk)} / {len(questions)}")

   if __name__ == "__main__":
       import argparse

       parser = argparse.ArgumentParser()
       parser.add_argument("--questions-file", required=True)
       parser.add_argument("--batch-size", type=int, default=20)
       main(**vars(parser.parse_args()))
   ```

   Скрипт можно запускать раз в час, подмешивая реальные пользовательские фразы, чтобы `CachedOpenAIEmbeddings` почти всегда находил ключ локально.【F:app/backend/rag/agent.py†L73-L95】

2. **Генерация n-грамм**. Для длинных вопросов полезно сохранять отдельные n‑граммы. Создайте вспомогательный модуль, который будет генерировать все подстроки длиной 3–8 токенов и класть их в Redis тем же классом. Это позволит reuse embedding-а даже при переформулировке вопросов.

3. **Локальные модели**. Если есть GPU, рассмотрите запуск `text-embedding-nomic` или `instructor-large` через `langchain.embeddings.HuggingFaceInstructEmbeddings`. Индекс построить один раз офлайн (`scripts/build_chroma_index.py`), а в рантайме работать только с локальными векторами.

## 2. Долгий RTT до первого чанка LLM
* После завершения embedding-а поток `get_response_generator` запускает LangChain-цепочку, но первый токен ответа фиксируется через ~3.0 с (строка "Первый токен получен через 3.039с").【F:../Логи_работы_бота.txt†L70-L77】
* Код генератора сперва полностью конфигурирует retriever и запускает `.stream()`, выполняя всё последовательно внутри одного event loop без перекрытия с TTS, что усугубляет задержку при высоком сетевом `RTT`.【F:app/backend/rag/agent.py†L367-L419】

**Что можно сделать:**

1. **Разделить прогрев retriever-а и генерацию**. Вынесите загрузку контекста и прогоны по базе знаний в отдельную задачу:

   ```python
   async def warmup_context(agent, question: str):
       # вытаскиваем документы заранее, пока TTS проигрывает приветствие
       return await agent.vectorstore.asimilarity_search(question, k=4)

   async def stream_answer(agent, question: str):
       docs_task = asyncio.create_task(warmup_context(agent, question))
       llm = agent.llm.bind(max_tokens=200, top_p=0.7)
       async for chunk in llm.astream(agent.build_prompt(question, await docs_task)):
           yield chunk
   ```

   Такое разделение даёт время на сетевые вызовы ещё до старта стрима.【F:app/backend/rag/agent.py†L367-L419】

2. **Partial streaming**. Добавьте fallback на короткий "safety"-ответ, если retriever не успел. Пример хука в `get_response_generator`:

   ```python
   async def get_response_generator(...):
       response_ready = asyncio.Event()

       async def produce():
           async for chunk in stream_answer(agent, question):
               response_ready.set()
               yield chunk

       producer = produce()
       try:
           chunk = await asyncio.wait_for(producer.__anext__(), timeout=0.8)
       except asyncio.TimeoutError:
           yield "Извините за ожидание, уточняю информацию..."
       else:
           yield chunk
           async for chunk in producer:
               yield chunk
   ```

3. **Настройка параметров**. Для первых ответов используйте профиль "fast" (`max_tokens=128`, `temperature=0.7`, `top_p=0.8`), а после получения первого токена можно переключить модель на "rich"-настройки. В LangChain это можно оформить как два `Runnable` и переключение между ними по флагу пользователя.

## 3. Искусственные паузы в обработчике звонка
* При фильтрации "неинформативных" реплик устанавливается задержка `asyncio.sleep(0.5)` перед перезапуском записи — это добавляет полсекунды к каждому ложному срабатыванию фильтра.【F:app/backend/asterisk/stasis_handler_optimized.py†L336-L358】
* Независимо от результатов фильтра перед обращением к LLM выполняется обязательная пауза `await asyncio.sleep(0.20)` для проигрывания filler-а.【F:app/backend/asterisk/stasis_handler_optimized.py†L380-L399】

**Что можно сделать:**

1. **Условные паузы**. Введите счётчик "ожиданий" и отключайте `sleep` после первых двух срабатываний:

   ```python
   if ctx.repeated_silence > 2:
       await asyncio.sleep(0)
   else:
       await asyncio.sleep(0.2)
   ```

2. **Параллельный filler**. Вместо `await asyncio.sleep(0.20)` создайте таск для аудиовставки и сразу переходите к запросу LLM:

   ```python
   filler_task = asyncio.create_task(play_filler())
   llm_task = asyncio.create_task(stream_answer(...))
   await asyncio.wait({filler_task}, timeout=0.2)
   async for chunk in llm_task:
       yield chunk
   ```

3. **Асинхронная фильтрация**. Оберните тяжёлые шаги в `asyncio.create_task`, чтобы не блокировать основной поток. Для детектора шума/тишины можно использовать отдельный `asyncio.Queue`, куда складывать фреймы и считывать их worker-ом.

## 4. Потери времени на уровне TTS/ARI
* Каждый чанк речи сохраняется на диск и проигрывается через ARI, после чего обработчик ждёт `max(0.5, estimated_duration)` — то есть минимум полсекунды, даже для коротких кусков.【F:app/backend/services/parallel_tts.py†L214-L259】
* `speak_optimized` для каждого синтезированного текста создаёт новый `AsteriskARIClient` (новая `aiohttp` сессия).【F:app/backend/asterisk/stasis_handler_optimized.py†L733-L788】 Это приводит к повторной установке HTTP-соединений и тратит драгоценные миллисекунды на handshakes.

**Что можно сделать:**

1. **Пул ARI-клиентов**. Создайте контекстный менеджер, который открывает `AsteriskARIClient` один раз на звонок:

   ```python
   @asynccontextmanager
   async def ari_session(channel_id: str):
       client = AsteriskARIClient()
       try:
           await client.connect()
           yield client
       finally:
           await client.close()
   ```

   И используйте его в `speak_optimized`, чтобы переиспользовать HTTP-сессию на каждый чанк.【F:app/backend/asterisk/stasis_handler_optimized.py†L733-L788】

2. **Подписка на PlaybackFinished**. Вместо `await asyncio.sleep(max(0.5, estimated_duration))` подпишитесь на событие из ARI:

   ```python
   async def wait_playback(client, playback_id):
       async for event in client.events("PlaybackFinished"):
           if event.playback["id"] == playback_id:
               return
   ```

   Такой подход убирает фиксированный минимум и синхронизируется с реальным окончанием фразы.【F:app/backend/services/parallel_tts.py†L214-L259】

3. **Буферизация TTS**. Добавьте локальный `asyncio.Queue`, куда TTS worker кладёт готовые аудиофайлы, а ARI их воспроизводит без промежуточной записи на диск. Базовый пример:

   ```python
   audio_queue: asyncio.Queue[AudioChunk] = asyncio.Queue(maxsize=3)

   async def tts_worker(text_stream):
       async for text in text_stream:
           audio_queue.put_nowait(await synthesize(text))

   async def ari_worker(client):
       while True:
           chunk = await audio_queue.get()
           await client.play(chunk)
           audio_queue.task_done()
   ```

   Диск всё ещё можно использовать как fallback, но основной поток будет идти из памяти.

## 5. Суммарное влияние
* Холодный embedding (~0.65 с) + сетевой старт LLM (~3.0 с) + обязательный filler (0.2 с) дают основную задержку ~3.8 с до осмысленного ответа.
* Дополнительные паузы (0.5 с на фильтр, ≥0.5 с на TTS `sleep`) увеличивают общее время при каждом повторе.

Устранение перечисленных точек (параллельное выполнение filler/LLM, агрессивный прогрев кеша, отказ от постоянных `sleep` и переиспользование ARI-сессий) позволит приблизить `Time To First Audio` к заявленным 1.1 с даже при новых вопросах. Дополнительно рекомендуем завести `scripts/latency_bench.py`, который будет прогонять синтетические звонки и строить отчёт в `docs/latency_dashboard.html`, чтобы ИДЕ Курсор АИ могла быстро отслеживать регрессии.