import base64
import hashlib
import json
import os
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.mutable import MutableList
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

LIQPAY_PUBLIC_KEY = os.getenv("LIQPAY_PUBLIC_KEY")
LIQPAY_PRIVATE_KEY = os.getenv("LIQPAY_PRIVATE_KEY")
SERVER_URL = os.getenv("SERVER_URL")

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

UPLOAD = "static/images"
os.makedirs(UPLOAD, exist_ok=True)

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}


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

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship(
        "Order", back_populates="user", cascade="all, delete-orphan"
    )
    reservations = db.relationship(
        "Reservation", back_populates="user", cascade="all, delete-orphan"
    )
    cart_items = db.relationship(
        "CartItem", back_populates="user", cascade="all, delete-orphan"
    )


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
    rating = db.Column(db.Numeric(10, 1), nullable=False)
    ratings = db.Column(MutableList.as_mutable(db.ARRAY(db.Numeric(10, 1))))

    weight = db.Column(db.Integer)
    calories = db.Column(db.Integer)
    cooking_time = db.Column(db.Integer)
    ingredients = db.Column(db.Text)

    is_available = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)

    image_url = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    category = db.relationship("Category", back_populates="products")

    order_items = db.relationship("OrderItem", back_populates="product")


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, default=1)

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="cascade"), nullable=False
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="cascade"), nullable=False
    )

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

    payment_status = db.Column(
        db.Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False
    )

    delivery_address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    comment = db.Column(db.Text)
    kitchen_comment = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="cascade"), nullable=False
    )
    user = db.relationship("User", back_populates="orders")

    items = db.relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)

    product_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="cascade"), nullable=False
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="set null"), nullable=True
    )

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")


class Table(db.Model):
    __tablename__ = "tables"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    seats = db.Column(db.Integer, nullable=False)
    is_available = db.Column(db.Boolean, nullable=False)
    type = db.Column(db.String(30), nullable=False)

    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)


class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)

    reserved_at = db.Column(db.DateTime, nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default="active")
    phone = db.Column(db.String(30), nullable=False)
    comment = db.Column(db.String(400))

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="cascade"))
    table_id = db.Column(db.Integer, db.ForeignKey("tables.id"))

    user = db.relationship("User", back_populates="reservations")
    table = db.relationship("Table")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def verify_liqpay_signature(data_b64, signature):
    if not LIQPAY_PRIVATE_KEY:
        return False

    key_bytes = LIQPAY_PRIVATE_KEY.encode("utf-8")
    data_bytes = data_b64.encode("utf-8")
    expected = base64.b64encode(
        hashlib.sha1(key_bytes + data_bytes + key_bytes).digest()
    ).decode("ascii")
    return expected == signature


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return func(*args, **kwargs)

    return wrapper


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/menu")
def menu():
    products = Product.query.filter_by(is_available=True, is_deleted=False).all()
    return render_template("menu.html", products=products)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("menu"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if User.query.filter_by(email=email).first():
            flash("Email already exists", "error")
            return redirect(url_for("register"))

        if not password or len(password) < 6:
            flash("Password must be at least 6 characters", "error")
            return redirect(url_for("register"))

        new_user = User(
            email=email, password=generate_password_hash(password), is_admin=False
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Successfully created", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("menu"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Successfully logged in", "success")
            return redirect(url_for("menu"))
        flash("Invalid credentials. Try again!", "error")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/profile")
@login_required
def profile():
    orders = (
        Order.query.filter_by(user_id=current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    reservations = (
        Reservation.query.filter_by(user_id=current_user.id)
        .order_by(Reservation.created_at.desc())
        .all()
    )
    return render_template(
        "profile.html", user=current_user, orders=orders, reservations=reservations
    )


@app.route("/position/<int:id>")
def position(id):
    position = db.session.get(Product, id)
    return render_template("position.html", position=position)


@app.route("/position/<int:id>/rating", methods=["POST"])
def add_rating(id):
    position = db.session.get(Product, id)
    if not position.ratings:
        position.ratings = []
    ratings = position.ratings
    ratings.append(Decimal(request.form.get("rating")))
    rating = round(sum(ratings) / Decimal(len(ratings)), 1)
    position.ratings = ratings
    position.rating = rating
    db.session.commit()
    return redirect(url_for("position", id=position.id))


@app.route("/cart")
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    return render_template("cart.html", items=items)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    item = CartItem.query.filter_by(
        user_id=current_user.id,
        product_id=product_id,
    ).first()

    if item:
        item.quantity += 1
    else:
        item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(item)

    db.session.commit()
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_from_cart(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        abort(403)

    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("cart"))


@app.route("/cart/update/<int:item_id>", methods=["POST"])
@login_required
def update_cart(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        abort(403)

    try:
        qty = int(request.form.get("quantity", 1))
    except (ValueError, TypeError):
        qty = 1
    item.quantity = max(1, qty)
    db.session.commit()
    return redirect(url_for("cart"))


@app.route("/order/create", methods=["POST"])
@login_required
def create_order():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash("Cart is empty", "warning")
        return redirect(url_for("cart"))

    try:
        order_type = OrderType(request.form.get("order_type"))
    except Exception:
        flash("Invalid order type", "error")
        return redirect(url_for("cart"))

    phone = request.form.get("phone")
    address = request.form.get("address")

    total = sum(i.product.price * i.quantity for i in items)

    order = Order(
        user_id=current_user.id,
        total=total,
        order_type=order_type,
        phone=phone,
        delivery_address=address,
        payment_status=PaymentStatus.pending,
        status=OrderStatus.new,
    )
    db.session.add(order)
    db.session.flush()

    for item in items:
        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                product_name=item.product.name,
                price=item.product.price,
                quantity=item.quantity,
            )
        )

    CartItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

    order_id = f"ORDER_{order.id}"

    liqpay_data = {
        "public_key": LIQPAY_PUBLIC_KEY,
        "version": "3",
        "action": "pay",
        "amount": str(total),
        "currency": "UAH",
        "description": f"Оплата замовлення #{order.id}",
        "order_id": order_id,
        "sandbox": "1",
        "server_url": f"{SERVER_URL}/liqpay_order_callback",
        "result_url": f"{SERVER_URL}/order_result/{order.id}",
    }

    data_json = json.dumps(liqpay_data)
    data_b64 = base64.b64encode(data_json.encode("utf-8")).decode("utf-8")

    signature = base64.b64encode(
        hashlib.sha1(
            (LIQPAY_PRIVATE_KEY + data_b64 + LIQPAY_PRIVATE_KEY).encode("utf-8")
        ).digest()
    ).decode("utf-8")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Перенаправлення на оплату...</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
            .loader {{ border: 5px solid #f3f3f3; border-top: 5px solid #3498db; 
                        border-radius: 50%; width: 50px; height: 50px; 
                        animation: spin 1s linear infinite; margin: 20px auto; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 
                                100% {{ transform: rotate(360deg); }} }}
        </style>
    </head>
    <body>
        <h2>Перенаправлення на сторінку оплати...</h2>
        <div class="loader"></div>
        <p>Будь ласка, зачекайте...</p>
        <form id="liqpay_form" method="POST" action="https://www.liqpay.ua/api/3/checkout">
            <input type="hidden" name="data" value="{data_b64}" />
            <input type="hidden" name="signature" value="{signature}" />
        </form>
        <script>
            setTimeout(function() {{
                document.getElementById('liqpay_form').submit();
            }}, 1000);
        </script>
    </body>
    </html>
    """
    return html


@app.route("/liqpay_order_callback", methods=["POST"])
def liqpay_order_callback():
    data_b64 = request.form.get("data")
    signature = request.form.get("signature")

    if not data_b64 or not signature:
        app.logger.error("Missing data or signature in callback")
        return "Missing data", 400

    if not verify_liqpay_signature(data_b64, signature):
        app.logger.error("Invalid signature in callback")
        return "Invalid signature", 400

    try:
        data_json = base64.b64decode(data_b64).decode("utf-8")
        data = json.loads(data_json)

        app.logger.info(f"LiqPay callback data: {data}")

        received_order_id = data.get("order_id")
        status = data.get("status")

        if not received_order_id:
            app.logger.error("Missing order_id in callback")
            return "Missing order_id", 400

        try:
            order_id = int(received_order_id.split("_")[1])
        except (IndexError, ValueError):
            app.logger.error(f"Invalid order_id format: {received_order_id}")
            return "Invalid order_id format", 400

        order = db.session.get(Order, order_id)
        if not order:
            app.logger.error(f"Order not found: {order_id}")
            return "Order not found", 404

        app.logger.info(
            f"Processing order {order_id}, current payment_status: {order.payment_status}, LiqPay status: {status}"
        )
        if order.payment_status != PaymentStatus.pending:
            app.logger.info(
                f"Order {order_id} already processed (payment_status: {order.payment_status})"
            )
            return "OK", 200

        if status in ["success", "sandbox"]:
            order.payment_status = PaymentStatus.paid
            db.session.commit()
            app.logger.info(
                f"Order {order_id} payment marked as paid (LiqPay status: {status})"
            )
            return "OK", 200

        elif status in ["failure", "error", "reversed"]:
            order.payment_status = PaymentStatus.failed
            db.session.commit()
            app.logger.warning(f"Order {order_id} payment failed with status: {status}")
            return "FAILED", 200

        else:
            app.logger.info(f"Order {order_id} intermediate status: {status}")
            return "OK", 200

    except Exception as e:
        app.logger.error(f"Error processing callback: {str(e)}")
        db.session.rollback()
        return "Error processing callback", 500


@app.route("/order_result/<int:order_id>")
@login_required
def order_result(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)

    if order.user_id != current_user.id:
        abort(403)

    if order.payment_status == PaymentStatus.paid:
        return redirect(url_for("order_success", order_id=order_id))
    elif order.payment_status == PaymentStatus.failed:
        flash(
            "Оплата не пройшла. Спробуйте ще раз або оберіть інший спосіб оплати.",
            "error",
        )
        return redirect(url_for("profile"))
    else:
        flash(
            "Обробка платежу... Перевірте статус замовлення через кілька хвилин.",
            "info",
        )
        return redirect(url_for("profile"))


@app.route("/order_success/<int:order_id>")
@login_required
def order_success(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)

    if order.user_id != current_user.id:
        abort(403)

    return render_template("order_success.html", order=order)


@app.route("/admin")
@admin_required
def admin_dashboard():
    orders_count = Order.query.count()
    users_count = User.query.count()
    products_count = Product.query.filter_by(is_deleted=False).count()

    return render_template(
        "admin/dashboard.html",
        orders_count=orders_count,
        users_count=users_count,
        products_count=products_count,
    )


@app.route("/admin/orders")
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=orders)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_change_order_status(order_id):
    order = Order.query.get_or_404(order_id)

    try:
        new_status = OrderStatus(request.form.get("status"))
        order.status = new_status
        db.session.commit()
        flash("Статус заказа обновлён", "success")
    except Exception:
        flash("Неверный статус", "error")

    return redirect(url_for("admin_orders"))


@app.route("/admin/products")
@admin_required
def admin_products():
    products = Product.query.order_by(Product.created_at.desc()).all()
    categories = Category.query.all()
    return render_template(
        "admin/products.html",
        products=products,
        categories=categories,
    )


@app.route("/admin/products/add", methods=["POST"])
@admin_required
def admin_add_product():
    image = request.files.get("image")

    image_url = request.form.get("image_url", None)

    if image and allowed_file(image.filename):
        ext = image.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"

        filepath = os.path.join(UPLOAD, filename)
        image.save(filepath)
        image_url = filepath

    product = Product(
        name=request.form.get("name"),
        description=request.form.get("description"),
        price=request.form.get("price"),
        weight=request.form.get("weight"),
        calories=request.form.get("calories"),
        cooking_time=request.form.get("cooking_time"),
        ingredients=request.form.get("ingredients"),
        category_id=request.form.get("category_id"),
        image_url=image_url,
        is_available=True,
    )

    db.session.add(product)
    db.session.commit()
    flash("Товар добавлен", "success")

    return redirect(url_for("admin_products"))


@app.route("/admin/products/<int:product_id>/toggle")
@admin_required
def admin_toggle_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_deleted = not product.is_deleted
    db.session.commit()

    flash("Статус товара изменён", "info")
    return redirect(url_for("admin_products"))


@app.route("/admin/users")
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/<int:user_id>/toggle-admin")
@admin_required
def admin_toggle_user_admin(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("Нельзя изменить себя", "warning")
        return redirect(url_for("admin_users"))

    user.is_admin = not user.is_admin
    db.session.commit()
    flash("Роль пользователя изменена", "success")

    return redirect(url_for("admin_users"))


@app.route("/admin/tables")
def admin_tables():
    tables = Table.query.all()
    return render_template("admin/tables.html", tables=tables)


@app.route("/admin/tables/save", methods=["POST"])
def add_table():
    data = request.get_json()
    tables = data.get("tables", [])

    try:
        Table.query.delete()

        for table_data in tables:
            if table_data["type"] == "round":
                seats = 2
            elif table_data["type"] == "square":
                seats = 4
            else:
                seats = 6

            if str(table_data["id"]).startswith("new_"):
                table = Table(
                    number=table_data["number"],
                    type=table_data["type"],
                    is_available=True,
                    seats=seats,
                    x=table_data["x"],
                    y=table_data["y"],
                )
            else:
                table = Table(
                    number=table_data["number"],
                    type=table_data["type"],
                    x=table_data["x"],
                    y=table_data["y"],
                )
            db.session.add(table)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})


@app.route("/admin/tables/update/position", methods=["POST"])
def update_table_position():
    data = request.json
    table = db.session.get(Table, data.get("id"))
    table.x = data.get("x")
    table.y = data.get("y")
    db.session.commit()
    return {"status": "ok"}


@app.route("/book")
def book():
    tables = Table.query.all()

    tables_data = [
        {
            "id": t.id,
            "number": t.number,
            "type": t.type,
            "seats": t.seats,
            "available": t.is_available,
            "x": t.x,
            "y": t.y,
        }
        for t in tables
    ]
    return render_template("book.html", tables_data=tables_data)


@app.route("/reservation/create", methods=["POST"])
@login_required
def create_reservation():
    table_id = request.form.get("table_id")
    date = request.form.get("date")
    time = request.form.get("time")
    guests = request.form.get("guests")
    phone = request.form.get("phone")
    comment = request.form.get("comment")

    datetime_str = f"{date} {time}"
    reservation_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")

    reservation = Reservation(
        user_id=current_user.id,
        table_id=table_id,
        reserved_at=reservation_datetime,
        guests=guests,
        status="active",
        phone=phone,
        comment=comment,
    )

    table = Table.query.get(table_id)
    table.is_available = False

    db.session.add(reservation)
    db.session.commit()

    flash("Столик успішно забронований!", "success")
    return redirect(url_for("profile"))


@app.route("/details")
def details():
    return render_template("details.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("menu"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
