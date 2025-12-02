#!/bin/sh
set -e

echo "⚙ Esperando a la base de datos..."

if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
  # Espera a que el puerto de la BD esté disponible
  until nc -z "$DB_HOST" "$DB_PORT"; do
    echo "⏳ Base de datos no disponible aún en ${DB_HOST}:${DB_PORT}..."
    sleep 2
  done
fi

echo "📦 collectstatic..."
python manage.py collectstatic --noinput

echo "📚 migrate..."
python manage.py migrate --noinput

# Crear superusuario automático si hay variables definidas
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "👤 Verificando/creando superusuario..."

  python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
email = "${DJANGO_SUPERUSER_EMAIL}"
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(
        email=email,
        password="${DJANGO_SUPERUSER_PASSWORD}",
        username="${DJANGO_SUPERUSER_USERNAME or 'admin'}",
    )
    print("✅ Superusuario creado:", email)
else:
    print("ℹ Superusuario ya existe:", email)
EOF

fi

echo "🚀 Levantando servidor Gunicorn..."
gunicorn core.wsgi:application --bind 0.0.0.0:8000
