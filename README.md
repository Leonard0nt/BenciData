# BenciData · Demo de Administrador

Esta rama prepara una empresa y una sucursal ficticias con diésel a **$927/L**, una pistola simulada y un turno activo en modo pistola. La cuenta de acceso usa el perfil **Administrador** y sus permisos reales.

## Desplegar con Docker Compose

Necesitas Git, Docker y Docker Compose v2. Si Docker requiere privilegios en tu equipo, antepón `sudo` a sus comandos.

```sh
git clone --branch codex/demo-administrador https://github.com/Leonard0nt/BenciData.git bencidata-administrador
cd bencidata-administrador
cp demo/deploy.env.example .env
```

Edita `.env` y define valores propios para `DEMO_DB_PASSWORD`, `DEMO_SECRET_KEY`, `IOT_SECRET_TOKEN` y `BENCIDATA_DEMO_PASSWORD`. Puedes generar un valor distinto para cada variable con `openssl rand -hex 32`. Mantén el archivo fuera de Git.

```sh
docker compose -p bencidata-administrador -f compose.demo.yml up --build -d
docker compose -p bencidata-administrador -f compose.demo.yml logs -f app
```

Cuando Gunicorn esté escuchando, abre [http://127.0.0.1:58002](http://127.0.0.1:58002). Pulsa Ctrl+C para salir de los logs.

- **Correo** `administrador@bencidata.demo`
- **Contraseña** el valor de `BENCIDATA_DEMO_PASSWORD` que pusiste en `.env`
- **Recorrido** En Sucursales, revisa la sucursal asignada y su personal. En Inicio de servicio, abre el turno activo en modo pistola.

## Simular dos despachos

Desde el directorio del repositorio, sustituye `TU_TOKEN` por el valor de `IOT_SECRET_TOKEN`. El simulador usa la biblioteca estándar de Python 3.

```sh
env IOT_SECRET_TOKEN=TU_TOKEN python3 demo/simulate.py 10.50 --url http://127.0.0.1:58002
env IOT_SECRET_TOKEN=TU_TOKEN python3 demo/simulate.py 24.75 --url http://127.0.0.1:58002
```

Los dos despachos suman **35,25 L**. Cada ejecución registra una lectura adicional. El token permite enviar lecturas simuladas al endpoint IoT.

## Acceso desde otro equipo

El puerto queda ligado a localhost. En un servidor, publica la demo mediante un proxy inverso HTTPS con acceso restringido. Haz que el proxy envíe al puerto 58002 el `Host` original y fije `X-Forwarded-Proto: https`. Configura `DEMO_ALLOWED_HOSTS` con tu dominio, `BENCIDATA_DEMO_CSRF_ORIGINS` con su origen HTTPS y `BENCIDATA_DEMO_HTTPS=1` en `.env`, y vuelve a ejecutar `up`.

Para detenerla conservando sus datos, ejecuta `docker compose -p bencidata-administrador -f compose.demo.yml down`.
