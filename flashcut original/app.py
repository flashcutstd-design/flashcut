"""
FlashCut — Flask Backend
========================
• Production  → Supabase (PostgreSQL) + ImageKit CDN
• Local dev   → SQLite fallback (no env vars needed)

Run locally:  python app.py  →  http://localhost:5000
Admin panel:  http://localhost:5000/admin
Deploy:       Render  (see render.yaml)

Required env vars for production (Render dashboard):
  SUPABASE_URL          https://xxxx.supabase.co
  SUPABASE_KEY          service_role key (full DB access)
  IMAGEKIT_PUBLIC_KEY   from imagekit.io
  IMAGEKIT_PRIVATE_KEY  from imagekit.io
  IMAGEKIT_URL_ENDPOINT https://ik.imagekit.io/your_id
  IMAGEKIT_FOLDER       flashcut
  ADMIN_USER            admin username
  ADMIN_PASS            admin password
  FLASHCUT_SECRET       random secret string
"""

import os, uuid, json, sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask, request, jsonify, send_from_directory,
    g, render_template_string, session, redirect, url_for
)
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).parent.resolve()

# Persistent data dir: /data on Render, ./data locally, /tmp on Vercel
DATA_DIR = Path(os.environ.get('RENDER_DISK_PATH', BASE_DIR / 'data'))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    DATA_DIR = Path('/tmp')

UPLOAD_DIR = DATA_DIR / 'uploads'
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

DB_PATH = DATA_DIR / 'flashcut.db'

ALLOWED_VIDEO = {'mp4', 'mov', 'webm', 'avi', 'm4v', 'mkv'}
ALLOWED_IMAGE = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

ADMIN_USER = os.environ.get('ADMIN_USER', 'flashcut123')
ADMIN_PASS = os.environ.get('ADMIN_PASS', '43214321')

# ── Supabase ──────────────────────────────────────────────
# ── Supabase ──────────────────────────────────────────────
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '').strip()
# Only use Supabase if both values are set AND key looks like a real JWT
USE_SUPABASE = bool(
    SUPABASE_URL and SUPABASE_KEY
    and SUPABASE_URL.startswith('https://')
    and len(SUPABASE_KEY) > 100   # real JWT keys are always > 100 chars
)

if USE_SUPABASE:
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print('[OK]  Supabase connected')
    except Exception as _sb_err:
        print(f'[WARN]  Supabase connection failed: {_sb_err} — falling back to SQLite')
        USE_SUPABASE = False

# ── ImageKit ──────────────────────────────────────────────
IK_PUBLIC   = os.environ.get('IMAGEKIT_PUBLIC_KEY', '')
IK_PRIVATE  = os.environ.get('IMAGEKIT_PRIVATE_KEY', '')
IK_ENDPOINT = os.environ.get('IMAGEKIT_URL_ENDPOINT', '')
IK_FOLDER   = os.environ.get('IMAGEKIT_FOLDER', 'flashcut')
USE_IMAGEKIT = bool(IK_PRIVATE)   # v5 only requires private_key

if USE_IMAGEKIT:
    from imagekitio import ImageKit
    ik = ImageKit(private_key=IK_PRIVATE)

# ══════════════════════════════════════════════════════════
#  FLASK APP
# ══════════════════════════════════════════════════════════
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path='')
app.secret_key = os.environ.get('FLASHCUT_SECRET', 'flashcut-dev-secret-change-me')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
CORS(app, resources={r'/api/*': {'origins': '*'}})


# ══════════════════════════════════════════════════════════
#  DATABASE LAYER  — Supabase in prod, SQLite locally
# ══════════════════════════════════════════════════════════

# ── SQLite helpers (local dev only) ──────────────────────
def get_sqlite():
    db = getattr(g, '_sqlite', None)
    if db is None:
        db = g._sqlite = sqlite3.connect(str(DB_PATH))
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_sqlite(_):
    db = getattr(g, '_sqlite', None)
    if db:
        db.close()

def init_sqlite():
    """Create SQLite tables and seed data for local dev."""
    with app.app_context():
        db = get_sqlite()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, email TEXT NOT NULL,
                phone TEXT, message TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT,
                shoot_date TEXT, shoot_time TEXT, location TEXT,
                shoot_type TEXT, package TEXT, notes TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS newsletter (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS pricing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_key TEXT NOT NULL UNIQUE, plan_name TEXT NOT NULL,
                price INTEGER NOT NULL, cycle TEXT NOT NULL,
                description TEXT, features TEXT,
                popular INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, tag TEXT, video_url TEXT,
                thumb_color TEXT DEFAULT '#d4a017,#3a2c00',
                sort_order INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, role TEXT,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                review TEXT NOT NULL, approved INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        # Seed pricing
        if db.execute('SELECT COUNT(*) FROM pricing').fetchone()[0] == 0:
            db.executemany(
                'INSERT INTO pricing (plan_key,plan_name,price,cycle,description,features,popular,sort_order)'
                ' VALUES (?,?,?,?,?,?,?,?)',
                [
                    ('starter','Starter',999,'per shoot',
                     'Perfect for creators just getting started.',
                     '1-hour shoot session|4K quality|1 reel|Delivery in 10 minutes',0,1),
                    ('pro','Pro',4499,'per shoot',
                     'For serious creators who publish consistently.',
                     '5-hour shoot session|5 edited reels|Priority editing queue|4K export',1,2),
                    ('business','Business',11999,'per event',
                     '2-3 day full coverage for weddings and all functions.',
                     '2-3 day shoot coverage|Weddings & events|Unlimited reels|4K footage|Dedicated crew|Same-day highlight',0,3),
                ]
            )
        # Portfolio starts empty — admin adds items with videos via the admin panel
        # No seed data for portfolio
        # Reviews start empty — real reviews come from customers via the site
        # No seed data for reviews
        db.commit()


# ── Unified DB interface ──────────────────────────────────
# Each function returns plain Python dicts so the rest of
# the app doesn't care whether it's Supabase or SQLite.

def db_select(table, filters=None, order=None, limit=None):
    """SELECT rows. filters = dict of {col: val} (AND logic).
       order = 'col'  or  ('col', True/False for descending)
    """
    if USE_SUPABASE:
        q = supabase.table(table).select('*')
        if filters:
            for col, val in filters.items():
                q = q.eq(col, val)
        if order:
            if isinstance(order, str):
                q = q.order(order, desc=False)
            else:
                col, descending = order
                q = q.order(col, desc=descending)
        if limit:
            q = q.limit(limit)
        return q.execute().data or []
    else:
        db = get_sqlite()
        sql    = f'SELECT * FROM {table}'
        params = []
        if filters:
            # Normalize Python bools to SQLite integers (True→1, False→0)
            normalized = {
                c: (1 if v is True else 0 if v is False else v)
                for c, v in filters.items()
            }
            clauses = [f'{c}=?' for c in normalized]
            sql    += ' WHERE ' + ' AND '.join(clauses)
            params  = list(normalized.values())
        if order:
            if isinstance(order, str):
                col, direction = order, 'ASC'
            else:
                col, descending = order
                direction = 'DESC' if descending else 'ASC'
            # Only add ORDER BY if the column actually exists in this table
            try:
                db.execute(f'SELECT {col} FROM {table} LIMIT 0')
                sql += f' ORDER BY {col} {direction}'
            except sqlite3.OperationalError:
                pass   # column doesn't exist — skip ordering
        if limit:
            sql += f' LIMIT {limit}'
        return [dict(r) for r in db.execute(sql, params).fetchall()]


def db_insert(table, data):
    """INSERT a row. Returns the inserted row dict."""
    if USE_SUPABASE:
        result = supabase.table(table).insert(data).execute()
        return result.data[0] if result.data else {}
    else:
        db = get_sqlite()
        cols   = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        cur = db.execute(
            f'INSERT INTO {table} ({cols}) VALUES ({placeholders})',
            list(data.values())
        )
        db.commit()
        return {**data, 'id': cur.lastrowid}


def db_update(table, row_id, data):
    """UPDATE row by id. Returns updated row dict."""
    if USE_SUPABASE:
        result = supabase.table(table).update(data).eq('id', row_id).execute()
        return result.data[0] if result.data else {}
    else:
        db = get_sqlite()
        sets = ', '.join([f'{c}=?' for c in data])
        db.execute(f'UPDATE {table} SET {sets} WHERE id=?', [*data.values(), row_id])
        db.commit()
        return {**data, 'id': row_id}


def db_delete(table, row_id):
    """DELETE row by id."""
    if USE_SUPABASE:
        supabase.table(table).delete().eq('id', row_id).execute()
    else:
        db = get_sqlite()
        db.execute(f'DELETE FROM {table} WHERE id=?', (row_id,))
        db.commit()


def db_insert_unique(table, data, unique_col):
    """INSERT ignoring duplicate on unique_col. Returns (row, already_existed)."""
    if USE_SUPABASE:
        # upsert with onConflict ignore
        result = supabase.table(table).upsert(
            data, on_conflict=unique_col, ignore_duplicates=True
        ).execute()
        if result.data:
            return result.data[0], False
        # already existed — fetch it
        existing = supabase.table(table).select('*').eq(unique_col, data[unique_col]).execute()
        return (existing.data[0] if existing.data else {}), True
    else:
        try:
            row = db_insert(table, data)
            return row, False
        except sqlite3.IntegrityError:
            return {}, True


# ── Upload helpers ────────────────────────────────────────
def allowed(filename, exts):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in exts

def do_upload(file_obj, original_name):
    """Upload to ImageKit (v5 SDK) if configured, else save locally.
       Returns (url, filename, storage_type).
    """
    ext  = original_name.rsplit('.', 1)[1].lower()
    name = f'{uuid.uuid4().hex}.{ext}'

    if USE_IMAGEKIT:
        file_data = file_obj.read()
        # ImageKit v5 SDK: ik.files.upload(file=..., file_name=..., folder=...)
        response  = ik.files.upload(
            file      = file_data,
            file_name = name,
            folder    = f'/{IK_FOLDER}',
        )
        # v5 returns a FileUploadResponse — url is in response.url
        cdn_url = getattr(response, 'url', None) or \
                  f'{IK_ENDPOINT.rstrip("/")}/{IK_FOLDER}/{name}'
        return cdn_url, name, 'imagekit'
    else:
        path = UPLOAD_DIR / name
        file_obj.save(str(path))
        return f'uploads/{name}', name, 'local'


# ══════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*a, **kw)
    return wrapped


# ══════════════════════════════════════════════════════════
#  STATIC FILE SERVING
# ══════════════════════════════════════════════════════════
@app.route('/')
def index():
    return send_from_directory(str(BASE_DIR), 'index.html')

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(str(UPLOAD_DIR), filename)

@app.route('/<path:filename>')
def static_files(filename):
    if filename.startswith(('admin', 'api')):
        return 'Not found', 404
    return send_from_directory(str(BASE_DIR), filename)


# ══════════════════════════════════════════════════════════
#  PUBLIC APIs
# ══════════════════════════════════════════════════════════

@app.route('/api/pricing')
def api_pricing():
    try:
        # Supabase pricing cols: id, name, price, currency, description, is_active
        active = True if USE_SUPABASE else 1
        rows = db_select('pricing', filters={'is_active': active})
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e), 'ok': False}), 500


@app.route('/api/portfolio')
def api_portfolio():
    try:
        # Supabase portfolio cols: id, title, tag, video_url, thumb_color, sort_order, is_active
        active = True if USE_SUPABASE else 1
        rows = db_select('portfolio', filters={'is_active': active}, order=('sort_order', False))
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e), 'ok': False}), 500


@app.route('/api/reviews', methods=['GET'])
def api_reviews_get():
    try:
        # Supabase reviews cols: id, name, role, rating, review, approved
        approved = True if USE_SUPABASE else 1
        rows = db_select('reviews', filters={'approved': approved}, order=('id', True))
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e), 'ok': False}), 500


@app.route('/api/reviews', methods=['POST'])
def api_reviews_post():
    d      = request.get_json(silent=True) or request.form
    name   = (d.get('name')   or '').strip()[:120]
    role   = (d.get('role')   or '').strip()[:120]
    rating = int(d.get('rating') or 0)
    review = (d.get('review') or '').strip()[:1000]

    if not name or not review:
        return jsonify({'ok': False, 'error': 'Name and review are required'}), 400
    if not (1 <= rating <= 5):
        return jsonify({'ok': False, 'error': 'Rating must be 1-5'}), 400

    db_insert('reviews', {
        'name': name, 'role': role,
        'rating': rating, 'review': review,
        'approved': False if USE_SUPABASE else 0,
    })
    return jsonify({'ok': True, 'message': 'Thank you! Your review is pending approval.'})


@app.route('/api/contact', methods=['POST'])
def api_contact():
    d       = request.get_json(silent=True) or request.form
    name    = (d.get('name')    or '').strip()[:200]
    email   = (d.get('email')   or '').strip()[:200]
    phone   = (d.get('phone')   or '').strip()[:50]
    message = (d.get('message') or '').strip()[:2000]

    if not name or not email or not message:
        return jsonify({'ok': False, 'error': 'name, email and message are required'}), 400
    if '@' not in email:
        return jsonify({'ok': False, 'error': 'Please enter a valid email address'}), 400

    db_insert('contacts', {
        'name': name, 'email': email, 'phone': phone, 'message': message
    })

    # Send email notification via Formspree (non-blocking)
    try:
        import threading
        def _notify():
            requests.post(
                'https://formspree.io/f/xwlkrnjp',
                json={
                    '_subject': f'New FlashCut Message — {name}',
                    '_replyto': email,
                    'Name':    name,
                    'Email':   email,
                    'Phone':   phone or '—',
                    'Message': message,
                },
                timeout=5
            )
        threading.Thread(target=_notify, daemon=True).start()
    except Exception:
        pass

    return jsonify({'ok': True, 'message': "Thanks! We'll get back to you within 24 hours."})


@app.route('/api/booking', methods=['POST'])
def api_booking():
    d          = request.get_json(silent=True) or request.form
    name       = (d.get('name')       or d.get('fullName') or '').strip()[:200]
    email      = (d.get('email')      or '').strip()[:200]
    phone      = (d.get('phone')      or '').strip()[:50]
    shoot_date = (d.get('shoot_date') or d.get('date')      or '').strip()[:100]
    shoot_time = (d.get('shoot_time') or d.get('time')      or '').strip()[:50]
    location   = (d.get('location')   or '').strip()[:500]
    shoot_type = (d.get('shoot_type') or d.get('shootType') or '').strip()[:100]
    package    = (d.get('package')    or '').strip()[:100]
    notes      = (d.get('notes')      or '').strip()[:2000]

    if not name or not email:
        return jsonify({'ok': False, 'error': 'name and email are required'}), 400
    if '@' not in email:
        return jsonify({'ok': False, 'error': 'Please enter a valid email address'}), 400

    db_insert('bookings', {
        'name': name, 'email': email, 'phone': phone,
        'shoot_date': shoot_date, 'shoot_time': shoot_time,
        'location': location, 'shoot_type': shoot_type,
        'package': package, 'notes': notes, 'status': 'pending',
    })

    # Send email notification via Formspree (non-blocking)
    try:
        import threading
        def _notify():
            requests.post(
                'https://formspree.io/f/xwlkrnjp',
                json={
                    '_subject': f'New FlashCut Booking — {name} ({shoot_type})',
                    '_replyto': email,
                    'Customer Name': name,
                    'Email':         email,
                    'Phone':         phone,
                    'Shoot Type':    shoot_type,
                    'Package':       package,
                    'Date':          shoot_date,
                    'Time':          shoot_time,
                    'Location':      location,
                    'Notes':         notes or '—',
                },
                timeout=5
            )
        threading.Thread(target=_notify, daemon=True).start()
    except Exception:
        pass  # never block the booking response

    return jsonify({'ok': True, 'message': "Booking confirmed! We'll contact you shortly."})


@app.route('/api/settings')
def api_settings_public():
    """Public endpoint — returns contact details for the frontend."""
    try:
        rows = db_select('site_settings')
        if rows and 'setting_key' in rows[0]:
            return jsonify({r['setting_key']: r['setting_value'] for r in rows})
        return jsonify({})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/newsletter', methods=['POST'])
def api_newsletter():
    d     = request.get_json(silent=True) or request.form
    email = (d.get('email') or '').strip()[:200]
    if not email:
        return jsonify({'ok': False, 'error': 'email is required'}), 400

    _, existed = db_insert_unique('newsletter', {'email': email}, 'email')
    if existed:
        return jsonify({'ok': True, 'message': 'Already subscribed!'})
    return jsonify({'ok': True, 'message': 'Subscribed!'})


# ══════════════════════════════════════════════════════════
#  ADMIN APIs
# ══════════════════════════════════════════════════════════

@app.route('/api/admin/upload', methods=['POST'])
@login_required
def api_admin_upload():
    """Admin-only file upload.
    Uses ImageKit v3 SDK when configured, local disk as fallback.
    """
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No file uploaded'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'ok': False, 'error': 'No file selected'}), 400
    if not (allowed(f.filename, ALLOWED_VIDEO) or allowed(f.filename, ALLOWED_IMAGE)):
        return jsonify({'ok': False, 'error': 'File type not allowed (MP4, MOV, WEBM, JPG, PNG, GIF…)'}), 400

    try:
        url, filename, storage = do_upload(f, f.filename)
        return jsonify({
            'ok':       True,
            'file_url': url,          # full CDN URL (ImageKit) or relative path (local)
            'url':      url,          # alias kept for admin panel JS
            'filename': filename,
            'storage':  storage,      # 'imagekit' or 'local'
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/admin/booking/<int:bid>/status', methods=['PATCH'])
@login_required
def api_booking_status(bid):
    status = ((request.get_json(silent=True) or {}).get('status') or '').strip()
    if status not in ('pending', 'confirmed', 'cancelled'):
        return jsonify({'ok': False, 'error': 'invalid status'}), 400
    db_update('bookings', bid, {'status': status})
    return jsonify({'ok': True})


@app.route('/api/admin/booking/<int:bid>', methods=['DELETE'])
@login_required
def api_delete_booking(bid):
    db_delete('bookings', bid)
    return jsonify({'ok': True})


@app.route('/api/admin/contact/<int:cid>', methods=['DELETE'])
@login_required
def api_delete_contact(cid):
    db_delete('contacts', cid)
    return jsonify({'ok': True})


@app.route('/api/admin/newsletter/<int:nid>', methods=['DELETE'])
@login_required
def api_delete_newsletter(nid):
    db_delete('newsletter', nid)
    return jsonify({'ok': True})


@app.route('/api/admin/review/<int:rid>/approve', methods=['PATCH'])
@login_required
def api_approve_review(rid):
    db_update('reviews', rid, {'approved': True if USE_SUPABASE else 1})
    return jsonify({'ok': True})


@app.route('/api/admin/review/<int:rid>', methods=['DELETE'])
@login_required
def api_delete_review(rid):
    db_delete('reviews', rid)
    return jsonify({'ok': True})


@app.route('/api/admin/pricing/<int:pid>', methods=['PATCH'])
@login_required
def api_update_pricing(pid):
    data = request.get_json(silent=True) or {}
    # All pricing columns: name, label, price, currency, description, features, popular, is_active, cycle
    allowed_cols = {'name', 'label', 'price', 'currency', 'description',
                    'features', 'popular', 'is_active', 'cycle'}
    update = {k: v for k, v in data.items() if k in allowed_cols}
    if not update:
        return jsonify({'ok': False, 'error': 'nothing to update'}), 400
    db_update('pricing', pid, update)
    return jsonify({'ok': True})


@app.route('/api/admin/portfolio', methods=['POST'])
@login_required
def api_add_portfolio():
    data  = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()[:200]
    if not title:
        return jsonify({'ok': False, 'error': 'title is required'}), 400
    row = db_insert('portfolio', {
        'title':       title,
        'tag':         (data.get('tag')         or '').strip()[:100],
        'video_url':   (data.get('video_url')   or '').strip()[:500],
        'thumb_color': (data.get('thumb_color') or '#d4a017,#3a2c00').strip()[:100],
        'sort_order':  int(data.get('sort_order') or 99),
        'is_active':   True if USE_SUPABASE else 1,
    })
    return jsonify({'ok': True, 'id': row.get('id')})


@app.route('/api/admin/portfolio/<int:pid>', methods=['PATCH'])
@login_required
def api_update_portfolio(pid):
    data = request.get_json(silent=True) or {}
    allowed_cols = {'title', 'tag', 'video_url', 'thumb_color', 'sort_order', 'is_active'}
    update = {k: v for k, v in data.items() if k in allowed_cols}
    if not update:
        return jsonify({'ok': False, 'error': 'nothing to update'}), 400
    db_update('portfolio', pid, update)
    return jsonify({'ok': True})


@app.route('/api/admin/portfolio/<int:pid>', methods=['DELETE'])
@login_required
def api_delete_portfolio(pid):
    db_delete('portfolio', pid)
    return jsonify({'ok': True})


# ── Status endpoint (health check) ───────────────────────
@app.route('/api/status')
def api_status():
    return jsonify({
        'ok':       True,
        'database': 'supabase' if USE_SUPABASE else 'sqlite',
        'storage':  'imagekit' if USE_IMAGEKIT else 'local',
    })


# ── Settings GET / POST ───────────────────────────────────
@app.route('/api/admin/settings', methods=['GET'])
@login_required
def api_settings_get():
    """Return all settings as a flat dict {setting_key: setting_value}."""
    try:
        rows = db_select('site_settings')
        if rows and 'setting_key' in rows[0]:
            return jsonify({'ok': True, 'settings': {r['setting_key']: r['setting_value'] for r in rows}})
        return jsonify({'ok': True, 'settings': {}})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'settings': {}}), 200


@app.route('/api/admin/settings', methods=['POST'])
@login_required
def api_settings_post():
    """Upsert settings. Accepts {key: value, ...} dict."""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({'ok': False, 'error': 'no data'}), 400
    try:
        if USE_SUPABASE:
            for key, value in data.items():
                # Check if row exists
                existing = supabase.table('site_settings').select('id').eq('setting_key', key).execute()
                if existing.data:
                    supabase.table('site_settings').update(
                        {'setting_value': str(value)}
                    ).eq('setting_key', key).execute()
                else:
                    supabase.table('site_settings').insert(
                        {'setting_key': key, 'setting_value': str(value)}
                    ).execute()
        else:
            db = get_sqlite()
            db.execute("""CREATE TABLE IF NOT EXISTS site_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT,
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )""")
            for key, value in data.items():
                db.execute(
                    'INSERT INTO site_settings (setting_key,setting_value) VALUES (?,?) '
                    'ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value',
                    (key, str(value))
                )
            db.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════════════════
#  ADMIN LOGIN TEMPLATE
# ══════════════════════════════════════════════════════════
LOGIN_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>FlashCut Admin Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#080808;color:#f0f0f0;
  min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;
  background-image:radial-gradient(ellipse at 50% 0%,rgba(212,160,23,.12) 0%,transparent 60%)}
.box{background:#111;border:1px solid rgba(212,160,23,.25);border-radius:20px;
  padding:48px 44px;width:100%;max-width:420px;box-shadow:0 0 80px rgba(212,160,23,.07)}
.logo{font-size:1.8rem;font-weight:800;margin-bottom:4px;letter-spacing:-1px}
.logo span{color:#d4a017}
.sub{color:#555;font-size:.85rem;margin-bottom:36px}
label{display:block;font-size:.72rem;color:#777;text-transform:uppercase;letter-spacing:.14em;margin-bottom:8px}
input{width:100%;padding:13px 16px;background:#0d0d0d;border:1px solid #222;border-radius:12px;
  color:#f0f0f0;font-size:.92rem;outline:none;margin-bottom:20px;transition:border-color .2s,box-shadow .2s}
input:focus{border-color:#d4a017;box-shadow:0 0 0 3px rgba(212,160,23,.15)}
button{width:100%;padding:14px;background:linear-gradient(135deg,#d4a017,#b8860b);color:#000;
  border:none;border-radius:12px;font-size:.95rem;font-weight:700;cursor:pointer;
  box-shadow:0 4px 20px rgba(212,160,23,.3);transition:opacity .2s,transform .15s}
button:hover{opacity:.9;transform:translateY(-1px)}
.err{color:#ff6b6b;font-size:.82rem;margin-top:12px;text-align:center;padding:12px;
  background:rgba(255,107,107,.08);border:1px solid rgba(255,107,107,.2);border-radius:10px}
.hint{margin-top:20px;font-size:.75rem;color:#333;text-align:center}
.hint code{color:#d4a017;background:rgba(212,160,23,.1);padding:2px 8px;border-radius:4px}
.badges{display:flex;gap:8px;justify-content:center;margin-bottom:24px;flex-wrap:wrap}
.badge{font-size:.68rem;padding:4px 10px;border-radius:50px;font-weight:600}
.ok{background:rgba(34,197,94,.12);color:#22c55e;border:1px solid rgba(34,197,94,.3)}
.warn{background:rgba(245,158,11,.12);color:#f59e0b;border:1px solid rgba(245,158,11,.3)}
</style>
</head>
<body>
<div class="box">
  <div class="logo">Flash<span>Cut</span></div>
  <div class="sub">Admin dashboard — sign in to continue</div>
  <div class="badges">
    <span class="badge {% if db_mode == 'supabase' %}ok{% else %}warn{% endif %}">
      {% if db_mode == 'supabase' %}🟢 Supabase{% else %}🟡 SQLite (local){% endif %}
    </span>
    <span class="badge {% if ik_ok %}ok{% else %}warn{% endif %}">
      {% if ik_ok %}[CDN] ImageKit{% else %}[disk] Local uploads{% endif %}
    </span>
  </div>
  <form method="POST">
    <label>Username</label>
    <input type="text" name="username" autocomplete="username" required autofocus/>
    <label>Password</label>
    <input type="password" name="password" autocomplete="current-password" required/>
    <button type="submit">Sign In →</button>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
  </form>
  <div class="hint">Default: <code>flashcut123</code> / <code>43214321</code></div>
</div>
</body></html>"""


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    error = None
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '').strip()
        if u == ADMIN_USER and p == ADMIN_PASS:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        error = 'Invalid username or password.'
    return render_template_string(LOGIN_TEMPLATE, error=error,
                                  db_mode='supabase' if USE_SUPABASE else 'sqlite',
                                  ik_ok=USE_IMAGEKIT)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


# ══════════════════════════════════════════════════════════
#  ADMIN DASHBOARD TEMPLATE
# ══════════════════════════════════════════════════════════
ADMIN_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>FlashCut Admin</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#080808;--bg2:#0d0d0d;--card:#111;--border:rgba(212,160,23,.15);
  --gold:#d4a017;--gold2:#b8860b;--gdim:rgba(212,160,23,.08);--text:#f0f0f0;--muted:#777;--r:14px}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);display:flex;min-height:100vh;overflow-x:hidden}
.sb{width:230px;min-height:100vh;background:var(--card);border-right:1px solid var(--border);
  display:flex;flex-direction:column;position:fixed;top:0;left:0;z-index:100;box-shadow:4px 0 24px rgba(0,0,0,.4)}
.sb-logo{padding:26px 22px 20px;font-size:1.35rem;font-weight:800;border-bottom:1px solid var(--border);letter-spacing:-.5px}
.sb-logo span{color:var(--gold)}
.sb-tag{font-size:.62rem;color:var(--muted);font-weight:400;letter-spacing:.15em;text-transform:uppercase;display:block;margin-top:2px}
.sb-nav{display:flex;flex-direction:column;gap:3px;padding:14px 10px;flex:1}
.ni{display:flex;align-items:center;gap:11px;padding:10px 13px;border-radius:10px;text-decoration:none;
  color:var(--muted);font-size:.86rem;font-weight:500;transition:all .2s;cursor:pointer;border:none;background:none;width:100%;text-align:left}
.ni:hover{background:var(--gdim);color:var(--text)}
.ni.active{background:rgba(212,160,23,.12);color:var(--text);border-left:3px solid var(--gold);padding-left:10px}
.ni .ico{font-size:1rem;width:20px;text-align:center;flex-shrink:0}
.nb{margin-left:auto;background:var(--gold);color:#000;font-size:.6rem;font-weight:700;padding:2px 6px;border-radius:50px;min-width:18px;text-align:center}
.sb-foot{padding:12px 10px;border-top:1px solid var(--border)}
.main{margin-left:230px;flex:1;padding:28px 24px;min-width:0}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px;flex-wrap:wrap;gap:10px}
.topbar h1{font-size:1.4rem;font-weight:800;letter-spacing:-.5px}
.topbar h1 span{color:var(--gold)}
.tr{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.pill{font-size:.7rem;color:var(--muted);background:var(--card);border:1px solid var(--border);border-radius:50px;padding:4px 11px}
.pill.ok{color:#22c55e;border-color:rgba(34,197,94,.3);background:rgba(34,197,94,.07)}
.pill.warn{color:#f59e0b;border-color:rgba(245,158,11,.3);background:rgba(245,158,11,.07)}
.btn-lo{padding:7px 16px;background:rgba(212,160,23,.1);color:var(--gold);border:1px solid rgba(212,160,23,.3);
  border-radius:8px;text-decoration:none;font-size:.8rem;font-weight:600;transition:all .2s}
.btn-lo:hover{background:rgba(212,160,23,.2)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:28px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:20px 18px;text-align:center;transition:border-color .2s}
.stat:hover{border-color:rgba(212,160,23,.35)}
.stat .n{font-size:2rem;font-weight:800;line-height:1}
.stat .l{font-size:.7rem;color:var(--muted);margin-top:5px;text-transform:uppercase;letter-spacing:.09em}
.stat.g{border-color:rgba(212,160,23,.28);background:rgba(212,160,23,.04)}
.stat.g .n{color:var(--gold)}
.sec{display:none}.sec.active{display:block}
.sh{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:8px}
.sh h2{font-size:1.05rem;font-weight:700}
.sh h2 small{display:block;font-size:.68rem;color:var(--muted);font-weight:400;text-transform:uppercase;letter-spacing:.12em;margin-bottom:2px}
.tw{overflow-x:auto;border-radius:var(--r);border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;background:var(--bg2);min-width:480px}
th,td{padding:11px 13px;text-align:left;font-size:.8rem;border-bottom:1px solid var(--border)}
th{background:var(--card);color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-size:.68rem;font-weight:600}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:rgba(212,160,23,.02)}
.er td{color:var(--muted);font-size:.86rem;padding:28px;text-align:center}
.badge{display:inline-block;padding:2px 9px;border-radius:50px;font-size:.68rem;font-weight:700;text-transform:capitalize}
.badge.pending{background:rgba(245,158,11,.15);color:#f59e0b}
.badge.confirmed{background:rgba(34,197,94,.15);color:#22c55e}
.badge.cancelled{background:rgba(239,68,68,.15);color:#ef4444}
.btn{padding:6px 12px;border-radius:7px;font-size:.75rem;font-weight:600;cursor:pointer;border:none;
  transition:all .2s;display:inline-flex;align-items:center;gap:4px;text-decoration:none}
.bg{background:rgba(212,160,23,.12);color:var(--gold);border:1px solid rgba(212,160,23,.3)}
.bg:hover{background:rgba(212,160,23,.22)}
.bd{background:rgba(239,68,68,.1);color:#ef4444;border:1px solid rgba(239,68,68,.3)}
.bd:hover{background:rgba(239,68,68,.22)}
.bs{background:rgba(34,197,94,.1);color:#22c55e;border:1px solid rgba(34,197,94,.3)}
.bs:hover{background:rgba(34,197,94,.22)}
.bp{background:linear-gradient(135deg,var(--gold),var(--gold2));color:#000;padding:9px 20px;border-radius:10px;font-size:.86rem;font-weight:700;border:none}
.bp:hover{opacity:.9;transform:translateY(-1px)}
.fg{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}
.fv{display:flex;flex-direction:column;gap:5px}
.fv.full{grid-column:span 2}
.lbl{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;font-weight:600}
.inp{padding:9px 13px;background:var(--bg);border:1px solid rgba(255,255,255,.1);border-radius:9px;
  color:var(--text);font-size:.86rem;font-family:inherit;outline:none;transition:border-color .2s;width:100%}
.inp:focus{border-color:var(--gold);box-shadow:0 0 0 3px rgba(212,160,23,.1)}
textarea.inp{min-height:80px;resize:vertical}
select.inp option{background:var(--bg2)}
.cp{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:20px;margin-bottom:20px}
.cp h3{font-size:.86rem;font-weight:700;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border)}
.pcw{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px}
.pce{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:20px;position:relative}
.pce.pop{border-color:rgba(212,160,23,.4)}
.pce-lbl{font-size:.72rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:3px}
.pce-price{font-size:2.2rem;font-weight:800;line-height:1;margin-bottom:12px}
.pce-price small{font-size:.9rem;color:var(--gold)}
.pop-badge{position:absolute;top:-9px;left:50%;transform:translateX(-50%);background:var(--gold);color:#000;
  font-size:.6rem;font-weight:700;padding:2px 10px;border-radius:50px;letter-spacing:.07em;text-transform:uppercase;white-space:nowrap}
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;margin-bottom:20px}
.pi{border-radius:11px;overflow:hidden;position:relative;border:1px solid var(--border);aspect-ratio:16/9;cursor:pointer}
.pi video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.pi-ov{position:absolute;inset:0;background:rgba(0,0,0,.65);display:flex;flex-direction:column;
  justify-content:flex-end;padding:9px;opacity:0;transition:.2s}
.pi:hover .pi-ov{opacity:1}
.pi-title{font-size:.72rem;font-weight:600;margin-bottom:2px;color:#fff}
.pi-tag{font-size:.62rem;color:var(--gold);text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px}
.pa{display:flex;gap:4px}
.uz{border:2px dashed rgba(212,160,23,.3);border-radius:13px;padding:28px;text-align:center;
  cursor:pointer;transition:all .2s;background:var(--gdim)}
.uz:hover,.uz.dv{border-color:var(--gold);background:rgba(212,160,23,.1)}
.uz p{color:var(--muted);font-size:.84rem;margin-top:6px}
.storage-info{background:rgba(34,197,94,.06);border:1px solid rgba(34,197,94,.2);border-radius:10px;
  padding:12px 16px;font-size:.8rem;color:var(--muted);margin-bottom:16px}
.storage-info.warn{background:rgba(245,158,11,.06);border-color:rgba(245,158,11,.2)}
.storage-info strong{color:#22c55e}
.storage-info.warn strong{color:#f59e0b}
.mb{position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:999;display:none;
  align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(4px)}
.mb.open{display:flex}
.modal{background:var(--card);border:1px solid var(--border);border-radius:18px;
  padding:28px;width:100%;max-width:540px;max-height:90vh;overflow-y:auto;position:relative}
.modal h3{font-size:1.05rem;font-weight:700;margin-bottom:20px;display:flex;align-items:center;gap:7px}
.mc{position:absolute;top:14px;right:14px;background:rgba(255,255,255,.06);border:none;
  color:var(--text);width:32px;height:32px;border-radius:50%;cursor:pointer;font-size:1rem}
.mc:hover{background:rgba(255,255,255,.12)}
.toast{position:fixed;bottom:22px;right:22px;background:var(--card);border:1px solid var(--gold);
  color:var(--text);padding:11px 18px;border-radius:11px;font-size:.86rem;font-weight:500;
  z-index:9999;opacity:0;transform:translateY(8px);transition:all .3s;pointer-events:none}
.toast.show{opacity:1;transform:translateY(0)}
.toast.err{border-color:#ef4444}
.dr{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid var(--border);font-size:.84rem}
.dr:last-child{border-bottom:none}
.dl{color:var(--muted);min-width:100px;flex-shrink:0;text-transform:uppercase;letter-spacing:.07em;font-size:.68rem;padding-top:1px}
.dv{color:var(--text);word-break:break-word}
select.ss{background:var(--bg2);border:1px solid var(--border);color:var(--text);
  border-radius:6px;padding:4px 7px;font-size:.76rem;cursor:pointer;outline:none}
@media(max-width:800px){.sb{width:190px}.main{margin-left:190px;padding:16px 14px}}
@media(max-width:600px){.sb{transform:translateX(-100%)}.main{margin-left:0}}
</style>
</head>
<body>
<aside class="sb">
  <div class="sb-logo">Flash<span>Cut</span><small class="sb-tag">Admin Panel</small></div>
  <nav class="sb-nav">
    <button class="ni active" onclick="showSec('dashboard',this)"><span class="ico">📊</span> Dashboard</button>
    <button class="ni" onclick="showSec('bookings',this)"><span class="ico">📅</span> Bookings{% if cnt.pb %}<span class="nb">{{cnt.pb}}</span>{% endif %}</button>
    <button class="ni" onclick="showSec('contacts',this)"><span class="ico">✉️</span> Messages{% if cnt.c %}<span class="nb">{{cnt.c}}</span>{% endif %}</button>
    <button class="ni" onclick="showSec('reviews',this)"><span class="ico">⭐</span> Reviews{% if cnt.pr %}<span class="nb">{{cnt.pr}}</span>{% endif %}</button>
    <button class="ni" onclick="showSec('portfolio',this)"><span class="ico">🎬</span> Portfolio</button>
    <button class="ni" onclick="showSec('pricing',this)"><span class="ico">💰</span> Pricing</button>
    <button class="ni" onclick="showSec('newsletter',this)"><span class="ico">📧</span> Newsletter</button>
    <button class="ni" onclick="showSec('uploads',this)"><span class="ico">📁</span> Uploads</button>
    <button class="ni" onclick="showSec('settings',this)"><span class="ico">⚙️</span> Settings</button>
  </nav>
  <div class="sb-foot">
    <a href="/" target="_blank" class="ni" style="margin-bottom:5px"><span class="ico">🌐</span> View Site</a>
    <a href="/admin/logout" class="ni" style="color:#ef4444"><span class="ico">🚪</span> Logout</a>
  </div>
</aside>

<main class="main">
  <div class="topbar">
    <h1>Flash<span>Cut</span> <span style="font-size:.88rem;color:var(--muted);font-weight:400">Admin</span></h1>
    <div class="tr">
      <span class="pill {% if db_mode == 'supabase' %}ok{% else %}warn{% endif %}">
        {% if db_mode == 'supabase' %}🟢 Supabase{% else %}🟡 SQLite{% endif %}
      </span>
      <span class="pill {% if ik_ok %}ok{% else %}warn{% endif %}">
        {% if ik_ok %}[CDN] ImageKit{% else %}[disk] Local{% endif %}
      </span>
      <span class="pill">[U] {{admin_user}}</span>
      <a href="/admin/logout" class="btn-lo">Logout</a>
    </div>
  </div>

  <!-- DASHBOARD -->
  <div class="sec active" id="sec-dashboard">
    <div class="stats">
      <div class="stat g"><div class="n">{{cnt.b}}</div><div class="l">Bookings</div></div>
      <div class="stat g"><div class="n">{{cnt.pb}}</div><div class="l">Pending</div></div>
      <div class="stat"><div class="n">{{cnt.c}}</div><div class="l">Messages</div></div>
      <div class="stat"><div class="n">{{cnt.r}}</div><div class="l">Reviews</div></div>
      <div class="stat g"><div class="n">{{cnt.pr}}</div><div class="l">Pending Reviews</div></div>
      <div class="stat"><div class="n">{{cnt.n}}</div><div class="l">Subscribers</div></div>
    </div>
    <div class="cp">
      <h3>📅 Recent Bookings</h3>
      <div class="tw"><table>
        <thead><tr><th>Name</th><th>Package</th><th>Date</th><th>Status</th><th></th></tr></thead>
        <tbody>
        {% for b in recent_bookings %}
        <tr>
          <td><strong>{{b.name}}</strong><br><span style="color:var(--muted);font-size:.72rem">{{b.email}}</span></td>
          <td>{{b.package or '—'}}</td><td>{{b.shoot_date or '—'}}</td>
          <td><span class="badge {{b.status}}">{{b.status}}</span></td>
          <td><button class="btn bg" onclick="viewBooking({{b.id}})">View</button></td>
        </tr>
        {% else %}<tr class="er"><td colspan="5">No bookings yet</td></tr>{% endfor %}
        </tbody>
      </table></div>
    </div>
  </div>

  <!-- BOOKINGS -->
  <div class="sec" id="sec-bookings">
    <div class="sh"><h2><small>Management</small>All Bookings</h2></div>
    <div class="tw"><table>
      <thead><tr><th>Name</th><th>Phone</th><th>Shoot</th><th>Package</th><th>Date/Time</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>
      {% for b in bookings %}
      <tr id="brow-{{b.id}}">
        <td><strong>{{b.name}}</strong><br><span style="color:var(--muted);font-size:.72rem">{{b.email}}</span></td>
        <td>{{b.phone or '—'}}</td><td>{{b.shoot_type or '—'}}</td><td>{{b.package or '—'}}</td>
        <td>{{b.shoot_date or '—'}}<br><span style="color:var(--muted);font-size:.72rem">{{b.shoot_time or ''}}</span></td>
        <td><select class="ss" onchange="updateStatus({{b.id}},this.value)">
          <option value="pending"   {{'selected' if b.status=='pending'}}>Pending</option>
          <option value="confirmed" {{'selected' if b.status=='confirmed'}}>Confirmed</option>
          <option value="cancelled" {{'selected' if b.status=='cancelled'}}>Cancelled</option>
        </select></td>
        <td style="display:flex;gap:5px">
          <button class="btn bg" onclick="viewBooking({{b.id}})">View</button>
          <button class="btn bd" onclick="delBooking({{b.id}})">Del</button>
        </td>
      </tr>
      {% else %}<tr class="er"><td colspan="7">No bookings yet</td></tr>{% endfor %}
      </tbody>
    </table></div>
  </div>

  <!-- CONTACTS -->
  <div class="sec" id="sec-contacts">
    <div class="sh"><h2><small>Inbox</small>Messages</h2></div>
    <div class="tw"><table>
      <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Message</th><th>Date</th><th></th></tr></thead>
      <tbody>
      {% for c in contacts %}
      <tr id="crow-{{c.id}}">
        <td><strong>{{c.name}}</strong></td>
        <td><a href="mailto:{{c.email}}" style="color:var(--gold)">{{c.email}}</a></td>
        <td>{{c.phone or '—'}}</td>
        <td style="max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{c.message}}</td>
        <td style="white-space:nowrap;color:var(--muted);font-size:.72rem">{{(c.created_at or '')[:10]}}</td>
        <td style="display:flex;gap:5px">
          <button class="btn bg" onclick="viewContact('{{c.name|e}}','{{c.email|e}}','{{c.phone or ''|e}}','{{c.message|e}}','{{c.created_at or ''}}')">View</button>
          <button class="btn bd" onclick="delContact({{c.id}})">Del</button>
        </td>
      </tr>
      {% else %}<tr class="er"><td colspan="6">No messages yet</td></tr>{% endfor %}
      </tbody>
    </table></div>
  </div>

  <!-- REVIEWS -->
  <div class="sec" id="sec-reviews">
    <div class="sh"><h2><small>Moderation</small>Reviews</h2></div>
    <div class="tw"><table>
      <thead><tr><th>Name</th><th>Role</th><th>Rating</th><th>Review</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>
      {% for rv in reviews %}
      <tr id="rrow-{{rv.id}}">
        <td><strong>{{rv.name}}</strong></td>
        <td style="color:var(--muted);font-size:.78rem">{{rv.role or '—'}}</td>
        <td style="color:#f59e0b;letter-spacing:2px">{{ '★'*rv.rating }}</td>
        <td style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{rv.review}}</td>
        <td>{% if rv.approved %}<span class="badge confirmed">Approved</span>{% else %}<span class="badge pending">Pending</span>{% endif %}</td>
        <td style="display:flex;gap:5px">
          {% if not rv.approved %}<button class="btn bs" onclick="approveRev({{rv.id}})">Approve</button>{% endif %}
          <button class="btn bd" onclick="delRev({{rv.id}})">Del</button>
        </td>
      </tr>
      {% else %}<tr class="er"><td colspan="6">No reviews yet</td></tr>{% endfor %}
      </tbody>
    </table></div>
  </div>

  <!-- PORTFOLIO -->
  <div class="sec" id="sec-portfolio">
    <div class="sh"><h2><small>Media</small>Portfolio</h2>
      <button class="btn bp" onclick="openPortModal()">+ Add Item</button>
    </div>
    <div class="pgrid">
    {% for item in portfolio %}
      <div class="pi" id="pi-{{item.id}}" style="background:linear-gradient(135deg,{{item.thumb_color}})">
        {% if item.video_url %}
        {% set vurl = item.video_url if item.video_url.startswith('http') else '/' + item.video_url %}
        <video muted loop playsinline preload="metadata" src="{{vurl}}"
          onmouseenter="this.play()" onmouseleave="this.pause();this.currentTime=0"></video>
        {% endif %}
        <div class="pi-ov">
          <div class="pi-tag">{{item.tag or ''}}</div>
          <div class="pi-title">{{item.title}}</div>
          <div class="pa">
            <button class="btn bg" style="padding:3px 8px;font-size:.68rem"
              onclick="editPort({{item.id}},'{{item.title|e}}','{{item.tag or ''|e}}','{{item.video_url or ''|e}}','{{item.thumb_color|e}}',{{item.sort_order}})">Edit</button>
            <button class="btn bd" style="padding:3px 8px;font-size:.68rem" onclick="delPort({{item.id}})">Del</button>
          </div>
        </div>
      </div>
    {% else %}
      <div style="grid-column:span 4;text-align:center;color:var(--muted);padding:36px">No portfolio items yet</div>
    {% endfor %}
    </div>
  </div>

  <!-- PRICING -->
  <div class="sec" id="sec-pricing">
    <div class="sh"><h2><small>Plans</small>Pricing Editor</h2></div>
    <div class="pcw">
    {% for p in pricing %}
      <div class="pce {% if p.get('popular') %}pop{% endif %}">
        {% if p.get('popular') %}<div class="pop-badge">Most Popular</div>{% endif %}
        {% if p.get('label') %}
        <div style="font-size:.65rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:var(--gold);margin-bottom:8px">{{p.label}}</div>
        {% endif %}
        <div class="pce-lbl">{{p.name}}</div>
        <p style="font-size:.78rem;color:var(--muted);margin-bottom:14px;line-height:1.5">{{p.description or ''}}</p>
        <div class="pce-price"><small>₹</small>{{"{:,}".format(p.price | int)}}
          <span style="font-size:.78rem;color:var(--muted);font-weight:400"> + GST · {{p.cycle or 'per shoot'}}</span>
        </div>
        {% if p.get('features') %}
        <div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:14px 0 8px">What's Included</div>
        <div style="font-size:.78rem;color:var(--muted);line-height:1.8">
          {% for ft in p.features.split('|') %}
          <div style="display:flex;align-items:flex-start;gap:8px">
            <span style="color:var(--gold);flex-shrink:0;margin-top:1px">✓</span>{{ft.strip()}}
          </div>
          {% endfor %}
        </div>
        {% endif %}
        <div style="margin-top:12px;font-size:.72rem">
          Status: <strong style="color:{% if p.is_active %}#22c55e{% else %}#ef4444{% endif %}">
            {% if p.is_active %}Active{% else %}Inactive{% endif %}
          </strong>
        </div>
        <button class="btn bg" style="width:100%;margin-top:14px"
          onclick="editPricing({{p.id}},'{{p.name|e}}','{{(p.label or '')|e}}',{{p.price | int}},'{{(p.cycle or 'per shoot')|e}}','{{(p.currency or 'INR')|e}}','{{(p.description or '')|e}}','{{(p.features or '')|e}}',{{p.is_active|lower}},{{(p.popular or false)|lower}})">
          ✏️ Edit Plan
        </button>
      </div>
    {% endfor %}
    </div>
  </div>

  <!-- NEWSLETTER -->
  <div class="sec" id="sec-newsletter">
    <div class="sh"><h2><small>Subscribers</small>Newsletter</h2></div>
    <div class="tw"><table>
      <thead><tr><th>Email</th><th>Subscribed</th><th></th></tr></thead>
      <tbody>
      {% for nl in newsletter %}
      <tr id="nrow-{{nl.id}}">
        <td><a href="mailto:{{nl.email}}" style="color:var(--gold)">{{nl.email}}</a></td>
        <td style="color:var(--muted);font-size:.78rem">{{(nl.created_at or '')[:10]}}</td>
        <td><button class="btn bd" onclick="delNL({{nl.id}})">Remove</button></td>
      </tr>
      {% else %}<tr class="er"><td colspan="3">No subscribers yet</td></tr>{% endfor %}
      </tbody>
    </table></div>
  </div>

  <!-- UPLOADS -->
  <div class="sec" id="sec-uploads">
    <div class="sh"><h2><small>Media Library</small>Upload Files</h2></div>
    <div class="storage-info {% if not ik_ok %}warn{% endif %}">
      {% if ik_ok %}
        <strong>[CDN] ImageKit connected</strong> — files are uploaded to the ImageKit CDN and served globally.
      {% else %}
        <strong>[WARN] ImageKit not configured</strong> — files save locally (lost on Render restart).
        Set <code>IMAGEKIT_PUBLIC_KEY</code>, <code>IMAGEKIT_PRIVATE_KEY</code>, <code>IMAGEKIT_URL_ENDPOINT</code>.
      {% endif %}
      &nbsp;&nbsp;|&nbsp;&nbsp;
      {% if db_mode == 'supabase' %}
        <strong style="color:#22c55e">🟢 Supabase DB</strong>
      {% else %}
        <strong style="color:#f59e0b">🟡 SQLite (local dev)</strong>
      {% endif %}
    </div>
    <div class="uz" id="uz" onclick="document.getElementById('fi').click()"
         ondragover="event.preventDefault();this.classList.add('dv')"
         ondragleave="this.classList.remove('dv')" ondrop="handleDrop(event)">
      <div style="font-size:2rem;margin-bottom:4px">📁</div>
      <strong>Click to upload or drag &amp; drop</strong>
      <p>MP4, MOV, WEBM, JPG, PNG, GIF — max 500 MB</p>
      <input type="file" id="fi" style="display:none" accept="video/*,image/*" onchange="uploadFile(this.files[0])"/>
    </div>
    <div id="upProg" style="display:none;margin-top:14px">
      <div style="background:rgba(255,255,255,.08);border-radius:6px;height:5px;overflow:hidden">
        <div id="upBar" style="height:100%;background:linear-gradient(90deg,var(--gold),var(--gold2));width:0%;transition:width .3s"></div>
      </div>
      <p id="upStat" style="font-size:.78rem;color:var(--muted);margin-top:6px;text-align:center"></p>
    </div>
    <div id="upRes" style="margin-top:14px"></div>
  </div>

  <!-- SETTINGS -->
  <div class="sec" id="sec-settings">
    <div class="sh"><h2><small>Site Configuration</small>Contact Details</h2></div>
    <div class="cp">
      <h3>📞 Contact Information</h3>
      <p style="font-size:.78rem;color:var(--muted);margin-bottom:18px">
        These details appear on the Contact page and footer. Changes save instantly.
      </p>
      <div class="fg">
        <div class="fv"><label class="lbl">Email</label>
          <input class="inp" id="s-email" type="email" placeholder="hello@flashcut.com"/></div>
        <div class="fv"><label class="lbl">Phone</label>
          <input class="inp" id="s-phone" type="text" placeholder="+91 98765 43210"/></div>
        <div class="fv"><label class="lbl">WhatsApp Number</label>
          <input class="inp" id="s-whatsapp" type="text" placeholder="+91 98765 43210"/></div>
        <div class="fv"><label class="lbl">Instagram URL</label>
          <input class="inp" id="s-instagram" type="text" placeholder="https://instagram.com/..."/></div>
        <div class="fv full"><label class="lbl">Office Address</label>
          <input class="inp" id="s-address" type="text" placeholder="42 MG Road, Bengaluru, KA 560001"/></div>
      </div>
      <button class="btn bp" style="min-width:180px" onclick="saveSettings()">[disk] Save Settings</button>
      <span id="settingsSaveMsg" style="margin-left:12px;font-size:.8rem;color:#22c55e;display:none">[OK] Saved!</span>
    </div>

    <div class="cp" style="margin-top:20px">
      <h3>🎨 Brand Settings</h3>
      <div class="fg">
        <div class="fv"><label class="lbl">Site Title</label>
          <input class="inp" id="s-title" type="text" placeholder="FlashCut — Shoot. Edit. Deliver."/></div>
        <div class="fv"><label class="lbl">Tagline</label>
          <input class="inp" id="s-tagline" type="text" placeholder="In 10 Minutes."/></div>
        <div class="fv full"><label class="lbl">Meta Description</label>
          <input class="inp" id="s-meta" type="text" placeholder="Professional video production with editing delivered in 10 minutes."/></div>
      </div>
      <button class="btn bp" style="min-width:180px" onclick="saveBrandSettings()">[disk] Save Brand</button>
      <span id="brandSaveMsg" style="margin-left:12px;font-size:.8rem;color:#22c55e;display:none">[OK] Saved!</span>
    </div>
  </div>

</main>

<!-- MODALS -->
<div class="mb" id="mBooking"><div class="modal">
  <button class="mc" onclick="closeM('mBooking')">×</button>
  <h3>📅 Booking Details</h3><div id="mBookingBody"></div>
</div></div>

<div class="mb" id="mContact"><div class="modal">
  <button class="mc" onclick="closeM('mContact')">×</button>
  <h3>✉️ Message</h3><div id="mContactBody"></div>
</div></div>

<div class="mb" id="mPricing"><div class="modal">
  <button class="mc" onclick="closeM('mPricing')">×</button>
  <h3>💰 Edit Plan</h3>
  <input type="hidden" id="ePid"/>
  <div class="fg">
    <div class="fv"><label class="lbl">Plan Name</label>
      <input class="inp" id="ePname" type="text" placeholder="Quick Shoot"/></div>
    <div class="fv"><label class="lbl">Label (eyebrow)</label>
      <input class="inp" id="eLabel" type="text" placeholder="For a Single Reel"/></div>
    <div class="fv"><label class="lbl">Price (₹)</label>
      <input class="inp" id="ePrice" type="number"/></div>
    <div class="fv"><label class="lbl">Cycle</label>
      <input class="inp" id="eCycle" type="text" placeholder="per shoot"/></div>
    <div class="fv"><label class="lbl">Currency</label>
      <input class="inp" id="eCurrency" type="text" value="INR"/></div>
    <div class="fv"><label class="lbl">Popular</label>
      <select class="inp" id="ePop">
        <option value="false">No</option>
        <option value="true">Yes — Most Popular</option>
      </select></div>
    <div class="fv full"><label class="lbl">Description</label>
      <input class="inp" id="eDesc" type="text" placeholder="Short description of this plan"/></div>
    <div class="fv full"><label class="lbl">Features (pipe-separated  |)</label>
      <textarea class="inp" id="eFeat" rows="5" placeholder="1-hour shoot session|1 edited reel|Quick delivery"></textarea></div>
    <div class="fv full"><label class="lbl">Active</label>
      <select class="inp" id="eActive">
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select></div>
  </div>
  <button class="btn bp" style="width:100%" onclick="savePricing()">Save Changes</button>
</div></div>

<div class="mb" id="mPort"><div class="modal">
  <button class="mc" onclick="closeM('mPort')">×</button>
  <h3>🎬 <span id="mPortTitle">Add Portfolio Item</span></h3>
  <input type="hidden" id="ePortId"/>
  <div class="fg">
    <div class="fv full"><label class="lbl">Title</label><input class="inp" id="ePortTitle" type="text"/></div>
    <div class="fv"><label class="lbl">Tag</label><input class="inp" id="ePortTag" type="text"/></div>
    <div class="fv"><label class="lbl">Sort Order</label><input class="inp" id="ePortOrd" type="number" value="99"/></div>
    <div class="fv full"><label class="lbl">Video URL (ImageKit or local)</label>
      <input class="inp" id="ePortVid" type="text" placeholder="https://ik.imagekit.io/... or uploads/video.mp4"/></div>
    <div class="fv full"><label class="lbl">Gradient (2 hex colors, comma-separated)</label>
      <input class="inp" id="ePortCol" type="text" placeholder="#d4a017,#3a2c00"/></div>
  </div>
  <button class="btn bp" style="width:100%" onclick="savePort()">Save</button>
</div></div>

<div class="toast" id="toast"></div>

<script>
const BOOKINGS = {{ bookings_json | safe }};
function showSec(id,el){
  document.querySelectorAll('.sec').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.ni').forEach(n=>n.classList.remove('active'));
  document.getElementById('sec-'+id).classList.add('active');
  if(el) el.classList.add('active');
}
function toast(msg,err=false){
  const t=document.getElementById('toast');
  t.textContent=msg;t.className='toast show'+(err?' err':'');
  setTimeout(()=>t.className='toast',3200);
}
function openM(id){document.getElementById(id).classList.add('open');}
function closeM(id){document.getElementById(id).classList.remove('open');}
document.querySelectorAll('.mb').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)m.classList.remove('open');}));
function viewBooking(id){
  const b=BOOKINGS.find(x=>x.id===id);if(!b)return;
  const rows=[['Name',b.name],['Email',b.email],['Phone',b.phone||'—'],
    ['Shoot',b.shoot_type||'—'],['Package',b.package||'—'],
    ['Date',b.shoot_date||'—'],['Time',b.shoot_time||'—'],
    ['Location',b.location||'—'],['Notes',b.notes||'—'],
    ['Status',b.status],['Created',(b.created_at||'').slice(0,19)]];
  document.getElementById('mBookingBody').innerHTML=
    rows.map(([l,v])=>`<div class="dr"><span class="dl">${l}</span><span class="dv">${v}</span></div>`).join('');
  openM('mBooking');
}
function viewContact(name,email,phone,msg,created){
  const rows=[['Name',name],['Email',email],['Phone',phone||'—'],['Message',msg],['Date',created]];
  document.getElementById('mContactBody').innerHTML=
    rows.map(([l,v])=>`<div class="dr"><span class="dl">${l}</span><span class="dv">${v}</span></div>`).join('');
  openM('mContact');
}
async function updateStatus(id,status){
  const d=await(await fetch('/api/admin/booking/'+id+'/status',{method:'PATCH',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({status})})).json();
  d.ok?toast('Status → '+status):toast(d.error,true);
}
async function delBooking(id){if(!confirm('Delete?'))return;
  const d=await(await fetch('/api/admin/booking/'+id,{method:'DELETE'})).json();
  if(d.ok){document.getElementById('brow-'+id)?.remove();toast('Deleted');}else toast('Error',true);}
async function delContact(id){if(!confirm('Delete?'))return;
  const d=await(await fetch('/api/admin/contact/'+id,{method:'DELETE'})).json();
  if(d.ok){document.getElementById('crow-'+id)?.remove();toast('Deleted');}else toast('Error',true);}
async function approveRev(id){
  const d=await(await fetch('/api/admin/review/'+id+'/approve',{method:'PATCH'})).json();
  if(d.ok)location.reload();else toast('Error',true);}
async function delRev(id){if(!confirm('Delete?'))return;
  const d=await(await fetch('/api/admin/review/'+id,{method:'DELETE'})).json();
  if(d.ok){document.getElementById('rrow-'+id)?.remove();toast('Deleted');}else toast('Error',true);}
async function delNL(id){if(!confirm('Remove?'))return;
  const d=await(await fetch('/api/admin/newsletter/'+id,{method:'DELETE'})).json();
  if(d.ok){document.getElementById('nrow-'+id)?.remove();toast('Removed');}else toast('Error',true);}
function editPricing(id,name,label,price,cycle,currency,desc,features,active,popular){
  document.getElementById('ePid').value=id;
  document.getElementById('ePname').value=name;
  document.getElementById('eLabel').value=label||'';
  document.getElementById('ePrice').value=price;
  document.getElementById('eCycle').value=cycle||'per shoot';
  document.getElementById('eCurrency').value=currency||'INR';
  document.getElementById('eDesc').value=desc||'';
  document.getElementById('eFeat').value=features||'';
  document.getElementById('eActive').value=active?'true':'false';
  document.getElementById('ePop').value=popular?'true':'false';
  openM('mPricing');
}
async function savePricing(){
  const id=document.getElementById('ePid').value;
  const data={
    name:        document.getElementById('ePname').value,
    label:       document.getElementById('eLabel').value,
    price:       parseInt(document.getElementById('ePrice').value),
    cycle:       document.getElementById('eCycle').value||'per shoot',
    currency:    document.getElementById('eCurrency').value||'INR',
    description: document.getElementById('eDesc').value,
    features:    document.getElementById('eFeat').value,
    is_active:   document.getElementById('eActive').value==='true',
    popular:     document.getElementById('ePop').value==='true',
  };
  const d=await(await fetch('/api/admin/pricing/'+id,{method:'PATCH',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})).json();
  if(d.ok){toast('Saved!');closeM('mPricing');setTimeout(()=>location.reload(),600);}
  else toast('Error: '+(d.error||'unknown'),true);
}
function openPortModal(){
  document.getElementById('ePortId').value='';
  document.getElementById('mPortTitle').textContent='Add Portfolio Item';
  ['ePortTitle','ePortTag','ePortVid','ePortCol'].forEach(x=>document.getElementById(x).value='');
  document.getElementById('ePortOrd').value=99;openM('mPort');}
function editPort(id,title,tag,vid,col,ord){
  document.getElementById('ePortId').value=id;
  document.getElementById('mPortTitle').textContent='Edit Item';
  document.getElementById('ePortTitle').value=title;document.getElementById('ePortTag').value=tag;
  document.getElementById('ePortVid').value=vid;document.getElementById('ePortCol').value=col;
  document.getElementById('ePortOrd').value=ord;openM('mPort');}
async function savePort(){
  const id=document.getElementById('ePortId').value;
  const data={title:document.getElementById('ePortTitle').value,
    tag:document.getElementById('ePortTag').value,
    video_url:document.getElementById('ePortVid').value,
    thumb_color:document.getElementById('ePortCol').value,
    sort_order:parseInt(document.getElementById('ePortOrd').value)||99};
  const url=id?'/api/admin/portfolio/'+id:'/api/admin/portfolio';
  const method=id?'PATCH':'POST';
  const d=await(await fetch(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})).json();
  if(d.ok){toast(id?'Updated!':'Added!');closeM('mPort');setTimeout(()=>location.reload(),500);}
  else toast('Error: '+d.error,true);}
async function delPort(id){if(!confirm('Delete?'))return;
  const d=await(await fetch('/api/admin/portfolio/'+id,{method:'DELETE'})).json();
  if(d.ok){document.getElementById('pi-'+id)?.remove();toast('Deleted');}else toast('Error',true);}
// ── Settings ─────────────────────────────────────────────
async function loadSettings(){
  try{
    const d=await(await fetch('/api/admin/settings')).json();
    if(d.settings){
      const s=d.settings;
      if(s.contact_email)   document.getElementById('s-email').value=s.contact_email;
      if(s.contact_phone)   document.getElementById('s-phone').value=s.contact_phone;
      if(s.whatsapp)        document.getElementById('s-whatsapp').value=s.whatsapp;
      if(s.instagram)       document.getElementById('s-instagram').value=s.instagram;
      if(s.contact_address) document.getElementById('s-address').value=s.contact_address;
      if(s.site_title)      document.getElementById('s-title').value=s.site_title;
      if(s.tagline)         document.getElementById('s-tagline').value=s.tagline;
      if(s.meta_description)document.getElementById('s-meta').value=s.meta_description;
    }
  }catch(e){console.warn('Settings load failed',e);}
}
async function saveSettings(){
  const data={
    contact_email:   document.getElementById('s-email').value,
    contact_phone:   document.getElementById('s-phone').value,
    whatsapp:        document.getElementById('s-whatsapp').value,
    instagram:       document.getElementById('s-instagram').value,
    contact_address: document.getElementById('s-address').value,
  };
  const d=await(await fetch('/api/admin/settings',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})).json();
  const msg=document.getElementById('settingsSaveMsg');
  if(d.ok){msg.style.display='inline';toast('Contact details saved!');setTimeout(()=>msg.style.display='none',3000);}
  else toast('Error: '+(d.error||'unknown'),true);
}
async function saveBrandSettings(){
  const data={
    site_title:       document.getElementById('s-title').value,
    tagline:          document.getElementById('s-tagline').value,
    meta_description: document.getElementById('s-meta').value,
  };
  const d=await(await fetch('/api/admin/settings',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})).json();
  const msg=document.getElementById('brandSaveMsg');
  if(d.ok){msg.style.display='inline';toast('Brand settings saved!');setTimeout(()=>msg.style.display='none',3000);}
  else toast('Error: '+(d.error||'unknown'),true);
}
// Load settings when Settings tab is opened
document.querySelector('[onclick*="settings"]')?.addEventListener('click',loadSettings);

function handleDrop(e){
  e.preventDefault();document.getElementById('uz').classList.remove('dv');
  uploadFile(e.dataTransfer.files[0]);}
async function uploadFile(file){
  if(!file)return;
  const prog=document.getElementById('upProg'),bar=document.getElementById('upBar'),
        stat=document.getElementById('upStat'),res=document.getElementById('upRes');
  prog.style.display='block';bar.style.width='15%';
  stat.textContent='Uploading '+file.name+'…';res.innerHTML='';
  const fd=new FormData();fd.append('file',file);
  try{
    bar.style.width='55%';
    const d=await(await fetch('/api/admin/upload',{method:'POST',body:fd})).json();
    bar.style.width='100%';
    if(d.ok){
      stat.textContent='[OK] Uploaded via '+d.storage+'!';
      const isVid=/[.](mp4|mov|webm|avi|mkv)$/i.test(d.filename);
      res.innerHTML=`<div style="background:var(--bg2);border:1px solid var(--border);border-radius:11px;padding:14px;margin-top:8px">
        <p style="font-size:.78rem;color:var(--muted);margin-bottom:6px">
          Storage: <strong style="color:var(--gold)">${d.storage==='imagekit'?'[CDN] ImageKit CDN':'[disk] Local'}</strong>
        </p>
        <code style="background:rgba(212,160,23,.1);color:var(--gold);padding:5px 10px;border-radius:5px;font-size:.78rem;display:block;word-break:break-all">${d.url}</code>
        <button class="btn bg" style="margin-top:8px" onclick="navigator.clipboard.writeText('${d.url}');toast('Copied!')">📋 Copy URL</button>
        ${isVid?`<video src="${d.url}" controls style="width:100%;border-radius:8px;margin-top:10px;max-height:180px"></video>`
               :`<img src="${d.url}" style="width:100%;border-radius:8px;margin-top:10px;max-height:180px;object-fit:contain">`}
      </div>`;toast('Uploaded!');
    }else{stat.textContent='❌ '+d.error;toast(d.error,true);}
  }catch{stat.textContent='❌ Upload failed';toast('Upload failed',true);}
  setTimeout(()=>{prog.style.display='none';bar.style.width='0%';},2200);}
</script>
</body></html>"""


# ══════════════════════════════════════════════════════════
#  ADMIN DASHBOARD ROUTE
# ══════════════════════════════════════════════════════════
@app.route('/admin')
@app.route('/admin/')
@login_required
def admin():
    bookings   = db_select('bookings',   order=('created_at', True))
    contacts   = db_select('contacts',   order=('created_at', True))
    reviews    = db_select('reviews',    order=('created_at', True))
    portfolio  = db_select('portfolio',  order='sort_order')
    pricing    = db_select('pricing')          # no sort_order column in Supabase
    newsletter = db_select('newsletter', order=('created_at', True))

    cnt = {
        'b':  len(bookings),
        'pb': sum(1 for b in bookings if b.get('status') == 'pending'),
        'c':  len(contacts),
        'r':  len(reviews),
        'pr': sum(1 for r in reviews if not r.get('approved')),
        'n':  len(newsletter),
    }

    return render_template_string(
        ADMIN_TEMPLATE,
        bookings        = bookings,
        contacts        = contacts,
        reviews         = reviews,
        portfolio       = portfolio,
        pricing         = pricing,
        newsletter      = newsletter,
        cnt             = cnt,
        recent_bookings = bookings[:5],
        admin_user      = ADMIN_USER,
        bookings_json   = json.dumps(bookings),
        db_mode         = 'supabase' if USE_SUPABASE else 'sqlite',
        ik_ok           = USE_IMAGEKIT,
    )


# ══════════════════════════════════════════════════════════
#  GLOBAL ERROR HANDLER — always return JSON, never HTML
# ══════════════════════════════════════════════════════════
@app.errorhandler(Exception)
def handle_exception(e):
    """Return JSON for all unhandled exceptions instead of HTML."""
    import traceback
    return jsonify({
        'ok':    False,
        'error': str(e),
        'type':  type(e).__name__,
    }), 500


# ══════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    if not USE_SUPABASE:
        init_sqlite()
    print('━' * 56)
    print('[*]  FlashCut  →  http://localhost:5000')
    print('[#]  Admin      →  http://localhost:5000/admin')
    print(f'[U]  Login       →  {ADMIN_USER} / {ADMIN_PASS}')
    print(f'[DB]  Database    →  {"Supabase" if USE_SUPABASE else "SQLite (local)"}')
    print(f'{"[CDN] " if USE_IMAGEKIT else "[disk] "} Storage     →  {"ImageKit CDN" if USE_IMAGEKIT else "Local uploads"}')
    print('━' * 56)
    app.run(debug=True, port=5000)
