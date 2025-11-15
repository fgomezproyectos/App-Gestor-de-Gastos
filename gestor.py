from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timedelta
import functools
from werkzeug.security import generate_password_hash, check_password_hash
import traceback
from collections import defaultdict

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
                username TEXT NOT NULL
            );
        """)
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
        user = session.get('user')
        print(f"DEBUG INDEX: usuario={user}")

        if request.method == 'POST':
            descripcion = request.form.get('descripcion', '').strip()
            monto_str = request.form.get('monto', '').strip()
            print(f"DEBUG POST: descripcion='{descripcion}', monto='{monto_str}'")
            if descripcion and monto_str:
                try:
                    monto_float = float(monto_str)
                    cursor.execute("INSERT INTO gastos (descripcion, monto, username) VALUES (%s, %s, %s)",
                                   (descripcion, monto_float, user))
                    conn.commit()
                    print(f"DEBUG: gasto insertado para user='{user}'")
                except ValueError as ve:
                    print("Error: monto no válido:", monto_str, ve)
                except Exception as e:
                    print("Error insert gasto:", str(e))
                    traceback.print_exc()
            conn.close()
            return redirect(url_for('index'))

        # GET - Recuperar gastos
        cursor.execute("SELECT id, descripcion, monto, fecha_creacion FROM gastos WHERE username = %s ORDER BY fecha_creacion DESC", (user,))
        raw_gastos = cursor.fetchall()
        print(f"DEBUG: gastos encontrados para user='{user}': {len(raw_gastos) if raw_gastos else 0}")
        
        if raw_gastos:
            for i, row in enumerate(raw_gastos):
                print(f"  Gasto {i}: id={row[0]}, desc='{row[1]}', monto={row[2]}, fecha={row[3]}")

        gastos = []
        total = 0.0
        if raw_gastos:
            for row in raw_gastos:
                fecha_formateada = row[3].strftime('%Y-%m-%d %H:%M') if row[3] else 'N/A'
                gasto = {'id': row[0], 'descripcion': row[1], 'monto': float(row[2]), 'fecha': fecha_formateada}
                gastos.append(gasto)
                total += gasto['monto']

        print(f"DEBUG: gastos procesados={len(gastos)}, total={total}")
        conn.close()
        return render_template('index.html', gastos=gastos, total=total, user=user)
    except Exception as e:
        print("ERROR INDEX:", str(e))
        traceback.print_exc()
        flash('Error interno en el servidor.')
        try:
            conn.close()
        except:
            pass
        return render_template('index.html', gastos=[], total=0.0, user=session.get('user'))

@app.route('/modificar/<int:id>', methods=('GET', 'POST'))
@login_required
def modificar(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        user = session.get('user')

        cursor.execute('SELECT id, descripcion, monto, fecha_creacion FROM gastos WHERE id = %s AND username = %s', (id, user))
        raw_gasto = cursor.fetchone()

        if raw_gasto is None:
            conn.close()
            flash('Gasto no encontrado o sin permiso.')
            return redirect(url_for('index'))

        gasto = {
            'id': raw_gasto[0],
            'descripcion': raw_gasto[1],
            'monto': float(raw_gasto[2]),
            'fecha': raw_gasto[3].strftime('%Y-%m-%d %H:%M') if raw_gasto[3] else 'N/A',
            'fecha_iso': raw_gasto[3].strftime('%Y-%m-%dT%H:%M') if raw_gasto[3] else ''
        }

        if request.method == 'GET':
            conn.close()
            return render_template('modificar.html', gasto=gasto)

        descripcion = request.form.get('descripcion', '').strip()
        monto_str = request.form.get('monto', '').strip()
        fecha_str = request.form.get('fecha', '')
        
        try:
            monto_float = float(monto_str)
            # Convertir fecha de formato datetime-local a datetime
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M') if fecha_str else None
            
            cursor.execute('UPDATE gastos SET descripcion = %s, monto = %s, fecha_creacion = %s WHERE id = %s AND username = %s',
                           (descripcion, monto_float, fecha_obj, id, user))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))
        except ValueError as ve:
            conn.close()
            return render_template('modificar.html', gasto=gasto, error="Monto o fecha inválidos.")
    except Exception as e:
        print("ERROR modificar:", str(e))
        traceback.print_exc()
        flash('Error interno en el servidor.')
        try:
            conn.close()
        except:
            pass
        return redirect(url_for('index'))

@app.route('/eliminar/<int:id>', methods=('POST',))
@login_required
def eliminar(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        user = session.get('user')
        cursor.execute("DELETE FROM gastos WHERE id = %s AND username = %s", (id, user))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    except Exception as e:
        print("ERROR eliminar:", str(e))
        traceback.print_exc()
        flash('Error interno en el servidor.')
        try:
            conn.close()
        except:
            pass
        return redirect(url_for('index'))

@app.route('/estadisticas')
@login_required
def estadisticas():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        user = session.get('user')
        
        # Obtener todos los gastos del usuario
        cursor.execute(
            "SELECT descripcion, monto, fecha_creacion FROM gastos WHERE username = %s ORDER BY fecha_creacion DESC",
            (user,)
        )
        raw_gastos = cursor.fetchall()
        conn.close()
        
        # Procesar datos para gráficas
        gastos_por_mes = defaultdict(float)
        gastos_por_descripcion = defaultdict(float)
        gastos_por_mes_detalle = defaultdict(lambda: {'total': 0, 'cantidad': 0})
        
        for row in raw_gastos:
            descripcion = row[0]
            monto = float(row[1])
            fecha = row[2]
            
            # Clave mes (ej: "2025-11")
            mes_key = fecha.strftime('%Y-%m')
            mes_label = fecha.strftime('%B %Y')  # Ej: "November 2025"
            
            gastos_por_mes[mes_key] = gastos_por_mes.get(mes_key, 0) + monto
            gastos_por_mes_detalle[mes_key]['total'] += monto
            gastos_por_mes_detalle[mes_key]['cantidad'] += 1
            gastos_por_descripcion[descripcion] += monto
        
        # Preparar datos para Chart.js
        meses_ordenados = sorted(gastos_por_mes.keys(), reverse=True)[:12]  # Últimos 12 meses
        meses_labels = [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in meses_ordenados]
        totales_por_mes = [gastos_por_mes.get(m, 0) for m in meses_ordenados]
        
        # Top 8 descripciones
        top_descripciones = sorted(gastos_por_descripcion.items(), key=lambda x: x[1], reverse=True)[:8]
        descripciones_labels = [d[0] for d in top_descripciones]
        totales_por_descripcion = [float(d[1]) for d in top_descripciones]
        
        # Resumen detallado por mes
        resumen_meses = []
        for mes in meses_ordenados:
            detalle = gastos_por_mes_detalle[mes]
            resumen_meses.append({
                'mes': datetime.strptime(mes, '%Y-%m').strftime('%B %Y'),
                'total': detalle['total'],
                'cantidad': detalle['cantidad'],
                'promedio': detalle['total'] / detalle['cantidad'] if detalle['cantidad'] > 0 else 0
            })
        
        return render_template(
            'estadisticas.html',
            meses_labels=meses_labels,
            totales_por_mes=totales_por_mes,
            descripciones_labels=descripciones_labels,
            totales_por_descripcion=totales_por_descripcion,
            resumen_meses=resumen_meses,
            user=user
        )
    except Exception as e:
        print("ERROR ESTADISTICAS:", str(e))
        traceback.print_exc()
        flash('Error al cargar estadísticas.')
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