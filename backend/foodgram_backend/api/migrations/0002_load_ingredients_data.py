from django.db import migrations
import os
import json


def load_data_from_json(apps, schema_editor):
    Ingredient = apps.get_model("recipes", "Ingredient")

    file_path = os.path.join("data/ingredients.json")

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
        for item in data:
            Ingredient.objects.get_or_create(
                name=item["name"], measurment=item["measurement_unit"]
            )


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0001_load_ingredients_data"),
    ]

    operations = [
        migrations.RunPython(load_data_from_json),
    ]
