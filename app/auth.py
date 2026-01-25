from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import get_db_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=('GET', 'POST'))
def register():
    """Simple registration for development (create users)."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password required.')
            return render_template('register.html')
        
        pwd_hash = generate_password_hash(password)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, pwd_hash))
            conn.commit()
            conn.close()
            return redirect(url_for('auth.login'))
        except Exception as e:
            conn.close()
            flash('Error creating user (may already exist).')
            return render_template('register.html')
    
    return render_template('register.html')

@auth_bp.route('/login', methods=('GET', 'POST'))
def login():
    """User login."""
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
            return redirect(url_for('gastos.index'))
        else:
            flash('Incorrect username or password.')
            return render_template('login.html')
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """User logout."""
    session.clear()
    return redirect(url_for('auth.login'))
