from flask import Flask, request, jsonify, send_file
from openai import OpenAI
import sqlite3
import csv
import io
from datetime import datetime
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Database setup
DATABASE = 'chat_history.db'

def init_db():
    """Initialize the database"""
    with sqlite3.connect(DATABASE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT CHECK(role IN ('user', 'assistant')),
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def save_message(role, content):
    """Save a message to the database"""
    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            "INSERT INTO chats (role, content) VALUES (?, ?)",
            (role, content)
        )
        conn.commit()

def get_recent_chats(limit=20):
    """Get recent chat history"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content, timestamp FROM chats ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
    return [{"role": row[0], "content": row[1], "timestamp": row[2]} for row in reversed(rows)]

def clear_history():
    """Clear all chat history"""
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("DELETE FROM chats")
        conn.commit()

def export_to_csv():
    """Export chat history to CSV"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content, timestamp FROM chats ORDER BY timestamp"
        )
        rows = cursor.fetchall()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Role', 'Content', 'Timestamp'])
    writer.writerows(rows)
    
    # Prepare for download
    output.seek(0)
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    output.close()
    
    return mem

# Konfigurasi upload
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'docx', 'py'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes
@app.route('/')
def home():
    return send_file('templates/index.html')

@app.route('/get_history')
def get_history():
    return jsonify({"history": get_recent_chats()})

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json['message']
    
    # Save user message
    save_message('user', user_message)
    
    # Get context (last 5 messages)
    context = get_recent_chats(limit=5)
    
    # Prepare messages for OpenAI (without timestamps)
    openai_messages = [
        {"role": msg['role'], "content": msg['content']} 
        for msg in context
    ]
    openai_messages.append({"role": "user", "content": user_message})
    
    # Get response from OpenAI
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=openai_messages,
        temperature=0.7
    )
    
    bot_reply = response.choices[0].message.content
    
    # Save assistant's reply
    save_message('assistant', bot_reply)
    
    return jsonify({
        "reply": bot_reply,
        "history": get_recent_chats()
    })

@app.route('/clear_history', methods=['POST'])
def handle_clear_history():
    clear_history()
    return jsonify({"status": "success"})

@app.route('/export_history')
def handle_export_history():
    csv_data = export_to_csv()
    return send_file(
        csv_data,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'chat_history_{datetime.now().strftime("%Y%m%d")}.csv'
    )

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Proses file (contoh: baca isi file teks)
        if filename.endswith('.txt'):
            with open(filepath, 'r') as f:
                content = f.read(1000)  # Baca 1000 karakter pertama
        else:
            content = f"File {filename} berhasil diupload (tipe: {file.content_type})"
        
        # Simpan ke riwayat chat
        save_message('user', f"[FILE] {filename}")
        
        # Dapatkan respons dari AI (contoh sederhana)
        reply = f"Saya menerima file Anda: {filename}\nIsi: {content[:200]}..."
        save_message('assistant', reply)
        
        return jsonify({"reply": reply})
    
    return jsonify({"error": "File type not allowed"}), 400


if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)