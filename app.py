from flask import Flask, render_template, request, redirect, url_for, session
from config import DB_CONFIG  # Veritabanı bilgilerini config dosyasından alıyoruz.
from models import db, Customer, Admin, Product  # Modelleri ve db'yi içe aktar

# Flask ve SQLAlchemy ayarları
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'asdf'  # Gizli anahtar tanımlanması

# Veritabanı başlatma
db.init_app(app)

# Rotalar
@app.route('/')
def login_page():
    return render_template('customerLogin.html')

@app.route('/customerlogin', methods=['POST'])
def customer_login():
    customername = request.form['customername']
    password = request.form['password']
    
    # Müşteri doğrulama
    customer = Customer.query.filter_by(CustomerName=customername, Password=password).first()
    if customer:
        # Oturuma müşteri adını kaydet
        session['customer_name'] = customer.CustomerName
        session['customer_id'] = customer.CustomerID
        return redirect(url_for('index'))
    else:
        return "Geçersiz giriş bilgileri. Lütfen tekrar deneyin."

@app.route('/index', methods=['GET'])
def index():
    # Oturumdan müşteri adını ve ID'sini al
    customer_name = session.get('customer_name')
    customer_id = session.get('customer_id')
    
    if not customer_id:
        return redirect(url_for('login_page'))  # Eğer giriş yapılmadıysa login sayfasına yönlendir

    # Veritabanından müşteri bilgilerini al
    customer = Customer.query.get(customer_id)
    
    # Veritabanından tüm ürünleri çek
    products = Product.query.all()

    return render_template('index.html', customer=customer, products=products)

@app.route('/adminlogin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        adminname = request.form['adminname']
        password = request.form['password']
        
        # Admin doğrulama
        admin = Admin.query.filter_by(AdminName=adminname, Password=password).first()
        if admin:
            return redirect(url_for('admin_panel'))
        else:
            return "Geçersiz giriş bilgileri. Lütfen tekrar deneyin."
    return render_template('adminLogin.html')

# Admin paneli rotası
@app.route('/adminPanel')
def admin_panel():
    return render_template('adminPanel.html')

@app.route('/order', methods=['POST'])
def place_order():
    product_id = int(request.form['product_id'])
    quantity = int(request.form['quantity'])

    # Ürün kontrolü
    product = Product.query.get(product_id)
    if product and product.Stock >= quantity:
        product.Stock -= quantity
        db.session.commit()
        return f"Sipariş başarılı! {quantity} adet {product.ProductName} satın aldınız."
    else:
        return "Stok yetersiz!"

# Flask uygulamasını çalıştır
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Veritabanı tablolarını oluşturur
    app.run(debug=True)