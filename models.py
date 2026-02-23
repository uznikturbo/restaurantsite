from datetime import datetime, timezone
from enum import Enum

from flask_login import UserMixin

from extensions import db


class OrderStatus(Enum):
    new = "new"
    cooking = "cooking"
    ready = "ready"
    delivered = "delivered"
    cancelled = "cancelled"


class OrderType(Enum):
    dine_in = "dine_in"
    takeaway = "takeaway"
    delivery = "delivery"


class PaymentStatus(Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    username = db.Column(db.String(50), unique=True)
    phone = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    orders = db.relationship("Order", back_populates="user", cascade="all, delete-orphan")
    reservations = db.relationship("Reservation", back_populates="user", cascade="all, delete-orphan")
    cart_items = db.relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    ratings = db.relationship("ProductRating", back_populates="user", cascade="all, delete-orphan")


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    products = db.relationship("Product", back_populates="category")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(400))
    price = db.Column(db.Numeric(10, 2), nullable=False)
    rating = db.Column(db.Numeric(10, 1), nullable=False, default=0)

    weight = db.Column(db.Integer)
    calories = db.Column(db.Integer)
    cooking_time = db.Column(db.Integer)
    ingredients = db.Column(db.Text)

    is_available = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)

    image_url = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    category = db.relationship("Category", back_populates="products")

    order_items = db.relationship("OrderItem", back_populates="product")
    ratings = db.relationship("ProductRating", back_populates="product", cascade="all, delete-orphan")


class ProductRating(db.Model):
    __tablename__ = "product_ratings"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="cascade"), nullable=False)
    value = db.Column(db.Numeric(2, 1), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    product = db.relationship("Product", back_populates="ratings")
    user = db.relationship("User", back_populates="ratings")

    __table_args__ = (
        db.UniqueConstraint("product_id", "user_id", name="uix_product_user_rating"),
    )


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, default=1)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="cascade"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="cascade"), nullable=False)

    user = db.relationship("User", back_populates="cart_items")
    product = db.relationship("Product")

    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uix_user_product"),
    )


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.new, nullable=False)
    order_type = db.Column(db.Enum(OrderType), nullable=False)
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    delivery_address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    comment = db.Column(db.Text)
    kitchen_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="cascade"), nullable=False)
    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="cascade"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="set null"), nullable=True)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")


class Table(db.Model):
    __tablename__ = "tables"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    seats = db.Column(db.Integer, nullable=False)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    type = db.Column(db.String(30), nullable=False)
    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)

    reservations = db.relationship("Reservation", back_populates="table")


class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    reserved_at = db.Column(db.DateTime, nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default="active")
    phone = db.Column(db.String(30), nullable=False)
    comment = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="cascade"))
    table_id = db.Column(db.Integer, db.ForeignKey("tables.id"))

    user = db.relationship("User", back_populates="reservations")
    table = db.relationship("Table", back_populates="reservations")