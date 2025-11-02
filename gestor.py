from flask import Flask, render_template, request, redirect, url_for
import sqlite3

# Inicializa Flask
app = Flask(__name__)
# Usamos un nombre de archivo de BD temporal o persistente
# Render creará este archivo en el inicio
NOMBRE_BASE_DATOS = 'gastos.db' 

# --- Lógica de la Base de Datos ---
def get_db_connection():
    conn = sqlite3.connect(NOMBRE_BASE_DATOS)
    conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre
    return conn

def inicializar_bd():
    """
    Crea la tabla 'gastos' si no existe. 
    Esto es CRUCIAL para el despliegue en la nube, donde la base de datos es efímera.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Consulta SQL para crear la tabla si NO existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY,
            descripcion TEXT NOT NULL,
            monto REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# --- Rutas de la Aplicación Web ---

@app.route('/', methods=('GET', 'POST'))
def index():
    conn = get_db_connection()
    
    # --- Manejar la adición de un gasto (POST) ---
    if request.method == 'POST':
        descripcion = request.form.get('descripcion')
        monto_str = request.form.get('monto')

        if descripcion and monto_str:
            try:
                monto_float = float(monto_str)
                conn.execute("INSERT INTO gastos (descripcion, monto) VALUES (?, ?)", 
                             (descripcion, monto_float))
                conn.commit()
            except ValueError:
                # En un entorno real, manejarías el error de manera más amigable
                print("Error: El monto no es un número válido.")
            except Exception as e:
                print(f"Error al insertar en BD: {e}")
        
        conn.close() 
        return redirect(url_for('index'))
    
    # --- Obtener gastos y total (GET) ---
    # Ordenamos por ID descendente para ver los nuevos primero
    gastos = conn.execute("SELECT * FROM gastos ORDER BY id DESC").fetchall()
    
    # Calcular el total
    total = sum(gasto['monto'] for gasto in gastos)
    
    conn.close()
    
    return render_template('index.html', gastos=gastos, total=total)

@app.route('/modificar/<int:id>', methods=('GET', 'POST'))
def modificar(id):
    conn = get_db_connection()
    gasto = conn.execute('SELECT * FROM gastos WHERE id = ?', (id,)).fetchone()
    
    if gasto is None:
        conn.close()
        return "Gasto no encontrado", 404 # Devuelve error si la ID no existe
    
    # Si la solicitud es GET, simplemente mostramos la plantilla con los datos
    if request.method == 'GET':
        conn.close()
        # Renderiza la plantilla: 'modificar.html'
        return render_template('modificar.html', gasto=gasto)

    # Si la solicitud es POST, guardamos los cambios en la BD
    elif request.method == 'POST':
        descripcion = request.form['descripcion']
        monto_str = request.form['monto']
        
        try:
            monto_float = float(monto_str)
            # Consulta SQL para actualizar la fila
            conn.execute('UPDATE gastos SET descripcion = ?, monto = ? WHERE id = ?',
                         (descripcion, monto_float, id))
            conn.commit()
            
            conn.close()
            # Redirige a la página principal después de modificar
            return redirect(url_for('index'))
            
        except ValueError:
            conn.close()
            # Si el monto es inválido, vuelve a mostrar el formulario con el error
            return render_template('modificar.html', gasto=gasto, error="Monto inválido.")

@app.route('/eliminar/<int:id>', methods=('POST',))
def eliminar(id):
    conn = get_db_connection()
    
    # Consulta SQL para eliminar la fila por ID
    conn.execute("DELETE FROM gastos WHERE id = ?", (id,))
    conn.commit()
    
    conn.close() 
    
    return redirect(url_for('index'))

# --- Inicio de la Aplicación (Ajustado para Despliegue) ---
if __name__ == '__main__':
    inicializar_bd()
    # Cambiamos host a '0.0.0.0' para que sea accesible en tu red local si pruebas antes de Render
    app.run(host='0.0.0.0', port=5000, debug=True) 
