/**
 * asterisk-vox-bot -сценарий для голосового ассистента 
 * Версия 8.4.1 (стабильная, с защитой от ложного barge-in)
 *
 * Отличия: говорим целыми предложениями (по '|'), очередь TTS, баргин чистит очередь.
 */

require(Modules.ASR);

// ─── конфигурация ────────────────────────────────────────
const WS_URL = "ws://31.207.75.71:9000/ws";
const VOICE = VoiceList.TBank.ru_RU_Alyona;

const SPEECH_END_TIMEOUT = 200;   // страховка: озвучить хвост без '|', мс
const DEBOUNCE_TIMEOUT   = 700;   // защита от эха сразу после старта TTS, мс
const BARGE_IN_GUARD_MS  = 400;   // игнор баргина первые N мс
const INPUT_DEBOUNCE_MS  = 1200;  // тишина пользователя = конец реплики, мс
// ─────────────────────────────────────────────────────────

// ─── глобальное состояние ────────────────────────────────
let call, asr, wsReady = false;

// буфер от бэкенда (ответ бота → для TTS)
let buf = "";
let bufTimer = null;

// буфер речи пользователя (ASR)
let utterBuf = "";
let utterTimer = null;
let lastUtter = "";

// TTS
let currentPlayer = null;
let isSpeaking = false;
let lastSpeakStartedAt = 0;

// очередь TTS
let ttsQueue = [];
let ttsBusy  = false;
// ─────────────────────────────────────────────────────────

function clean(txt) {
  // Можно в конце добавить точку, если хотите чётче каденс:
  // if (s && !/[.!?…]$/.test(s)) s += ".";
  return String(txt).replace(/[|*]/g, " ").replace(/\s+/g, " ").trim();
}

VoxEngine.addEventListener(AppEvents.CallAlerting, function (ev) {
  call = ev.call;
  Logger.write("🚀 start, callId=" + call.id);
  call.answer();

  // 1) ASR
  const HINTS_EXTRA = [
    "кН","кн","килоньютон","килоньютоны","килоньютона","ка-эн","кэ-эн","к эн","к эН","кэн",
    "Н","ньютон","ньютонов","ньютоне",
    "Н·м","ньютон-метр","ньютон метр","н м",
    "Н·мм","ньютон миллиметр","н мм",
    "МПа","мпа","мэ-пэ-а","эм-пэ-а","мега паскаль","мегапаскаль",
    "кПа","кпа","кэ-пэ-а","килопаскаль","кило паскаль","паскаль","Па",
    "Н/мм²","ньютон на миллиметр квадратный","н на мм2","н/мм2",
    "Гц","герц","частота в герцах",
    "мм","миллиметр","миллиметры","миллиметров","mm",
    "см","сантиметр","сантиметры","сантиметров","cm",
    "м","метр","метры","метров",
    "мм/мин","миллиметров в минуту","мм в минуту",
    "мм/с","миллиметров в секунду","мм в секунду",
    "м/с","метров в секунду",
    "об/мин","rpm","об в минуту",
    "кг","килограмм","килограмма","килограммы","kg",
    "грамм","грамма","граммы",
    "т","тонна","тонны",
    "%","проценты","процент",
    "л/мин","литр в минуту","литров в минуту","l/min",
    "бар","bar","кгс/см²","килограмм силы на сантиметр квадратный",
    "Вт","ватт","w","кВт","квт","киловатт","kw","кВт·ч","квтч","киловатт час",
    "В","вольт","v","А","ампер","amp","Ом","омы","ohm","Ω",
    "дБ","децибел","db",
    "мин/ч","минут в час","мин на час",
    "ISO 7500-1","ASTM E4","ISO 6892-1","ASTM E8","ASTM E9",
  ];

  asr = VoxEngine.createASR({
    profile: ASRProfileList.TBank.ru_RU,
    interimResults: true,
    phraseHints: [
      "твердомер","твердомеры","твердомер Роквелла","твердомер Бринелля","твердомер Виккерса","микротвердомер",
      "разрывная машина","разрывные машины","испытательная машина","испытательные машины","универсальная разрывная машина",
      "испытательный пресс","испытательные прессы","пресс ПИ",
      "РГМ","РГМ-1000","РГМ-1000-А",
      "динамическая машина","усталостная машина",
      "испытание на растяжение","испытание на сжатие","испытание на изгиб","Метротэст",
      "РГМ-Г-А","РЭМ","РЭМ-I-0,1","РЭМ-1","РЭМ-50","РЭМ-100","РЭМ-200","РЭМ-300","РЭМ-500","РЭМ-600",
      "РЭМ-I-2","РЭМ-I-3","РЭМ-I-5","РЭМ-I-10",
      "УИМ-Д","УИМ-Д-100","УИМ-Д-250","УИМ-Д-500","УИМ-Д-750","пневмодинамическая машина",
      "ПИМ-МР-100","ПИМ-МР-200","ПИМ-МР-300",
      "универсальные испытательные машины","универсальная машина",
      "машина на усталость","усталостные испытания",
      "машины на кручение","машины на изгиб",
      "МК","МКС","МКС-1000","МКС-2000","МКС-3000","МКС-500",
      "системы температурных испытаний","СТИ",
      "экстензометр","УИД-ПБ","M-VIEW",
      "копра маятниковая","копры","КМ","КВ","КММ","ИКМ-450-А",
      "стилоскоп","СЛП","СЛ-13У","СЛ-15",
      "климатические камеры","КТХ","КИО","КИУ","КТВ","КТЗ","КТЧ",
      "ресурсное испытание","испытание на износ",
      "машины шлифовально-полировальные","МШП","МП",
      "микроскоп металлографический","ММИ","ММР","ММП",
      "лаборатория модульная","ЛММ-25",
      "мебель лабораторная","СКЗ-1","СКЗ-2","СКЗ-3-А","СКЗ-4"
    ].concat(HINTS_EXTRA)
  });

  // баргин: останавливаем/отменяем TTS и очередь (если не слишком рано)
  const stopPlayerOnBargeIn = (eventName) => {
    const sinceStart = Date.now() - lastSpeakStartedAt;
    if (currentPlayer && sinceStart < BARGE_IN_GUARD_MS) {
      // слишком рано — вероятное эхо; игнорируем
      return;
    }
    Logger.write(`[BARGE-IN] '${eventName}' → cancel TTS (sinceStart=${sinceStart}ms).`);
    if (currentPlayer) {
      try { currentPlayer.stop(); } catch (e) {}
      currentPlayer = null;
    }
    isSpeaking = false;
    // очищаем очередь, чтобы не договаривать устаревшее
    if (ttsQueue.length) {
      ttsQueue = [];
      ttsBusy  = false;
    }
  };

  // безопасные подписки на события ASR (разные провайдеры поддерживают разный набор)
  function hasASREvent(name) {
    return typeof ASREvents !== 'undefined' && ASREvents && typeof ASREvents[name] !== 'undefined';
  }
  if (hasASREvent('CaptureStarted')) {
    asr.addEventListener(ASREvents.CaptureStarted, () => stopPlayerOnBargeIn('CaptureStarted'));
  }
  if (hasASREvent('InterimResult')) {
    asr.addEventListener(ASREvents.InterimResult, () => stopPlayerOnBargeIn('InterimResult'));
  }

  // Быстрый флаш пользовательской реплики по окончанию захвата речи
  function flushUserUtterance(reason) {
    if (!utterBuf) return;
    if (utterTimer) { clearTimeout(utterTimer); utterTimer = null; }
    const normalizedReady = normalizeUtterance(utterBuf.trim());
    Logger.write(`🗣️ RAW(${reason}): ` + utterBuf);
    if (normalizedReady && wsReady && normalizedReady !== lastUtter && isInformative(normalizedReady)) {
      Logger.write("🧭 NORM SEND: " + normalizedReady);
      socket.send(normalizedReady);
      lastUtter = normalizedReady;
    } else {
      Logger.write("⏳ skipped non-informative user chunk");
    }
    utterBuf = "";
    // если в этот момент шёл набор ответа — обнулим его, чтобы не смешивать
    if (bufTimer) { clearTimeout(bufTimer); bufTimer = null; buf = ""; }
  }

  if (hasASREvent('CaptureStopped')) {
    asr.addEventListener(ASREvents.CaptureStopped, function () {
      flushUserUtterance('CaptureStopped');
    });
  }

  // нормализация распознанного текста
  function normalizeUtterance(input) {
    if (!input) return input;
    let t = input;
    t = t.replace(/[–—−]/g, "-").replace(/\s+/g, " ");

    t = t.replace(/\b(рэм|рем|рен)\b/gi, "РЭМ");
    t = t.replace(/\b(ргм|эргэм)\b/gi, "РГМ");
    t = t.replace(/\b(стилос?коп|стелоскоп|стилоска?п|филос\w*|филоскоп)\b/gi, "стилоскоп");

    t = t.replace(/\b(к\s?эн|ка-эн|кэ-эн|к\s?ен|к\s?э\s?н|кэн)\b/gi, "кН");
    t = t.replace(/\bкило\s?ньютоны?\b/gi, "кН");
    t = t.replace(/\bкн\b/gi, "кН");

    t = t.replace(/\b(м\s?п\s?а|мэ-пэ-а|эм-пэ-а|мегапаскал[ьяеы]?|мега\s?паскал[ьяеы]?)\b/gi, "МПа");
    t = t.replace(/\b(к\s?п\s?а|кэ-пэ-а|килопаскал[ьяеы]?|кило\s?паскал[ьяеы]?)\b/gi, "кПа");
    t = t.replace(/\b(герц|герцы|гц)\b/gi, "Гц");

    t = t.replace(/\bньютон[а-я]*\b/gi, "Н");
    t = t.replace(/\b(ньюто[нн][ -]?метр[а-я]*|н\s?м)\b/gi, "Н·м");
    t = t.replace(/\b(ньюто[нн][ -]?миллиметр[а-я]*|н\s?мм)\b/gi, "Н·мм");
    t = t.replace(/\b(н(ь?ютон)?\s*(?:\/|на)\s*мм\s*(?:\^?2|²)|ньютон\s+на\s+миллиметр\s+квадратн[а-я]*)\b/gi, "Н/мм²");

    t = t.replace(/\bмиллиметр[а-я]*\b/gi, "мм");
    t = t.replace(/\bmm\b/gi, "мм");
    t = t.replace(/\bсантиметр[а-я]*\b/gi, "см");
    t = t.replace(/\bcm\b/gi, "см");
    t = t.replace(/\bметр[а-я]*\b/gi, "м");

    t = t.replace(/\b(миллиметров\s+в\s+минуту|мм\s+в\s+минуту)\b/gi, "мм/мин");
    t = t.replace(/\b(миллиметров\s+в\s+секунду|мм\s+в\s+секунду|мм\/с)\b/gi, "мм/с");
    t = t.replace(/\b(метров\s+в\s+секунду)\b/gi, "м/с");
    t = t.replace(/\b(r\s?p\s?m|оборотов?\s+в\s+минуту|об\/?мин)\b/gi, "об/мин");

    t = t.replace(/\bкилограмм[а-я]*\b/gi, "кг");
    t = t.replace(/\bkg\b/gi, "кг");
    t = t.replace(/\bграмм[а-я]*\b/gi, "г");
    t = t.replace(/\bтонн[а-я]*\b/gi, "т");

    t = t.replace(/\bградус(ов)?\s+цельсия\b/gi, "°C");
    t = t.replace(/\bпо\s+цельсию\b/gi, "°C");
    t = t.replace(/\bпроцент(ов)?\b/gi, "%");

    t = t.replace(/\b(ватт(а|ов)?|w)\b/gi, "Вт");
    t = t.replace(/\b(киловатт(а|ов)?|к\s?вт|kw)\b/gi, "кВт");
    t = t.replace(/\b(кВт\s*[·xx]\s*ч|киловатт\s*час[а-я]*|квтч)\b/gi, "кВт·ч");
    t = t.replace(/\b(вольт(а|ов)?|v)\b/gi, "В");
    t = t.replace(/\b(ампер(а|ов)?|amp(?:s)?)\b/gi, "А");
    t = t.replace(/\b(ом(а|ов)?|ohm|Ω)\b/gi, "Ом");

    t = t.replace(/\b(литр(ов)?\s*в\s*минуту|л\/?мин|l\/?min)\b/gi, "л/мин");
    t = t.replace(/\b(бар|bar)\b/gi, "бар");
    t = t.replace(/\b(кгс\s*\/\s*см\s*(?:\^?2|²)|килограмм\s*силы\s*на\s*сантиметр\s*квадратн[а-я]*)\b/gi, "кгс/см²");

    t = t.replace(/\b(децибел(а|ов)?|дб|db)\b/gi, "дБ");
    t = t.replace(/\s+\/\s+/g, "/");

    return t.trim();
  }

  function isInformative(text) {
    if (!text) return false;
    const trimmed = text.trim().toLowerCase();
    const fillers = ["да","ага","угу","ну","ок","окей","хорошо","понятно","о","угу-угу"];
    if (trimmed.length <= 2) return false;
    if (fillers.includes(trimmed)) return false;
    if (/[0-9]/.test(trimmed)) return true;
    if (/(кн|мпа|мм\/с|мм\/мин|гц|iso|astm|гост|ргм|рэм|стилоскоп|арматур|твердомер)/i.test(trimmed)) return true;
    return trimmed.split(/\s+/).length >= 3;
  }

  asr.addEventListener(ASREvents.Result, function (e) {
    if (!e.text) return;

    // аккуратно собираем растущий результат
    const txt = e.text.trim();
    if (!utterBuf) {
      utterBuf = txt;
    } else if (txt.startsWith(utterBuf)) {
      utterBuf = txt; // растёт
    } else if (!utterBuf.startsWith(txt)) {
      utterBuf = (utterBuf + " " + txt).replace(/\s+/g, " ").trim();
    }

    if (utterTimer) clearTimeout(utterTimer);
    utterTimer = setTimeout(function () {
      const normalizedReady = normalizeUtterance(utterBuf.trim());
      Logger.write("🗣️ RAW: " + utterBuf);
      if (normalizedReady && wsReady && normalizedReady !== lastUtter && isInformative(normalizedReady)) {
        Logger.write("🧭 NORM SEND: " + normalizedReady);
        socket.send(normalizedReady);
        lastUtter = normalizedReady;
      } else {
        Logger.write("⏳ skipped non-informative user chunk");
      }
      utterBuf = "";
      utterTimer = null;

      // если в этот момент шёл набор ответа — обнулим его, чтобы не смешивать
      if (bufTimer) { clearTimeout(bufTimer); bufTimer = null; buf = ""; }
    }, INPUT_DEBOUNCE_MS);
  });

  // 2) подключаем входящий звук к ASR
  call.sendMediaTo(asr);

  // 3) WebSocket к бэкенду
  const callerId = call.callerid();
  const urlWithCallerId = `${WS_URL}?callerId=${encodeURIComponent(callerId)}`;
  const socket = VoxEngine.createWebSocket(urlWithCallerId);

  socket.addEventListener(WebSocketEvents.OPEN, function () {
    wsReady = true;
    Logger.write(`✅ WS open for ${callerId}.`);
  });

  // Говорим только целыми предложениями по символу '|'
  socket.addEventListener(WebSocketEvents.MESSAGE, function (m) {
    if (!m.text) return;

    buf += m.text;

    // 1) выговорим все завершённые предложения
    while (buf.includes("|")) {
      const idx = buf.indexOf("|");
      const sentence = clean(buf.slice(0, idx));
      buf = buf.slice(idx + 1);
      if (sentence) speakQueued(sentence);
    }

    // 2) если остался «хвост» без '|', заведём страховочный таймер
    if (bufTimer) clearTimeout(bufTimer);
    if (buf) {
      bufTimer = setTimeout(function () {
        const tail = clean(buf);
        buf = "";
        bufTimer = null;
        if (tail) speakQueued(tail);
      }, SPEECH_END_TIMEOUT);
    } else {
      bufTimer = null;
    }
  });

  socket.addEventListener(WebSocketEvents.ERROR, function (e) {
    Logger.write("❌ WS error:" + JSON.stringify(e));
  });

  socket.addEventListener(WebSocketEvents.CLOSE, function () {
    Logger.write("🔌 WS close.");
    wsReady = false;
  });

  // 4) завершение звонка
  call.addEventListener(CallEvents.Disconnected, function () {
    Logger.write("📴 hang-up.");
    VoxEngine.terminate();
  });
});

// ─── Очередь TTS ─────────────────────────────────────────
function speakQueued(text) {
  if (!text) return;
  ttsQueue.push(text);
  if (!ttsBusy) processTTSQueue();
}

function processTTSQueue() {
  if (ttsBusy) return;
  const next = ttsQueue.shift();
  if (!next) return;

  ttsBusy = true;
  speakOne(next, function () {
    ttsBusy = false;
    processTTSQueue();
  });
}

/* Проиграть одну фразу */
function speakOne(text, done) {
  Logger.write(`▶️ TTS: "${text}"`);

  if (currentPlayer) {
    try { currentPlayer.stop(); } catch (e) {}
    currentPlayer = null;
  }

  isSpeaking = true;
  lastSpeakStartedAt = Date.now();
  setTimeout(() => { isSpeaking = false; }, DEBOUNCE_TIMEOUT);

  currentPlayer = VoxEngine.createTTSPlayer(text, {
    language: VOICE,
    progressivePlayback: true // фраза уже целиком → просодия ровная
  });
  currentPlayer.sendMediaTo(call);

  const finish = () => {
    currentPlayer = null;
    if (typeof done === "function") done();
  };

  currentPlayer.addEventListener(PlayerEvents.PlaybackFinished, finish);
  currentPlayer.addEventListener(PlayerEvents.Stopped,          finish);
}
