from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator


# Create your models here.
class User(AbstractUser):
    email = models.EmailField(
        "Адрес электронной почты",
        max_length=254,
        unique=True
    )

    username = models.CharField(
        "Уникальный юзернейм",
        max_length=150,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[\w.@+-]+$",
                message=(
                    "Username должен содержать только латинские буквы, "
                    "цифры, знаки @ + - ."
                ),
                code="invalid_username",
            ),
        ],
    )

    first_name = models.CharField(
        "Имя",
        max_length=150,
    )

    last_name = models.CharField(
        "Фамилия",
        max_length=150,
    )

    image = models.ImageField(
        upload_to="users/images/", null=True, default=None
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
