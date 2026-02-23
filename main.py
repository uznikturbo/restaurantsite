import base64
import hashlib
import json
import os
import uuid
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

import crud
from extensions import login_manager
from forms import (
    AddProductForm,
    AddToCartForm,
    LoginForm,
    OrderForm,
    OrderStatusForm,
    RatingForm,
    RegisterForm,
    RemoveCartForm,
    ReservationForm,
    ToggleAdminForm,
    ToggleProductForm,
    UpdateCartForm,
)
from models import OrderStatus, OrderType, PaymentStatus
from utils import (
    LIQPAY_PRIVATE_KEY,
    LIQPAY_PUBLIC_KEY,
    SERVER_URL,
    UPLOAD,
    allowed_file,
    verify_liqpay_signature,
)

load_dotenv()

main_bp = Blueprint("main", __name__)

@login_manager.user_loader
def load_user(user_id):
    return crud.get_user_by_id(user_id)

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return func(*args, **kwargs)
    return wrapper

# ── Public routes ──────────────────────────────────────────────────────────────

@main_bp.route("/")
def home():
    return render_template("index.html")

@main_bp.route("/menu")
def menu():
    products = crud.get_all_products()
    return render_template("menu.html", products=products)

@main_bp.route("/details")
def details():
    return render_template("details.html")

@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.menu"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        if crud.get_user_by_email(email):
            flash("Email уже существует", "error")
            return redirect(url_for("main.register"))

        crud.create_user(email, generate_password_hash(form.password.data))
        flash("Успешная регистрация", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html", form=form)

@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.menu"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = crud.get_user_by_email(email)
        
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash("Вы успешно вошли", "success")
            return redirect(url_for("main.menu"))

        flash("Неверные учетные данные. Попробуйте снова!", "error")

    return render_template("login.html", form=form)

@main_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.menu"))

@main_bp.route("/profile")
@login_required
def profile():
    orders = crud.get_user_orders(current_user.id)
    reservations = crud.get_user_reservations(current_user.id)
    return render_template("profile.html", user=current_user, orders=orders, reservations=reservations)

# ── Product / position ─────────────────────────────────────────────────────────

@main_bp.route("/position/<int:product_id>")
def position(product_id):
    product = crud.get_product(product_id)
    if not product or product.is_deleted:
        abort(404)
        
    rating_form = RatingForm()
    add_to_cart_form = AddToCartForm()
    
    return render_template(
        "position.html", 
        position=product, 
        rating_form=rating_form, 
        add_to_cart_form=add_to_cart_form
    )

@main_bp.route("/position/<int:product_id>/rating", methods=["POST"])
@login_required
def add_rating(product_id):
    product = crud.get_product(product_id)
    if not product or product.is_deleted:
        abort(404)

    form = RatingForm()
    if form.validate_on_submit():
        crud.add_or_update_rating(product_id=product_id, user_id=current_user.id, value=form.rating.data)
        flash("Оценка сохранена", "success")
    else:
        flash("Некорректное значение рейтинга", "error")

    return redirect(url_for("main.position", product_id=product_id))

# ── Cart ───────────────────────────────────────────────────────────────────────

@main_bp.route("/cart")
@login_required
def cart():
    items = crud.get_cart_items(current_user.id)
    update_form = UpdateCartForm()
    remove_form = RemoveCartForm()
    order_form = OrderForm()
    
    return render_template(
        "cart.html", 
        items=items, 
        update_form=update_form, 
        remove_form=remove_form, 
        order_form=order_form
    )

@main_bp.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    form = AddToCartForm()
    if form.validate_on_submit():
        product = crud.get_product(product_id)
        if not product or product.is_deleted or not product.is_available:
            abort(404)
        crud.add_to_cart(current_user.id, product_id)
        flash("Товар добавлен в корзину", "success")
    return redirect(url_for("main.cart"))

@main_bp.route("/cart/update/<int:item_id>", methods=["POST"])
@login_required
def update_cart(item_id):
    item = crud.get_cart_item_by_id(item_id)
    if not item or item.user_id != current_user.id:
        abort(403)
        
    form = UpdateCartForm()
    if form.validate_on_submit():
        crud.update_cart_item(item, form.quantity.data)
    return redirect(url_for("main.cart"))

@main_bp.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_from_cart(item_id):
    item = crud.get_cart_item_by_id(item_id)
    if not item or item.user_id != current_user.id:
        abort(403)
        
    form = RemoveCartForm()
    if form.validate_on_submit():
        crud.remove_cart_item(item)
    return redirect(url_for("main.cart"))

# ── Orders / LiqPay ────────────────────────────────────────────────────────────

@main_bp.route("/order/create", methods=["POST"])
@login_required
def create_order():
    form = OrderForm()
    
    if not form.validate_on_submit():
        flash("Проверьте правильность заполнения данных заказа", "error")
        return redirect(url_for("main.cart"))

    items = crud.get_cart_items(current_user.id)
    if not items:
        flash("Корзина пуста", "warning")
        return redirect(url_for("main.cart"))

    order_type = OrderType(form.order_type.data)
    total = sum(i.product.price * i.quantity for i in items)

    order = crud.create_order(
        user_id=current_user.id,
        total=total,
        order_type=order_type,
        phone=form.phone.data.strip(),
        address=form.address.data.strip() if form.address.data else "",
        payment_status=PaymentStatus.pending,
        status=OrderStatus.new,
    )

    for item in items:
        crud.add_order_item(order.id, item)

    crud.clear_cart(current_user.id)
    crud.commit()

    liqpay_data = {
        "public_key": LIQPAY_PUBLIC_KEY,
        "version": "3",
        "action": "pay",
        "amount": str(total),
        "currency": "UAH",
        "description": f"Оплата заказа #{order.id}",
        "order_id": f"ORDER_{order.id}",
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

    return render_template("liqpay_redirect.html", data_b64=data_b64, signature=signature)

@main_bp.route("/liqpay_order_callback", methods=["POST"])
def liqpay_order_callback():
    data_b64 = request.form.get("data")
    signature = request.form.get("signature")

    if not data_b64 or not signature:
        current_app.logger.error("Missing data or signature in callback")
        return "Missing data", 400

    if not verify_liqpay_signature(data_b64, signature):
        current_app.logger.error("Invalid signature in callback")
        return "Invalid signature", 400

    try:
        data = json.loads(base64.b64decode(data_b64).decode("utf-8"))

        received_order_id = data.get("order_id")
        status = data.get("status")

        if not received_order_id:
            return "Missing order_id", 400

        try:
            order_id = int(received_order_id.split("_")[1])
        except (IndexError, ValueError):
            return "Invalid order_id format", 400

        order = crud.get_order(order_id)
        if not order:
            return "Order not found", 404

        if order.payment_status != PaymentStatus.pending:
            return "OK", 200

        if status in ("success", "sandbox"):
            crud.update_payment_status(order, PaymentStatus.paid)
            current_app.logger.info(f"Order {order_id} marked as paid")
        elif status in ("failure", "error", "reversed"):
            crud.update_payment_status(order, PaymentStatus.failed)
            current_app.logger.warning(f"Order {order_id} payment failed: {status}")
        else:
            current_app.logger.info(f"Order {order_id} intermediate status: {status}")

        return "OK", 200

    except Exception as e:
        current_app.logger.error(f"Error processing LiqPay callback: {e}")
        crud.rollback()
        return "Error processing callback", 500

@main_bp.route("/order_result/<int:order_id>")
@login_required
def order_result(order_id):
    order = crud.get_order(order_id)
    if not order:
        abort(404)
    if order.user_id != current_user.id:
        abort(403)

    if order.payment_status == PaymentStatus.paid:
        return redirect(url_for("main.order_success", order_id=order_id))
    elif order.payment_status == PaymentStatus.failed:
        flash("Оплата не прошла. Попробуйте еще раз или выберите другой способ оплаты.", "error")
    else:
        flash("Обработка платежа... Проверьте статус заказа через несколько минут.", "info")

    return redirect(url_for("main.profile"))

@main_bp.route("/order_success/<int:order_id>")
@login_required
def order_success(order_id):
    order = crud.get_order(order_id)
    if not order:
        abort(404)
    if order.user_id != current_user.id:
        abort(403)
    return render_template("order_success.html", order=order)

# ── Reservations ───────────────────────────────────────────────────────────────

@main_bp.route("/book")
def book():
    tables = crud.get_all_tables()
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
    
    reservation_form = ReservationForm()
    return render_template("book.html", tables_data=tables_data, form=reservation_form)

@main_bp.route("/reservation/create", methods=["POST"])
@login_required
def create_reservation():
    form = ReservationForm()
    
    if not form.validate_on_submit():
        flash("Ошибка в данных бронирования", "error")
        return redirect(url_for("main.book"))

    table = crud.get_table(form.table_id.data)
    if not table:
        flash("Столик не найден", "error")
        return redirect(url_for("main.book"))

    crud.create_reservation(
        user_id=current_user.id,
        table_id=table.id,
        reserved_at=form.reserved_at.data,
        guests=int(form.guests.data),
        phone=form.phone.data.strip(),
        comment=form.comment.data.strip() if form.comment.data else None,
    )
    crud.set_table_availability(table, is_available=False)

    flash("Столик успешно забронирован!", "success")
    return redirect(url_for("main.profile"))

# ── Admin ──────────────────────────────────────────────────────────────────────

@main_bp.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    return render_template(
        "admin/dashboard.html",
        orders_count=crud.count_orders(),
        users_count=crud.count_users(),
        products_count=crud.count_products(),
    )

@main_bp.route("/admin/orders")
@login_required
@admin_required
def admin_orders():
    orders = crud.get_all_orders()
    status_form = OrderStatusForm()
    return render_template("admin/orders.html", orders=orders, status_form=status_form)

@main_bp.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@login_required
@admin_required
def admin_change_order_status(order_id):
    order = crud.get_order(order_id)
    if not order:
        abort(404)

    form = OrderStatusForm()
    if form.validate_on_submit():
        new_status = OrderStatus(form.status.data)
        crud.update_order_status(order, new_status)
        flash("Статус заказа обновлен", "success")
    else:
        flash("Неверный статус", "error")
        
    return redirect(url_for("main.admin_orders"))

@main_bp.route("/admin/products")
@login_required
@admin_required
def admin_products():
    products = crud.get_all_products()
    categories = crud.get_all_categories()
    add_form = AddProductForm(categories=categories)
    toggle_form = ToggleProductForm()
    
    return render_template(
        "admin/products.html", 
        products=products, 
        categories=categories,
        add_form=add_form,
        toggle_form=toggle_form
    )

@main_bp.route("/admin/products/add", methods=["POST"])
@login_required
@admin_required
def admin_add_product():
    categories = crud.get_all_categories()
    form = AddProductForm(categories=categories)

    if form.validate_on_submit():
        image_url = form.image_url.data or None
        image_file = form.image.data 

        if image_file and allowed_file(image_file.filename):
            ext = image_file.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(UPLOAD, filename)
            image_file.save(filepath)
            image_url = filepath

        category_id = form.category_id.data if form.category_id.data != 0 else None

        crud.add_product(
            name=form.name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            price=form.price.data,
            weight=form.weight.data,
            calories=form.calories.data,
            cooking_time=form.cooking_time.data,
            ingredients=form.ingredients.data,
            category_id=category_id,
            image_url=image_url,
        )
        flash("Товар добавлен", "success")
    else:
        flash("Ошибка при добавлении товара. Проверьте данные.", "error")
        
    return redirect(url_for("main.admin_products"))

@main_bp.route("/admin/products/<int:product_id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_product(product_id):
    form = ToggleProductForm()
    if form.validate_on_submit():
        product = crud.get_product(product_id)
        if not product:
            abort(404)
        crud.toggle_product_deleted(product)
        flash("Статус товара изменен", "info")
    return redirect(url_for("main.admin_products"))

@main_bp.route("/admin/users")
@login_required
@admin_required
def admin_users():
    users = crud.get_all_users()
    toggle_admin_form = ToggleAdminForm()
    return render_template("admin/users.html", users=users, form=toggle_admin_form)

@main_bp.route("/admin/users/<int:user_id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def admin_toggle_user_admin(user_id):
    form = ToggleAdminForm()
    if form.validate_on_submit():
        if user_id == current_user.id:
            flash("Нельзя изменить собственную роль", "warning")
            return redirect(url_for("main.admin_users"))

        user = crud.get_user_by_id(user_id)
        if not user:
            abort(404)

        crud.toggle_user_admin(user)
        flash("Роль пользователя изменена", "success")
        
    return redirect(url_for("main.admin_users"))

@main_bp.route("/admin/tables")
@login_required
@admin_required
def admin_tables():
    tables = crud.get_all_tables()
    return render_template("admin/tables.html", tables=tables)

@main_bp.route("/admin/tables/save", methods=["POST"])
@login_required
@admin_required
def admin_save_tables():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    tables = data.get("tables", [])
    required_fields = {"number", "type", "x", "y"}

    for t in tables:
        if not required_fields.issubset(t.keys()):
            return jsonify({"success": False, "error": "Missing table fields"}), 400

    try:
        crud.replace_all_tables(tables)
        return jsonify({"success": True})
    except Exception as e:
        crud.rollback()
        current_app.logger.error(f"Error saving tables: {e}")
        return jsonify({"success": False, "error": "Internal error"}), 500

@main_bp.route("/admin/tables/update/position", methods=["POST"])
@login_required
@admin_required
def update_table_position():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    table_id = data.get("id")
    try:
        x = int(data.get("x"))
        y = int(data.get("y"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates"}), 400

    table = crud.get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found"}), 404

    crud.update_table_position(table, x, y)
    return jsonify({"status": "ok"})