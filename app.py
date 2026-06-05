from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os, uuid
from datetime import datetime
import cloudinary
import cloudinary.uploader
import pymysql
import pymysql.cursors
from dbutils.pooled_db import PooledDB
from dotenv import load_dotenv
load_dotenv()

print("DB_HOST =", os.environ.get('DB_HOST', 'NOT SET'))

app = Flask(__name__, static_folder='static')
CORS(app)

# ── Cloudinary ────────────────────────────────────────────────────
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

# ── Connection Pool ───────────────────────────────────────────────
# Opens 3 connections at startup and reuses them for every request.
# This eliminates the per-request connection overhead that was causing
# slow updates.
pool = PooledDB(
    creator=pymysql,
    mincached=3,       # keep 3 connections open at all times
    maxcached=10,      # pool up to 10 idle connections
    maxconnections=20, # never exceed 20 total
    blocking=True,     # wait for a free connection instead of crashing
    host=os.environ.get('DB_HOST', 'localhost'),
    port=int(os.environ.get('DB_PORT', 3306)),
    user=os.environ.get('DB_USER', 'root'),
    password=os.environ.get('DB_PASSWORD', ''),
    db=os.environ.get('DB_NAME', 'joi_products'),
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True,
)

def get_db():
    """Get a connection from the pool (auto-returned on .close())."""
    return pool.connection()

# ── DB Init ───────────────────────────────────────────────────────
def init_db():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id          VARCHAR(8)    NOT NULL PRIMARY KEY,
                    name        VARCHAR(120)  NOT NULL,
                    cat         VARCHAR(80)   NOT NULL,
                    price       DECIMAL(10,2) NOT NULL DEFAULT 0,
                    tag         VARCHAR(60)   DEFAULT '',
                    description TEXT,
                    img         TEXT,
                    active      TINYINT(1)    NOT NULL DEFAULT 1,
                    stock       INT           NOT NULL DEFAULT 0,
                    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.execute("SELECT COUNT(*) AS cnt FROM products")
            if cur.fetchone()['cnt'] == 0:
                defaults = [
                    ('p0000001', 'Velvet Noir Serum',    'Serums',      148, 'Bestseller',  'A midnight-dark elixir that revives and illuminates dull skin overnight.',       'https://images.pexels.com/photos/5632386/pexels-photo-5632386.jpeg?auto=compress&cs=tinysrgb&w=600', 1, 42),
                    ('p0000002', 'Gold Radiance Cream',  'Moisturizers',195, 'New',         'Infused with 24k gold particles for a luminous, sculpted complexion.',           'https://images.pexels.com/photos/6621462/pexels-photo-6621462.jpeg?auto=compress&cs=tinysrgb&w=600', 1, 28),
                    ('p0000003', 'Obsidian Eye Elixir',  'Eye Care',    112, 'Award Winner','Deep-repairing formula that erases dark circles and fine lines.',                'https://images.pexels.com/photos/4762440/pexels-photo-4762440.jpeg?auto=compress&cs=tinysrgb&w=600', 1, 15),
                    ('p0000004', 'Charles Lip Nectar',   'Lip Care',     68, 'Fan Favorite','Plumping lip treatment with a mirror-like finish and rich hydration.',           'https://images.pexels.com/photos/3997989/pexels-photo-3997989.jpeg?auto=compress&cs=tinysrgb&w=600', 1, 60),
                    ('p0000005', 'Navy Mist Toner',      'Toners',       85, 'Vegan',       'Balancing botanical mist that preps skin for effortless absorption.',            'https://images.pexels.com/photos/6424249/pexels-photo-6424249.jpeg?auto=compress&cs=tinysrgb&w=600', 1, 33),
                    ('p0000006', 'Imperial Body Oil',    'Body',        135, 'Luxury',      'A silky dry oil blend of rose hip, argan and jasmine for goddess skin.',         'https://images.pexels.com/photos/4041391/pexels-photo-4041391.jpeg?auto=compress&cs=tinysrgb&w=600', 1, 20),
                ]
                cur.executemany("""
                    INSERT INTO products (id,name,cat,price,tag,description,img,active,stock)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, defaults)
    finally:
        conn.close()

# ── Helpers ───────────────────────────────────────────────────────
def row_to_dict(row):
    return {
        'id':         row['id'],
        'name':       row['name'],
        'cat':        row['cat'],
        'price':      float(row['price']),
        'tag':        row['tag'] or '',
        'desc':       row['description'] or '',
        'img':        row['img'] or '',
        'active':     bool(row['active']),
        'stock':      row['stock'],
        'created_at': row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at']),
        'updated_at': row['updated_at'].isoformat() if hasattr(row['updated_at'], 'isoformat') else str(row['updated_at']),
    }

def ok(data, status=200):
    return jsonify({'success': True, 'data': data}), status

def err(message, status=400):
    return jsonify({'success': False, 'error': message}), status

# ── Validation ────────────────────────────────────────────────────
def validate_product(data, require_all=True):
    errors = []
    if require_all:
        for field in ['name', 'cat']:
            if not data.get(field):
                errors.append(f'"{field}" is required')
    if 'name' in data:
        name = str(data['name']).strip()
        if len(name) < 2:   errors.append('"name" must be at least 2 characters')
        if len(name) > 120: errors.append('"name" must be under 120 characters')
        data['name'] = name
    if 'price' in data:
        try:
            price = float(data['price'])
            if price < 0:       errors.append('"price" cannot be negative')
            if price > 100_000: errors.append('"price" seems unrealistically high')
            data['price'] = round(price, 2)
        except (TypeError, ValueError):
            errors.append('"price" must be a number')
    if 'stock' in data:
        try:
            stock = int(data['stock'])
            if stock < 0: errors.append('"stock" cannot be negative')
            data['stock'] = stock
        except (TypeError, ValueError):
            errors.append('"stock" must be an integer')
    if 'img' in data and data['img']:
        img = str(data['img']).strip()
        if not img.startswith(('http://', 'https://', '/')):
            errors.append('"img" must be a valid URL or path')
        data['img'] = img
    if errors:
        return None, '; '.join(errors)
    return data, None

# ── Routes ────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return err('No file provided')
    file = request.files['file']
    if not file.filename:
        return err('Empty filename')
    try:
        result = cloudinary.uploader.upload(
            file,
            folder='joi-products',
            transformation=[{'width': 800, 'crop': 'limit', 'quality': 'auto', 'fetch_format': 'auto'}]
        )
        return ok({'url': result['secure_url'], 'public_id': result['public_id']})
    except Exception as e:
        return err(f'Upload failed: {str(e)}')

@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            clauses, params = [], []

            active_param = request.args.get('active')
            if active_param is not None:
                clauses.append('active = %s')
                params.append(1 if active_param.lower() == 'true' else 0)

            cat = request.args.get('cat', '').strip()
            if cat:
                clauses.append('cat = %s')
                params.append(cat)

            try:
                min_price = float(request.args.get('min_price', 0))
                max_price = float(request.args.get('max_price', 9999999))
                clauses.append('price BETWEEN %s AND %s')
                params += [min_price, max_price]
            except ValueError:
                return err('min_price and max_price must be numbers')

            q = request.args.get('q', '').strip()
            if q:
                clauses.append('(name LIKE %s OR cat LIKE %s OR description LIKE %s OR tag LIKE %s)')
                like = f'%{q}%'
                params += [like, like, like, like]

            where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''

            cur.execute(f'SELECT COUNT(*) AS cnt FROM products {where}', params)
            total = cur.fetchone()['cnt']

            sort_map = {'price':'price','name':'name','created_at':'created_at','stock':'stock'}
            sf = sort_map.get(request.args.get('sort', 'created_at'), 'created_at')
            so = 'DESC' if request.args.get('order', 'asc').lower() == 'desc' else 'ASC'

            try:
                page  = max(1, int(request.args.get('page', 1)))
                limit = min(100, max(1, int(request.args.get('limit', total or 1))))
            except ValueError:
                return err('page and limit must be integers')

            offset = (page - 1) * limit
            cur.execute(
                f'SELECT * FROM products {where} ORDER BY {sf} {so} LIMIT %s OFFSET %s',
                params + [limit, offset]
            )
            rows  = [row_to_dict(r) for r in cur.fetchall()]
            pages = max(1, -(-total // limit)) if limit else 1

        return jsonify({
            'success': True, 'data': rows,
            'meta': {
                'total': total, 'page': page, 'limit': limit,
                'pages': pages,
                'has_next': offset + limit < total,
                'has_prev': page > 1,
            }
        })
    finally:
        conn.close()

@app.route('/api/products/<product_id>', methods=['GET'])
def get_product(product_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM products WHERE id = %s', (product_id,))
            row = cur.fetchone()
        return ok(row_to_dict(row)) if row else err('Product not found', 404)
    finally:
        conn.close()

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json
    if not data: return err('Request body must be JSON')
    data, error = validate_product(data, require_all=True)
    if error: return err(error)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM products WHERE LOWER(name) = LOWER(%s)', (data['name'],))
            if cur.fetchone():
                return err(f'A product named "{data["name"]}" already exists', 409)
            new_id = str(uuid.uuid4())[:8]
            cur.execute("""
                INSERT INTO products (id, name, cat, price, tag, description, img, active, stock)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                new_id,
                data.get('name', ''),
                str(data.get('cat', '')).strip(),
                data.get('price', 0),
                str(data.get('tag', '')).strip(),
                str(data.get('desc', '')).strip(),
                data.get('img', ''),
                int(bool(data.get('active', True))),
                int(data.get('stock', 0)),
            ))
            cur.execute('SELECT * FROM products WHERE id = %s', (new_id,))
            new_product = row_to_dict(cur.fetchone())
        return ok(new_product, 201)
    finally:
        conn.close()

@app.route('/api/products/<product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.json
    if not data: return err('Request body must be JSON')
    data, error = validate_product(data, require_all=False)
    if error: return err(error)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Single query: fetch + duplicate-check + update + re-fetch
            # all on the same already-open pooled connection = fast
            cur.execute('SELECT * FROM products WHERE id = %s', (product_id,))
            existing = cur.fetchone()
            if not existing:
                return err('Product not found', 404)

            new_name = data.get('name', existing['name'])
            cur.execute(
                'SELECT id FROM products WHERE LOWER(name) = LOWER(%s) AND id != %s',
                (new_name, product_id)
            )
            if cur.fetchone():
                return err(f'Another product named "{new_name}" already exists', 409)

            sets, vals = [], []
            for key, col in [('name','name'),('cat','cat'),('price','price'),('tag','tag'),
                              ('desc','description'),('img','img'),('active','active'),('stock','stock')]:
                if key in data:
                    sets.append(f'{col} = %s')
                    val = data[key]
                    if key == 'active': val = int(bool(val))
                    vals.append(val)

            if sets:
                vals.append(product_id)
                cur.execute(f'UPDATE products SET {", ".join(sets)} WHERE id = %s', vals)

            cur.execute('SELECT * FROM products WHERE id = %s', (product_id,))
            return ok(row_to_dict(cur.fetchone()))
    finally:
        conn.close()

@app.route('/api/products/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM products WHERE id = %s', (product_id,))
            if not cur.fetchone():
                return err('Product not found', 404)
            cur.execute('DELETE FROM products WHERE id = %s', (product_id,))
        return ok({'deleted_id': product_id})
    finally:
        conn.close()

@app.route('/api/products/<product_id>/toggle', methods=['POST'])
def toggle_product(product_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM products WHERE id = %s', (product_id,))
            row = cur.fetchone()
            if not row:
                return err('Product not found', 404)
            new_active = 0 if row['active'] else 1
            cur.execute('UPDATE products SET active = %s WHERE id = %s', (new_active, product_id))
            cur.execute('SELECT * FROM products WHERE id = %s', (product_id,))
            return ok(row_to_dict(cur.fetchone()))
    finally:
        conn.close()

@app.route('/api/products/bulk', methods=['POST'])
def bulk_action():
    data   = request.json or {}
    action = data.get('action')
    ids    = data.get('ids', [])
    if action not in ('delete', 'activate', 'deactivate', 'set_category'):
        return err('Invalid action')
    if not ids or not isinstance(ids, list):
        return err('"ids" must be a non-empty list')

    placeholders = ','.join(['%s'] * len(ids))
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if action == 'delete':
                cur.execute(f'DELETE FROM products WHERE id IN ({placeholders})', ids)
                affected = cur.rowcount
            elif action == 'set_category':
                new_cat = str(data.get('category', '')).strip()
                if not new_cat:
                    return err('"category" is required for set_category action')
                cur.execute(
                    f'UPDATE products SET cat = %s WHERE id IN ({placeholders})',
                    [new_cat] + ids
                )
                affected = cur.rowcount
            else:
                active_val = 1 if action == 'activate' else 0
                cur.execute(
                    f'UPDATE products SET active = %s WHERE id IN ({placeholders})',
                    [active_val] + ids
                )
                affected = cur.rowcount
        return ok({'action': action, 'affected': affected})
    finally:
        conn.close()

@app.route('/api/products/batch', methods=['POST'])
def batch_create():
    data     = request.json or {}
    products = data.get('products', [])
    if not products:
        return err('"products" list is required')

    created, skipped, details = 0, 0, []
    conn = get_db()
    try:
        with conn.cursor() as cur:
            for p in products:
                p, error = validate_product(dict(p), require_all=True)
                if error:
                    skipped += 1
                    details.append({'name': p.get('name', '?'), 'reason': error})
                    continue
                cur.execute('SELECT id FROM products WHERE LOWER(name) = LOWER(%s)', (p['name'],))
                if cur.fetchone():
                    skipped += 1
                    details.append({'name': p['name'], 'reason': 'Duplicate name'})
                    continue
                new_id = str(uuid.uuid4())[:8]
                cur.execute("""
                    INSERT INTO products (id,name,cat,price,tag,description,img,active,stock)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    new_id, p['name'],
                    str(p.get('cat', '')).strip(),
                    p.get('price', 0),
                    str(p.get('tag', '')).strip(),
                    str(p.get('desc', '')).strip(),
                    p.get('img', ''),
                    int(bool(p.get('active', True))),
                    int(p.get('stock', 0)),
                ))
                created += 1
        return ok({'created': created, 'skipped': skipped, 'details': details})
    finally:
        conn.close()

@app.route('/api/categories', methods=['GET'])
def get_categories():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT cat AS name, COUNT(*) AS count FROM products GROUP BY cat ORDER BY cat')
            return ok(list(cur.fetchall()))
    finally:
        conn.close()

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*)                            AS total_products,
                    SUM(active = 1)                     AS active_products,
                    SUM(active = 0)                     AS inactive_products,
                    COUNT(DISTINCT cat)                 AS total_categories,
                    ROUND(AVG(price), 2)                AS avg_price,
                    MIN(price)                          AS min_price,
                    MAX(price)                          AS max_price,
                    SUM(stock)                          AS total_stock,
                    SUM(stock > 0 AND stock <= 10)      AS low_stock_count,
                    SUM(stock = 0)                      AS out_of_stock_count
                FROM products
            """)
            row   = cur.fetchone()
            stats = {k: (float(v) if v is not None else 0) for k, v in row.items()}
            for k in ('total_products','active_products','inactive_products',
                      'total_categories','total_stock','low_stock_count','out_of_stock_count'):
                stats[k] = int(stats[k])
        return ok(stats)
    finally:
        conn.close()

# ── Health ────────────────────────────────────────────────────────
@app.route('/health')
def health():
    try:
        conn = get_db(); conn.ping(); conn.close()
        return jsonify({'status': 'ok', 'db': 'connected'})
    except Exception as e:
        return jsonify({'status': 'degraded', 'db': str(e)}), 500

# ── Error handlers ────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):          return err('Endpoint not found', 404)
@app.errorhandler(405)
def method_not_allowed(e): return err('Method not allowed', 405)
@app.errorhandler(500)
def server_error(e):       return err('Internal server error', 500)

# ── Boot ──────────────────────────────────────────────────────────
init_db()

if __name__ == '__main__':
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)