# 🚀 ASTERISK - БЫСТРАЯ ШПАРГАЛКА

**Версия**: 2.0 | **Дата**: 01.10.2025

---

## ⚡ ОСНОВНЫЕ КОМАНДЫ

### Проверка статуса (30 секунд)
```bash
# Asterisk работает?
sudo systemctl status asterisk

# Endpoints настроены?
sudo asterisk -rx "pjsip show endpoints" | grep novofon

# Identify правила есть?
sudo asterisk -rx "pjsip show identifies"

# Python бот подключен?
sudo asterisk -rx "stasis show apps"

# ARI на localhost?
sudo asterisk -rx "http show status"
```

---

## 🔧 ПЕРЕЗАГРУЗКА

```bash
# PJSIP (после изменения pjsip.conf)
sudo asterisk -rx "pjsip reload"

# Dialplan (после изменения extensions.conf)
sudo asterisk -rx "dialplan reload"

# Весь Asterisk (крайний случай)
sudo systemctl restart asterisk
```

---

## 📊 МОНИТОРИНГ

```bash
# Активные звонки
sudo asterisk -rx "core show channels"

# Логи в реальном времени
sudo tail -f /var/log/asterisk/messages.log

# Атаки (блокировки)
sudo tail -f /var/log/asterisk/messages.log | grep "No matching endpoint"
```

---

## 🛡️ ЗАЩИТА

### Что защищает систему:
1. ✅ **PJSIP Identify** - только IP провайдера (37.139.38.56, 37.139.38.224)
2. ✅ **Dialplan** - только реальные DID (79581114700, 04912, 0011)
3. ✅ **ARI на localhost** - доступ только с сервера
4. ✅ **Нет anonymous endpoint** - нет анонимных звонков

### Проверить защиту:
```bash
# Anonymous удален?
sudo asterisk -rx "pjsip show endpoint anonymous"
# Должно: Unable to find object anonymous

# Identify правила есть?
sudo asterisk -rx "pjsip show identifies"
# Должно: Match: 37.139.38.56/32
```

---

## 🐍 PYTHON БОТ

```bash
# Запустить бота
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
python app/backend/asterisk/stasis_handler_optimized.py

# Проверить что работает
ps aux | grep stasis_handler

# Убить бота (если завис)
pkill -f stasis_handler_optimized.py
```

---

## 🚨 БЫСТРЫЕ РЕШЕНИЯ

### Звонки не проходят
```bash
# 1. Перезагрузить PJSIP
sudo asterisk -rx "pjsip reload"

# 2. Проверить Python бот
ps aux | grep stasis_handler

# 3. Перезапустить Asterisk (крайний случай)
sudo systemctl restart asterisk
```

### Бот не отвечает
```bash
# 1. Проверить ARI
sudo asterisk -rx "http show status"

# 2. Перезапустить бота
pkill -f stasis_handler_optimized.py
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
python app/backend/asterisk/stasis_handler_optimized.py
```

### Атаки проходят
```bash
# 1. Проверить anonymous УДАЛЕН
sudo asterisk -rx "pjsip show endpoint anonymous"

# 2. Проверить identify правила
sudo asterisk -rx "pjsip show identifies"

# 3. Если нет - восстановить из /etc/asterisk/pjsip.conf
```

---

## 📁 ВАЖНЫЕ ФАЙЛЫ

```
/etc/asterisk/pjsip.conf        ← Endpoints, identify
/etc/asterisk/extensions.conf   ← Dialplan
/etc/asterisk/http.conf         ← ARI настройки
/var/log/asterisk/messages.log  ← Логи
/root/Asterisk_bot/asterisk-vox-bot/  ← Python бот
```

---

## 🎯 IP-АДРЕСА ПРОВАЙДЕРА

**Novofon:**
- `37.139.38.224` (sip.novofon.ru)
- `37.139.38.56` (pbx.novofon.com)

**Ваш сервер:**
- `31.207.75.71`

---

## 📞 ОСНОВНОЙ НОМЕР

**79581114700** (Novofon)

---

**Полная документация:** `docs/asterisk-system-guide.md`

