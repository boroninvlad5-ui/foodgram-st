import io
import secrets

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from api.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                        ShoppingCart, Subscription, User)


RECIPES = [
    ('Картофель с сыром', 35, [('картофель', 'г', 500),
                               ('сыр', 'г', 150)], (215, 160, 75)),
    ('Овощной салат', 15, [('помидоры', 'г', 250),
                           ('огурцы', 'г', 200)], (110, 160, 95)),
    ('Рис с овощами', 30, [('рис', 'г', 200),
                           ('морковь', 'г', 100)], (215, 180, 110)),
    ('Томатный суп', 40, [('помидоры', 'г', 400),
                          ('лук репчатый', 'г', 100)], (190, 90, 75)),
    ('Молочная каша', 20, [('молоко', 'мл', 400),
                           ('рис', 'г', 100)], (220, 205, 170)),
    ('Домашние лепёшки', 45, [('мука', 'г', 300),
                              ('молоко', 'мл', 150)], (190, 145, 100)),
    ('Морковный гарнир', 25, [('морковь', 'г', 300),
                              ('лук репчатый', 'г', 80)], (220, 125, 65)),
]


def demo_image(color):
    image = Image.new('RGB', (720, 480), (242, 237, 226))
    draw = ImageDraw.Draw(image)
    draw.ellipse((170, 45, 550, 425), fill=(248, 248, 245),
                 outline=(205, 199, 185), width=7)
    draw.ellipse((225, 95, 495, 375), fill=color)
    draw.ellipse((270, 140, 330, 200), fill=(245, 210, 130))
    draw.ellipse((380, 235, 450, 305), fill=(245, 210, 130))
    output = io.BytesIO()
    image.save(output, format='JPEG', quality=88)
    return ContentFile(output.getvalue())


class Command(BaseCommand):
    help = 'Создать локальные демонстрационные аккаунты и рецепты.'

    def add_arguments(self, parser):
        parser.add_argument('--password', default=None)

    def handle(self, *args, **options):
        password = options['password'] or secrets.token_urlsafe(12)
        users = []
        for username, email, first_name, is_staff in (
            ('demo', 'demo@example.com', 'Демо', False),
            ('chef', 'chef@example.com', 'Повар', False),
            ('admin', 'admin@example.com', 'Админ', True),
        ):
            user, _ = User.objects.get_or_create(username=username,
                                                 defaults={'email': email})
            user.email = email
            user.first_name = first_name
            user.last_name = 'Фудграм'
            user.is_staff = is_staff
            user.is_superuser = is_staff
            user.set_password(password)
            user.save()
            users.append(user)
        for index, (name, minutes, ingredients, color) in enumerate(RECIPES):
            recipe = Recipe.objects.filter(
                name=name, author=users[index % 3]).first()
            if recipe is None:
                recipe = Recipe(
                    author=users[index % 3], name=name,
                    text='Простой домашний рецепт для демонстрации.',
                    cooking_time=minutes,
                )
                recipe.image.save(f'demo-{index + 1}.jpg', demo_image(color),
                                  save=False)
                recipe.save()
                for ingredient_name, unit, amount in ingredients:
                    ingredient = Ingredient.objects.get(
                        name=ingredient_name, measurement_unit=unit
                    )
                    RecipeIngredient.objects.create(
                        recipe=recipe, ingredient=ingredient, amount=amount
                    )
        Subscription.objects.get_or_create(user=users[0], author=users[1])
        first_recipe = Recipe.objects.filter(name=RECIPES[0][0]).first()
        Favorite.objects.get_or_create(user=users[0], recipe=first_recipe)
        ShoppingCart.objects.get_or_create(user=users[0], recipe=first_recipe)
        self.stdout.write(self.style.SUCCESS(
            'Готово. Пользователи: demo@example.com, chef@example.com, '
            f'admin@example.com. Пароль для всех: {password}'
        ))
