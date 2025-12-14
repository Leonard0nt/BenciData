#!/bin/sh
set -e

echo "🔹 Esperando a que la base de datos esté lista..."

# Esperar a que Postgres esté arriba
# (requiere que la imagen tenga el binario `pg_isready`; si no, lo quitamos)
if command -v pg_isready > /dev/null 2>&1; then
  until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
    echo "⏳ DB no lista aún, reintentando en 2s..."
    sleep 2
  done
fi

echo "✅ Base de datos lista, corriendo migraciones..."
python manage.py migrate --noinput

echo "📦 Recogiendo archivos estáticos..."
python manage.py collectstatic --noinput || echo "⚠️ collectstatic falló (ambiente dev), continuando..."

echo "👑 Creando superusuario si no existe..."
python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
import os

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "leopoldowall9@gmail.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin123")

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )
    print(f"✅ Superusuario '{username}' creado.")
else:
    print(f"ℹ️ Superusuario '{username}' ya existe, no se crea otro.")
EOF

echo "🚀 Levantando Gunicorn..."
gunicorn core.wsgi:application --bind 0.0.0.0:8000