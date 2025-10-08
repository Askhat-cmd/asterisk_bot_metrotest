#!/bin/bash

# ============================================
# 🚀 СКРИПТ ДЛЯ БЫСТРОГО PUSH В GITHUB
# ============================================
# Автоматизирует процесс: add → commit → push
# Использование: ./quick_push.sh "Описание изменений"
# ============================================

# Цвета для красивого вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Переходим в корень проекта
cd /root/Asterisk_bot

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   🚀 Git Quick Push - Быстрый пуш    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Проверка аргумента (описание коммита)
if [ -z "$1" ]; then
    echo -e "${RED}❌ ОШИБКА: Не указано описание коммита!${NC}"
    echo ""
    echo -e "${YELLOW}Использование:${NC}"
    echo -e "  ./quick_push.sh \"Описание ваших изменений\""
    echo ""
    echo -e "${YELLOW}Примеры:${NC}"
    echo -e "  ./quick_push.sh \"Исправил баг с зависанием\""
    echo -e "  ./quick_push.sh \"Добавил новую функцию TTS\""
    echo -e "  ./quick_push.sh \"Обновил документацию\""
    echo ""
    exit 1
fi

COMMIT_MESSAGE="$1"

# Шаг 1: Показываем статус
echo -e "${BLUE}📋 Шаг 1: Проверяем изменённые файлы...${NC}"
echo ""
git status --short
echo ""

# Подсчитываем количество изменённых файлов
CHANGED_FILES=$(git status --short | wc -l)

if [ "$CHANGED_FILES" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Нет изменений для коммита!${NC}"
    echo -e "${YELLOW}   Все файлы уже закоммичены или ничего не изменилось.${NC}"
    echo ""
    exit 0
fi

echo -e "${GREEN}✅ Найдено изменений: $CHANGED_FILES файл(ов)${NC}"
echo ""

# Шаг 2: Добавляем все файлы
echo -e "${BLUE}📦 Шаг 2: Добавляем все изменения (git add .)...${NC}"
git add .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Все файлы добавлены!${NC}"
else
    echo -e "${RED}❌ Ошибка при добавлении файлов!${NC}"
    exit 1
fi
echo ""

# Шаг 3: Создаём коммит
echo -e "${BLUE}💾 Шаг 3: Создаём коммит с описанием...${NC}"
echo -e "${YELLOW}   Описание: \"$COMMIT_MESSAGE\"${NC}"
git commit -m "$COMMIT_MESSAGE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Коммит создан!${NC}"
else
    echo -e "${RED}❌ Ошибка при создании коммита!${NC}"
    exit 1
fi
echo ""

# Шаг 4: Отправляем на GitHub
echo -e "${BLUE}🚀 Шаг 4: Отправляем изменения на GitHub (git push)...${NC}"
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✅ УСПЕШНО! Изменения на GitHub!   ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}🔗 Репозиторий: https://github.com/Askhat-cmd/asterisk_bot_metrotest${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}╔════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   ❌ ОШИБКА при отправке на GitHub!  ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}💡 Возможные причины:${NC}"
    echo -e "   1. Проблемы с интернет-соединением"
    echo -e "   2. Неправильный токен в ~/.git-credentials"
    echo -e "   3. Нет прав на запись в репозиторий"
    echo ""
    echo -e "${YELLOW}🔧 Попробуйте вручную:${NC}"
    echo -e "   git push origin main"
    echo ""
    exit 1
fi

