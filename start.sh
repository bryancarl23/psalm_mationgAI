 #!/usr/bin/env bash
 set -euo pipefail

 PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
 cd "$PROJECT_DIR"

 PYTHON=${PYTHON:-python3}
 VENV_DIR="$PROJECT_DIR/.venv"

 if [ ! -d "$VENV_DIR" ]; then
 	"$PYTHON" -m venv "$VENV_DIR"
 fi

 # shellcheck source=/dev/null
 source "$VENV_DIR/bin/activate"

 pip install --upgrade pip
 pip install -r requirements.txt

# Create .env if missing; use provided key as default
if [ ! -f "$PROJECT_DIR/.env" ]; then
	ENV_GOOGLE_API="${GOOGLE_API_KEY:-AIzaSyD_yIm5zuEV3XE6nNnvl81Ofo4q4Ki8VFg}"
	printf 'DJANGO_SECRET_KEY=%s\nGOOGLE_API_KEY=%s\n' \
		'django-insecure-streamplus-demo-secret-key' "$ENV_GOOGLE_API" > "$PROJECT_DIR/.env"
fi

 python manage.py migrate --noinput

HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

# If desired port is in use, find the next available up to +20
is_port_in_use() {
	ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":$1$"
}

TRY_PORT=$PORT
for _ in $(seq 1 20); do
	if is_port_in_use "$TRY_PORT"; then
		TRY_PORT=$((TRY_PORT+1))
	else
		break
	fi
done

if [ "$TRY_PORT" != "$PORT" ]; then
	echo "Port $PORT is busy; starting on $TRY_PORT instead." >&2
fi

exec python manage.py runserver "$HOST:$TRY_PORT"


