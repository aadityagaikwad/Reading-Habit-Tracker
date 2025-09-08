# Reading Habit Tracker
# A comprehensive application to track daily reading progress with analytics

import sqlite3
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)

# Database setup
def init_db():
    """Initialize the SQLite database"""
    conn = sqlite3.connect('reading_tracker.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reading_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            pages_read INTEGER NOT NULL,
            book_title TEXT,
            notes TEXT,
            reading_time INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reading_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_type TEXT NOT NULL,
            target_value INTEGER NOT NULL,
            period TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('reading_tracker.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/log_reading', methods=['POST'])
def log_reading():
    """Log a reading session"""
    data = request.json
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reading_sessions (date, pages_read, book_title, notes, reading_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['date'],
            data['pages_read'],
            data.get('book_title', ''),
            data.get('notes', ''),
            data.get('reading_time', 0)
        ))
        
        conn.commit()
        session_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'session_id': session_id})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_stats')
def get_stats():
    """Get reading statistics"""
    conn = get_db_connection()
    
    # Get total pages read
    total_pages = conn.execute('SELECT SUM(pages_read) FROM reading_sessions').fetchone()[0] or 0
    
    # Get current streak
    streak = calculate_reading_streak(conn)
    
    # Get this week's reading
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
    week_pages = conn.execute(
        'SELECT SUM(pages_read) FROM reading_sessions WHERE date >= ?', 
        (week_start,)
    ).fetchone()[0] or 0
    
    # Get this month's reading
    month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    month_pages = conn.execute(
        'SELECT SUM(pages_read) FROM reading_sessions WHERE date >= ?', 
        (month_start,)
    ).fetchone()[0] or 0
    
    # Get average pages per day
    first_entry = conn.execute('SELECT MIN(date) FROM reading_sessions').fetchone()[0]
    if first_entry:
        days_since_start = (datetime.now() - datetime.strptime(first_entry, '%Y-%m-%d')).days + 1
        avg_pages = total_pages / days_since_start if days_since_start > 0 else 0
    else:
        avg_pages = 0
    
    conn.close()
    
    return jsonify({
        'total_pages': total_pages,
        'current_streak': streak,
        'week_pages': week_pages,
        'month_pages': month_pages,
        'avg_pages_per_day': round(avg_pages, 1)
    })

@app.route('/api/get_chart_data')
def get_chart_data():
    """Get data for charts"""
    conn = get_db_connection()
    
    # Last 30 days data
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    daily_data = conn.execute('''
        SELECT date, SUM(pages_read) as pages
        FROM reading_sessions 
        WHERE date >= ?
        GROUP BY date
        ORDER BY date
    ''', (thirty_days_ago,)).fetchall()
    
    # Monthly data for the year
    monthly_data = conn.execute('''
        SELECT 
            strftime('%Y-%m', date) as month,
            SUM(pages_read) as pages
        FROM reading_sessions 
        WHERE date >= date('now', '-12 months')
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month
    ''').fetchall()
    
    # Book distribution
    book_data = conn.execute('''
        SELECT 
            CASE 
                WHEN book_title = '' OR book_title IS NULL THEN 'Unspecified'
                ELSE book_title
            END as book,
            SUM(pages_read) as pages
        FROM reading_sessions
        GROUP BY book
        ORDER BY pages DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return jsonify({
        'daily': [{'date': row['date'], 'pages': row['pages']} for row in daily_data],
        'monthly': [{'month': row['month'], 'pages': row['pages']} for row in monthly_data],
        'books': [{'book': row['book'], 'pages': row['pages']} for row in book_data]
    })

@app.route('/api/get_recent_sessions')
def get_recent_sessions():
    """Get recent reading sessions"""
    conn = get_db_connection()
    
    sessions = conn.execute('''
        SELECT date, pages_read, book_title, notes, reading_time
        FROM reading_sessions
        ORDER BY date DESC, created_at DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return jsonify([{
        'date': session['date'],
        'pages_read': session['pages_read'],
        'book_title': session['book_title'] or 'Unspecified',
        'notes': session['notes'] or '',
        'reading_time': session['reading_time'] or 0
    } for session in sessions])

def calculate_reading_streak(conn):
    """Calculate current reading streak"""
    today = datetime.now().strftime('%Y-%m-%d')
    streak = 0
    current_date = datetime.now()
    
    while True:
        date_str = current_date.strftime('%Y-%m-%d')
        pages = conn.execute(
            'SELECT SUM(pages_read) FROM reading_sessions WHERE date = ?', 
            (date_str,)
        ).fetchone()[0] or 0
        
        if pages > 0:
            streak += 1
        else:
            break
            
        current_date -= timedelta(days=1)
    
    return streak

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

# Additional utility functions for data analysis
class ReadingAnalytics:
    """Advanced analytics for reading data"""
    
    @staticmethod
    def get_reading_velocity(conn, days=7):
        """Calculate reading velocity over specified days"""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        result = conn.execute('''
            SELECT AVG(pages_read) as avg_pages, COUNT(*) as reading_days
            FROM reading_sessions 
            WHERE date >= ? AND pages_read > 0
        ''', (cutoff_date,)).fetchone()
        
        return {
            'avg_pages_per_session': round(result['avg_pages'] or 0, 1),
            'reading_days': result['reading_days'] or 0,
            'period_days': days
        }
    
    @staticmethod
    def get_reading_patterns(conn):
        """Analyze reading patterns by day of week"""
        result = conn.execute('''
            SELECT 
                CASE strftime('%w', date)
                    WHEN '0' THEN 'Sunday'
                    WHEN '1' THEN 'Monday'
                    WHEN '2' THEN 'Tuesday'
                    WHEN '3' THEN 'Wednesday'
                    WHEN '4' THEN 'Thursday'
                    WHEN '5' THEN 'Friday'
                    WHEN '6' THEN 'Saturday'
                END as day_name,
                AVG(pages_read) as avg_pages,
                COUNT(*) as sessions
            FROM reading_sessions
            GROUP BY strftime('%w', date)
            ORDER BY strftime('%w', date)
        ''').fetchall()
        
        return [{
            'day': row['day_name'],
            'avg_pages': round(row['avg_pages'], 1),
            'sessions': row['sessions']
        } for row in result]

# CLI interface for quick logging
def cli_log_reading():
    """Command line interface for logging reading"""
    print("Reading Tracker - Quick Log")
    print("-" * 30)
    
    date = input("Date (YYYY-MM-DD, press Enter for today): ").strip()
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        pages = int(input("Pages read: "))
        book = input("Book title (optional): ").strip()
        notes = input("Notes (optional): ").strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reading_sessions (date, pages_read, book_title, notes)
            VALUES (?, ?, ?, ?)
        ''', (date, pages, book, notes))
        
        conn.commit()
        conn.close()
        
        print(f"✓ Logged {pages} pages for {date}")
        
    except ValueError:
        print("Invalid input. Please enter a valid number for pages.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        cli_log_reading()
    else:
        init_db()
        app.run(debug=True)