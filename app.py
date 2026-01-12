import sqlite3
import os
import uuid
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from PIL import Image
import io
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

if not app.secret_key:
    raise ValueError("No SECRET_KEY set for Flask application. Did you forget to create a .env file?")

DB_NAME = os.getenv('DB_PATH', 'links.db')
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'ico', 'svg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Internationalization ---
TRANSLATIONS = {
    'es': {
        'title': 'Hub de Aplicaciones',
        'my_apps': 'Mis Aplicaciones',
        'my_links': 'Mis Links',
        'add_link': 'Añadir Link',
        'add_new': 'Añadir Nuevo',
        'manage_categories': 'Gestionar Categorías',
        'theme': 'Tema',
        'add_new_link': 'Añadir Nuevo Link',
        'edit_link': 'Editar Link',
        'title_label': 'Título de la Aplicación',
        'url_label': 'URL Completa',
        'category_label': 'Categoría',
        'icon_label': 'Icono',
        'use_emoji': 'Usar Emoji',
        'upload_image': 'Subir Imagen',
        'fetch_url': 'Usar Icono de la URL (Automático)',
        'fetch_url_overwrite': 'Buscar en URL (Sobrescribir actual)',
        'save_link': 'Guardar Link',
        'save_changes': 'Guardar Cambios',
        'cancel': 'Cancelar',
        'delete_confirm': '¿Estás seguro de querer borrar este link?',
        'no_links': 'No hay links configurados aún.',
        'start_adding': '¡Empieza añadiendo uno!',
        'new_category': 'Nueva Categoría',
        'edit_category': 'Editar Categoría',
        'cat_name_label': 'Nombre de la Categoría',
        'actions': 'Acciones',
        'delete': 'Borrar',
        'edit': 'Editar',
        'delete_cat_confirm': '¿Borrar esta categoría? Los links asociados se moverán a otra categoría.',
        'flash_cat_added': 'Categoría añadida.',
        'flash_cat_updated': 'Categoría actualizada.',
        'flash_cat_deleted': 'Categoría eliminada.',
        'flash_cat_only_one': 'No puedes borrar la única categoría.',
        'flash_link_deleted': 'Link eliminado correctamente!',
        'flash_error_image': 'Error guardando la imagen.',
        'flash_error_fetch': 'No se pudo guardar el favicon descargado.',
        'flash_error_fetch_not_found': 'No se pudo encontrar el favicon en la URL.',
        'flash_title_url_required': '¡Título y URL son obligatorios!',
        'flash_link_not_found': '¡Link no encontrado!',
        'support_png': 'Soporta PNG, JPG, WEBP.',
        'fetch_info_add': 'Al guardar, intentaremos descargar el favicon de la URL proporcionada y usarlo como icono.',
        'fetch_info_edit': 'Se descargará el favicon de la URL y reemplazará al icono actual.',
        'current_icon': 'Icono Actual:',
        'classic_themes': 'Clásicos',
        'minimalist_themes': 'Minimalistas',
        'vibrant_themes': 'Vibrantes',
        'language': 'Idioma',
        'light': 'Claro',
        'dark': 'Oscuro',
        'forest': 'Bosque',
        'ocean': 'Océano',
        'nord': 'Nord',
        'dracula': 'Dracula',
        'coffee': 'Café',
        'lavender': 'Lavanda',
        'cyberpunk': 'Cyberpunk'
    },
    'en': {
        'title': 'App Hub',
        'my_apps': 'My Apps',
        'my_links': 'My Links',
        'add_link': 'Add Link',
        'add_new': 'Add New',
        'manage_categories': 'Manage Categories',
        'theme': 'Theme',
        'add_new_link': 'Add New Link',
        'edit_link': 'Edit Link',
        'title_label': 'Application Title',
        'url_label': 'Full URL',
        'category_label': 'Category',
        'icon_label': 'Icon',
        'use_emoji': 'Use Emoji',
        'upload_image': 'Upload Image',
        'fetch_url': 'Use URL Icon (Auto)',
        'fetch_url_overwrite': 'Fetch from URL (Overwrite)',
        'save_link': 'Save Link',
        'save_changes': 'Save Changes',
        'cancel': 'Cancel',
        'delete_confirm': 'Are you sure you want to delete this link?',
        'no_links': 'No links configured yet.',
        'start_adding': 'Start by adding one!',
        'new_category': 'New Category',
        'edit_category': 'Edit Category',
        'cat_name_label': 'Category Name',
        'actions': 'Actions',
        'delete': 'Delete',
        'edit': 'Edit',
        'delete_cat_confirm': 'Delete this category? Associated links will be moved to another category.',
        'flash_cat_added': 'Category added.',
        'flash_cat_updated': 'Category updated.',
        'flash_cat_deleted': 'Category deleted.',
        'flash_cat_only_one': 'Cannot delete the only category.',
        'flash_link_deleted': 'Link deleted successfully!',
        'flash_error_image': 'Error saving image.',
        'flash_error_fetch': 'Could not save fetched favicon.',
        'flash_error_fetch_not_found': 'Could not find favicon at URL.',
        'flash_title_url_required': 'Title and URL are required!',
        'flash_link_not_found': 'Link not found!',
        'support_png': 'Supports PNG, JPG, WEBP.',
        'fetch_info_add': 'On save, we will attempt to download the favicon from the provided URL.',
        'fetch_info_edit': 'The favicon will be downloaded from the URL and replace the current icon.',
        'current_icon': 'Current Icon:',
        'classic_themes': 'Classics',
        'minimalist_themes': 'Minimalists',
        'vibrant_themes': 'Vibrants',
        'language': 'Language',
        'light': 'Light',
        'dark': 'Dark',
        'forest': 'Forest',
        'ocean': 'Ocean',
        'nord': 'Nord',
        'dracula': 'Dracula',
        'coffee': 'Coffee',
        'lavender': 'Lavender',
        'cyberpunk': 'Cyberpunk'
    }
}

def get_locale():
    return session.get('lang', 'es')

def t(key):
    lang = get_locale()
    return TRANSLATIONS.get(lang, TRANSLATIONS['es']).get(key, key)

@app.context_processor
def inject_i18n():
    return dict(t=t, current_language=get_locale())

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in TRANSLATIONS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

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
            flash(t('flash_cat_added'))
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
            flash(t('flash_cat_updated'))
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
        flash(t('flash_cat_only_one'))
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
    flash(t('flash_cat_deleted'))
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
                        flash(t('flash_error_image'))
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
                     flash(t('flash_error_fetch'))
                     icon_type = 'emoji'
            else:
                flash(t('flash_error_fetch_not_found'))
                icon_type = 'emoji'

        if not title or not url:
            flash(t('flash_title_url_required'))
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
                    flash(t('flash_error_fetch'))
                    icon_type = current_link['icon_type']
                    icon_value = current_link['icon_value']
             else:
                flash(t('flash_error_fetch_not_found'))
                icon_type = current_link['icon_type']
                icon_value = current_link['icon_value']

        if not title or not url:
            flash(t('flash_title_url_required'))
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
        flash(t('flash_link_not_found'))
        return redirect(url_for('index'))

    return render_template('edit.html', link=link, categories=categories)

@app.route('/delete/<int:id>', methods=('POST',))
def delete(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM links WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash(t('flash_link_deleted'))
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
