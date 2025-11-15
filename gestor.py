from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import functools
from werkzeug.security import generate_password_hash, check_password_hash
import traceback

# Carga las variables de entorno (solo para desarrollo local)
load_dotenv()

# Inicializa Flask
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')
if app.secret_key == 'dev-secret':
    print("WARNING: usando SECRET_KEY por defecto. Define SECRET_KEY en env en producción.")

# --- Lógica de la Base de Datos ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise Exception("Error: La variable DATABASE_URL no está configurada. Debe configurarse en Render.")

def get_db_connection():
    """Intenta conectar a PostgreSQL, prueba con/ sin sslmode si hace falta."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e1:
        # Intento alternativo con sslmode (Render suele requerir ssl)
        try:
            print("DB: primer intento falló, reintentando con sslmode=require...", str(e1))
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            return conn
        except Exception as e2:
            print("DB: fallo al conectar a la BD:", str(e1), str(e2))
            raise

def inicializar_bd():
    """Crea las tablas 'users' y 'gastos' si no existen."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id SERIAL PRIMARY KEY,
                descripcion TEXT NOT NULL,
                monto NUMERIC(10, 2) NOT NULL,
                fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                username TEXT
            );
        """)
        cursor.execute("ALTER TABLE gastos ADD COLUMN IF NOT EXISTS username TEXT;")
        try:
            cursor.execute("""
                ALTER TABLE gastos
                ADD CONSTRAINT gastos_username_fkey FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE;
            """)
        except Exception:
            pass
        conn.commit()
        print("INFO: Tablas 'users' y 'gastos' verificadas/creadas exitosamente.")
    except Exception as e:
        print("Error al inicializar la BD:", e)
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

inicializar_bd()

# --- Helpers de autenticación ---
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view

@app.route('/register', methods=('GET', 'POST'))
def register():
    """Registro simple para desarrollo (crear usuarios)."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Usuario y contraseña requeridos.')
            return render_template('register.html')
        try:
            pwd_hash = generate_password_hash(password)
            conn = get_db_connection()
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, pwd_hash))
            conn.close()
            print(f"DEBUG: usuario '{username}' creado.")
            return redirect(url_for('login'))
        except Exception as e:
            print("ERROR REGISTER:", str(e))
            traceback.print_exc()
            flash('Error creando usuario (quizá ya existe).')
            return render_template('register.html')
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Usuario y contraseña requeridos.')
            return render_template('login.html')
        try:
            conn = get_db_connection()
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
                    row = cursor.fetchone()
            conn.close()
            print(f"DEBUG LOGIN: usuario buscado='{username}', encontrado={row is not None}")
            if row:
                password_hash = row[0]
                # Protección extra: aseguramos que password_hash no sea None
                if password_hash and check_password_hash(password_hash, password):
                    session.clear()
                    session['user'] = username
                    print(f"DEBUG LOGIN: login exitoso para '{username}'")
                    return redirect(url_for('index'))
            flash('Usuario o contraseña incorrectos.')
            return render_template('login.html')
        except Exception as e:
            print("ERROR LOGIN:", str(e))
            traceback.print_exc()
            flash('Error interno en el servidor.')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Rutas de la Aplicación Web ---
@app.route('/', methods=('GET', 'POST'))
@login_required
def index():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        user = session['user']

        if request.method == 'POST':
            descripcion = request.form.get('descripcion')
            monto_str = request.form.get('monto')
            if descripcion and monto_str:
                try:
                    monto_float = float(monto_str)
                    cursor.execute("INSERT INTO gastos (descripcion, monto, username) VALUES (%s, %s, %s)",
                                   (descripcion, monto_float, user))
                    conn.commit()
                except ValueError:
                    print("Error: monto no válido:", monto_str)
                except Exception as e:
                    print("Error insert gasto:", str(e))
            conn.close()
            return redirect(url_for('index'))

        cursor.execute("SELECT id, descripcion, monto, fecha_creacion FROM gastos WHERE username = %s ORDER BY id DESC", (user,))
        raw_gastos = cursor.fetchall()

        gastos = []
        total = 0.0
        for row in raw_gastos:
            fecha_formateada = row[3].strftime('%Y-%m-%d %H:%M') if row[3] else 'N/A'
            gasto = {'id': row[0], 'descripcion': row[1], 'monto': float(row[2]), 'fecha': fecha_formateada}
            gastos.append(gasto)
            total += gasto['monto']

        conn.close()
        return render_template('index.html', gastos=gastos, total=total, user=user)
    except Exception as e:
        print("ERROR INDEX:", str(e))
        traceback.print_exc()
        flash('Error interno en el servidor.')
        return render_template('index.html', gastos=[], total=0.0, user=session.get('user'))

@app.route('/modificar/<int:id>', methods=('GET', 'POST'))
@login_required
def modificar(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        user = session['user']

        cursor.execute('SELECT id, descripcion, monto, fecha_creacion FROM gastos WHERE id = %s AND username = %s', (id, user))
        raw_gasto = cursor.fetchone()

        if raw_gasto is None:
            conn.close()
            return "Gasto no encontrado o sin permiso", 404

        gasto = {
            'id': raw_gasto[0],
            'descripcion': raw_gasto[1],
            'monto': float(raw_gasto[2]),
            'fecha': raw_gasto[3].strftime('%Y-%m-%d %H:%M') if raw_gasto[3] else 'N/A'
        }

        if request.method == 'GET':
            conn.close()
            return render_template('modificar.html', gasto=gasto)

        descripcion = request.form['descripcion']
        monto_str = request.form['monto']
        try:
            monto_float = float(monto_str)
            cursor.execute('UPDATE gastos SET descripcion = %s, monto = %s WHERE id = %s AND username = %s',
                           (descripcion, monto_float, id, user))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))
        except ValueError:
            conn.close()
            return render_template('modificar.html', gasto=gasto, error="Monto inválido.")
    except Exception as e:
        print("ERROR modificar:", str(e))
        traceback.print_exc()
        flash('Error interno en el servidor.')
        return redirect(url_for('index'))

@app.route('/eliminar/<int:id>', methods=('POST',))
@login_required
def eliminar(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        user = session['user']
        cursor.execute("DELETE FROM gastos WHERE id = %s AND username = %s", (id, user))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    except Exception as e:
        print("ERROR eliminar:", str(e))
        traceback.print_exc()
        flash('Error interno en el servidor.')
        return redirect(url_for('index'))

# Error handler (log)
@app.errorhandler(500)
def internal_error(e):
    print("ERROR 500:", e)
    traceback.print_exc()
    return "Internal Server Error", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # En Render conviene escuchar en 0.0.0.0
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')