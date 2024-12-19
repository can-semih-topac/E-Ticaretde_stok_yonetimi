from flask_sqlalchemy import SQLAlchemy
from datetime import datetime  # datetime modülünü içe aktarın
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
    OrderDate = db.Column(db.DateTime, default=datetime.utcnow)  # OrderDate alanı eklendi

    Customer = db.relationship('Customer', backref=db.backref('orders', lazy=True))
    Product = db.relationship('Product', backref=db.backref('orders', lazy=True))

class ConfirmedOrder(db.Model):
    __tablename__ = 'ConfirmedOrders'
    OrderID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    CustomerID = db.Column(db.Integer, db.ForeignKey('Customers.CustomerID'), nullable=False)
    ProductID = db.Column(db.Integer, db.ForeignKey('Products.ProductID'), nullable=False)
    Quantity = db.Column(db.Integer, nullable=False)
    TotalPrice = db.Column(db.Float, nullable=False)
    OrderDate = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', backref='confirmed_orders', lazy=True)
    product = db.relationship('Product', backref='confirmed_orders', lazy=True)