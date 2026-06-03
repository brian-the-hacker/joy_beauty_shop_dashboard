from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json, os, uuid
from datetime import datetime
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__, static_folder='static')
CORS(app)

# ── Cloudinary Configuration ─────────────────────────────────────

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

# ── Storage path ─────────────────────────────────────────────────
# On Render: set DATA_DIR=/data  (mount your disk at /data)
# Locally:   defaults to the project folder  (./products.json)
DATA_DIR  = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, 'products.json')

DEFAULT_PRODUCTS = [
    {"id": "1", "name": "Velvet Noir Serum", "cat": "Serums", "price": 148, "tag": "Bestseller", "desc": "A midnight-dark elixir that revives and illuminates dull skin overnight.", "img": "https://images.pexels.com/photos/5632386/pexels-photo-5632386.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True, "stock": 42, "created_at": "2024-01-01T00:00:00"},
    {"id": "2", "name": "Gold Radiance Cream", "cat": "Moisturizers", "price": 195, "tag": "New", "desc": "Infused with 24k gold particles for a luminous, sculpted complexion.", "img": "https://images.pexels.com/photos/6621462/pexels-photo-6621462.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True, "stock": 28, "created_at": "2024-01-02T00:00:00"},
    {"id": "3", "name": "Obsidian Eye Elixir", "cat": "Eye Care", "price": 112, "tag": "Award Winner", "desc": "Deep-repairing formula that erases dark circles and fine lines.", "img": "https://images.pexels.com/photos/4762440/pexels-photo-4762440.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True, "stock": 15, "created_at": "2024-01-03T00:00:00"},
    {"id": "4", "name": "Charles Lip Nectar", "cat": "Lip Care", "price": 68, "tag": "Fan Favorite", "desc": "Plumping lip treatment with a mirror-like finish and rich hydration.", "img": "https://images.pexels.com/photos/3997989/pexels-photo-3997989.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True, "stock": 60, "created_at": "2024-01-04T00:00:00"},
    {"id": "5", "name": "Navy Mist Toner", "cat": "Toners", "price": 85, "tag": "Vegan", "desc": "Balancing botanical mist that preps skin for effortless absorption.", "img": "https://images.pexels.com/photos/6424249/pexels-photo-6424249.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True, "stock": 33, "created_at": "2024-01-05T00:00:00"},
    {"id": "6", "name": "Imperial Body Oil", "cat": "Body", "price": 135, "tag": "Luxury", "desc": "A silky dry oil blend of rose hip, argan and jasmine for goddess skin.", "img": "https://images.pexels.com/photos/4041391/pexels-photo-4041391.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True, "stock": 20, "created_at": "2024-01-06T00:00:00"},
]

# ── Data helpers ─────────────────────────────────────────────────

def load_products():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    save_products(DEFAULT_PRODUCTS)
    return DEFAULT_PRODUCTS

def save_products(products):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(products, f, indent=2)

# ── Validation ───────────────────────────────────────────────────

REQUIRED_FIELDS = ['name', 'cat']

def validate_product(data, require_all=True):
    errors = []
    if require_all:
        for field in REQUIRED_FIELDS:
            if not data.get(field):
                errors.append(f'"{field}" is required')
    if 'name' in data:
        name = str(data['name']).strip()
        if len(name) < 2:  errors.append('"name" must be at least 2 characters')
        if len(name) > 120: errors.append('"name" must be under 120 characters')
        data['name'] = name
    if 'price' in data:
        try:
            price = float(data['price'])
            if price < 0: errors.append('"price" cannot be negative')
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

# ── Response helpers ─────────────────────────────────────────────

def ok(data, status=200):
    return jsonify({'success': True, 'data': data}), status

def err(message, status=400):
    return jsonify({'success': False, 'error': message}), status

# ── Routes ───────────────────────────────────────────────────────

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
    products = load_products()
    active_param = request.args.get('active')
    if active_param is not None:
        want_active = active_param.lower() == 'true'
        products = [p for p in products if p.get('active', True) == want_active]
    cat = request.args.get('cat', '').strip()
    if cat:
        products = [p for p in products if p.get('cat', '').lower() == cat.lower()]
    try:
        min_price = float(request.args.get('min_price', 0))
        max_price = float(request.args.get('max_price', float('inf')))
        products = [p for p in products if min_price <= p.get('price', 0) <= max_price]
    except ValueError:
        return err('min_price and max_price must be numbers')
    q = request.args.get('q', '').strip().lower()
    if q:
        products = [p for p in products if any(q in str(p.get(f, '')).lower() for f in ['name', 'cat', 'desc', 'tag'])]
    sort_field = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'asc').lower()
    if sort_field in {'price', 'name', 'created_at', 'stock'}:
        reverse = sort_order == 'desc'
        products = sorted(
            products,
            key=lambda p: (p.get(sort_field) or 0) if sort_field in {'price', 'stock'} else str(p.get(sort_field, '')).lower(),
            reverse=reverse
        )
    total = len(products)
    try:
        page  = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', total))))
    except ValueError:
        return err('page and limit must be integers')
    start = (page - 1) * limit
    paginated = products[start:start + limit]
    return jsonify({
        'success': True, 'data': paginated,
        'meta': {
            'total': total, 'page': page, 'limit': limit,
            'pages': max(1, -(-total // limit)),
            'has_next': start + limit < total, 'has_prev': page > 1,
        }
    })

@app.route('/api/products/<product_id>', methods=['GET'])
def get_product(product_id):
    products = load_products()
    p = next((p for p in products if p['id'] == product_id), None)
    return ok(p) if p else err('Product not found', 404)

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json
    if not data: return err('Request body must be JSON')
    data, error = validate_product(data, require_all=True)
    if error: return err(error)
    products = load_products()
    if any(p['name'].lower() == data['name'].lower() for p in products):
        return err(f'A product named "{data["name"]}" already exists', 409)
    new_product = {
        'id': str(uuid.uuid4())[:8],
        'name': data.get('name', ''),
        'cat': str(data.get('cat', '')).strip(),
        'price': data.get('price', 0),
        'tag': str(data.get('tag', '')).strip(),
        'desc': str(data.get('desc', '')).strip(),
        'img': data.get('img', ''),
        'active': bool(data.get('active', True)),
        'stock': int(data.get('stock', 0)),
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
    }
    products.append(new_product)
    save_products(products)
    return ok(new_product, 201)

@app.route('/api/products/<product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.json
    if not data: return err('Request body must be JSON')
    data, error = validate_product(data, require_all=False)
    if error: return err(error)
    products = load_products()
    for i, p in enumerate(products):
        if p['id'] == product_id:
            new_name = data.get('name', p['name'])
            if any(x['name'].lower() == new_name.lower() and x['id'] != product_id for x in products):
                return err(f'Another product named "{new_name}" already exists', 409)
            products[i] = {**p, **{k: v for k, v in data.items() if k not in ('id', 'created_at')}, 'id': product_id, 'updated_at': datetime.utcnow().isoformat()}
            save_products(products)
            return ok(products[i])
    return err('Product not found', 404)

@app.route('/api/products/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    products = load_products()
    original_len = len(products)
    products = [p for p in products if p['id'] != product_id]
    if len(products) == original_len:
        return err('Product not found', 404)
    save_products(products)
    return ok({'deleted_id': product_id})

@app.route('/api/products/<product_id>/toggle', methods=['POST'])
def toggle_product(product_id):
    products = load_products()
    for i, p in enumerate(products):
        if p['id'] == product_id:
            products[i]['active'] = not p.get('active', True)
            products[i]['updated_at'] = datetime.utcnow().isoformat()
            save_products(products)
            return ok(products[i])
    return err('Product not found', 404)

@app.route('/api/products/bulk', methods=['POST'])
def bulk_action():
    data = request.json or {}
    action = data.get('action')
    ids = data.get('ids', [])
    if action not in ('delete', 'activate', 'deactivate', 'set_category'):
        return err('Invalid action')
    if not ids or not isinstance(ids, list):
        return err('"ids" must be a non-empty list')
    products = load_products()
    affected = 0
    if action == 'delete':
        before = len(products)
        products = [p for p in products if p['id'] not in ids]
        affected = before - len(products)
    elif action == 'set_category':
        new_cat = str(data.get('category', '')).strip()
        if not new_cat:
            return err('"category" is required for set_category action')
        for i, p in enumerate(products):
            if p['id'] in ids:
                products[i]['cat'] = new_cat
                products[i]['updated_at'] = datetime.utcnow().isoformat()
                affected += 1
    else:
        active_val = action == 'activate'
        for i, p in enumerate(products):
            if p['id'] in ids:
                products[i]['active'] = active_val
                products[i]['updated_at'] = datetime.utcnow().isoformat()
                affected += 1
    save_products(products)
    return ok({'action': action, 'affected': affected})

@app.route('/api/categories', methods=['GET'])
def get_categories():
    products = load_products()
    cats = {}
    for p in products:
        cat = p.get('cat', 'Uncategorized')
        cats[cat] = cats.get(cat, 0) + 1
    return ok([{'name': k, 'count': v} for k, v in sorted(cats.items())])

@app.route('/api/stats', methods=['GET'])
def get_stats():
    products = load_products()
    active  = [p for p in products if p.get('active', True)]
    prices  = [p['price'] for p in products if 'price' in p]
    stocks  = [p.get('stock', 0) for p in products]
    return ok({
        'total_products': len(products), 'active_products': len(active),
        'inactive_products': len(products) - len(active),
        'total_categories': len(set(p.get('cat') for p in products)),
        'avg_price': round(sum(prices) / len(prices), 2) if prices else 0,
        'min_price': min(prices) if prices else 0, 'max_price': max(prices) if prices else 0,
        'total_stock': sum(stocks),
        'low_stock_count': sum(1 for s in stocks if 0 < s <= 10),
        'out_of_stock_count': sum(1 for s in stocks if s == 0),
    })

# ── Health check (Render uses this) ─────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'data_file': DATA_FILE, 'exists': os.path.exists(DATA_FILE)})

# ── Error handlers ───────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e): return err('Endpoint not found', 404)

@app.errorhandler(405)
def method_not_allowed(e): return err('Method not allowed', 405)

@app.errorhandler(500)
def server_error(e): return err('Internal server error', 500)

# ── Entry point ──────────────────────────────────────────────────

if __name__ == '__main__':
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    print(f"  Data file : {DATA_FILE}")
    print(f"  Port      : {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
