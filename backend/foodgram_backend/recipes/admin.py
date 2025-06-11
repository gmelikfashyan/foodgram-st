from django.contrib import admin

from .models import Recipe, Ingredient, UserFavorite, WishList, Follow, AmountIngredientInRecipe

@admin.register(Recipe)
class RecipeRegister(admin.ModelAdmin):
    search_fields = ('author', 'name')
    list_display = ('name', 'author__username', 'count_of_favorites')
    readonly_fields = ('count_of_favorites',)

    def count_of_favorites(self, obj):
        return obj.userfavorite_set.count()
    
@admin.register(Ingredient)
class IngredientRegister(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'measurment')


admin.site.register(UserFavorite)
admin.site.register(WishList)
admin.site.register(Follow)
admin.site.register(AmountIngredientInRecipe)
