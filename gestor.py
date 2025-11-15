
from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import psycopg2 
from dotenv import load_dotenv
from datetime import datetime 
import functools
from werkzeug.security import generate_password_hash, check_password_hash

# Carga las variables de entorno (solo para desarrollo local)
load_dotenv()

# Inicializa Flask
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')  # fija SECRET_KEY en .env en producción

# --- Lógica de la Base de Datos ---
DATABASE_URL = os.environ.get('DATABASE_URL') 
if not DATABASE_URL:
    raise Exception("Error: La variable DATABASE_URL no está configurada. Debe configurarse en Render.")

def get_db_connection():
    """Establece y devuelve la conexión a PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL.replace('postgresql://', 'postgres://'))
    return conn

def inicializar_bd():
    """Crea las tablas 'users' y 'gastos' si no existen y asegura la columna username en gastos."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Tabla de usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Tabla de gastos con columna username (propietario)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id SERIAL PRIMARY KEY,
                descripcion TEXT NOT NULL,
                monto NUMERIC(10, 2) NOT NULL,
                fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                username TEXT
            );
        """)
        # Aseguramos que la columna username exista (por si la tabla existía sin ella)
        cursor.execute("ALTER TABLE gastos ADD COLUMN IF NOT EXISTS username TEXT;")
        # (Opcional) agregar FK si lo deseas (puede fallar si ya hay datos inconsistentes)
        try:
            cursor.execute("""
                ALTER TABLE gastos
                ADD CONSTRAINT gastos_username_fkey FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE;
            """)
        except Exception:
            # Si ya existe la constraint o hay conflicto, lo ignoramos para evitar fallo de inicialización.
            pass

        conn.commit()
        print("INFO: Tablas 'users' y 'gastos' verificadas/creadas exitosamente.")
    except Exception as e:
        print(f"Error al inicializar la BD: {e}")
    finally:
        if conn:
            conn.close()

# Ejecutamos la función de inicialización.
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
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Usuario y contraseña requeridos.')
            return render_template('register.html')
        pwd_hash = generate_password_hash(password)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, pwd_hash))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except Exception as e:
            conn.close()
            flash('Error creando usuario (puede que ya exista).')
            return render_template('register.html')
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
        row = cursor.fetchone()
        conn.close()
        if row and check_password_hash(row[0], password):
            session.clear()
            session['user'] = username
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos.')
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
    conn = get_db_connection()
    cursor = conn.cursor()
    user = session['user']
    
    # --- Manejar la adición de un gasto (POST) ---
    if request.method == 'POST':
        descripcion = request.form.get('descripcion')
        monto_str = request.form.get('monto')

        if descripcion and monto_str:
            try:
                monto_float = float(monto_str)
                # Insertamos con username asociado
                cursor.execute("INSERT INTO gastos (descripcion, monto, username) VALUES (%s, %s, %s)", 
                             (descripcion, monto_float, user))
                conn.commit()
            except ValueError:
                print("Error: El monto no es un número válido.")
            except Exception as e:
                print(f"Error al insertar en BD: {e}")
        
        conn.close() 
        return redirect(url_for('index'))
    
    # --- Obtener gastos y total (GET) ---
    cursor.execute("SELECT id, descripcion, monto, fecha_creacion FROM gastos WHERE username = %s ORDER BY id DESC", (user,))
    raw_gastos = cursor.fetchall()
    
    # Procesar los gastos para la plantilla
    gastos = []
    total = 0.0
    for row in raw_gastos:
        fecha_formateada = row[3].strftime('%Y-%m-%d %H:%M') if row[3] else 'N/A'
        gasto = {
            'id': row[0],
            'descripcion': row[1],
            'monto': float(row[2]), 
            'fecha': fecha_formateada
        }
        gastos.append(gasto)
        total += gasto['monto']
    
    conn.close()
    
    return render_template('index.html', gastos=gastos, total=total, user=user)

@app.route('/modificar/<int:id>', methods=('GET', 'POST'))
@login_required
def modificar(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    user = session['user']
    
    # Seleccionamos el gasto solo si pertenece al usuario
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
    
    elif request.method == 'POST':
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

@app.route('/eliminar/<int:id>', methods=('POST',))
@login_required
def eliminar(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    user = session['user']
    
    cursor.execute("DELETE FROM gastos WHERE id = %s AND username = %s", (id, user))
    conn.commit()
    
    conn.close() 
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
