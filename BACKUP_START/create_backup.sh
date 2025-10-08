#!/bin/bash

###############################################################################
# Скрипт автоматического создания бекапа проекта Asterisk Voice Bot
# Автор: Claude (Anthropic)
# Дата: 7 октября 2025
###############################################################################

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Настройки
PROJECT_DIR="/root/Asterisk_bot"
BACKUP_DIR="${PROJECT_DIR}/project_backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Функция вывода сообщений
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Функция для получения размера в читаемом формате
get_human_size() {
    local size=$1
    if [ $size -lt 1024 ]; then
        echo "${size}B"
    elif [ $size -lt 1048576 ]; then
        echo "$(($size / 1024))KB"
    elif [ $size -lt 1073741824 ]; then
        echo "$(($size / 1048576))MB"
    else
        echo "$(($size / 1073741824))GB"
    fi
}

###############################################################################
# MAIN SCRIPT
###############################################################################

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}📦 Создание бекапа проекта Asterisk Voice Bot${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Проверка существования директории проекта
if [ ! -d "$PROJECT_DIR" ]; then
    print_error "Директория проекта не найдена: $PROJECT_DIR"
    exit 1
fi

# Создание директории для бекапов если не существует
if [ ! -d "$BACKUP_DIR" ]; then
    print_info "Создание директории для бекапов: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

# Запрос описания бекапа (опционально)
echo -n "Введите описание бекапа (Enter для пропуска): "
read BACKUP_DESCRIPTION

# Формирование имени файла бекапа
if [ -n "$BACKUP_DESCRIPTION" ]; then
    # Заменяем пробелы на подчеркивания
    BACKUP_DESC_CLEAN=$(echo "$BACKUP_DESCRIPTION" | tr ' ' '_' | tr -cd '[:alnum:]_-')
    BACKUP_NAME="backup_${BACKUP_DESC_CLEAN}_${TIMESTAMP}.tar.gz"
else
    BACKUP_NAME="backup_${TIMESTAMP}.tar.gz"
fi

BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

print_info "Имя бекапа: $BACKUP_NAME"
echo ""

# Подсчет размера проекта (без папки бекапов)
print_info "Подсчет размера всего репозитория..."
cd "$PROJECT_DIR" || exit 1

PROJECT_SIZE=$(du -sb --exclude='project_backup' . 2>/dev/null | cut -f1)
if [ -n "$PROJECT_SIZE" ]; then
    HUMAN_SIZE=$(get_human_size $PROJECT_SIZE)
    print_info "Размер репозитория (без бекапов): $HUMAN_SIZE"
fi

echo ""
print_info "Создание ПОЛНОГО архива /root/Asterisk_bot/ (включая venv и chroma)..."
print_warning "Исключаются только: project_backup/, .git/, __pycache__, *.pyc, logs/"
echo ""

# Создание бекапа
# Бекапим ВЕСЬ корень /root/Asterisk_bot/ (кроме project_backup)
# ВКЛЮЧАЯ venv и chroma для полного восстановления
tar -czf "$BACKUP_PATH" \
    --exclude='project_backup' \
    --exclude='.git' \
    --exclude='asterisk-vox-bot/.git' \
    --exclude='__pycache__' \
    --exclude='**/__pycache__' \
    --exclude='**/*.pyc' \
    --exclude='asterisk-vox-bot/logs' \
    --exclude='asterisk-vox-bot/nohup.out' \
    --exclude='*.log' \
    --exclude='restore_temp' \
    -C "$(dirname "$PROJECT_DIR")" "$(basename "$PROJECT_DIR")" \
    2>&1 | grep -v "Removing leading"

# Получаем код возврата tar (первая команда в pipeline)
TAR_EXIT_CODE=${PIPESTATUS[0]}

# Проверка успешности создания бекапа
if [ $TAR_EXIT_CODE -eq 0 ] && [ -f "$BACKUP_PATH" ]; then
    BACKUP_SIZE=$(stat -c%s "$BACKUP_PATH" 2>/dev/null || stat -f%z "$BACKUP_PATH" 2>/dev/null)
    BACKUP_SIZE_HUMAN=$(get_human_size $BACKUP_SIZE)
    
    echo ""
    print_success "Бекап успешно создан!"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}📊 Информация о бекапе:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  📁 Файл:     ${YELLOW}$BACKUP_NAME${NC}"
    echo -e "  📦 Размер:   ${YELLOW}$BACKUP_SIZE_HUMAN${NC}"
    echo -e "  📍 Путь:     ${YELLOW}$BACKUP_PATH${NC}"
    echo -e "  🕐 Время:    ${YELLOW}$(date '+%Y-%m-%d %H:%M:%S')${NC}"
    if [ -n "$BACKUP_DESCRIPTION" ]; then
        echo -e "  📝 Описание: ${YELLOW}$BACKUP_DESCRIPTION${NC}"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Показываем последние 5 бекапов
    print_info "Последние 5 бекапов в папке:"
    echo ""
    ls -lht "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -5 | awk '{
        size = $5
        name = $9
        sub(".*/", "", name)
        printf "  📦 %-50s %8s\n", name, size
    }'
    
    echo ""
    
    # Подсчет общего размера всех бекапов
    TOTAL_BACKUPS=$(ls -1 "$BACKUP_DIR"/*.tar.gz 2>/dev/null | wc -l)
    TOTAL_SIZE=$(du -sb "$BACKUP_DIR" 2>/dev/null | cut -f1)
    TOTAL_SIZE_HUMAN=$(get_human_size $TOTAL_SIZE)
    
    print_info "Всего бекапов: $TOTAL_BACKUPS"
    print_info "Общий размер папки бекапов: $TOTAL_SIZE_HUMAN"
    
    # Проверка свободного места на диске
    echo ""
    AVAILABLE_SPACE=$(df -B1 "$BACKUP_DIR" | tail -1 | awk '{print $4}')
    AVAILABLE_SPACE_HUMAN=$(get_human_size $AVAILABLE_SPACE)
    print_info "Свободно на диске: $AVAILABLE_SPACE_HUMAN"
    
    # Предупреждение если мало места
    if [ $AVAILABLE_SPACE -lt 1073741824 ]; then # Меньше 1GB
        echo ""
        print_warning "Мало свободного места на диске! Рекомендуется удалить старые бекапы."
    fi
    
    echo ""
    
    # Автоматическая очистка старых бекапов (оставляем только последние 7)
    print_info "Проверка старых бекапов..."
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/*.tar.gz 2>/dev/null | wc -l)
    
    if [ $BACKUP_COUNT -gt 7 ]; then
        OLD_BACKUPS_COUNT=$(($BACKUP_COUNT - 7))
        print_warning "Найдено $BACKUP_COUNT бекапов. Удаляю $OLD_BACKUPS_COUNT старых..."
        
        # Удаляем все кроме последних 7
        ls -t "$BACKUP_DIR"/*.tar.gz | tail -n +8 | while read old_backup; do
            OLD_NAME=$(basename "$old_backup")
            OLD_SIZE=$(stat -c%s "$old_backup" 2>/dev/null || stat -f%z "$old_backup" 2>/dev/null)
            OLD_SIZE_HUMAN=$(get_human_size $OLD_SIZE)
            print_info "  🗑️  Удаляю: $OLD_NAME ($OLD_SIZE_HUMAN)"
            rm -f "$old_backup"
        done
        
        NEW_COUNT=$(ls -1 "$BACKUP_DIR"/*.tar.gz 2>/dev/null | wc -l)
        print_success "Очистка завершена. Осталось бекапов: $NEW_COUNT"
        echo ""
    else
        print_info "Бекапов: $BACKUP_COUNT (лимит: 7). Очистка не требуется."
        echo ""
    fi
    
else
    print_error "Ошибка при создании бекапа!"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Опция для просмотра содержимого бекапа
echo -n "Показать содержимое бекапа? (y/N): "
read SHOW_CONTENT

if [ "$SHOW_CONTENT" = "y" ] || [ "$SHOW_CONTENT" = "Y" ]; then
    echo ""
    print_info "Содержимое бекапа (первые 50 файлов):"
    echo ""
    tar -tzf "$BACKUP_PATH" | head -50
    
    FILE_COUNT=$(tar -tzf "$BACKUP_PATH" | wc -l)
    if [ $FILE_COUNT -gt 50 ]; then
        echo ""
        print_info "... и еще $(($FILE_COUNT - 50)) файлов"
    fi
    echo ""
fi

print_success "Готово! 🎉"
echo ""

