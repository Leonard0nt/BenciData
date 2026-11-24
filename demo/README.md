# Demo local de BenciData

Necesitas Python 3.12 y una base PostgreSQL dedicada a la demo. Desde una terminal Bash en la raíz del repositorio, prepara las dependencias.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Si tienes Docker, puedes crear la base de prueba con este comando. Si ya tienes PostgreSQL, crea una base vacía y ajusta las variables de conexión del siguiente bloque.

```sh
docker run -d --name bencidata-demo-db \
  -e POSTGRES_DB=bencidata_demo -e POSTGRES_USER=bencidata \
  -e POSTGRES_PASSWORD=bencidata -p 127.0.0.1:55432:5432 postgres:15
```

Cuando PostgreSQL esté listo, carga los datos ficticios y arranca Django.

```sh
export DB_NAME=bencidata_demo DB_USER=bencidata DB_PASSWORD=bencidata
export DB_HOST=127.0.0.1 DB_PORT=55432
export DEBUG=True ALLOWED_HOSTS=localhost,127.0.0.1
export IOT_SECRET_TOKEN=demo-local-token
python manage.py migrate --settings=demo.settings
python manage.py shell --settings=demo.settings < demo/seed.py
python manage.py runserver 127.0.0.1:58000 --settings=demo.settings
```

Abre http://127.0.0.1:58000 en el navegador del mismo equipo. La demo abre directamente con el perfil asignado a esta rama. El panel inicial muestra las opciones de ese perfil. El script de carga también imprime la ruta directa del turno.

Desde otra terminal situada en la raíz del repositorio, envía lecturas al mismo endpoint que usa la pistola:

```sh
IOT_SECRET_TOKEN=demo-local-token python3.12 demo/simulate.py 10.50
IOT_SECRET_TOKEN=demo-local-token python3.12 demo/simulate.py 24.75
```

Recarga el turno para verlas en **Informe de lecturas IoT**. Cada ejecución registra un despacho nuevo.
