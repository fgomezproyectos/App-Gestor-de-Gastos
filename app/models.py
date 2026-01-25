import psycopg2
from config import Config

def get_db_connection():
    """Establishes and returns a PostgreSQL connection."""
    conn = psycopg2.connect(Config.DATABASE_URL.replace('postgresql://', 'postgres://'))
    return conn

def inicializar_bd():
    """Creates the 'users' and 'gastos' tables if they don't exist."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Expenses table with username (owner)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id SERIAL PRIMARY KEY,
                descripcion TEXT NOT NULL,
                monto NUMERIC(10, 2) NOT NULL,
                fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                username TEXT
            );
        """)
        
        # Ensure username column exists
        cursor.execute("ALTER TABLE gastos ADD COLUMN IF NOT EXISTS username TEXT;")
        
        # Add foreign key constraint (optional, may fail if data is inconsistent)
        try:
            cursor.execute("""
                ALTER TABLE gastos
                ADD CONSTRAINT gastos_username_fkey FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE;
            """)
        except Exception:
            pass
        
        conn.commit()
        print("INFO: Tables 'users' and 'gastos' verified/created successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        if conn:
            conn.close()
