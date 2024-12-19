from flask import Flask, render_template, request, redirect, url_for, session
from config import DB_CONFIG  # Veritabanı bilgilerini config dosyasından alıyoruz.
from models import db, Customer, Admin, Product, Order, ConfirmedOrder  # Modelleri ve db'yi içe aktar

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
    # Oturumdan müşteri ID'sini al
    customer_id = session.get('customer_id')
    if not customer_id:
        return redirect(url_for('login_page'))  # Eğer giriş yapılmadıysa login sayfasına yönlendir

    # Formdan seçilen ürün ID'leri ve miktarlarını al
    product_ids = request.form.getlist('product_ids')
    quantities = request.form.getlist('quantities')

    # Veritabanından müşteri bilgilerini al
    customer = Customer.query.get(customer_id)

    # Sipariş toplam fiyatını hesapla
    total_order_price = 0
    orders_to_add = []

    for product_id, quantity in zip(product_ids, quantities):
        product = Product.query.get(int(product_id))
        quantity = int(quantity)

        if not product:
            return f"Ürün ID {product_id} bulunamadı."

        total_price = product.Price * quantity
        total_order_price += total_price

        # Sipariş detayını kaydetmek için listeye ekle
        orders_to_add.append({
            "product": product,
            "quantity": quantity,
            "total_price": total_price
        })

    # Bütçe kontrolü
    if customer.Budget < total_order_price:
        return "Yetersiz Bütçe! Lütfen daha düşük bir sipariş girin."

    # Siparişi tamamla
    for order in orders_to_add:
        product = order["product"]
        quantity = order["quantity"]
        total_price = order["total_price"]

        # Siparişi Orders tablosuna kaydet
        new_order = Order(
            CustomerID=customer.CustomerID,
            ProductID=product.ProductID,
            Quantity=quantity,
            TotalPrice=total_price
        )
        db.session.add(new_order)

    # Veritabanını güncelle
    db.session.commit()

    return f"Sipariş başarıyla verildi! Toplam: {total_order_price:.2f} TL"


@app.route('/orderOperations', methods=['GET'])
def order_operations():
    orders = Order.query.all()  # Orders tablosundaki tüm siparişleri al
    confirmed_orders = ConfirmedOrder.query.all()  # ConfirmedOrders tablosundaki tüm siparişleri al
    return render_template('orderOperations.html', orders=orders, confirmed_orders=confirmed_orders)

@app.route('/approveOrder', methods=['POST'])
def approve_order():
    order_id = request.form['order_id']  # Formdan gelen sipariş ID'sini al
    order = Order.query.get(order_id)  # Orders tablosundan siparişi al

    if not order:
        return "Sipariş bulunamadı!"

    # Veritabanından ürün bilgilerini al
    product = Product.query.get(order.ProductID)
    if not product:
        return "Ürün bulunamadı!"

    # Stok kontrolü
    if order.Quantity > product.Stock:
        return f"Yetersiz stok! {product.ProductName} için maksimum {product.Stock} adet onaylanabilir."

    # Ürünün stok miktarını güncelle
    product.Stock -= order.Quantity

    # Siparişi ConfirmedOrders tablosuna ekle
    confirmed_order = ConfirmedOrder(
        CustomerID=order.CustomerID,
        ProductID=order.ProductID,
        Quantity=order.Quantity,
        TotalPrice=order.TotalPrice,
        OrderDate=order.OrderDate
    )
    db.session.add(confirmed_order)

    # Orders tablosundan sil
    db.session.delete(order)
    db.session.commit()  # Veritabanını güncelle

    return redirect(url_for('order_operations'))




@app.route('/productOperations', methods=['GET'])
def product_operations():
    products = Product.query.all()  # Veritabanındaki tüm ürünleri al
    return render_template('productOperations.html', products=products)

@app.route('/deleteProduct', methods=['POST'])
def delete_product():
    product_id = request.form['product_id']  # Formdan gelen ürün ID'sini al
    product = Product.query.get(product_id)  # Veritabanından ürünü al

    if product:
        db.session.delete(product)  # Ürünü sil
        db.session.commit()  # Veritabanını güncelle
        return redirect(url_for('product_operations'))
    else:
        return "Ürün bulunamadı!"


@app.route('/updateStock', methods=['POST'])
def update_stock():
    product_id = request.form['product_id']  # Formdan gelen ürün ID'sini al
    new_stock = int(request.form['new_stock'])  # Formdan gelen yeni stok miktarını al
    product = Product.query.get(product_id)  # Veritabanından ürünü al

    if product:
        product.Stock = new_stock  # Stok miktarını güncelle
        db.session.commit()  # Veritabanını güncelle
        return redirect(url_for('product_operations'))
    else:
        return "Ürün bulunamadı!"

@app.route('/addProduct', methods=['GET'])
def add_product_page():
    return render_template('addProduct.html')

@app.route('/addProduct', methods=['POST'])
def add_product():
    # Formdan gelen verileri al
    product_name = request.form['productName']
    stock = int(request.form['stock'])
    price = float(request.form['price'])

    # Yeni ürün nesnesi oluştur
    new_product = Product(
        ProductName=product_name,
        Stock=stock,
        Price=price
    )

    # Veritabanına ekle
    db.session.add(new_product)
    db.session.commit()

    return redirect(url_for('product_operations'))  # Ürün işlemleri sayfasına yönlendir


# Flask uygulamasını çalıştır
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Veritabanı tablolarını oluşturur
    app.run(debug=True)