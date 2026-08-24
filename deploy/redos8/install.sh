#!/usr/bin/env bash
# Запускать НА РЕД ОС 8, от root (sudo ./install.sh), из папки, куда
# распакован офлайн-бандл (там же, где этот файл лежит рядом с
# python-standalone.tar.gz, wheelhouse/, frontend-dist/, app/).
#
# Интернет не требуется — все зависимости уже внутри бандла.
# Требуется предустановленный (из локального/офлайн-репозитория РЕД ОС)
# пакет nginx: dnf install nginx
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Запустите от root: sudo ./install.sh" >&2
    exit 1
fi

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/vacation-planner}"
SERVICE_USER="${SERVICE_USER:-vacation}"
# HTTPS с корпоративным сертификатом (.pfx/.p12, выданным доменным CA) —
# необязательно. Задайте перед запуском, например:
#   sudo TLS_PFX_PATH=/root/server.pfx TLS_PFX_PASSWORD=secret ./install.sh
# Без этого nginx поднимается на обычном HTTP (как раньше). См. README,
# раздел "HTTPS через корпоративный сертификат".
TLS_PFX_PATH="${TLS_PFX_PATH:-}"
TLS_PFX_PASSWORD="${TLS_PFX_PASSWORD:-}"

for f in python-standalone.tar.gz wheelhouse frontend-dist app nginx-vacation.conf nginx-vacation-tls.conf vacation-backend.service .env.example; do
    if [[ ! -e "$BUNDLE_DIR/$f" ]]; then
        echo "Не найден $BUNDLE_DIR/$f — запускайте install.sh из распакованного бандла" >&2
        exit 1
    fi
done

# Бандл мог быть собран на Windows и содержать CRLF (\r\n) в текстовых
# файлах — тихо ломает значения в .env (например, DATABASE_URL) и конфиги.
# Приводим к LF перед использованием.
sed -i 's/\r$//' \
    "$BUNDLE_DIR/nginx-vacation.conf" \
    "$BUNDLE_DIR/nginx-vacation-tls.conf" \
    "$BUNDLE_DIR/vacation-backend.service" \
    "$BUNDLE_DIR/.env.example"

echo "==> Каталог установки: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

if id "$SERVICE_USER" &>/dev/null; then
    echo "==> Пользователь $SERVICE_USER уже существует"
else
    echo "==> Создаю системного пользователя $SERVICE_USER"
    useradd --system --no-create-home --shell /sbin/nologin "$SERVICE_USER"
fi

echo "==> [1/7] Распаковываю portable Python 3.11"
if [[ ! -x "$INSTALL_DIR/python/bin/python3.11" ]]; then
    tar -xzf "$BUNDLE_DIR/python-standalone.tar.gz" -C "$INSTALL_DIR"
fi
PYTHON_BIN="$INSTALL_DIR/python/bin/python3.11"
if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Не нашёл $PYTHON_BIN — проверьте архив python-standalone.tar.gz" >&2
    exit 1
fi

echo "==> [2/7] Копирую исходники бэкенда и статику фронтенда"
rsync -a --delete "$BUNDLE_DIR/app/" "$INSTALL_DIR/app/" 2>/dev/null || {
    rm -rf "$INSTALL_DIR/app"
    cp -r "$BUNDLE_DIR/app" "$INSTALL_DIR/app"
}
rsync -a --delete "$BUNDLE_DIR/frontend-dist/" "$INSTALL_DIR/frontend-dist/" 2>/dev/null || {
    rm -rf "$INSTALL_DIR/frontend-dist"
    cp -r "$BUNDLE_DIR/frontend-dist" "$INSTALL_DIR/frontend-dist"
}

echo "==> [3/7] Создаю venv и ставлю зависимости офлайн (--no-index)"
if [[ ! -x "$INSTALL_DIR/venv/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install --no-index --find-links="$BUNDLE_DIR/wheelhouse" \
    --upgrade pip setuptools wheel
"$INSTALL_DIR/venv/bin/pip" install --no-index --find-links="$BUNDLE_DIR/wheelhouse" \
    -e "$INSTALL_DIR/app/backend[dev]"

# python-gssapi (нужен только для KERBEROS_MODE=python, см. README) не
# входит в основной набор зависимостей выше — на PyPI нет готовых
# manylinux-колёс под него, а требовать его для всех установок (в т.ч. с
# KERBEROS_MODE=nginx или AUTH_PROVIDER=dev) было бы лишним. Если такое
# колесо руками положили в wheelhouse (см. README, раздел про
# KERBEROS_MODE=python) — ставим его; если нет — тихо пропускаем, это не
# ошибка установки.
if compgen -G "$BUNDLE_DIR/wheelhouse/gssapi-*.whl" > /dev/null; then
    echo "    Найден gssapi в wheelhouse — ставлю (для KERBEROS_MODE=python)"
    "$INSTALL_DIR/venv/bin/pip" install --no-index --find-links="$BUNDLE_DIR/wheelhouse" gssapi
fi

echo "==> [4/7] Настраиваю .env (не трогаю, если уже существует)"
if [[ ! -f "$INSTALL_DIR/app/backend/.env" ]]; then
    cp "$BUNDLE_DIR/.env.example" "$INSTALL_DIR/app/backend/.env"
    echo "    Создан $INSTALL_DIR/app/backend/.env — ОБЯЗАТЕЛЬНО отредактируйте"
    echo "    (DATABASE_URL, CORS_ORIGINS, AUTH_PROVIDER) перед реальной эксплуатацией."
else
    echo "    $INSTALL_DIR/app/backend/.env уже существует, оставляю как есть"
fi

echo "==> [5/7] Применяю миграции БД"
(
    cd "$INSTALL_DIR/app/backend"
    "$INSTALL_DIR/venv/bin/alembic" upgrade head
)

chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"

echo "==> [6/7] Устанавливаю systemd-юнит бэкенда"
sed \
    -e "s#__INSTALL_DIR__#$INSTALL_DIR#g" \
    -e "s#__SERVICE_USER__#$SERVICE_USER#g" \
    "$BUNDLE_DIR/vacation-backend.service" > /etc/systemd/system/vacation-backend.service
systemctl daemon-reload
systemctl enable --now vacation-backend

NGINX_CONF_SRC="$BUNDLE_DIR/nginx-vacation.conf"

if [[ -n "$TLS_PFX_PATH" ]]; then
    echo "==> Конвертирую $TLS_PFX_PATH (.pfx) в PEM для nginx"
    if [[ ! -f "$TLS_PFX_PATH" ]]; then
        echo "TLS_PFX_PATH указан, но файл не найден: $TLS_PFX_PATH" >&2
        exit 1
    fi
    if ! command -v openssl &>/dev/null; then
        echo "openssl не найден — нужен для конвертации .pfx в PEM. Установите: dnf install openssl" >&2
        exit 1
    fi
    mkdir -p "$INSTALL_DIR/tls"
    # -legacy нужен части openssl 3.x, если .pfx создан старым Windows-CA
    # (RC2/3DES-шифрование) — без флага падает с "Mac verify error". Сначала
    # пробуем без него (актуальные .pfx часто уже в новом формате), при
    # неудаче — с ним.
    convert_pfx() {
        local extra_args=("$@")
        openssl pkcs12 -in "$TLS_PFX_PATH" -clcerts -nokeys \
            -out "$INSTALL_DIR/tls/server.crt" \
            -passin "pass:$TLS_PFX_PASSWORD" "${extra_args[@]}" 2>/tmp/pfx-convert.err \
            && openssl pkcs12 -in "$TLS_PFX_PATH" -nocerts -nodes \
                -out "$INSTALL_DIR/tls/server.key" \
                -passin "pass:$TLS_PFX_PASSWORD" "${extra_args[@]}" 2>>/tmp/pfx-convert.err
    }
    if ! convert_pfx; then
        echo "    Не получилось без -legacy, пробую с ним (старый формат PKCS#12 из Windows CA)"
        if ! convert_pfx -legacy; then
            echo "Не удалось сконвертировать $TLS_PFX_PATH — вывод openssl:" >&2
            cat /tmp/pfx-convert.err >&2
            rm -f /tmp/pfx-convert.err
            exit 1
        fi
    fi
    rm -f /tmp/pfx-convert.err
    chown root:root "$INSTALL_DIR/tls/server.crt" "$INSTALL_DIR/tls/server.key"
    chmod 644 "$INSTALL_DIR/tls/server.crt"
    chmod 600 "$INSTALL_DIR/tls/server.key"
    echo "    OK: $INSTALL_DIR/tls/server.crt, $INSTALL_DIR/tls/server.key"
    NGINX_CONF_SRC="$BUNDLE_DIR/nginx-vacation-tls.conf"
fi

echo "==> [7/7] Настраиваю nginx (раздача фронтенда + прокси /api$([ -n "$TLS_PFX_PATH" ] && echo ", HTTPS"))"
if ! command -v nginx &>/dev/null; then
    echo "    nginx не найден. Установите его из локального репозитория РЕД ОС:"
    echo "      dnf install nginx"
    echo "    и запустите install.sh ещё раз (шаги 1-6 уже выполнены, повторный запуск безопасен)."
else
    sed "s#__INSTALL_DIR__#$INSTALL_DIR#g" "$NGINX_CONF_SRC" \
        > /etc/nginx/conf.d/vacation-planner.conf

    if command -v semanage &>/dev/null; then
        semanage fcontext -a -t httpd_sys_content_t "$INSTALL_DIR/frontend-dist(/.*)?" 2>/dev/null || true
        restorecon -Rv "$INSTALL_DIR/frontend-dist" >/dev/null || true
        if [[ -n "$TLS_PFX_PATH" ]]; then
            semanage fcontext -a -t cert_t "$INSTALL_DIR/tls(/.*)?" 2>/dev/null || true
            restorecon -Rv "$INSTALL_DIR/tls" >/dev/null || true
        fi
    fi
    if command -v getenforce &>/dev/null && [[ "$(getenforce)" != "Disabled" ]]; then
        setsebool -P httpd_can_network_connect 1 2>/dev/null || \
            echo "    Не удалось выставить httpd_can_network_connect через setsebool — если nginx" \
                 "не сможет проксировать на бэкенд (502), настройте SELinux вручную."
    fi

    nginx -t
    systemctl enable --now nginx
    systemctl reload nginx
fi

if command -v firewall-cmd &>/dev/null && systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-service=http >/dev/null || true
    firewall-cmd --permanent --add-service=https >/dev/null || true
    firewall-cmd --reload >/dev/null || true
fi

echo ""
echo "Готово."
echo "  Бэкенд:  systemctl status vacation-backend   (слушает 127.0.0.1:8000)"
echo "  Проверка API напрямую: curl http://127.0.0.1:8000/health"
if [[ -n "$TLS_PFX_PATH" ]]; then
    echo "  Приложение через nginx: https://<этот-сервер>/  (http перенаправляет на https)"
else
    echo "  Приложение через nginx: http://<этот-сервер>/"
fi
echo ""
echo "Не забудьте отредактировать $INSTALL_DIR/app/backend/.env под реальные"
echo "значения (БД, CORS, авторизация) и перезапустить: systemctl restart vacation-backend"
