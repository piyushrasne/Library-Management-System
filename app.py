import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'library_secret_key_2025'
DATABASE = os.path.join(os.path.dirname(__file__), 'library.db')


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users table (admin & members)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            phone TEXT,
            address TEXT,
            membership_date TEXT DEFAULT CURRENT_DATE,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Books table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT UNIQUE,
            category TEXT,
            publisher TEXT,
            year INTEGER,
            total_copies INTEGER DEFAULT 1,
            available_copies INTEGER DEFAULT 1,
            description TEXT,
            added_date TEXT DEFAULT CURRENT_DATE
        )
    ''')

    # Transactions table (issue/return)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            fine REAL DEFAULT 0.0,
            status TEXT DEFAULT 'issued',
            FOREIGN KEY (book_id) REFERENCES books(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Seed admin user
    cursor.execute("SELECT id FROM users WHERE email = 'admin@library.com'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
        ''', ('Administrator', 'admin@library.com',
              generate_password_hash('admin123'), 'admin'))



    # Seed sample books
    books = [
        ('Systems Analysis and Design', 'Gary B. Shelly', '978-1111526313', 'Computer Science', 'Course Technology', 2011, 5, 5, 'Comprehensive guide to systems analysis and design.'),
        ('Management Information Systems', 'Kenneth C. Laudon', '978-0134898131', 'Management', 'Pearson Education', 2019, 3, 3, 'Managing the Digital Firm.'),
        ('Software Engineering', 'Roger S. Pressman', '978-0078022128', 'Engineering', 'McGraw-Hill', 2014, 4, 4, 'A Practitioner\'s Approach to software engineering.'),
        ('Database Management Systems', 'Sumathi & Esakkirajan', '978-3540483991', 'Computer Science', 'Springer', 2017, 3, 3, 'Fundamentals of Relational Database Management Systems.'),
        ('Research Methodology', 'C.R. Kothari', '978-8122424881', 'Research', 'New Age International', 2019, 6, 6, 'Methods and Techniques for research.'),
        ('Python Programming', 'Mark Lutz', '978-1449355739', 'Programming', 'O\'Reilly Media', 2013, 4, 4, 'Learning Python, 5th Edition.'),
        ('Introduction to Algorithms', 'Thomas H. Cormen', '978-0262033848', 'Algorithms', 'MIT Press', 2009, 3, 3, 'Classic textbook on algorithms and data structures.'),
        ('Computer Networks', 'Andrew S. Tanenbaum', '978-0132126953', 'Networking', 'Pearson', 2010, 5, 5, 'Comprehensive study of computer networking.'),
        ('Operating System Concepts', 'Abraham Silberschatz', '978-1118063330', 'Operating Systems', 'Wiley', 2012, 4, 4, 'Dinosaur Book on OS concepts.'),
        ('Artificial Intelligence', 'Stuart Russell', '978-0136042594', 'AI', 'Pearson', 2009, 2, 2, 'A Modern Approach to Artificial Intelligence.'),
    ]
    for book in books:
        cursor.execute("SELECT id FROM books WHERE isbn = ?", (book[2],))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO books (title, author, isbn, category, publisher, year, total_copies, available_copies, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', book)

    conn.commit()
    conn.close()


# --- Auth Decorators ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# --- Routes ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role_selected = request.form.get('role', 'member')
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND is_active = 1', (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            if user['role'] != role_selected and role_selected == 'admin':
                flash('You do not have admin privileges.', 'danger')
                return redirect(url_for('login'))
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['role'] = user['role']
            flash(f"Welcome, {user['name']}!", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    total_books = conn.execute('SELECT COUNT(*) FROM books').fetchone()[0]
    total_members = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'member'").fetchone()[0]
    active_issues = conn.execute("SELECT COUNT(*) FROM transactions WHERE status = 'issued'").fetchone()[0]
    overdue = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE status = 'issued' AND due_date < ?",
        (datetime.today().strftime('%Y-%m-%d'),)
    ).fetchone()[0]
    total_fines = conn.execute("SELECT COALESCE(SUM(fine), 0) FROM transactions WHERE fine > 0").fetchone()[0]
    recent_transactions = conn.execute('''
        SELECT t.*, b.title as book_title, u.name as member_name
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN users u ON t.user_id = u.id
        ORDER BY t.id DESC LIMIT 8
    ''').fetchall()
    conn.close()
    return render_template('dashboard.html',
                           total_books=total_books,
                           total_members=total_members,
                           active_issues=active_issues,
                           overdue=overdue,
                           total_fines=round(total_fines, 2),
                           recent_transactions=recent_transactions,
                           today=datetime.today().strftime('%Y-%m-%d'))


# --- Books ---

@app.route('/books')
@login_required
def books():
    q = request.args.get('q', '')
    cat = request.args.get('category', '')
    conn = get_db()
    query = 'SELECT * FROM books WHERE 1=1'
    params = []
    if q:
        query += ' AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)'
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if cat:
        query += ' AND category = ?'
        params.append(cat)
    query += ' ORDER BY title'
    all_books = conn.execute(query, params).fetchall()
    categories = conn.execute('SELECT DISTINCT category FROM books ORDER BY category').fetchall()
    conn.close()
    return render_template('books.html', books=all_books, categories=categories, q=q, selected_cat=cat)


@app.route('/books/add', methods=['GET', 'POST'])
@admin_required
def add_book():
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')
        category = request.form.get('category')
        publisher = request.form.get('publisher')
        year = request.form.get('year')
        copies = int(request.form.get('copies', 1))
        description = request.form.get('description')
        conn = get_db()
        conn.execute('''
            INSERT INTO books (title, author, isbn, category, publisher, year, total_copies, available_copies, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, author, isbn, category, publisher, year, copies, copies, description))
        conn.commit()
        conn.close()
        flash('Book added successfully!', 'success')
        return redirect(url_for('books'))
    return render_template('add_book.html')


@app.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
@admin_required
def edit_book(book_id):
    conn = get_db()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    if not book:
        flash('Book not found.', 'danger')
        conn.close()
        return redirect(url_for('books'))
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')
        category = request.form.get('category')
        publisher = request.form.get('publisher')
        year = request.form.get('year')
        copies = int(request.form.get('copies', 1))
        description = request.form.get('description')
        issued = book['total_copies'] - book['available_copies']
        new_available = max(0, copies - issued)
        conn.execute('''
            UPDATE books SET title=?, author=?, isbn=?, category=?, publisher=?, year=?, 
            total_copies=?, available_copies=?, description=? WHERE id=?
        ''', (title, author, isbn, category, publisher, year, copies, new_available, description, book_id))
        conn.commit()
        conn.close()
        flash('Book updated successfully!', 'success')
        return redirect(url_for('books'))
    conn.close()
    return render_template('edit_book.html', book=book)


@app.route('/books/delete/<int:book_id>', methods=['POST'])
@admin_required
def delete_book(book_id):
    conn = get_db()
    active = conn.execute("SELECT COUNT(*) FROM transactions WHERE book_id = ? AND status = 'issued'", (book_id,)).fetchone()[0]
    if active > 0:
        flash('Cannot delete book with active issues.', 'danger')
    else:
        conn.execute('DELETE FROM books WHERE id = ?', (book_id,))
        conn.commit()
        flash('Book deleted successfully!', 'success')
    conn.close()
    return redirect(url_for('books'))


# --- Members ---

@app.route('/members')
@admin_required
def members():
    q = request.args.get('q', '')
    conn = get_db()
    if q:
        all_members = conn.execute(
            "SELECT * FROM users WHERE role = 'member' AND (name LIKE ? OR email LIKE ?) ORDER BY name",
            (f'%{q}%', f'%{q}%')
        ).fetchall()
    else:
        all_members = conn.execute("SELECT * FROM users WHERE role = 'member' ORDER BY name").fetchall()
    conn.close()
    return render_template('members.html', members=all_members, q=q)


@app.route('/members/add', methods=['GET', 'POST'])
@admin_required
def add_member():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        address = request.form.get('address')
        conn = get_db()
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            flash('Email already registered.', 'danger')
            conn.close()
            return redirect(url_for('add_member'))
        conn.execute('''
            INSERT INTO users (name, email, password, role, phone, address)
            VALUES (?, ?, ?, 'member', ?, ?)
        ''', (name, email, generate_password_hash(password), phone, address))
        conn.commit()
        conn.close()
        flash('Member added successfully!', 'success')
        return redirect(url_for('members'))
    return render_template('add_member.html')


@app.route('/members/edit/<int:member_id>', methods=['GET', 'POST'])
@admin_required
def edit_member(member_id):
    conn = get_db()
    member = conn.execute('SELECT * FROM users WHERE id = ? AND role = ?', (member_id, 'member')).fetchone()
    if not member:
        flash('Member not found.', 'danger')
        conn.close()
        return redirect(url_for('members'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        is_active = 1 if request.form.get('is_active') else 0
        conn.execute('''
            UPDATE users SET name=?, email=?, phone=?, address=?, is_active=? WHERE id=?
        ''', (name, email, phone, address, is_active, member_id))
        conn.commit()
        conn.close()
        flash('Member updated successfully!', 'success')
        return redirect(url_for('members'))
    conn.close()
    return render_template('edit_member.html', member=member)


@app.route('/members/delete/<int:member_id>', methods=['POST'])
@admin_required
def delete_member(member_id):
    conn = get_db()
    active = conn.execute("SELECT COUNT(*) FROM transactions WHERE user_id = ? AND status = 'issued'", (member_id,)).fetchone()[0]
    if active > 0:
        flash('Cannot delete member with active book issues.', 'danger')
    else:
        conn.execute('DELETE FROM users WHERE id = ?', (member_id,))
        conn.commit()
        flash('Member deleted.', 'success')
    conn.close()
    return redirect(url_for('members'))


# --- Issue & Return ---

@app.route('/transactions')
@login_required
def transactions():
    conn = get_db()
    today = datetime.today().strftime('%Y-%m-%d')
    if session['role'] == 'admin':
        txns = conn.execute('''
            SELECT t.*, b.title as book_title, u.name as member_name
            FROM transactions t
            JOIN books b ON t.book_id = b.id
            JOIN users u ON t.user_id = u.id
            ORDER BY t.id DESC
        ''').fetchall()
    else:
        txns = conn.execute('''
            SELECT t.*, b.title as book_title, u.name as member_name
            FROM transactions t
            JOIN books b ON t.book_id = b.id
            JOIN users u ON t.user_id = u.id
            WHERE t.user_id = ?
            ORDER BY t.id DESC
        ''', (session['user_id'],)).fetchall()
    books_available = conn.execute("SELECT * FROM books WHERE available_copies > 0 ORDER BY title").fetchall()
    members_list = conn.execute("SELECT * FROM users WHERE role = 'member' AND is_active = 1 ORDER BY name").fetchall()
    conn.close()
    return render_template('transactions.html', transactions=txns, books=books_available,
                           members=members_list, today=today)


@app.route('/transactions/issue', methods=['POST'])
@admin_required
def issue_book():
    book_id = request.form.get('book_id')
    user_id = request.form.get('user_id')
    issue_date = datetime.today().strftime('%Y-%m-%d')
    days = request.form.get('days', type=int)
    if not days or days < 1:
        days = 14
    due_date = (datetime.today() + timedelta(days=days)).strftime('%Y-%m-%d')
    conn = get_db()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    if not book or book['available_copies'] < 1:
        flash('Book not available.', 'danger')
        conn.close()
        return redirect(url_for('transactions'))
    existing = conn.execute(
        "SELECT id FROM transactions WHERE book_id=? AND user_id=? AND status='issued'",
        (book_id, user_id)
    ).fetchone()
    if existing:
        flash('This member already has this book issued.', 'warning')
        conn.close()
        return redirect(url_for('transactions'))
    conn.execute('''
        INSERT INTO transactions (book_id, user_id, issue_date, due_date) VALUES (?, ?, ?, ?)
    ''', (book_id, user_id, issue_date, due_date))
    conn.execute('UPDATE books SET available_copies = available_copies - 1 WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()
    flash('Book issued successfully! Due date: ' + due_date, 'success')
    return redirect(url_for('transactions'))


@app.route('/transactions/return/<int:txn_id>', methods=['POST'])
@admin_required
def return_book(txn_id):
    conn = get_db()
    txn = conn.execute("SELECT * FROM transactions WHERE id = ? AND status = 'issued'", (txn_id,)).fetchone()
    if not txn:
        flash('Transaction not found.', 'danger')
        conn.close()
        return redirect(url_for('transactions'))
    return_date = datetime.today().strftime('%Y-%m-%d')
    fine = 0.0
    due = datetime.strptime(txn['due_date'], '%Y-%m-%d')
    today = datetime.today()
    if today > due:
        days_late = (today - due).days
        fine = days_late * 5.0  # ₹5 per day fine
    conn.execute('''
        UPDATE transactions SET return_date=?, fine=?, status='returned' WHERE id=?
    ''', (return_date, fine, txn_id))
    conn.execute('UPDATE books SET available_copies = available_copies + 1 WHERE id = ?', (txn['book_id'],))
    conn.commit()
    conn.close()
    if fine > 0:
        flash(f'Book returned. Fine: ₹{fine:.2f}', 'warning')
    else:
        flash('Book returned successfully. No fine!', 'success')
    return redirect(url_for('transactions'))


@app.route('/transactions/add_fine/<int:txn_id>', methods=['POST'])
@admin_required
def add_fine(txn_id):
    fine_amount = request.form.get('fine_amount', type=float)
    if fine_amount is None or fine_amount <= 0:
        flash('Invalid fine amount.', 'danger')
        return redirect(url_for('transactions'))
        
    conn = get_db()
    txn = conn.execute("SELECT * FROM transactions WHERE id = ?", (txn_id,)).fetchone()
    if not txn:
        flash('Transaction not found.', 'danger')
        conn.close()
        return redirect(url_for('transactions'))
        
    new_fine = txn['fine'] + fine_amount
    conn.execute('UPDATE transactions SET fine=? WHERE id=?', (new_fine, txn_id))
    conn.commit()
    conn.close()
    
    flash(f'Successfully added ₹{fine_amount:.2f} fine.', 'success')
    return redirect(url_for('transactions'))


# --- Reports ---

@app.route('/reports')
@admin_required
def reports():
    conn = get_db()
    today = datetime.today().strftime('%Y-%m-%d')
    # Overdue books
    overdue_books = conn.execute('''
        SELECT t.*, b.title as book_title, u.name as member_name, u.phone
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN users u ON t.user_id = u.id
        WHERE t.status = 'issued' AND t.due_date < ?
        ORDER BY t.due_date
    ''', (today,)).fetchall()
    # Most borrowed books
    popular_books = conn.execute('''
        SELECT b.title, b.author, COUNT(t.id) as borrow_count
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        GROUP BY t.book_id
        ORDER BY borrow_count DESC LIMIT 5
    ''').fetchall()
    # Fines summary
    total_fines = conn.execute("SELECT COALESCE(SUM(fine), 0) FROM transactions WHERE fine > 0").fetchone()[0]
    pending_fines = conn.execute(
        "SELECT COALESCE(SUM(fine), 0) FROM transactions WHERE status = 'issued' AND due_date < ?", (today,)
    ).fetchone()[0]
    # Monthly stats
    monthly = conn.execute('''
        SELECT strftime('%Y-%m', issue_date) as month, COUNT(*) as count
        FROM transactions
        GROUP BY month ORDER BY month DESC LIMIT 6
    ''').fetchall()
    # Category stats
    cat_stats = conn.execute('''
        SELECT b.category, COUNT(t.id) as cnt
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        GROUP BY b.category ORDER BY cnt DESC
    ''').fetchall()
    conn.close()
    return render_template('reports.html',
                           overdue_books=overdue_books,
                           popular_books=popular_books,
                           total_fines=round(total_fines, 2),
                           pending_fines=round(pending_fines, 2),
                           monthly=monthly,
                           cat_stats=cat_stats)


# --- Project Info ---

@app.route('/info')
@login_required
def info():
    return render_template('info.html')


# --- Profile ---

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        new_password = request.form.get('new_password')
        if new_password:
            conn.execute('UPDATE users SET name=?, phone=?, address=?, password=? WHERE id=?',
                         (name, phone, address, generate_password_hash(new_password), session['user_id']))
        else:
            conn.execute('UPDATE users SET name=?, phone=?, address=? WHERE id=?',
                         (name, phone, address, session['user_id']))
        conn.commit()
        session['user_name'] = name
        flash('Profile updated!', 'success')
        conn.close()
        return redirect(url_for('profile'))
    conn.close()
    return render_template('profile.html', user=user)


# --- API for search autocomplete ---
@app.route('/api/books/search')
@login_required
def api_search_books():
    q = request.args.get('q', '')
    conn = get_db()
    results = conn.execute(
        "SELECT id, title, author FROM books WHERE (title LIKE ? OR author LIKE ?) LIMIT 10",
        (f'%{q}%', f'%{q}%')
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in results])


if __name__ == '__main__':
    init_db()
    print("\n" + "="*50)
    print("  Library Management System")
    print("  Running at: http://127.0.0.1:5000")
    print("  Admin Login: admin@library.com / admin123")
    print("  Member Login: member@library.com / member123")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
