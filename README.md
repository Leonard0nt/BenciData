# BenciData

BenciData es una aplicación web para gestionar estaciones de servicio. Centraliza el personal por sucursal, los turnos, las existencias de combustible y productos, los movimientos de caja y las lecturas de pistolas medidoras.

## Funcionalidades

- Administración de empresas, sucursales, usuarios y permisos por perfil.
- Configuración de estanques, islas, surtidores, pistolas y precios por combustible.
- Gestión de turnos, ventas de productos, créditos, comprobantes Transbank y otros movimientos de caja.
- Recepción de lecturas IoT y cierre de turnos en modo numeral o modo pistola.
- Consulta del historial de servicios y exportación de reportes a Excel.

Los perfiles disponibles son **Dueño**, **Administrador**, **Secretario(a)**, **Bombero encargado** y **Bombero**.

## Ejecutar en local

Necesitas **Python 3.12** y **PostgreSQL**. Puedes usar una instancia existente o crear una base local con Docker.

```bash
git clone https://github.com/Leonard0nt/BenciData.git
cd BenciData
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Si usas Docker, crea una base vacía para desarrollo con este comando. Espera a que PostgreSQL acepte conexiones antes de aplicar las migraciones.

```bash
docker run -d --name bencidata-dev-db \
  -e POSTGRES_DB=bencidata_dev -e POSTGRES_USER=bencidata \
  -e POSTGRES_PASSWORD=bencidata-local -p 127.0.0.1:55432:5432 postgres:15
docker exec bencidata-dev-db pg_isready -h 127.0.0.1 -U bencidata -d bencidata_dev
```

Crea un archivo `.env` en la raíz. Ajusta los valores de conexión si usas tu propio PostgreSQL y sustituye la clave de Django y el token IoT por valores locales propios.

```dotenv
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
SECRET_KEY=pon-una-clave-local
IOT_SECRET_TOKEN=pon-un-token-local
DB_NAME=bencidata_dev
DB_USER=bencidata
DB_PASSWORD=bencidata-local
DB_HOST=127.0.0.1
DB_PORT=55432
```

Crea `core/local_settings.py` con estos ajustes para usar HTTP y ver los correos de desarrollo en la terminal. Ambos archivos están excluidos de Git.

```python
from .settings import *

SESSION_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
```

Aplica las migraciones, carga los perfiles y crea la primera cuenta de Dueño. El último comando verifica el correo de ejemplo en la base local para permitir la entrada desde la interfaz.

```bash
export DJANGO_SETTINGS_MODULE=core.local_settings
python manage.py migrate
python manage.py shell -c 'from UsuarioApp.choices import PERMISOS; from UsuarioApp.models import Position; [Position.objects.get_or_create(user_position=name, defaults={"permission_code": code}) for code, name in PERMISOS]'
python manage.py createsuperuser --username dueno --email dueno@example.test
python manage.py shell -c 'from allauth.account.models import EmailAddress; from django.contrib.auth import get_user_model; user = get_user_model().objects.get(username="dueno"); EmailAddress.objects.update_or_create(user=user, email=user.email, defaults={"verified": True, "primary": True})'
python manage.py runserver 127.0.0.1:8000
```

Abre [http://127.0.0.1:8000](http://127.0.0.1:8000) e ingresa con `dueno@example.test` y la contraseña que definiste. Desde **Sucursales** puedes configurar la primera estación.

Si editas los estilos de Tailwind, instala Node.js y ejecuta `npm --prefix theme/static_src ci` seguido de `npm --prefix theme/static_src run build`.

## Integración IoT

La pistola o su proxy envía un JSON a `POST /api/iot/proxy/` con el encabezado `X-IoT-Token`. El UID debe corresponder a un bombero registrado. Usa el código IoT de una pistola configurada y abre un turno en su sucursal para asociar la lectura al servicio.

```json
{
  "uid": "UID-DE-EJEMPLO",
  "litros": 10.5,
  "pistola": "N1",
  "timestamp": "2026-01-01T12:00:00Z"
}
```

`timestamp` es opcional. En modo pistola, el cierre consolida las lecturas vinculadas a un numeral como litros vendidos. Los cobros se registran en caja.

## Estructura

| Ruta | Responsabilidad |
| --- | --- |
| `core/` | Configuración de Django y rutas |
| `UsuarioApp/` | Usuarios, perfiles y permisos |
| `sucursalApp/` | Sucursales, equipos, inventario, turnos y caja |
| `iotApp/` | Autenticación y recepción de lecturas IoT |
| `homeApp/` | Panel principal y métricas |
| `templates/`, `static/`, `theme/` | Interfaz y estilos |

## Pruebas y despliegue

Ejecuta la suite con `python manage.py test`. El usuario de PostgreSQL debe poder crear una base de pruebas.

El repositorio incluye `Dockerfile` y `docker-compose.yml` para Django con Gunicorn, PostgreSQL y Nginx. Antes de publicar un entorno, revisa la inicialización de usuarios y sustituye las credenciales de ejemplo del Compose. Configura `DEBUG=False`, claves propias, los hosts y orígenes CSRF de tu dominio, SMTP y un proxy HTTPS. Mantén los ajustes de `core/local_settings.py` para desarrollo local.

## Demos por perfil

Cada demo trae datos ficticios, simulación IoT y acceso directo con los permisos del perfil. Consulta su propio README para desplegarla.

| Perfil | Guía |
| --- | --- |
| Dueño | [Demo de Dueño](https://github.com/Leonard0nt/BenciData/tree/codex/demo-dueno) |
| Administrador | [Demo de Administrador](https://github.com/Leonard0nt/BenciData/tree/codex/demo-administrador) |
| Secretario(a) | [Demo de Secretario(a)](https://github.com/Leonard0nt/BenciData/tree/codex/demo-secretaria) |
| Bombero encargado | [Demo de Bombero encargado](https://github.com/Leonard0nt/BenciData/tree/codex/demo-bombero-encargado) |
| Bombero | [Demo de Bombero](https://github.com/Leonard0nt/BenciData/tree/codex/demo-bombero) |

También está disponible la [guía de la demo local original](https://github.com/Leonard0nt/BenciData/blob/codex/demo-bencidata/demo/README.md).
