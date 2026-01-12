import sqlite3
import os
import uuid
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from PIL import Image
import io

app = Flask(__name__)
app.secret_key = 'super_secret_key_change_this_in_production'
DB_NAME = os.getenv('DB_PATH', 'links.db')
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'ico', 'svg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_and_save_image(image_data, filename_prefix="icon"):
    """
    Toma datos binarios de imagen y los guarda como PNG.
    Se ha eliminado la funcionalidad de rembg para evitar errores en RPi.
    """
    try:
        input_image = Image.open(io.BytesIO(image_data))
        
        # Generar nombre único
        filename = f"{uuid.uuid4()}_{filename_prefix}.png"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Guardar simplemente como PNG
        input_image.save(save_path, format="PNG")
        return filename
    except Exception as e:
        print(f"Error saving image: {e}")
        return None

def fetch_favicon_from_url(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    def get_icon_url_from_html(html_content, base_url):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for rel in ['icon', 'shortcut icon', 'apple-touch-icon', 'apple-touch-icon-precomposed']:
                link = soup.find('link', rel=lambda x: x and rel in x.lower())
                if link and link.get('href'):
                    return urljoin(base_url, link.get('href'))
        except Exception:
            pass
        return None

    def try_download_image(img_url):
        try:
            r = requests.get(img_url, headers=headers, timeout=5)
            if r.status_code == 200 and len(r.content) > 0:
                return r.content
        except Exception:
            pass
        return None

    try:
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        parsed = urlparse(url)
        if not parsed.netloc:
            return None

        # 1. Try fetching the specific URL provided
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                icon_url = get_icon_url_from_html(response.text, response.url)
                if icon_url:
                    content = try_download_image(icon_url)
                    if content: return content
        except Exception as e:
            print(f"Warning: Could not fetch specific URL {url}: {e}")

        # 2. Try fetching the root domain if we haven't already
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        if base_url.rstrip('/') != url.rstrip('/'):
            try:
                response = requests.get(base_url, headers=headers, timeout=5)
                if response.status_code == 200:
                    icon_url = get_icon_url_from_html(response.text, response.url)
                    if icon_url:
                        content = try_download_image(icon_url)
                        if content: return content
            except Exception:
                pass

        # 3. Fallback: try /favicon.ico at the root
        favicon_url = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
        content = try_download_image(favicon_url)
        if content: return content

    except Exception as e:
        print(f"Error in fetch_favicon_from_url: {e}")

    return None

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Create links table
    c.execute('''
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL
        )
    ''')

    # Create categories table
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')

    # Ensure default category exists
    c.execute('SELECT count(*) FROM categories')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO categories (name) VALUES (?)', ('Mis Aplicaciones',))

    # Add columns to links if they don't exist
    try:
        c.execute('ALTER TABLE links ADD COLUMN icon_type TEXT DEFAULT "emoji"')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE links ADD COLUMN icon_value TEXT DEFAULT "🔗"')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE links ADD COLUMN category_id INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    links = conn.execute('SELECT * FROM links ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', links=links, categories=categories)

@app.route('/categories')
def manage_categories():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories ORDER BY id').fetchall()
    conn.close()
    return render_template('categories.html', categories=categories)

@app.route('/categories/add', methods=('GET', 'POST'))
def add_category():
    if request.method == 'POST':
        name = request.form['name']
        if name:
            conn = get_db_connection()
            conn.execute('INSERT INTO categories (name) VALUES (?)', (name,))
            conn.commit()
            conn.close()
            flash('Categoría añadida.')
            return redirect(url_for('manage_categories'))
    return render_template('category_form.html')

@app.route('/categories/edit/<int:id>', methods=('GET', 'POST'))
def edit_category(id):
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        if name:
            conn.execute('UPDATE categories SET name = ? WHERE id = ?', (name, id))
            conn.commit()
            conn.close()
            flash('Categoría actualizada.')
            return redirect(url_for('manage_categories'))
    
    category = conn.execute('SELECT * FROM categories WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('category_form.html', category=category)

@app.route('/categories/delete/<int:id>', methods=('POST',))
def delete_category(id):
    conn = get_db_connection()
    # Check if it's the only category or default
    count = conn.execute('SELECT count(*) FROM categories').fetchone()[0]
    if count <= 1:
        flash('No puedes borrar la única categoría.')
        conn.close()
        return redirect(url_for('manage_categories'))

    # Reassign links to the first available category that isn't the one being deleted
    default_cat = conn.execute('SELECT id FROM categories WHERE id != ? LIMIT 1', (id,)).fetchone()
    if default_cat:
        new_cat_id = default_cat['id']
        conn.execute('UPDATE links SET category_id = ? WHERE category_id = ?', (new_cat_id, id))
    
    conn.execute('DELETE FROM categories WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Categoría eliminada.')
    return redirect(url_for('manage_categories'))

@app.route('/add', methods=('GET', 'POST'))
def add():
    conn = get_db_connection()
    if request.method == 'POST':
        title = request.form['title']
        url = request.form['url']
        category_id = request.form.get('category_id')
        icon_type = request.form.get('icon_type', 'emoji')
        icon_value = '🔗'

        if icon_type == 'emoji':
            icon_value = request.form.get('icon_emoji', '🔗')
            
        elif icon_type == 'image':
            if 'icon_image' in request.files:
                file = request.files['icon_image']
                if file and allowed_file(file.filename):
                    file_data = file.read()
                    processed_filename = process_and_save_image(file_data, "upload")
                    if processed_filename:
                        icon_value = processed_filename
                    else:
                        flash('Error guardando la imagen.')
                        icon_type = 'emoji'
                else:
                    icon_type = 'emoji'
        
        elif icon_type == 'fetch':
            img_data = fetch_favicon_from_url(url)
            if img_data:
                processed_filename = process_and_save_image(img_data, "fetched")
                if processed_filename:
                    icon_type = 'image'
                    icon_value = processed_filename
                else:
                     flash('No se pudo guardar el favicon descargado.')
                     icon_type = 'emoji'
            else:
                flash('No se pudo encontrar el favicon en la URL.')
                icon_type = 'emoji'

        if not title or not url:
            flash('Title and URL are required!')
        else:
            conn.execute('INSERT INTO links (title, url, icon_type, icon_value, category_id) VALUES (?, ?, ?, ?, ?)', 
                      (title, url, icon_type, icon_value, category_id))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))
    
    categories = conn.execute('SELECT * FROM categories').fetchall()
    conn.close()
    return render_template('add.html', categories=categories)

@app.route('/edit/<int:id>', methods=('GET', 'POST'))
def edit(id):
    conn = get_db_connection()

    if request.method == 'POST':
        title = request.form['title']
        url = request.form['url']
        category_id = request.form.get('category_id')
        icon_type = request.form.get('icon_type', 'emoji')
        
        current_link = conn.execute('SELECT * FROM links WHERE id = ?', (id,)).fetchone()
        
        icon_value = current_link['icon_value'] if current_link else '🔗'

        if icon_type == 'emoji':
            icon_value = request.form.get('icon_emoji', '🔗')
            
        elif icon_type == 'image':
            if 'icon_image' in request.files:
                file = request.files['icon_image']
                if file and file.filename != '' and allowed_file(file.filename):
                    file_data = file.read()
                    processed_filename = process_and_save_image(file_data, "upload")
                    if processed_filename:
                        icon_value = processed_filename
                elif current_link['icon_type'] != 'image':
                     icon_type = 'emoji'
                     icon_value = '🔗'
        
        elif icon_type == 'fetch':
             img_data = fetch_favicon_from_url(url)
             if img_data:
                processed_filename = process_and_save_image(img_data, "fetched")
                if processed_filename:
                    icon_type = 'image'
                    icon_value = processed_filename
                else:
                    flash('Error guardando favicon.')
                    icon_type = current_link['icon_type']
                    icon_value = current_link['icon_value']
             else:
                flash('No se encontró favicon.')
                icon_type = current_link['icon_type']
                icon_value = current_link['icon_value']

        if not title or not url:
            flash('Title and URL are required!')
        else:
            conn.execute('UPDATE links SET title = ?, url = ?, icon_type = ?, icon_value = ?, category_id = ? WHERE id = ?', 
                      (title, url, icon_type, icon_value, category_id, id))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))
    
    link = conn.execute('SELECT * FROM links WHERE id = ?', (id,)).fetchone()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    conn.close()

    if link is None:
        flash('Link not found!')
        return redirect(url_for('index'))

    return render_template('edit.html', link=link, categories=categories)

@app.route('/delete/<int:id>', methods=('POST',))
def delete(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM links WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Link deleted successfully!')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
