#!/usr/bin/env bash
set -euo pipefail

### НАСТРОЙКИ ПОД ТВОЙ ПРОЕКТ ###

DOMAIN="faso312.ru"
PROJECT_DIR="/root/TH3"
PYTHON_BIN="python3.12"
VENV_DIR="/root/.venv"
DB_NAME="th3_db"
DB_USER="th3_app"
DB_PASSWORD="1234"   # если поменяешь — не забудь поменять в server.js и в SQL

echo "=== [1/9] Установка системных пакетов ==="
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  "$PYTHON_BIN" "$PYTHON_BIN-venv" python3-pip \
  build-essential libpq-dev \
  nginx \
  postgresql postgresql-contrib \
  curl git

echo "=== [2/9] Установка Node.js 22 + pm2 ==="
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
fi

npm install -g pm2

echo "=== [3/9] Настройка PostgreSQL (роль + БД) ==="
sudo -u postgres psql <<SQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_USER') THEN
      CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASSWORD';
   END IF;
END
\$\$;

DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME') THEN
      CREATE DATABASE $DB_NAME OWNER $DB_USER;
   END IF;
END
\$\$;

GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
SQL

if [ -f "$PROJECT_DIR/db/schema.sql" ]; then
  echo "=== [3b/9] Заливаю схему БД из db/schema.sql ==="
  sudo -u postgres psql -d "$DB_NAME" -f "$PROJECT_DIR/db/schema.sql"
else
  echo "!!! ВНИМАНИЕ: db/schema.sql не найден, БД без схемы"
fi

echo "=== [4/9] Python venv + зависимости ==="
if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_DIR/py_back/requirements.txt"

echo "=== [5/9] Node зависимости backend/front ==="
cd "$PROJECT_DIR/server"
npm ci

cd "$PROJECT_DIR/front_app"
npm ci

echo "=== [6/9] Сборка и деплой фронта ==="
cd "$PROJECT_DIR"
bash deploy.sh

echo "=== [7/9] Nginx конфиг для $DOMAIN (HTTP) ==="

cat >/etc/nginx/sites-available/faso312.ru <<'NGINX'
server {
    listen 80;
    server_name faso312.ru www.faso312.ru;

    root /var/www/faso312.ru;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade           $http_upgrade;
        proxy_set_header Connection        "upgrade";

        proxy_set_header If-Modified-Since "";
        proxy_set_header If-None-Match     "";
        etag off;
        expires off;
        add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0" always;
        proxy_cache_bypass 1;
        proxy_no_cache 1;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/faso312.ru /etc/nginx/sites-enabled/faso312.ru
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx
systemctl enable nginx

echo "=== [8/9] Настройка pm2 процессов ==="
cd "$PROJECT_DIR"

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

# th3-search (8001)
pm2 start py_back/search_service.py \
  --name th3-search \
  --interpreter "$VENV_DIR/bin/python" \
  --cwd "$PROJECT_DIR"

# runtime2 (8002)
pm2 start "uvicorn runtime_llm_itr4:app --app-dir $PROJECT_DIR/py_back/rexexp --host 127.0.0.1 --port 8002" \
  --name runtime2 \
  --interpreter "$VENV_DIR/bin/python" \
  --cwd "$PROJECT_DIR/py_back"

# server (Node, 5000)
pm2 start server/server.js \
  --name server \
  --cwd "$PROJECT_DIR/server"

pm2 save

echo "=== [9/9] pm2 автозапуск через systemd ==="
pm2 startup systemd -u root --hp /root >/tmp/pm2-startup.sh
bash /tmp/pm2-startup.sh
rm /tmp/pm2-startup.sh

echo "=== ГОТОВО ==="
echo "Проверка:"
echo "  - pm2 ls"
echo "  - curl http://127.0.0.1:5000/api/... (к твоим ручкам)"
echo "  - открыть http://$DOMAIN в браузере (по HTTP, без https пока)"
