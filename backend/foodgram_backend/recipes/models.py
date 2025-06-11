from django.contrib.auth import get_user_model
from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import CheckConstraint, Q, F, UniqueConstraint

User = get_user_model()


class Follow(models.Model):
    user = models.ForeignKey(
        User,
        related_name="follower",
        on_delete=models.CASCADE,
        verbose_name="Тот, кто подписывается",
        help_text="Указывает на пользователя, который подписывается",
    )
    following = models.ForeignKey(
        User,
        related_name="following",
        on_delete=models.CASCADE,
        verbose_name="Автор",
        help_text="Указывает на автора, на которого подписался пользователь.",
    )

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        constraints = (
            UniqueConstraint(
                fields=("user", "following"),
                name="get_unique_follow",
            ),
            CheckConstraint(
                check=~Q(user=F("following")),
                name="check_self_follow",
            ),
        )

    def __str__(self):
        return f"{self.user.username} подписался на {self.following.username}"


class Ingredient(models.Model):
    class Measurment(models.TextChoices):
        KG = "г"
        ML = "мл"
        SHT = "шт"
        TeaSpoon = "ч. л."
        TableSpoon = "ст. л."
        DROP = "капля"
        JAR = "банка"
        PIECE = "кусок"
        HANDFUL = "горсть"
        SPRIG = "веточка"
        PINCH = "щепотка"
        GLASS = "стакан"

    name = models.CharField(
        verbose_name="Название ингредиента",
    )
    measurment = models.CharField(
        choices=Measurment.choices, verbose_name="Единица измерения"
    )

    class Meta:
        verbose_name = "Ингредиент"
        verbose_name_plural = "Ингредиенты"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["name", "measurment"], name="unique_ingredient"
            )
        ]


class Recipe(models.Model):
    author = models.ForeignKey(
        User,
        related_name="recipes",
        on_delete=models.CASCADE,
        verbose_name="Автор рецепта",
    )

    name = models.CharField(max_length=256, verbose_name="Название")

    image = models.ImageField(upload_to="recipes/images/", null=False)

    description = models.TextField(verbose_name="Описание рецепта")

    ingredients = models.ManyToManyField(
        Ingredient, through="AmountIngredientInRecipe"
    )

    cookingTime = models.IntegerField(
        validators=[
            MinValueValidator(
                1, "Время приготовления не может быть меньше 1 минуты"
            )
        ],
        verbose_name="Время приготовления (в минутах)",
    )

    class Meta:
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"
        ordering = ["-id"]


class AmountIngredientInRecipe(models.Model):
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, verbose_name="Рецепт"
    )
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.CASCADE, verbose_name="Ингредиент"
    )

    amount = models.PositiveIntegerField(
        validators=[
            MinValueValidator(
                1, "Количество ингредиента не должго быть меньше 1"
            )
        ],
        verbose_name="Количество ингредиента",
    )

    class Meta:
        verbose_name = "Ингредиент в рецепте"
        verbose_name_plural = "Ингредиенты в рецептах"
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"],
                name="unique_recipe_ingredient",
            )
        ]

    def __str__(self):
        return (
            f"{self.ingredient.name} - "
            f"{self.amount} {self.ingredient.measurment}"
        )


class UserRecipeRelation(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
        verbose_name="Пользователь",
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
        verbose_name="Рецепт",
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.user.username} - {self.recipe.name}"


class UserFavorite(UserRecipeRelation):
    class Meta:
        verbose_name = "Избранный рецепт"
        verbose_name_plural = "Избранные рецепты"
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "user"], name="unique_recipe_user"
            )
        ]


class WishList(UserRecipeRelation):
    class Meta:
        verbose_name = "Список покупок"
        verbose_name_plural = "Списки покупок"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recipe"], name="unique_shopping_cart"
            )
        ]
