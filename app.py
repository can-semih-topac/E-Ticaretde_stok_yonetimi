from flask import Flask, render_template, request, redirect, url_for, session
from config import DB_CONFIG
from models import db, Customer, Admin, Product, Order, ConfirmedOrder, Log
from datetime import datetime
import threading 
from threading import Lock, Thread,Semaphore

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
    orders = db.session.query(Order, Customer).join(Customer).all()
    orders_with_priority = [
        (order, calculate_priority(order, customer))
        for order, customer in orders
    ]
    orders_with_priority.sort(key=lambda x: x[1], reverse=True)

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


# Sipariş verme fonksiyonu
# Sipariş verme fonksiyonu (threadsiz)
def process_order_without_thread(customer_id, product_ids, quantities):
    customer = Customer.query.get(customer_id)
    total_order_price = 0
    orders_to_add = []

    for product_id, quantity in zip(product_ids, quantities):
        product = Product.query.get(int(product_id))
        quantity = int(quantity)

        if not product or product.Stock < quantity:
            create_log(customer_id, None, "Hata", f"Ürün stoğu yetersiz: {product.ProductName if product else 'Bilinmiyor'}")
            return

        total_price = product.Price * quantity
        total_order_price += total_price
        orders_to_add.append({"product": product, "quantity": quantity, "total_price": total_price})

    if customer.Budget < total_order_price:
        create_log(customer_id, None, "Hata", "Bütçe yetersiz.")
        return

    for order in orders_to_add:
        product = order["product"]
        product.Stock -= order["quantity"]

        new_order = Order(
            CustomerID=customer.CustomerID,
            ProductID=product.ProductID,
            Quantity=order["quantity"],
            TotalPrice=order["total_price"]
        )
        db.session.add(new_order)

    customer.Budget -= total_order_price
    db.session.commit()
    create_log(customer_id, None, "Bilgilendirme", "Sipariş başarıyla tamamlandı.")

# Tek bir siparişi onaylama fonksiyonu
def process_approve_order(order_id):
    with lock:
        order = Order.query.get(order_id)
        if not order:
            create_log(None, order_id, "Hata", "Sipariş bulunamadı.")
            print(f"Sipariş bulunamadı: {order_id}")
            return

        product = Product.query.get(order.ProductID)
        if not product or order.Quantity > product.Stock:
            create_log(order.CustomerID, order_id, "Hata", "Stok yetersiz.")
            print(f"Stok yetersiz veya ürün bulunamadı: {order_id}")
            return

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
        db.session.commit()
        create_log(order.CustomerID, order_id, "Bilgilendirme", "Sipariş onaylandı.")
        print(f"Sipariş onaylandı: {order_id}")

# Ürün stok güncelleme fonksiyonu
def process_update_stock(product_id, new_stock):
    with lock:  # Kilit al
        product = Product.query.get(product_id)
        if product:
            product.Stock = new_stock
            db.session.commit()
            create_log(None, None, "Bilgilendirme", f"Stok güncellendi: {product.ProductName}")

# Ürün silme fonksiyonu
def process_delete_product(product_id):
    with lock:  # Kilit al
        product = Product.query.get(product_id)
        if product:
            db.session.delete(product)
            db.session.commit()
            create_log(None, None, "Bilgilendirme", f"Ürün silindi: {product.ProductName}")

# Yeni ürün ekleme fonksiyonu
def process_add_product(product_name, stock, price):
    with lock:  # Kilit al
        new_product = Product(
            ProductName=product_name,
            Stock=stock,
            Price=price
        )
        db.session.add(new_product)
        db.session.commit()
        create_log(None, None, "Bilgilendirme", f"Yeni ürün eklendi: {product_name}")



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
    orders = db.session.query(Order.OrderDate, Product.ProductName, Order.TotalPrice).join(
        Product, Product.ProductID == Order.ProductID
    ).filter(Order.CustomerID == customer_id).all()
    confirmed_orders = db.session.query(ConfirmedOrder.OrderDate, Product.ProductName, ConfirmedOrder.TotalPrice).join(
        Product, Product.ProductID == ConfirmedOrder.ProductID
    ).filter(ConfirmedOrder.CustomerID == customer_id).all()
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
@app.route('/yenimusteri', methods=['GET'])
def generate_customers():
    import random

    # Rastgele müşteri isimleri
    names = [
        "Ahmet", "Mehmet", "Ali", "Veli", "Ayşe", "Fatma", "Zeynep", "Elif", 
        "Hüseyin", "Hasan", "Hülya", "Emre", "İsmail", "Yasemin", "Cem"
    ]

    # Bağımlı tabloları temizleme (ConfirmedOrders ve Orders)
    ConfirmedOrder.query.delete()
    Order.query.delete()

    # Var olan tüm müşterileri sil
    Customer.query.delete()

    # 5 ile 10 arasında rastgele müşteri sayısı oluştur
    customer_count = random.randint(5, 10)

    # Yeni müşterileri oluştur
    customers = []
    for _ in range(customer_count):
        name = random.choice(names)
        budget = random.uniform(500, 3000)  # 500 ile 3000 arasında rastgele bütçe
        customer = Customer(
            CustomerName=name,
            Password="1234",  # Şifre 1234 olarak ayarlanıyor
            Budget=round(budget, 2),
            CustomerType="Standard",  # Varsayılan "Standard"
            TotalSpent=0.0
        )
        customers.append(customer)

    # Rastgele 2 müşteriyi premium olarak ayarla
    premium_customers = random.sample(customers, k=2)
    for customer in premium_customers:
        customer.CustomerType = "Premium"

    # Yeni müşterileri veritabanına ekle
    db.session.bulk_save_objects(customers)
    db.session.commit()

    return "Yeni müşteriler başarıyla oluşturuldu!"


@app.route('/order', methods=['POST'])
def place_order():
    customer_id = session.get('customer_id')
    if not customer_id:
        return redirect(url_for('login_page'))

    product_ids = request.form.getlist('product_ids')
    quantities = request.form.getlist('quantities')

    # Process order without threads
    process_order_without_thread(customer_id, product_ids, quantities)

    return redirect(url_for('index'))

@app.route('/refreshOrders', methods=['GET'])
def refresh_orders():
    orders = Order.query.all()
    for order in orders:
        customer = Customer.query.get(order.CustomerID)
        order.priority_score = calculate_priority(order, customer)
    return redirect(url_for('order_operations'))




@app.route('/approveAllOrders', methods=['POST'])
def approve_all_orders_route():
    def approve_all_in_thread():
        with app.app_context():  # Flask uygulama bağlamı oluştur
            try:
                approve_all_orders()  # Tüm siparişleri işleme al
            except Exception as e:
                print(f"Hata: {e}")

    # Thread'i başlat
    thread = Thread(target=approve_all_in_thread)
    thread.start()
    thread.join()

    return redirect(url_for('order_operations'))

@app.route('/approveOrder', methods=['POST'])
def approve_order():
    order_id = request.form.get('order_id')  # Formdan order_id alın
    if not order_id:  # Eğer order_id alınmazsa hata mesajı dön
        return "Sipariş ID eksik!", 400

    def approve_in_thread(order_id):
        with app.app_context():  # Flask uygulama bağlamı oluştur
            try:
                process_approve_order(order_id)  # Siparişi işleme al
            except Exception as e:
                print(f"Hata: {e}")

    # Thread'i başlat
    thread = Thread(target=approve_in_thread, args=(order_id,))
    thread.start()
    thread.join()

    return redirect(url_for('order_operations'))





@app.route('/deleteProduct', methods=['POST'])
def delete_product():
    product_id = request.form['product_id']
    product = Product.query.get(product_id)
    if product:
        db.session.delete(product)
        db.session.commit()
        create_log(None, None, "Bilgilendirme", f"Ürün silindi: {product.ProductName}")
    return redirect(url_for('product_operations'))

@app.route('/updateStock', methods=['POST'])
def update_stock():
    product_id = request.form['product_id']
    new_stock = int(request.form['new_stock'])

    product = Product.query.get(product_id)
    if product:
        product.Stock = new_stock
        db.session.commit()
        create_log(None, None, "Bilgilendirme", f"Stok güncellendi: {product.ProductName}")
    return redirect(url_for('product_operations'))

@app.route('/addProduct', methods=['POST'])
def add_product():
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
    create_log(None, None, "Bilgilendirme", f"Yeni ürün eklendi: {product_name}")
    return redirect(url_for('product_operations'))



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
