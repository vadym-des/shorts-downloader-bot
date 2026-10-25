#!/usr/bin/env bash
set -e

PLIST_NAME="com.shortsdownloader.bot.plist"
SRC_PLIST="$(cd "$(dirname "$0")" && pwd)/$PLIST_NAME"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$PLIST_NAME"
LOG_FILE="$HOME/Library/Logs/shortsdownloader-bot.log"
ERR_FILE="$HOME/Library/Logs/shortsdownloader-bot.err"

install_service() {
    mkdir -p "$TARGET_DIR"
    mkdir -p "$HOME/Library/Logs"
    cp -f "$SRC_PLIST" "$TARGET_PLIST"
    chmod 644 "$TARGET_PLIST"
    echo "✅ Файл служби скопійовано в: $TARGET_PLIST"
}

start_service() {
    install_service
    launchctl unload -w "$TARGET_PLIST" 2>/dev/null || true
    launchctl load -w "$TARGET_PLIST"
    echo "🚀 Shorts Downloader бот успішно запущений як фонова служба 24/7!"
    echo "📋 Логи: $LOG_FILE"
}

stop_service() {
    launchctl unload -w "$TARGET_PLIST" 2>/dev/null || true
    echo "🛑 Службу Shorts Downloader зупинено."
}

restart_service() {
    echo "🔄 Перезапуск фонової служби Shorts Downloader..."
    stop_service
    sleep 1
    start_service
}

status_service() {
    echo "=== Стан служби com.shortsdownloader.bot ==="
    launchctl list | grep "com.shortsdownloader.bot" || echo "⚠️ Служба зараз не запущена в launchctl."
    echo ""
    if [ -f "$LOG_FILE" ]; then
        echo "=== Останні логи ($LOG_FILE) ==="
        tail -n 15 "$LOG_FILE"
    fi
    if [ -f "$ERR_FILE" ]; then
        echo "=== Останні помилки ($ERR_FILE) ==="
        tail -n 15 "$ERR_FILE"
    fi
}

show_logs() {
    touch "$LOG_FILE"
    echo "📋 Відстеження логів у реальному часі (Ctrl+C для виходу)..."
    tail -f "$LOG_FILE"
}

case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        status_service
        ;;
    logs)
        show_logs
        ;;
    install)
        install_service
        ;;
    *)
        echo "Використання: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
