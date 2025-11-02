from flask import Flask, render_template, request, redirect, url_for
import os
import psycopg2 # Librería para conectar con PostgreSQL
from dotenv import load_dotenv

# Carga las variables de entorno (solo para desarrollo local)
load_dotenv()

# Inicializa Flask
app = Flask(__name__)

# --- Lógica de la Base de Datos ---

# 1. Obtener la URL de conexión. Render utiliza la variable de entorno 'DATABASE_URL'.
DATABASE_URL = os.environ.get('DATABASE_URL') 
if not DATABASE_URL:
    # Esto asegura que si no encuentra la variable (en Render o en local), la app falle
    raise Exception("Error: La variable DATABASE_URL no está configurada. Debe configurarse en Render.")

def get_db_connection():
    """Establece y devuelve la conexión a PostgreSQL."""
    # Reemplazamos 'postgresql://' por 'postgres://' si es necesario, 
    # ya que psycopg2 a veces lo requiere.
    conn = psycopg2.connect(DATABASE_URL.replace('postgresql://', 'postgres://'))
    return conn

def inicializar_bd():
    """
    Crea la tabla 'gastos' si no existe. 
    Esto se ejecutará en el primer arranque en Render para crear la tabla.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # El tipo SERIAL es la clave primaria con auto-incremento
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id SERIAL PRIMARY KEY,
                descripcion TEXT NOT NULL,
                monto NUMERIC(10, 2) NOT NULL
            );
        """)
        conn.commit()
    except Exception as e:
        print(f"Error al inicializar la BD: {e}")
    finally:
        if conn:
            conn.close()

# --- Rutas de la Aplicación Web (Actualizadas para usar PostgreSQL) ---

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
                # Usar %s como marcador de posición para psycopg2
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
    
    # Obtener todas las filas (ordenadas por ID descendente)
    cursor.execute("SELECT id, descripcion, monto FROM gastos ORDER BY id DESC")
    raw_gastos = cursor.fetchall()
    
    # Procesar los gastos para la plantilla
    gastos = []
    total = 0.0
    for row in raw_gastos:
        # Los resultados de cursor.fetchall() son tuplas, los mapeamos por índice
        gasto = {
            'id': row[0],
            'descripcion': row[1],
            # Convertir de Decimal de Postgres a float/numérico para sumar
            'monto': float(row[2]) 
        }
        gastos.append(gasto)
        total += gasto['monto']
    
    conn.close()
    
    return render_template('index.html', gastos=gastos, total=total)

@app.route('/modificar/<int:id>', methods=('GET', 'POST'))
def modificar(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Usamos %s como marcador de posición
    cursor.execute('SELECT id, descripcion, monto FROM gastos WHERE id = %s', (id,))
    raw_gasto = cursor.fetchone()
    
    if raw_gasto is None:
        conn.close()
        return "Gasto no encontrado", 404
        
    gasto = {
        'id': raw_gasto[0],
        'descripcion': raw_gasto[1],
        'monto': float(raw_gasto[2]) 
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
    # Inicializa la BD solo cuando el script se ejecuta directamente
    inicializar_bd() 
    app.run(debug=True)
