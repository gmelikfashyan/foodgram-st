import django_filters.rest_framework as filters
from recipes.models import Recipe


class RecipeFilter(filters.FilterSet):
    is_in_shopping_cart = filters.BooleanFilter(
        method="filter_in_shopping_cart"
    )
    is_favorited = filters.BooleanFilter(method="filter_favorited")
    author = filters.NumberFilter(field_name="author__id")

    class Meta:
        model = Recipe
        fields = ["author"]

    def filter_in_shopping_cart(self, queryset, name, value):
        if not self.request.user.is_authenticated:
            if value:
                return queryset.none()
            else:
                return queryset
        if value:
            return queryset.filter(wishlist_set__user=self.request.user)
        return queryset

    def filter_favorited(self, queryset, name, value):
        if not self.request.user.is_authenticated:
            if value:
                return queryset.none()
            else:
                return queryset
        if value:
            return queryset.filter(userfavorite_set__user=self.request.user)
        return queryset
