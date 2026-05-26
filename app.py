from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json, os, uuid

app = Flask(__name__, static_folder='static')
CORS(app)

DATA_FILE = 'products.json'

DEFAULT_PRODUCTS = [
    {"id": "1", "name": "Velvet Noir Serum", "cat": "Serums", "price": 148, "tag": "Bestseller", "desc": "A midnight-dark elixir that revives and illuminates dull skin overnight.", "img": "https://images.pexels.com/photos/5632386/pexels-photo-5632386.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True},
    {"id": "2", "name": "Gold Radiance Cream", "cat": "Moisturizers", "price": 195, "tag": "New", "desc": "Infused with 24k gold particles for a luminous, sculpted complexion.", "img": "https://images.pexels.com/photos/6621462/pexels-photo-6621462.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True},
    {"id": "3", "name": "Obsidian Eye Elixir", "cat": "Eye Care", "price": 112, "tag": "Award Winner", "desc": "Deep-repairing formula that erases dark circles and fine lines.", "img": "https://images.pexels.com/photos/4762440/pexels-photo-4762440.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True},
    {"id": "4", "name": "Charles Lip Nectar", "cat": "Lip Care", "price": 68, "tag": "Fan Favorite", "desc": "Plumping lip treatment with a mirror-like finish and rich hydration.", "img": "https://images.pexels.com/photos/3997989/pexels-photo-3997989.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True},
    {"id": "5", "name": "Navy Mist Toner", "cat": "Toners", "price": 85, "tag": "Vegan", "desc": "Balancing botanical mist that preps skin for effortless absorption.", "img": "https://images.pexels.com/photos/6424249/pexels-photo-6424249.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True},
    {"id": "6", "name": "Imperial Body Oil", "cat": "Body", "price": 135, "tag": "Luxury", "desc": "A silky dry oil blend of rose hip, argan and jasmine for goddess skin.", "img": "https://images.pexels.com/photos/4041391/pexels-photo-4041391.jpeg?auto=compress&cs=tinysrgb&w=600", "active": True},
]

def load_products():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    save_products(DEFAULT_PRODUCTS)
    return DEFAULT_PRODUCTS

def save_products(products):
    with open(DATA_FILE, 'w') as f:
        json.dump(products, f, indent=2)

# ── Routes ──────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/products', methods=['GET'])
def get_products():
    return jsonify(load_products())

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json
    products = load_products()
    new_product = {
        "id": str(uuid.uuid4())[:8],
        "name": data.get('name', ''),
        "cat": data.get('cat', ''),
        "price": float(data.get('price', 0)),
        "tag": data.get('tag', ''),
        "desc": data.get('desc', ''),
        "img": data.get('img', ''),
        "active": data.get('active', True),
    }
    products.append(new_product)
    save_products(products)
    return jsonify(new_product), 201

@app.route('/api/products/<product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.json
    products = load_products()
    for i, p in enumerate(products):
        if p['id'] == product_id:
            products[i] = {**p, **data, 'id': product_id}
            save_products(products)
            return jsonify(products[i])
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/products/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    products = load_products()
    products = [p for p in products if p['id'] != product_id]
    save_products(products)
    return jsonify({'success': True})

@app.route('/api/products/<product_id>/toggle', methods=['POST'])
def toggle_product(product_id):
    products = load_products()
    for i, p in enumerate(products):
        if p['id'] == product_id:
            products[i]['active'] = not p.get('active', True)
            save_products(products)
            return jsonify(products[i])
    return jsonify({'error': 'Not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)