GESTOR DE GASTOS (Desarrollo Local)

Este documento explica la configuración para trabajar localmente usando Docker como base de datos PostgreSQL.

1. REQUISITOS

Necesitas tener instalados Python 3.x y Docker.

2. CONFIGURACIÓN DE LA BASE DE DATOS (DOCKER)

2.1 Archivo .env

Crea un archivo llamado .env en la raíz del proyecto con este contenido:

DATABASE_URL="postgresql://myuser:mypass@localhost:5432/mydb"


2.2 Ejecutar el Contenedor

Ejecuta estos comandos en tu terminal para iniciar la base de datos local. Los dos primeros comandos sirven para limpiar y recrear la base de datos si ya existía:

# Detener y eliminar el contenedor existente
docker stop local-postgres 
docker rm local-postgres

# Crear e iniciar el nuevo contenedor de PostgreSQL
docker run --name local-postgres -e POSTGRES_USER=myuser -e POSTGRES_PASSWORD=mypass -e POSTGRES_DB=mydb -p 5432:5432 -d postgres:latest


3. INSTALACIÓN Y EJECUCIÓN

3.1 Dependencias Python

Crea el entorno virtual e instala las librerías (usando requirements.txt):

python --version 
source venv/bin/activate  # o .\venv\Scripts\activate en Windows
pip install -r requirements.txt 


3.2 Iniciar Aplicación

Con Docker activo y el entorno virtual activado, ejecuta la aplicación Flask:

python gestor.py


La aplicación estará en http://127.0.0.1:5000/.

4. DATOS DE CONEXIÓN (OPCIONAL)

Si necesitas conectarte a la base de datos local con una herramienta externa (como la extensión de VS Code), usa estos datos:


Host : localhost
Puerto : 5432
Base de Datos : mydb
Usuario : myuser
Contraseña: mypass