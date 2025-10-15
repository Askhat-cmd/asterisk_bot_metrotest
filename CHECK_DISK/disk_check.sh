#!/bin/bash

##############################################################################
# СКРИПТ МОНИТОРИНГА ДИСКОВОГО ПРОСТРАНСТВА
# Проект: Метротэст Voice Bot
# Версия: 1.0
# Дата: 15.10.2025
##############################################################################

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Файлы для истории
HISTORY_FILE="/root/Asterisk_bot/CHECK_DISK/.disk_history.txt"
CURRENT_FILE="/tmp/disk_current_$$.txt"

# Функции
print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_section() {
    echo ""
    echo -e "${GREEN}▶ $1${NC}"
    echo "────────────────────────────────────────────────────────────"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}🔴 $1${NC}"
}

print_ok() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Проверка использования диска
check_disk_usage() {
    USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    USED=$(df -h / | awk 'NR==2 {print $3}')
    AVAIL=$(df -h / | awk 'NR==2 {print $4}')
    
    echo "Использовано: $USED / Доступно: $AVAIL"
    
    if [ $USAGE -gt 95 ]; then
        print_error "КРИТИЧНО! Диск заполнен на $USAGE%"
        echo "  СРОЧНО: Запустите очистку логов!"
    elif [ $USAGE -gt 85 ]; then
        print_warning "Диск заполнен на $USAGE% - требуется очистка"
    elif [ $USAGE -gt 70 ]; then
        print_warning "Диск заполнен на $USAGE% - следите за ростом"
    else
        print_ok "Диск заполнен на $USAGE% - нормально"
    fi
    
    # Сохранить в текущий файл
    echo "DISK_USAGE=$USAGE" >> $CURRENT_FILE
    echo "DISK_USED=$USED" >> $CURRENT_FILE
    echo "DISK_AVAIL=$AVAIL" >> $CURRENT_FILE
}

# Топ-10 директорий
check_top_directories() {
    echo ""
    du -sh /root/Asterisk_bot/* 2>/dev/null | sort -hr | head -10 | \
    while read SIZE DIR; do
        printf "  %-10s %s\n" "$SIZE" "$(basename $DIR)"
    done
    
    # Сохранить размер проекта
    PROJECT_SIZE=$(du -sh /root/Asterisk_bot 2>/dev/null | awk '{print $1}')
    echo "PROJECT_SIZE=$PROJECT_SIZE" >> $CURRENT_FILE
}

# Топ-10 файлов
check_top_files() {
    echo ""
    find /root/Asterisk_bot -type f -exec du -h {} + 2>/dev/null | \
    sort -hr | head -10 | \
    while read SIZE FILE; do
        printf "  %-10s %s\n" "$SIZE" "$(basename $FILE)"
    done
}

# Большие логи
check_large_logs() {
    echo ""
    
    # Asterisk логи
    if [ -f /var/log/asterisk/messages.log ]; then
        ASTERISK_SIZE=$(du -h /var/log/asterisk/messages.log | awk '{print $1}')
        echo "  Asterisk messages.log: $ASTERISK_SIZE"
        
        # Проверка критичности
        ASTERISK_MB=$(du -m /var/log/asterisk/messages.log | awk '{print $1}')
        if [ $ASTERISK_MB -gt 1000 ]; then
            print_error "  ⚠️  КРИТИЧНО! Asterisk лог > 1GB!"
            echo "      Выполните: sudo logrotate -f /etc/logrotate.d/asterisk"
        elif [ $ASTERISK_MB -gt 500 ]; then
            print_warning "  ⚠️  Asterisk лог > 500MB, рекомендуется ротация"
        fi
        
        echo "ASTERISK_LOG_SIZE=$ASTERISK_SIZE" >> $CURRENT_FILE
    fi
    
    # Логи проекта
    if [ -d /var/log/metrotech ]; then
        METROTECH_SIZE=$(du -sh /var/log/metrotech 2>/dev/null | awk '{print $1}')
        echo "  Metrotech logs: $METROTECH_SIZE"
        echo "METROTECH_LOG_SIZE=$METROTECH_SIZE" >> $CURRENT_FILE
    fi
    
    # Другие большие логи
    find /var/log -type f -name "*.log" -size +50M 2>/dev/null | while read LOG; do
        SIZE=$(du -h "$LOG" | awk '{print $1}')
        echo "  $(basename $LOG): $SIZE"
    done
}

# Записи звонков
check_recordings() {
    echo ""
    
    if [ -d /var/spool/asterisk/recording ]; then
        REC_COUNT=$(find /var/spool/asterisk/recording -name "*.wav" 2>/dev/null | wc -l)
        REC_SIZE=$(du -sh /var/spool/asterisk/recording 2>/dev/null | awk '{print $1}')
        echo "  Записей звонков: $REC_COUNT файлов ($REC_SIZE)"
        echo "RECORDINGS_COUNT=$REC_COUNT" >> $CURRENT_FILE
        echo "RECORDINGS_SIZE=$REC_SIZE" >> $CURRENT_FILE
    fi
    
    if [ -d /var/lib/asterisk/sounds ]; then
        TTS_COUNT=$(find /var/lib/asterisk/sounds -name "stream_*.wav" 2>/dev/null | wc -l)
        TTS_SIZE=$(du -sh /var/lib/asterisk/sounds 2>/dev/null | awk '{print $1}')
        echo "  TTS файлов: $TTS_COUNT файлов ($TTS_SIZE)"
        echo "TTS_COUNT=$TTS_COUNT" >> $CURRENT_FILE
        echo "TTS_SIZE=$TTS_SIZE" >> $CURRENT_FILE
    fi
}

# Backups
check_backups() {
    echo ""
    
    if [ -d /root/Asterisk_bot/project_backup ]; then
        BACKUP_COUNT=$(ls -1 /root/Asterisk_bot/project_backup 2>/dev/null | wc -l)
        BACKUP_SIZE=$(du -sh /root/Asterisk_bot/project_backup 2>/dev/null | awk '{print $1}')
        echo "  Project backups: $BACKUP_COUNT директорий ($BACKUP_SIZE)"
        echo "BACKUP_COUNT=$BACKUP_COUNT" >> $CURRENT_FILE
        echo "BACKUP_SIZE=$BACKUP_SIZE" >> $CURRENT_FILE
        
        if [ $BACKUP_COUNT -gt 5 ]; then
            print_warning "  ⚠️  Много backups ($BACKUP_COUNT), рекомендуется оставить последние 3"
        fi
    fi
}

# Сравнение с предыдущей проверкой
compare_with_history() {
    if [ ! -f "$HISTORY_FILE" ]; then
        echo ""
        echo "Нет истории для сравнения (это первый запуск)"
        return
    fi
    
    echo ""
    
    # Загрузить предыдущие значения
    source "$HISTORY_FILE"
    PREV_USAGE=$DISK_USAGE
    PREV_PROJECT_SIZE=$PROJECT_SIZE
    PREV_ASTERISK_SIZE=$ASTERISK_LOG_SIZE
    
    # Загрузить текущие значения
    source "$CURRENT_FILE"
    CURR_USAGE=$DISK_USAGE
    CURR_PROJECT_SIZE=$PROJECT_SIZE
    CURR_ASTERISK_SIZE=$ASTERISK_LOG_SIZE
    
    # Дата предыдущей проверки
    PREV_DATE=$(stat -c %y "$HISTORY_FILE" | cut -d' ' -f1)
    
    echo "Сравнение с предыдущей проверкой ($PREV_DATE):"
    echo ""
    
    # Сравнить использование диска
    if [ $CURR_USAGE -gt $PREV_USAGE ]; then
        DIFF=$((CURR_USAGE - PREV_USAGE))
        print_warning "  Диск: $PREV_USAGE% → $CURR_USAGE% (+$DIFF%)"
    elif [ $CURR_USAGE -lt $PREV_USAGE ]; then
        DIFF=$((PREV_USAGE - CURR_USAGE))
        print_ok "  Диск: $PREV_USAGE% → $CURR_USAGE% (-$DIFF%)"
    else
        echo "  Диск: $CURR_USAGE% (без изменений)"
    fi
    
    # Сравнить размер проекта
    echo "  Проект: $PREV_PROJECT_SIZE → $CURR_PROJECT_SIZE"
    
    # Сравнить Asterisk лог
    if [ ! -z "$CURR_ASTERISK_SIZE" ] && [ ! -z "$PREV_ASTERISK_SIZE" ]; then
        echo "  Asterisk log: $PREV_ASTERISK_SIZE → $CURR_ASTERISK_SIZE"
    fi
}

# Рекомендации
show_recommendations() {
    USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    echo ""
    echo "Рекомендуемые действия:"
    echo ""
    
    if [ $USAGE -gt 85 ]; then
        echo "  1. ⚠️  СРОЧНО: Ротация Asterisk логов"
        echo "     sudo logrotate -f /etc/logrotate.d/asterisk"
        echo ""
        echo "  2. Удалить старые записи звонков (>30 дней)"
        echo "     find /var/spool/asterisk/recording/ -name \"*.wav\" -mtime +30 -delete"
        echo ""
        echo "  3. Удалить старые TTS файлы (>7 дней)"
        echo "     find /var/lib/asterisk/sounds/ -name \"stream_*.wav\" -mtime +7 -delete"
    elif [ $USAGE -gt 70 ]; then
        echo "  1. Проверить размер Asterisk логов"
        echo "     ls -lh /var/log/asterisk/messages.log"
        echo ""
        echo "  2. Настроить автоматическую очистку (см. CHECK_DISK/README.md)"
    else
        echo "  ✅ Всё в порядке! Продолжайте мониторинг раз в неделю."
    fi
    
    echo ""
    echo "Подробности: /root/Asterisk_bot/CHECK_DISK/README.md"
}

# Главная функция
main() {
    # Очистить текущий файл
    > $CURRENT_FILE
    
    # Заголовок
    clear
    print_header "💾 МОНИТОРИНГ ДИСКОВОГО ПРОСТРАНСТВА"
    echo "Дата: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    # 1. Общее использование
    print_section "1. Общее использование диска"
    check_disk_usage
    
    # 2. Топ директории
    print_section "2. Топ-10 самых больших директорий проекта"
    check_top_directories
    
    # 3. Топ файлы
    print_section "3. Топ-10 самых больших файлов"
    check_top_files
    
    # 4. Логи
    print_section "4. Большие логи (потенциальная проблема)"
    check_large_logs
    
    # 5. Записи
    print_section "5. Записи звонков и TTS файлы"
    check_recordings
    
    # 6. Backups
    print_section "6. Backups проекта"
    check_backups
    
    # 7. Сравнение (если есть флаг --compare)
    if [[ "$1" == "--compare" ]] || [[ "$2" == "--compare" ]]; then
        print_section "7. Сравнение с предыдущей проверкой"
        compare_with_history
    fi
    
    # 8. Рекомендации
    print_section "8. Рекомендации"
    show_recommendations
    
    # Сохранить историю (если есть флаг --save)
    if [[ "$1" == "--save" ]] || [[ "$2" == "--save" ]]; then
        cp $CURRENT_FILE $HISTORY_FILE
        echo ""
        print_ok "История сохранена в $HISTORY_FILE"
    fi
    
    # Очистить временный файл
    rm -f $CURRENT_FILE
    
    # Футер
    echo ""
    print_header "Проверка завершена"
    echo ""
}

# Справка
show_help() {
    echo "Использование: $0 [ОПЦИИ]"
    echo ""
    echo "Опции:"
    echo "  --save      Сохранить результаты для будущего сравнения"
    echo "  --compare   Сравнить с предыдущей проверкой"
    echo "  --help      Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0                    # Простая проверка"
    echo "  $0 --save             # Проверка с сохранением"
    echo "  $0 --compare          # Проверка со сравнением"
    echo "  $0 --save --compare   # Проверка, сохранение и сравнение"
    echo ""
}

# Обработка аргументов
if [[ "$1" == "--help" ]]; then
    show_help
    exit 0
fi

# Запуск
main "$@"

