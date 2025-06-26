# app.py
import os
import uuid
import sqlite3
import qrcode
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.config['UPLOAD_FOLDER'] = 'static/qr_codes'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


def init_db():
    with sqlite3.connect("database.db") as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            upi_id TEXT,
            api_key TEXT
        )
        """)


init_db()


class User(UserMixin):
    def __init__(self, id_, username, upi_id, api_key):
        self.id = id_
        self.username = username
        self.upi_id = upi_id
        self.api_key = api_key


@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect("database.db") as con:
        cur = con.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        if row:
            return User(row[0], row[1], row[3], row[4])
    return None


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html', page='login')


@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = generate_password_hash(request.form['password'])
    try:
        with sqlite3.connect("database.db") as con:
            con.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            con.commit()
            flash("Registered! Now login.")
    except sqlite3.IntegrityError:
        flash("Username already exists.")
    return redirect(url_for('index'))


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    with sqlite3.connect("database.db") as con:
        cur = con.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        if user and check_password_hash(user[2], password):
            login_user(User(user[0], user[1], user[3], user[4]))
            return redirect(url_for('dashboard'))
    flash("Invalid login")
    return redirect(url_for('index'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        upi_id = request.form['upi_id']
        with sqlite3.connect("database.db") as con:
            con.execute("UPDATE users SET upi_id=? WHERE id=?", (upi_id, current_user.id))
        flash("UPI ID updated")
        return redirect(url_for('dashboard'))
    return render_template('index.html', page='dashboard', upi_id=current_user.upi_id, api_key=current_user.api_key)


@app.route('/generate_api_key')
@login_required
def generate_api_key():
    api_key = str(uuid.uuid4())
    with sqlite3.connect("database.db") as con:
        con.execute("UPDATE users SET api_key=? WHERE id=?", (api_key, current_user.id))
    flash("API key generated")
    return redirect(url_for('dashboard'))


@app.route('/api/qr')
def api_qr():
    key = request.args.get('key')
    
    amount = request.args.get('amount', '10')  # default to ₹10

    if not key:
        return jsonify({'error': 'API key missing'}), 400

    if not amount.isdigit() or int(amount) <= 0:
        return jsonify({'error': 'Invalid amount'}), 400

    with sqlite3.connect("database.db") as con:
        cur = con.execute("SELECT username, upi_id FROM users WHERE api_key=?", (key,))
        user = cur.fetchone()
        if not user:
            return jsonify({'error': 'Invalid API key'}), 404

    username, upi_id = user
    upi_link = f"upi://pay?pa={upi_id}&pn={username}&am={amount}&cu=INR"
    filename = f"{key}_{amount}.png"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        qr_img = qrcode.make(upi_link)
        qr_img.save(filepath)

    return render_template("index.html", page="api", qr_filename=filename, username=username, amount=amount)


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

