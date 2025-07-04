from rest_framework import viewsets, status
from rest_framework.views import APIView
from djoser.views import UserViewSet
from .serializers import (
    CustomUserSerializer,
    CustomCreateUserSerializer,
    IngredientSerializer,
    RecipeSerializer,
    RecipeCreateSerializer,
    FollowUserSerializer,
    RecipeForFollowSerializer,
    SetPasswordSerializer,
    CustomUserCreateResponseSerializer,
    AvatarSerializer,
    AvatarDeleteSerializer
)
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
    AllowAny,
)
from .pagination import CustomUserPagination
from recipes.models import (
    Ingredient,
    Recipe,
    Follow,
    UserFavorite,
    WishList,
    AmountIngredientInRecipe,
)
from .permissions import OwnerOrReadOnly, ReadOnly
from .filters import RecipeFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum
from hashids import Hashids
from django.shortcuts import redirect


User = get_user_model()


class CustomUserViewSet(UserViewSet):
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return CustomCreateUserSerializer
        return CustomUserSerializer

    def get_permissions(self):
        if self.action == "list":
            return []
        if self.action == "me":
            return [IsAuthenticated()]
        return [AllowAny()]

    pagination_class = CustomUserPagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        response_serializer = CustomUserCreateResponseSerializer(user)

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["put", "delete"], url_path="me/avatar")
    def avatar(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Учетные данные не были предоставлены."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = request.user

        if request.method == "PUT":
            serializer = AvatarSerializer(
                user, 
                data=request.data,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            return Response(
                serializer.data,
                status=status.HTTP_200_OK
            )

        elif request.method == "DELETE":
            serializer = AvatarDeleteSerializer(
                data={},
                context={'user': user, 'request': request}
            )
            serializer.is_valid(raise_exception=True)
            
            user.image.delete()
            user.save()
            
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def subscriptions(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Учетные данные не были предоставлены."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        queryset = User.objects.filter(
            following__user=request.user
        ).distinct()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = FollowUserSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = FollowUserSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post", "delete"])
    def subscribe(self, request, id):

        if not request.user.is_authenticated:
            return Response(
                {"detail": "Учетные данные не были предоставлены."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        for_follow_user = get_object_or_404(User, id=id)

        if request.user == for_follow_user:
            return Response(
                {"detail": "Невозможно подписаться на самого себя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.method == "POST":
            if request.user.follower.filter(following=for_follow_user).exists():
                return Response(
                    {"detail": "Вы уже подписаны на этого пользователя."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
            # Создаем подписку
            Follow.objects.create(
                user=request.user, 
                following=for_follow_user
            )
            
            serializer = FollowUserSerializer(
                for_follow_user, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == "DELETE":
            try:
                follow = Follow.objects.get(
                    user=request.user, following=for_follow_user
                )
                follow.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Follow.DoesNotExist:
                return Response(
                    {"detail": "Вы не подписаны на пользователя."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    @action(detail=False, methods=["post"])
    def set_password(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Учетные данные не были предоставлены."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = SetPasswordSerializer(
            data=request.data, 
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        user = request.user
        new_password = serializer.validated_data["new_password"]
        user.set_password(new_password)
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None

    def get_permissions(self):
        return [IsAuthenticatedOrReadOnly()]

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get("name")

        if name:
            queryset = queryset.filter(name__istartswith=name)

        return queryset.order_by("name")


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return RecipeCreateSerializer
        return RecipeSerializer

    permission_classes = (OwnerOrReadOnly,)

    def get_permissions(self):
        if self.action == "retrieve":
            return (ReadOnly(),)
        return super().get_permissions()

    filter_backends = [DjangoFilterBackend]
    filterset_class = RecipeFilter

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hashids = Hashids(salt="Testing_salt", min_length=4)

    @action(detail=True, methods=["post", "delete"])
    def favorite(self, request, pk):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Учетные данные не были предоставлены."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        for_favorite_recipe = get_object_or_404(Recipe, pk=pk)

        if request.method == "POST":
            if request.user.userfavorite_set.filter(recipe=for_favorite_recipe).exists():
                return Response(
                    {"detail": "Вы уже добавили этот рецепт в избранное."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                UserFavorite.objects.create(
                    user=request.user, recipe=for_favorite_recipe
                )
            serializer = RecipeForFollowSerializer(
                for_favorite_recipe, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == "DELETE":
            try:
                userFavorite = UserFavorite.objects.get(
                    user=request.user, recipe=for_favorite_recipe
                )
                userFavorite.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except UserFavorite.DoesNotExist:
                return Response(
                    {"detail": "Вы не добавляли этот рецепт в избранное"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    @action(detail=True, methods=["post", "delete"])
    def shopping_cart(self, request, pk):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Учетные данные не были предоставлены."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if request.method == "POST":
            if request.user.wishlist_set.filter(recipe=pk).exists():
                return Response(
                    {
                        "detail": "Вы уже добавили этот рецепт в список."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                for_shopping_cart_recipe = get_object_or_404(Recipe, pk=pk)
                WishList.objects.create(
                    user=request.user, recipe=for_shopping_cart_recipe
                )
            serializer = RecipeForFollowSerializer(
                for_shopping_cart_recipe, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == "DELETE":
            for_shopping_cart_recipe = get_object_or_404(Recipe, pk=pk)
            try:
                wish = WishList.objects.get(
                    user=request.user, recipe=for_shopping_cart_recipe
                )
                wish.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except WishList.DoesNotExist:
                return Response(
                    {"detail": "Вы не добавляли этот рецепт в избранное"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    @action(detail=False, methods=["get"])
    def download_shopping_cart(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Учетные данные не были предоставлены."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


        if not request.user.wishlist_set.exists():
            return Response(
                {"detail": "Корзина покупок пуста."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ingredients = (
            AmountIngredientInRecipe.objects.filter(
                recipe__wishlist_set__user=request.user
            )
            .values("ingredient__name", "ingredient__measurment")
            .annotate(amount=Sum("amount"))
        )

        content_lines = [
            "СПИСОК ПОКУПОК",
            " " * 50,
        ]

        for item in ingredients:
            name = item["ingredient__name"]
            measurment = item["ingredient__measurment"]
            amount = item["amount"]
            content_lines.append(f"• {name} ({measurment}) — {amount}")

        content = "\n".join(content_lines)

        response = HttpResponse(
            content, content_type="text/plain; charset=utf-8"
        )

        response["Content-Disposition"] = 'attachment; filename="wishList.txt"'

        return response

    @action(
        detail=True,
        methods=["get"],
        url_path="get-link",
        permission_classes=[AllowAny],
    )
    def get_link(self, request, pk=None):
        instance = self.get_object()
        short_link = request.build_absolute_uri(f"/recipes/{instance.id}/")
        return Response({"short-link": short_link})

    @action(
        detail=True,
        methods=["get"],
        url_path="get-short-link",
        permission_classes=[AllowAny],
    )
    def get_short_link(self, request, pk=None):
        instance = self.get_object()
        hashid = self.hashids.encode(instance.id)
        short_link = request.build_absolute_uri(f"/s/{hashid}/")
        return Response({"short-link": short_link})


class RedirectFromShortView(APIView):
    permission_classes = (AllowAny,)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hashids = Hashids(salt="Testing_salt", min_length=4)

    def get(self, request, hashed):
        try:
            decoded_id = self.hashids.decode(hashed)
            if not decoded_id:
                raise ValueError
            recipe_id = decoded_id[0]
            _ = get_object_or_404(Recipe, pk=recipe_id)

            return redirect(f"/api/recipes/{recipe_id}/")

        except (ValueError, IndexError):
            return Response(
                {"detail": "Короткая ссылка повреждена"},
                status=status.HTTP_404_NOT_FOUND,
            )
