# BenciData · Demo de Dueño

Esta rama prepara una empresa y una sucursal ficticias con diésel a **$927/L**, una pistola simulada y un turno activo en modo pistola. La pantalla abre directamente con el perfil **Dueño** y sus permisos reales.

## Desplegar con Docker Compose

Necesitas Git, Docker y Docker Compose v2. Si Docker requiere privilegios en tu equipo, antepón `sudo` a sus comandos.

```sh
git clone --branch codex/demo-dueno https://github.com/Leonard0nt/BenciData.git bencidata-dueno
cd bencidata-dueno
cp demo/deploy.env.example .env
```

Edita `.env` y define valores propios para `DEMO_DB_PASSWORD`, `DEMO_SECRET_KEY` e `IOT_SECRET_TOKEN`. Puedes generar un valor distinto para cada variable con `openssl rand -hex 32`. Mantén el archivo fuera de Git.

```sh
docker compose -p bencidata-dueno -f compose.demo.yml up --build -d
docker compose -p bencidata-dueno -f compose.demo.yml logs -f app
```

Cuando Gunicorn esté escuchando, abre [http://127.0.0.1:58001](http://127.0.0.1:58001). La demo abre sin pedir usuario ni contraseña. Pulsa Ctrl+C para salir de los logs.

- **Recorrido** Configura la empresa y administra la sucursal, los equipos, los precios y el personal desde Sucursales y Usuarios.

## Simular dos despachos

Desde el directorio del repositorio, sustituye `TU_TOKEN` por el valor de `IOT_SECRET_TOKEN`. El simulador usa la biblioteca estándar de Python 3.

```sh
env IOT_SECRET_TOKEN=TU_TOKEN python3 demo/simulate.py 10.50 --url http://127.0.0.1:58001
env IOT_SECRET_TOKEN=TU_TOKEN python3 demo/simulate.py 24.75 --url http://127.0.0.1:58001
```

Los dos despachos suman **35,25 L**. Cada ejecución registra una lectura adicional. El token permite enviar lecturas simuladas al endpoint IoT.

## Acceso desde otro equipo

El puerto queda ligado a localhost. Cada visitante tiene los permisos del perfil de esta rama sobre los mismos datos ficticios. En un servidor, publica la demo mediante un proxy inverso HTTPS con acceso restringido. Haz que el proxy envíe al puerto 58001 el `Host` original y fije `X-Forwarded-Proto: https`. Configura `DEMO_ALLOWED_HOSTS` con tu dominio, `BENCIDATA_DEMO_CSRF_ORIGINS` con su origen HTTPS y `BENCIDATA_DEMO_HTTPS=1` en `.env`, y vuelve a ejecutar `up`.

Para detenerla conservando sus datos, ejecuta `docker compose -p bencidata-dueno -f compose.demo.yml down`.
