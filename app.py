from flask import Flask, render_template, request, redirect, url_for, session
from config import DB_CONFIG
from models import db, Customer, Admin, Product, Order, ConfirmedOrder, Log
from datetime import datetime
import threading

lock = threading.Lock()  # Global bir kilit nesnesi oluştur

# Flask ayarları
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'asdf'

db.init_app(app)

# Öncelik hesaplama ağırlığı
PRIORITY_WEIGHT = 0.5

# Öncelik skoru hesaplama fonksiyonu
def calculate_priority(order, customer):
    base_score = 15 if customer.CustomerType == 'Premium' else 10
    wait_time = (datetime.utcnow() - order.OrderDate).total_seconds()
    return base_score + (wait_time * PRIORITY_WEIGHT)

# Tüm siparişleri öncelik sırasına göre onaylama fonksiyonu
def approve_all_orders():
    # Tüm siparişleri veritabanından çek ve öncelik sırasına göre sırala
    orders = db.session.query(Order, Customer).join(Customer).all()

    # Her sipariş için öncelik skorunu hesapla
    orders_with_priority = [
        (order, calculate_priority(order, customer))
        for order, customer in orders
    ]

    # Siparişleri öncelik skoruna göre sırala
    orders_with_priority.sort(key=lambda x: x[1], reverse=True)

    # Onaylama işlemleri
    for order, _ in orders_with_priority:
        product = Product.query.get(order.ProductID)
        if product and product.Stock >= order.Quantity:
            product.Stock -= order.Quantity
            confirmed_order = ConfirmedOrder(
                CustomerID=order.CustomerID,
                ProductID=order.ProductID,
                Quantity=order.Quantity,
                TotalPrice=order.TotalPrice,
                OrderDate=order.OrderDate
            )
            db.session.add(confirmed_order)
            db.session.delete(order)
            create_log(order.CustomerID, order.OrderID, "Bilgilendirme", "Sipariş onaylandı.")
        else:
            create_log(order.CustomerID, order.OrderID, "Hata", f"Yetersiz stok: {product.ProductName if product else 'Bilinmiyor'}")

    db.session.commit()


# Log kaydetme fonksiyonu
def create_log(customer_id, order_id, log_type, log_details):
    new_log = Log(
        CustomerID=customer_id,
        OrderID=order_id,
        LogType=log_type,
        LogDetails=log_details
    )
    db.session.add(new_log)
    db.session.commit()

# Rotalar
@app.route('/')
def login_page():
    return render_template('customerLogin.html')

@app.route('/customerlogin', methods=['POST'])
def customer_login():
    customername = request.form['customername']
    password = request.form['password']

    customer = Customer.query.filter_by(CustomerName=customername, Password=password).first()
    if customer:
        session['customer_name'] = customer.CustomerName
        session['customer_id'] = customer.CustomerID
        return redirect(url_for('index'))
    return "Geçersiz giriş bilgileri. Lütfen tekrar deneyin."


@app.route('/index', methods=['GET'])
def index():
    # Oturumdan müşteri ID'sini al
    customer_id = session.get('customer_id')
    
    if not customer_id:
        return redirect(url_for('login_page'))  # Eğer giriş yapılmadıysa login sayfasına yönlendir

    # Veritabanından müşteri bilgilerini al
    customer = Customer.query.get(customer_id)
    
    if not customer:
        return redirect(url_for('login_page'))  # Geçersiz müşteri ID'si durumunda login sayfasına yönlendir

    # Veritabanından tüm ürünleri çek
    products = Product.query.all()

    # Müşterinin Orders tablosundaki siparişlerini al
    orders = db.session.query(Order.OrderDate, Product.ProductName, Order.TotalPrice).join(
        Product, Product.ProductID == Order.ProductID
    ).filter(Order.CustomerID == customer_id).all()

    # Müşterinin ConfirmedOrders tablosundaki siparişlerini al
    confirmed_orders = db.session.query(ConfirmedOrder.OrderDate, Product.ProductName, ConfirmedOrder.TotalPrice).join(
        Product, Product.ProductID == ConfirmedOrder.ProductID
    ).filter(ConfirmedOrder.CustomerID == customer_id).all()

    # Müşteri türünü belirleme (örnek olarak veritabanında CustomerType olduğunu varsayıyoruz)
    customer_type = "Premium" if customer.CustomerType == "Premium" else "Standart"

    return render_template(
        'index.html',
        customer=customer,
        products=products,
        orders=orders,
        confirmed_orders=confirmed_orders
    )

@app.route('/adminlogin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        adminname = request.form['adminname']
        password = request.form['password']
        admin = Admin.query.filter_by(AdminName=adminname, Password=password).first()
        if admin:
            session['admin_name'] = admin.AdminName
            return redirect(url_for('admin_panel'))
        return "Geçersiz giriş bilgileri. Lütfen tekrar deneyin."
    return render_template('adminLogin.html')

@app.route('/adminPanel', methods=['GET']) # İki seçenek sunan admin ekranı (Sipariş ve ürün işlemleri)
def admin_panel():
    if 'admin_name' not in session:
        return redirect(url_for('admin_login'))
    return render_template('adminPanel.html')

@app.route('/orderOperations', methods=['GET'])
def order_operations():
    orders = Order.query.all()
    for order in orders:
        customer = Customer.query.get(order.CustomerID)
        order.priority_score = calculate_priority(order, customer)
    confirmed_orders = ConfirmedOrder.query.all()
    return render_template('orderOperations.html', orders=orders, confirmed_orders=confirmed_orders)

@app.route('/productOperations', methods=['GET'])
def product_operations():
    products = Product.query.all()  # Veritabanındaki tüm ürünleri al
    return render_template('productOperations.html', products=products)

@app.route('/addProduct', methods=['GET'])
def add_product_page():
    return render_template('addProduct.html')

@app.route('/logout') # Müşteri sayfasındaki çıkış yapma fonksiyonu
def logout():
    session.clear()  # Oturum verilerini temizler
    return render_template('customerLogin.html')  # Giriş sayfasını döndürür

@app.route('/logs', methods=['GET']) # Logları görüntüleme fonksiyonu
def view_logs():
    logs = Log.query.order_by(Log.LogDate.desc()).all()
    return render_template('logs.html', logs=logs)





# Fonksiyonlar

@app.route('/order', methods=['POST'])
def place_order():
    with lock:  # Kilit al
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
                create_log(customer_id, None, "Hata", f"Ürün bulunamadı. Ürün ID: {product_id}")
                return redirect(url_for('index'))  # Ürün bulunamadıysa index sayfasına yönlendir

            total_price = product.Price * quantity
            total_order_price += total_price

            if product.Stock < quantity:
                create_log(customer_id, None, "Hata", f"Ürün stoğu yetersiz. Ürün: {product.ProductName}")
                return redirect(url_for('index'))  # Stok yetersizse index sayfasına yönlendir

            orders_to_add.append({
                "product": product,
                "quantity": quantity,
                "total_price": total_price
            })

        # Bütçe kontrolü
        if customer.Budget < total_order_price:
            create_log(customer_id, None, "Hata", "Müşteri bakiyesi yetersiz.")
            return redirect(url_for('index'))  # Bütçe yetersizse index sayfasına yönlendir

        # Siparişi tamamla
        for order in orders_to_add:
            product = order["product"]
            quantity = order["quantity"]
            total_price = order["total_price"]

            product.Stock -= quantity

            new_order = Order(
                CustomerID=customer.CustomerID,
                ProductID=product.ProductID,
                Quantity=quantity,
                TotalPrice=total_price
            )
            db.session.add(new_order)

        customer.Budget -= total_order_price
        db.session.commit()

        create_log(customer_id, None, "Bilgilendirme", "Satın alma başarılı.")
        return redirect(url_for('index'))  # Sayfayı yenileyip yeniden göster

@app.route('/refreshOrders', methods=['GET'])
def refresh_orders():
    orders = Order.query.all()
    for order in orders:
        customer = Customer.query.get(order.CustomerID)
        order.priority_score = calculate_priority(order, customer)
    return redirect(url_for('order_operations'))

@app.route('/approveAllOrders', methods=['POST'])
def approve_all_orders_route():
    with lock:  # Kilit al
        approve_all_orders()
    return redirect(url_for('order_operations'))




@app.route('/approveOrder', methods=['POST'])
def approve_order():
    with lock:  # Kilit al
        order_id = request.form['order_id']  # Formdan gelen sipariş ID'sini al
        order = Order.query.get(order_id)  # Orders tablosundan siparişi al

        if not order:
            create_log(None, order_id, "Hata", "Sipariş bulunamadı.")
            return "Sipariş bulunamadı!"

        # Veritabanından ürün bilgilerini al
        product = Product.query.get(order.ProductID)
        if not product:
            create_log(order.CustomerID, order_id, "Hata", "Ürün bulunamadı.")
            return "Ürün bulunamadı!"

        # Stok kontrolü
        if order.Quantity > product.Stock:
            create_log(order.CustomerID, order_id, "Hata", f"Yetersiz stok! Ürün: {product.ProductName}")
            return f"Yetersiz stok! {product.ProductName} için maksimum {product.Stock} adet onaylanabilir."

        product.Stock -= order.Quantity

        confirmed_order = ConfirmedOrder(
            CustomerID=order.CustomerID,
            ProductID=order.ProductID,
            Quantity=order.Quantity,
            TotalPrice=order.TotalPrice,
            OrderDate=order.OrderDate
        )
        db.session.add(confirmed_order)

        create_log(order.CustomerID, order.OrderID, "Bilgilendirme", "Sipariş onaylandı.")

        db.session.delete(order)
        db.session.commit()  # Veritabanını güncelle

        return redirect(url_for('order_operations'))


@app.route('/deleteProduct', methods=['POST'])
def delete_product():
    product_id = request.form['product_id']  # Formdan gelen ürün ID'sini al
    product = Product.query.get(product_id)  # Veritabanından ürünü al

    if product:
        db.session.delete(product)  # Ürünü sil
        create_log(None, None, "Bilgilendirme", f"Ürün silindi. Ürün ID: {product_id}")
        db.session.commit()  # Veritabanını güncelle
        return redirect(url_for('product_operations'))
    else:
        create_log(None, None, "Hata", f"Ürün silinemedi. Ürün ID: {product_id}")
        return "Ürün bulunamadı!"

@app.route('/updateStock', methods=['POST'])
def update_stock():
    product_id = request.form['product_id']  # Formdan gelen ürün ID'sini al
    new_stock = int(request.form['new_stock'])  # Formdan gelen yeni stok miktarını al
    product = Product.query.get(product_id)  # Veritabanından ürünü al

    if product:
        product.Stock = new_stock  # Stok miktarını güncelle
        db.session.commit()  # Veritabanını güncelle
        create_log(None, None, "Bilgilendirme", f"Ürün stoğu güncellendi. Ürün ID: {product_id}")
        return redirect(url_for('product_operations'))
    else:
        create_log(None, None, "Hata", f"Stok güncellenemedi. Ürün ID: {product_id}")
        return "Ürün bulunamadı!"

@app.route('/addProduct', methods=['POST'])
def add_product():
    # Formdan gelen verileri al
    product_name = request.form['productName']
    stock = int(request.form['stock'])
    price = float(request.form['price'])

    new_product = Product(
        ProductName=product_name,
        Stock=stock,
        Price=price
    )
    db.session.add(new_product)
    db.session.commit()

    create_log(None, None, "Bilgilendirme", f"Yeni ürün eklendi. Ürün: {product_name}")
    return redirect(url_for('product_operations'))  # Ürün işlemleri sayfasına yönlendir





if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
