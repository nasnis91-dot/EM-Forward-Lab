#!/bin/bash
# EM-Forward Lab - dobel-klik untuk menjalankan
# Developed by Yanis Mawardinur for Academic Purpose
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:$PATH"

PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  osascript -e 'display alert "EM-Forward Lab" message "Python 3.11 atau lebih baru belum terpasang.\nUnduh dari python.org, lalu dobel-klik Jalankan.command lagi."'
  open "https://www.python.org/downloads/macos/"
  exit 1
fi

if [ ! -f ".venv/.siap" ]; then
  echo "Persiapan pertama (sekali saja, butuh internet, ±2-5 menit)..."
  "$PY" -m venv .venv || exit 1
  ./.venv/bin/python -m pip install --upgrade pip -q
  if ./.venv/bin/python -m pip install -r requirements.txt; then
    touch .venv/.siap
  else
    osascript -e 'display alert "EM-Forward Lab" message "Gagal memasang paket. Periksa koneksi internet lalu coba lagi."'
    exit 1
  fi
fi

echo "Membuka EM-Forward Lab..."
./.venv/bin/python app.py
