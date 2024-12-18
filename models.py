from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Customer(db.Model):
    __tablename__ = 'Customers'
    CustomerID = db.Column(db.Integer, primary_key=True)
    CustomerName = db.Column(db.String(50), nullable=False)
    Password = db.Column(db.String(256), nullable=False)  # Şifre güvenliği için hash kullanın
    Budget = db.Column(db.Float, nullable=False, default=0.0)  # Bütçe alanı

class Admin(db.Model):
    __tablename__ = 'Admins'
    AdminID = db.Column(db.Integer, primary_key=True)
    AdminName = db.Column(db.String(50), nullable=False)
    Password = db.Column(db.String(256), nullable=False)

class Product(db.Model):
    __tablename__ = 'Products'
    ProductID = db.Column(db.Integer, primary_key=True)
    ProductName = db.Column(db.String(50), nullable=False)
    Stock = db.Column(db.Integer, nullable=False)
    Price = db.Column(db.Float, nullable=False)

class Order(db.Model):
    __tablename__ = 'Orders'
    OrderID = db.Column(db.Integer, primary_key=True)
    CustomerID = db.Column(db.Integer, db.ForeignKey('Customers.CustomerID'), nullable=False)
    ProductID = db.Column(db.Integer, db.ForeignKey('Products.ProductID'), nullable=False)
    Quantity = db.Column(db.Integer, nullable=False)
    TotalPrice = db.Column(db.Float, nullable=False)
    Customer = db.relationship('Customer', backref=db.backref('orders', lazy=True))
    Product = db.relationship('Product', backref=db.backref('orders', lazy=True))