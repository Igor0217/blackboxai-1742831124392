from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import re
from werkzeug.security import generate_password_hash, check_password_hash
import random

app = Flask(__name__)
app.secret_key = 'minibanco_secure_key_2024'  # Fixed secure key for session management

def init_db():
    conn = sqlite3.connect('banco.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  full_name TEXT NOT NULL,
                  identification TEXT UNIQUE NOT NULL,
                  address TEXT NOT NULL,
                  phone TEXT NOT NULL,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    
    # Create accounts table
    c.execute('''CREATE TABLE IF NOT EXISTS accounts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  account_number TEXT UNIQUE NOT NULL,
                  account_type TEXT NOT NULL,
                  balance REAL NOT NULL,
                  user_id INTEGER,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # Create transactions table
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  account_id INTEGER,
                  transaction_type TEXT NOT NULL,
                  amount REAL NOT NULL,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (account_id) REFERENCES accounts (id))''')
    
    conn.commit()
    conn.close()

def validate_password(password):
    if len(password) < 6:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('banco.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[6], password):
            session['user_id'] = user[0]
            session['username'] = user[5]
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        identification = request.form['identification']
        address = request.form['address']
        phone = request.form['phone']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if not validate_password(password):
            flash('Password must be at least 6 characters long and contain uppercase, number, and special character')
            return redirect(url_for('register'))
            
        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))
            
        try:
            conn = sqlite3.connect('banco.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (full_name, identification, address, phone, username, password) VALUES (?, ?, ?, ?, ?, ?)",
                     (full_name, identification, address, phone, username, generate_password_hash(password)))
            conn.commit()
            user_id = c.lastrowid
            conn.close()
            
            session['user_id'] = user_id
            session['username'] = username
            flash('Registro exitoso, ahora proceda a escoger su cuenta y el monto a consignar, lo mínimo son 100000')
            return redirect(url_for('create_account'))
        except sqlite3.IntegrityError:
            flash('Username or identification already exists')
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        account_type = request.form['account_type']
        initial_balance = float(request.form['initial_balance'])
        
        if initial_balance < 100000:
            flash('El monto mínimo de apertura es 100000')
            return redirect(url_for('create_account'))
            
        account_number = f"{account_type[0]}{random.randint(10000000, 99999999)}"
        
        conn = sqlite3.connect('banco.db')
        c = conn.cursor()
        c.execute("INSERT INTO accounts (account_number, account_type, balance, user_id) VALUES (?, ?, ?, ?)",
                 (account_number, account_type, initial_balance, session['user_id']))
        
        # Register initial deposit transaction
        c.execute("INSERT INTO transactions (account_id, transaction_type, amount) VALUES (?, ?, ?)",
                 (c.lastrowid, 'deposit', initial_balance))
                 
        conn.commit()
        conn.close()
        
        # En lugar de redireccionar al login, renderizamos account_created.html con los detalles
        return render_template('account_created.html', 
                             account_type=account_type,
                             account_number=account_number,
                             initial_balance=initial_balance)
        
    return render_template('create_account.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('banco.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    
    c.execute("SELECT * FROM accounts WHERE user_id = ?", (session['user_id'],))
    accounts = c.fetchall()
    conn.close()
    
    return render_template('dashboard.html', user=user, accounts=accounts)

@app.route('/transaction/<account_id>', methods=['GET', 'POST'])
def transaction(account_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        transaction_type = request.form['type']
        amount = float(request.form['amount'])
        
        conn = sqlite3.connect('banco.db')
        c = conn.cursor()
        c.execute("SELECT * FROM accounts WHERE id = ? AND user_id = ?", (account_id, session['user_id']))
        account = c.fetchone()
        
        if not account:
            flash('Account not found')
            return redirect(url_for('dashboard'))
            
        current_balance = account[3]
        
        if transaction_type == 'withdraw':
            if amount > current_balance:
                flash('Insufficient funds')
                return redirect(url_for('transaction', account_id=account_id))
            new_balance = current_balance - amount
        else:  # deposit
            new_balance = current_balance + amount
            
        c.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, account_id))
        c.execute("INSERT INTO transactions (account_id, transaction_type, amount) VALUES (?, ?, ?)",
                 (account_id, transaction_type, amount))
        conn.commit()
        conn.close()
        
        flash(f'Transaction successful. New balance: {new_balance}')
        return redirect(url_for('dashboard'))
        
    return render_template('transaction.html', account_id=account_id)

@app.route('/transactions/<account_id>')
def view_transactions(account_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('banco.db')
    c = conn.cursor()
    c.execute("""
        SELECT t.*, a.account_number 
        FROM transactions t 
        JOIN accounts a ON t.account_id = a.id 
        WHERE a.id = ? AND a.user_id = ?
    """, (account_id, session['user_id']))
    transactions = c.fetchall()
    conn.close()
    
    return render_template('transactions.html', transactions=transactions)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        flash('Please log in to edit your profile')
        return redirect(url_for('login'))
        
    try:
        conn = sqlite3.connect('banco.db')
        c = conn.cursor()
        
        if request.method == 'POST':
            address = request.form['address']
            phone = request.form['phone']
            
            c.execute("UPDATE users SET address = ?, phone = ? WHERE id = ?",
                     (address, phone, session['user_id']))
            conn.commit()
            
            flash('Profile updated successfully')
            return redirect(url_for('dashboard'))
            
        c.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        
        if user is None:
            flash('User not found')
            return redirect(url_for('dashboard'))
            
        return render_template('edit_profile.html', user=user)
        
    except Exception as e:
        flash('An error occurred while accessing your profile')
        return redirect(url_for('dashboard'))
        
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=8000)