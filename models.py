from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Customer(db.Model):
    __tablename__ = 'Customers'
    CustomerID = db.Column(db.Integer, primary_key=True)
    CustomerName = db.Column(db.String(50))
    Password = db.Column(db.String(256))
    Budget = db.Column(db.Float)
    CustomerType = db.Column(db.Enum('Premium', 'Standard'))
    TotalSpent = db.Column(db.Float, default=0)

class Admin(db.Model):
    __tablename__ = 'Admins'
    AdminID = db.Column(db.Integer, primary_key=True)
    AdminName = db.Column(db.String(50))
    Password = db.Column(db.String(256))

class Product(db.Model):
    __tablename__ = 'Products'
    ProductID = db.Column(db.Integer, primary_key=True)
    ProductName = db.Column(db.String(50))
    Stock = db.Column(db.Integer)
    Price = db.Column(db.Float)
