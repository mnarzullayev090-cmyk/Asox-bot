#!/bin/bash
# ASOX bot ma'lumotlarini kunlik zaxiralash
set -euo pipefail

SRC_DIR="/home/muxa"
BACKUP_ROOT="/home/muxa/backups"
DATE=$(date +%Y-%m-%d)
DEST="$BACKUP_ROOT/$DATE"
KEEP_DAYS=14

FILES=(
    "users.json"
    "sellers.json"
    "seller_whitelist.json"
    "promotions.json"
    "requests_log.json"
    "request_counter.json"
)

mkdir -p "$DEST"

for f in "${FILES[@]}"; do
    if [ -f "$SRC_DIR/$f" ]; then
        cp -p "$SRC_DIR/$f" "$DEST/$f"
    fi
done

# eski zaxiralarni tozalash
find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20*" -mtime "+$KEEP_DAYS" -exec rm -rf {} \;
