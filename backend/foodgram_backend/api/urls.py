from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CustomUserViewSet, IngredientViewSet, RecipeViewSet

router = DefaultRouter()
router.register('users', CustomUserViewSet)
router.register('ingredients', IngredientViewSet)
router.register('recipes', RecipeViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('', include('djoser.urls')),
    path("auth/", include("djoser.urls.authtoken")),
]
