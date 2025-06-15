import base64
import io
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from djoser.serializers import UserSerializer, UserCreateSerializer
from recipes.models import Ingredient, Recipe, AmountIngredientInRecipe
from django.conf import settings
from PIL import Image

User = get_user_model()


class CustomUserSerializer(UserSerializer):
    avatar = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
            "avatar",
        )

    def get_is_subscribed(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return request.user.follower.filter(following=obj).exists()
        return False

    def get_avatar(self, obj):
        if obj.image:
            return obj.image.url
        return None


class CustomCreateUserSerializer(UserCreateSerializer):
    class Meta:
        model = User
        fields = ("email", "username", "first_name", "last_name", "password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.error_messages["required"] = "Обязательное поле."
            field.error_messages["blank"] = "Обязательное поле."


class CustomUserCreateResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "email")


class IngredientSerializer(serializers.ModelSerializer):
    measurement_unit = serializers.CharField(
        source="measurment", read_only=True
    )

    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")
        read_only_fields = ("id", "name", "measurement_unit")


class AmountIngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source="ingredient.id")
    name = serializers.ReadOnlyField(source="ingredient.name")
    measurement_unit = serializers.ReadOnlyField(
        source="ingredient.measurment"
    )

    class Meta:
        model = AmountIngredientInRecipe
        fields = ("id", "name", "measurement_unit", "amount")


class RecipeIngredientCreateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField(
        min_value=settings.MIN_AMOUNT_VALUE,
        max_value=settings.MAX_AMOUNT_VALUE
    )


class RecipeSerializer(serializers.ModelSerializer):
    author = CustomUserSerializer(read_only=True)
    ingredients = AmountIngredientInRecipeSerializer(
        source="amountingredientinrecipe_set", many=True, read_only=True
    )

    image = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    text = serializers.CharField(source="description")
    cooking_time = serializers.IntegerField(source="cookingTime")

    class Meta:
        model = Recipe
        fields = (
            "id",
            "author",
            "ingredients",
            "is_favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "text",
            "cooking_time",
        )

    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.userfavorite_set.filter(user=request.user).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.wishlist_set.filter(user=request.user).exists()
        return False

    def get_image(self, obj):
        if obj.image:
            return obj.image.url
        return None


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith("data:image"):
            format, imgstr = data.split(";base64,")
            ext = format.split("/")[-1]

            data = ContentFile(base64.b64decode(imgstr), name="temp." + ext)

        return super().to_internal_value(data)


class RecipeCreateSerializer(serializers.ModelSerializer):
    cooking_time = serializers.IntegerField(
        source="cookingTime",
        min_value=settings.MIN_COOKING_TIME,
        max_value=settings.MAX_COOKING_TIME
    )
    ingredients = RecipeIngredientCreateSerializer(many=True, required=True)
    text = serializers.CharField(source="description")
    image = Base64ImageField(required=True)

    class Meta:
        model = Recipe
        fields = ("name", "image", "text", "cooking_time", "ingredients")
        extra_kwargs = {"author": {"read_only": True}}
    
    def _process_ingredients_in_recipe(self, recipe, ingredients):
        if hasattr(recipe, 'amountingredientinrecipe_set'):
            recipe.amountingredientinrecipe_set.all().delete()
        
        ingredient_objects = []
        for ingredient in ingredients:
            ingredient_objects.append(
                AmountIngredientInRecipe(
                    ingredient_id=ingredient["id"],
                    amount=ingredient["amount"],
                    recipe=recipe
                )
            )
        
        AmountIngredientInRecipe.objects.bulk_create(ingredient_objects)

    def to_internal_value(self, data):
        validated_data = super().to_internal_value(data)

        ingredients = data.get("ingredients", [])
        if not ingredients:
            raise serializers.ValidationError(
                {"ingredients": ["Ингредиенты не переданы"]}
            )
        ingredients_serializer = RecipeIngredientCreateSerializer(
            data=ingredients, many=True
        )
        ingredients_serializer.is_valid(raise_exception=True)
        validated_data["ingredients"] = ingredients_serializer.validated_data

        return validated_data

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError("Ингредиенты не переданы")

        all_ingredients = set()
        for ingredient in value:
            ingredient_id = ingredient["id"]
            if ingredient_id in all_ingredients:
                raise serializers.ValidationError("Ингредиент не уникален")
            all_ingredients.add(ingredient_id)

            if not Ingredient.objects.filter(id=ingredient_id).exists():
                raise serializers.ValidationError(
                    f"Ингредиента с {id} id не существует."
                )

        return value

    def create(self, validated_data):
        ingredients = validated_data.pop("ingredients")
        validated_data["author"] = self.context["request"].user
        recipe = Recipe.objects.create(**validated_data)
        self._process_ingredients_in_recipe(recipe, ingredients)
        return recipe
    
    def update(self, instance, validated_data):
        ingredients = validated_data.pop("ingredients", None)

        instance = super().update(instance, validated_data)

        instance.amountingredientinrecipe_set.all().delete()
        self._process_ingredients_in_recipe(instance, ingredients)
        return instance

    def to_representation(self, instance):
        return RecipeSerializer(instance, context=self.context).data


class RecipeForFollowSerializer(serializers.ModelSerializer):
    cooking_time = serializers.IntegerField(source="cookingTime")

    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")


class FollowUserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()
    recipes = RecipeForFollowSerializer(many=True, read_only=True)
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
            "recipes",
            "recipes_count",
            "avatar",
        )

    def get_is_subscribed(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return request.user.follower.filter(following=obj).exists()
        return False

    def get_avatar(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def to_representation(self, instance):
        data = super().to_representation(instance)

        request = self.context.get("request")
        if request:
            recipes_limit = request.query_params.get("recipes_limit")
            if recipes_limit:
                try:
                    recipes_limit = int(recipes_limit)
                    data["recipes"] = data["recipes"][:recipes_limit]
                except (ValueError, TypeError):
                    pass

        return data


class SetPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        required=True, error_messages={"required": "Обязательное поле."}
    )
    new_password = serializers.CharField(
        required=True, error_messages={"required": "Обязательное поле."}
    )

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Неверный текущий пароль")
        return value

class AvatarSerializer(serializers.ModelSerializer):
    avatar = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('avatar',)
    
    def validate_avatar(self, value):
        if not value:
            raise serializers.ValidationError("Это поле обязательно.")
        
        try:
            if isinstance(value, str) and value.startswith("data:image"):
                image_data = value.split("base64,")[-1]
            else:
                image_data = value
            
            decoded_image = base64.b64decode(image_data)
            
            image = Image.open(io.BytesIO(decoded_image))
            image.verify()
            
            image = Image.open(io.BytesIO(decoded_image))
            image_format = image.format.lower() if image.format else None
            if not image_format:
                raise serializers.ValidationError("Некорректный формат переданного файла")
            
            return (decoded_image, image_format)
            
        except Exception as e:
            raise serializers.ValidationError(f"Ошибка обработки изображения: {str(e)}")
    
    def update(self, instance, validated_data):
        decoded_image, image_format = validated_data['avatar']
        filename = f"{instance.id}.{image_format}"
        instance.image.save(filename, ContentFile(decoded_image))
        instance.save()
        return instance
    
    def to_representation(self, instance):
        return {
            'avatar': instance.image.url
        }
    
class AvatarDeleteSerializer(serializers.Serializer):
    def validate(self, attrs):
        user = self.context.get('request').user
        if not user.image:
            raise serializers.ValidationError("У пользователя нет аватара")
        return attrs
