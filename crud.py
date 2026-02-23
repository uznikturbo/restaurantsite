from decimal import Decimal

from sqlalchemy import func

from models import *

# ── Users ──────────────────────────────────────────────────────────────────────

def get_user_by_id(user_id: int):
    return db.session.get(User, user_id)


def get_user_by_email(email: str):
    return User.query.filter_by(email=email).first()


def create_user(email: str, password_hash: str, is_admin: bool = False):
    user = User(email=email, password=password_hash, is_admin=is_admin)
    db.session.add(user)
    db.session.commit()
    return user


def get_all_users():
    return User.query.order_by(User.created_at.desc()).all()


def toggle_user_admin(user: User):
    user.is_admin = not user.is_admin
    db.session.commit()
    return user


def count_users():
    return User.query.count()


# ── Products ───────────────────────────────────────────────────────────────────

def get_available_products():
    return Product.query.filter_by(is_available=True, is_deleted=False).all()


def get_product(product_id: int):
    return db.session.get(Product, product_id)


def get_all_products():
    return Product.query.order_by(Product.created_at.desc()).all()


def get_all_categories():
    return Category.query.all()


def count_active_products():
    return Product.query.filter_by(is_deleted=False).count()


# Alias used in dashboard
count_products = count_active_products


def add_product(name: str, description: str, price, weight, calories,
                cooking_time, ingredients, category_id, image_url,
                is_available: bool = True):
    product = Product(
        name=name,
        description=description,
        price=price,
        weight=weight,
        calories=calories,
        cooking_time=cooking_time,
        ingredients=ingredients,
        category_id=category_id,
        image_url=image_url,
        is_available=is_available,
        rating=0,
    )
    db.session.add(product)
    db.session.commit()
    return product


def toggle_product_deleted(product: Product):
    product.is_deleted = not product.is_deleted
    db.session.commit()
    return product


# ── Ratings ────────────────────────────────────────────────────────────────────

def add_or_update_rating(product_id: int, user_id: int, value):
    value = Decimal(str(value))
    if not (Decimal("1") <= value <= Decimal("5")):
        raise ValueError("Rating must be between 1 and 5")

    rating = ProductRating.query.filter_by(
        product_id=product_id,
        user_id=user_id,
    ).first()

    if rating:
        rating.value = value
    else:
        rating = ProductRating(product_id=product_id, user_id=user_id, value=value)
        db.session.add(rating)

    db.session.flush()
    _recalculate_product_rating(product_id)
    db.session.commit()
    return rating


def get_product_ratings(product_id: int):
    return ProductRating.query.filter_by(product_id=product_id).all()


def get_user_rating(product_id: int, user_id: int):
    return ProductRating.query.filter_by(
        product_id=product_id,
        user_id=user_id,
    ).first()


def delete_rating(product_id: int, user_id: int):
    rating = get_user_rating(product_id, user_id)
    if not rating:
        return None

    db.session.delete(rating)
    db.session.flush()
    _recalculate_product_rating(product_id)
    db.session.commit()
    return True


def _recalculate_product_rating(product_id: int):
    avg = db.session.query(
        func.avg(ProductRating.value)
    ).filter_by(product_id=product_id).scalar()

    product = db.session.get(Product, product_id)
    product.rating = round(avg or 0, 1)


# ── Cart ───────────────────────────────────────────────────────────────────────

def get_cart_items(user_id: int):
    return CartItem.query.filter_by(user_id=user_id).all()


def get_cart_item_by_id(item_id: int):
    return db.session.get(CartItem, item_id)


def get_cart_item(user_id: int, product_id: int):
    return CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()


def add_to_cart(user_id: int, product_id: int):
    item = get_cart_item(user_id, product_id)
    if item:
        item.quantity += 1
    else:
        item = CartItem(user_id=user_id, product_id=product_id, quantity=1)
        db.session.add(item)
    db.session.commit()
    return item


def update_cart_item(item: CartItem, quantity: int):
    item.quantity = max(1, quantity)
    db.session.commit()


def remove_cart_item(item: CartItem):
    db.session.delete(item)
    db.session.commit()


def clear_cart(user_id: int):
    CartItem.query.filter_by(user_id=user_id).delete()
    db.session.commit()


# ── Orders ─────────────────────────────────────────────────────────────────────

def create_order(user_id: int, total, order_type, phone: str,
                 address: str, payment_status, status):
    order = Order(
        user_id=user_id,
        total=total,
        order_type=order_type,
        phone=phone,
        delivery_address=address,
        payment_status=payment_status,
        status=status,
    )
    db.session.add(order)
    db.session.flush()
    return order


def add_order_item(order_id: int, cart_item: CartItem):
    """Create an OrderItem snapshot from a CartItem."""
    item = OrderItem(
        order_id=order_id,
        product_id=cart_item.product_id,
        product_name=cart_item.product.name,
        price=cart_item.product.price,
        quantity=cart_item.quantity,
    )
    db.session.add(item)


def get_order(order_id: int):
    return db.session.get(Order, order_id)


def get_user_orders(user_id: int):
    return Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()


def get_all_orders():
    return Order.query.order_by(Order.created_at.desc()).all()


def count_orders():
    return Order.query.count()


def update_order_status(order: Order, status: OrderStatus):
    order.status = status
    db.session.commit()


def update_payment_status(order: Order, payment_status: PaymentStatus):
    order.payment_status = payment_status
    db.session.commit()


# ── Tables ─────────────────────────────────────────────────────────────────────

SEATS_BY_TYPE = {"round": 2, "square": 4}
DEFAULT_SEATS = 6


def get_all_tables():
    return Table.query.all()


def get_table(table_id: int):
    return db.session.get(Table, table_id)


def replace_all_tables(tables_data: list):
    """Delete existing tables and insert new ones from the provided list."""
    Table.query.delete()
    for data in tables_data:
        table = Table(
            number=data["number"],
            type=data["type"],
            seats=SEATS_BY_TYPE.get(data["type"], DEFAULT_SEATS),
            is_available=True,
            x=data["x"],
            y=data["y"],
        )
        db.session.add(table)
    db.session.commit()


def update_table_position(table: Table, x: int, y: int):
    table.x = x
    table.y = y
    db.session.commit()


def set_table_availability(table: Table, is_available: bool):
    table.is_available = is_available
    db.session.commit()


# ── Reservations ───────────────────────────────────────────────────────────────

def create_reservation(user_id: int, table_id: int, reserved_at,
                       guests: int, phone: str, comment: str = None):
    reservation = Reservation(
        user_id=user_id,
        table_id=table_id,
        reserved_at=reserved_at,
        guests=guests,
        status="active",
        phone=phone,
        comment=comment,
    )
    db.session.add(reservation)
    db.session.commit()
    return reservation


def get_user_reservations(user_id: int):
    return Reservation.query.filter_by(user_id=user_id).order_by(Reservation.created_at.desc()).all()


# ── Helpers ────────────────────────────────────────────────────────────────────

def commit():
    db.session.commit()


def rollback():
    db.session.rollback()