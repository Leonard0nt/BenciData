#!/bin/sh
set -eu
python manage.py migrate --noinput --settings=demo.deployment
python manage.py shell --settings=demo.deployment < demo/seed.py
python manage.py collectstatic --noinput --settings=demo.deployment
export DJANGO_SETTINGS_MODULE=demo.deployment
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 2
