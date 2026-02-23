from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    DateTimeLocalField,
    DecimalField,
    EmailField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    TelField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Пароль", validators=[DataRequired(), Length(min=6)])


class RegisterForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Пароль", validators=[DataRequired(), Length(min=6, message="Мінімум 6 символів")])


class AddToCartForm(FlaskForm):
    pass


class UpdateCartForm(FlaskForm):
    quantity = IntegerField("Кількість", validators=[DataRequired(), NumberRange(min=1, max=99)])


class RemoveCartForm(FlaskForm):
    pass


class OrderForm(FlaskForm):
    order_type = SelectField(
        "Тип замовлення",
        choices=[("delivery", "Доставка"), ("takeaway", "Самовивіз"), ("dine_in", "В ресторані")],
        validators=[DataRequired()],
    )
    phone = TelField("Телефон", validators=[DataRequired(), Length(max=20)])
    address = StringField("Адреса", validators=[Optional(), Length(max=500)])


class RatingForm(FlaskForm):
    rating = HiddenField("Рейтинг", validators=[DataRequired()])

    def validate_rating(self, field):
        try:
            val = float(field.data)
            if not (1 <= val <= 5):
                raise ValidationError("Рейтинг має бути від 1 до 5")
        except (ValueError, TypeError):
            raise ValidationError("Некоректне значення рейтингу")


class ReservationForm(FlaskForm):
    table_id = HiddenField("Столик", validators=[DataRequired()])
    reserved_at = DateTimeLocalField(
        "Дата та час",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
    )
    guests = SelectField(
        "Гостей",
        choices=[(str(i), str(i)) for i in range(1, 7)],
        validators=[DataRequired()],
    )
    phone = TelField("Телефон", validators=[DataRequired(), Length(max=30)])
    comment = TextAreaField("Коментар", validators=[Optional(), Length(max=400)])


class AddProductForm(FlaskForm):
    name = StringField("Назва", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Опис", validators=[Optional(), Length(max=400)])
    price = DecimalField("Ціна", validators=[DataRequired(), NumberRange(min=0.01)])
    weight = IntegerField("Вага (г)", validators=[Optional(), NumberRange(min=0)])
    calories = IntegerField("Калорії", validators=[Optional(), NumberRange(min=0)])
    cooking_time = IntegerField("Час (хв)", validators=[Optional(), NumberRange(min=0)])
    ingredients = TextAreaField("Інгредієнти", validators=[Optional()])
    category_id = SelectField("Категорія", coerce=int, validators=[Optional()])
    image_url = StringField("URL зображення", validators=[Optional(), Length(max=2000)])
    image = FileField("Фото", validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp"])])

    def __init__(self, categories=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if categories:
            self.category_id.choices = [(0, "— без категорії —")] + [
                (c.id, c.name) for c in categories
            ]
        else:
            self.category_id.choices = [(0, "— без категорії —")]


class OrderStatusForm(FlaskForm):
    status = SelectField(
        "Статус",
        choices=[
            ("new", "Нове"),
            ("cooking", "Готується"),
            ("ready", "Готово"),
            ("delivered", "Доставлено"),
            ("cancelled", "Скасовано"),
        ],
        validators=[DataRequired()],
    )


class ToggleAdminForm(FlaskForm):
    pass


class ToggleProductForm(FlaskForm):
    pass
