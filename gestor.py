from flask import Flask, render_template, request, redirect, url_for
import os
import psycopg2 
from dotenv import load_dotenv
from datetime import datetime 

#https://gastos-1fzb.onrender.com/
# Carga las variables de entorno (solo para desarrollo local)
load_dotenv()

# Inicializa Flask
app = Flask(__name__)

# --- Lógica de la Base de Datos ---

DATABASE_URL = os.environ.get('DATABASE_URL') 
if not DATABASE_URL:
    raise Exception("Error: La variable DATABASE_URL no está configurada. Debe configurarse en Render.")

def get_db_connection():
    """Establece y devuelve la conexión a PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL.replace('postgresql://', 'postgres://'))
    return conn

def inicializar_bd():
    """Crea la tabla 'gastos' si no existe, incluyendo la columna de fecha."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Sentencia SQL con la columna fecha_creacion
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id SERIAL PRIMARY KEY,
                descripcion TEXT NOT NULL,
                monto NUMERIC(10, 2) NOT NULL,
                fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("INFO: Tabla 'gastos' verificada/creada exitosamente.")
    except Exception as e:
        print(f"Error al inicializar la BD: {e}")
    finally:
        if conn:
            conn.close()

# Ejecutamos la función de inicialización.
inicializar_bd()

# --- Rutas de la Aplicación Web ---

@app.route('/', methods=('GET', 'POST'))
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # --- Manejar la adición de un gasto (POST) ---
    if request.method == 'POST':
        descripcion = request.form.get('descripcion')
        monto_str = request.form.get('monto')

        if descripcion and monto_str:
            try:
                monto_float = float(monto_str)
                # La fecha se inserta automáticamente por el DEFAULT de la BD
                cursor.execute("INSERT INTO gastos (descripcion, monto) VALUES (%s, %s)", 
                             (descripcion, monto_float))
                conn.commit()
            except ValueError:
                print("Error: El monto no es un número válido.")
            except Exception as e:
                print(f"Error al insertar en BD: {e}")
        
        conn.close() 
        return redirect(url_for('index'))
    
    # --- Obtener gastos y total (GET) ---
    
    # Seleccionamos la nueva columna fecha_creacion
    cursor.execute("SELECT id, descripcion, monto, fecha_creacion FROM gastos ORDER BY id DESC")
    raw_gastos = cursor.fetchall()
    
    # Procesar los gastos para la plantilla
    gastos = []
    total = 0.0
    for row in raw_gastos:
        # Formateamos la fecha (que está en row[3])
        fecha_formateada = row[3].strftime('%Y-%m-%d %H:%M') if row[3] else 'N/A'

        gasto = {
            'id': row[0],
            'descripcion': row[1],
            'monto': float(row[2]), 
            'fecha': fecha_formateada # Se añade al diccionario
        }
        gastos.append(gasto)
        total += gasto['monto']
    
    conn.close()
    
    return render_template('index.html', gastos=gastos, total=total)

@app.route('/modificar/<int:id>', methods=('GET', 'POST'))
def modificar(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Seleccionamos fecha_creacion para mostrarla si es necesario
    cursor.execute('SELECT id, descripcion, monto, fecha_creacion FROM gastos WHERE id = %s', (id,))
    raw_gasto = cursor.fetchone()
    
    if raw_gasto is None:
        conn.close()
        return "Gasto no encontrado", 404
        
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
            
            cursor.execute('UPDATE gastos SET descripcion = %s, monto = %s WHERE id = %s',
                         (descripcion, monto_float, id))
            conn.commit()
            
            conn.close()
            return redirect(url_for('index'))
            
        except ValueError:
            conn.close()
            return render_template('modificar.html', gasto=gasto, error="Monto inválido.")

@app.route('/eliminar/<int:id>', methods=('POST',))
def eliminar(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM gastos WHERE id = %s", (id,))
    conn.commit()
    
    conn.close() 
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)