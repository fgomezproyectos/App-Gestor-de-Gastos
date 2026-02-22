from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import functools
from app.models import get_db_connection

gastos_bp = Blueprint('gastos', __name__)

def login_required(view):
    """Decorator to check if user is logged in."""
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapped_view

@gastos_bp.route('/', methods=('GET', 'POST'))
@login_required
def index():
    """Display expenses and handle adding new expenses."""
    conn = get_db_connection()
    cursor = conn.cursor()
    user = session['user']
    
    # Handle adding a new expense (POST)
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
                print("Error: Monto is not a valid number.")
            except Exception as e:
                print(f"Error inserting into database: {e}")
        
        conn.close()
        return redirect(url_for('gastos.index'))
    
    # Get expenses and total (GET)
    cursor.execute("SELECT id, descripcion, monto, fecha_creacion FROM gastos WHERE username = %s ORDER BY id DESC", (user,))
    raw_gastos = cursor.fetchall()
    
    # Process expenses for template
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

@gastos_bp.route('/modificar/<int:id>', methods=('GET', 'POST'))
@login_required
def modificar(id):
    """Edit an expense."""
    conn = get_db_connection()
    cursor = conn.cursor()
    user = session['user']
    
    # Select the expense only if it belongs to the user
    cursor.execute('SELECT id, descripcion, monto, fecha_creacion FROM gastos WHERE id = %s AND username = %s', (id, user))
    raw_gasto = cursor.fetchone()
    
    if raw_gasto is None:
        conn.close()
        return "Expense not found or no permission", 404
    
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
            return redirect(url_for('gastos.index'))
            
        except ValueError:
            conn.close()
            return render_template('modificar.html', gasto=gasto, error="Invalid amount.")

@gastos_bp.route('/eliminar/<int:id>', methods=('POST',))
@login_required
def eliminar(id):
    """Delete an expense."""
    conn = get_db_connection()
    cursor = conn.cursor()
    user = session['user']
    
    cursor.execute("DELETE FROM gastos WHERE id = %s AND username = %s", (id, user))
    conn.commit()
    conn.close()
    
    return redirect(url_for('gastos.index'))

@gastos_bp.route('/estadisticas', methods=('GET',))
@login_required
def estadisticas():
    """Display expense statistics by month."""
    conn = get_db_connection()
    cursor = conn.cursor()
    user = session['user']
    
    # Get all expenses grouped by month
    cursor.execute("""
        SELECT DATE_TRUNC('month', fecha_creacion)::date as mes, 
               SUM(monto) as total, 
               COUNT(*) as cantidad,
               AVG(monto) as promedio
        FROM gastos 
        WHERE username = %s
        GROUP BY DATE_TRUNC('month', fecha_creacion)
        ORDER BY mes DESC
    """, (user,))
    
    resultados = cursor.fetchall()
    
    # Process results
    resumen_meses = []
    totales_por_mes = []
    meses_labels = []
    
    for row in resultados:
        mes = row[0]
        total = float(row[1]) if row[1] else 0.0
        cantidad = int(row[2])
        promedio = float(row[3]) if row[3] else 0.0
        
        mes_str = mes.strftime('%B %Y') if mes else 'N/A'
        
        resumen_meses.append({
            'mes': mes_str,
            'total': total,
            'cantidad': cantidad,
            'promedio': promedio
        })
        
        totales_por_mes.append(total)
        meses_labels.append(mes_str)
    
    # Reverse to show oldest to newest
    resumen_meses.reverse()
    totales_por_mes.reverse()
    meses_labels.reverse()
    
    conn.close()
    
    return render_template('estadisticas.html', 
                          resumen_meses=resumen_meses,
                          totales_por_mes=totales_por_mes,
                          meses_labels=meses_labels)
