#!/usr/bin/env bash
# Запускать на машине С ИНТЕРНЕТОМ (Linux/macOS/WSL), в корне репозитория:
#   deploy/redos8/build-bundle.sh <URL-архива-python-build-standalone>
#
# URL portable-Python нужно взять руками со страницы релизов:
#   https://github.com/astral-sh/python-build-standalone/releases
# Искать самый свежий релиз, файл вида
#   cpython-3.11.<x>+<дата>-x86_64-unknown-linux-gnu-install_only.tar.gz
# (НЕ -debug, НЕ -noopt, НЕ freethreaded — обычный install_only build).
#
# Результат: deploy/redos8/dist/vacation-planner-offline-bundle-<дата>.tar.gz
# Этот архив переносится на РЕД ОС 8 и распаковывается там, дальше — install.sh.
set -euo pipefail

PYTHON_STANDALONE_URL="${1:?Укажите URL архива python-build-standalone (см. комментарий в начале файла)}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK_DIR="$(mktemp -d)"
BUNDLE_DIR="$WORK_DIR/bundle"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$ROOT_DIR/deploy/redos8/dist"

trap 'rm -rf "$WORK_DIR"' EXIT

echo "==> Рабочая директория: $WORK_DIR"
mkdir -p "$BUNDLE_DIR" "$OUT_DIR"

echo "==> [1/5] Скачиваю portable Python (для РЕД ОС 8, x86_64 glibc)"
curl -fL --retry 4 --retry-delay 2 -o "$BUNDLE_DIR/python-standalone.tar.gz" "$PYTHON_STANDALONE_URL"

echo "==> [2/5] Скачиваю wheel-пакеты бэкенда (Linux x86_64, Python 3.11, без сборки из исходников)"
mkdir -p "$BUNDLE_DIR/wheelhouse"
(
  cd "$ROOT_DIR/backend"
  python3 -m pip download -d "$BUNDLE_DIR/wheelhouse" \
    --platform manylinux_2_28_x86_64 \
    --platform manylinux2014_x86_64 \
    --python-version 311 \
    --implementation cp \
    --abi cp311 \
    --only-binary=:all: \
    "pip" "setuptools>=68" "wheel" ".[dev]"
)

echo "==> [3/5] Собираю фронтенд (статика, npm нужен только здесь, не на РЕД ОС)"
(
  cd "$ROOT_DIR/frontend"
  npm ci
  npm run build
)
cp -r "$ROOT_DIR/frontend/dist" "$BUNDLE_DIR/frontend-dist"

echo "==> [4/5] Копирую исходники бэкенда (без .venv/__pycache__/egg-info)"
mkdir -p "$BUNDLE_DIR/app/backend"
tar -C "$ROOT_DIR/backend" -cf - \
  --exclude='.venv' --exclude='__pycache__' --exclude='*.egg-info' \
  --exclude='.pytest_cache' \
  . | tar -C "$BUNDLE_DIR/app/backend" -xf -

echo "==> [5/5] Кладу конфиги установки и упаковываю бандл"
cp "$ROOT_DIR/deploy/redos8/install.sh" "$BUNDLE_DIR/"
cp "$ROOT_DIR/deploy/redos8/nginx-vacation.conf" "$BUNDLE_DIR/"
cp "$ROOT_DIR/deploy/redos8/vacation-backend.service" "$BUNDLE_DIR/"
cp "$ROOT_DIR/deploy/redos8/.env.example" "$BUNDLE_DIR/"
cp "$ROOT_DIR/deploy/redos8/README.md" "$BUNDLE_DIR/"
chmod +x "$BUNDLE_DIR/install.sh"

OUT_FILE="$OUT_DIR/vacation-planner-offline-bundle-$STAMP.tar.gz"
tar -C "$BUNDLE_DIR" -czf "$OUT_FILE" .

echo ""
echo "Готово: $OUT_FILE"
echo "Перенесите этот файл на РЕД ОС 8, распакуйте в отдельную папку и запустите:"
echo "  mkdir vacation-bundle && tar xzf $(basename "$OUT_FILE") -C vacation-bundle"
echo "  cd vacation-bundle && sudo ./install.sh"
