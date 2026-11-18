import base64
import io
import tempfile

from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from PIL import Image

from .models import Ingredient, User


class FoodgramApiTests(APITestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        media_setting = override_settings(MEDIA_ROOT=self.media_dir.name)
        media_setting.enable()
        self.addCleanup(media_setting.disable)
        self.author = User.objects.create_user(
            username='author', email='author@example.com', password='Test2026!'
        )
        self.reader = User.objects.create_user(
            username='reader', email='reader@example.com', password='Test2026!'
        )
        self.ingredient = Ingredient.objects.create(
            name='Сахар', measurement_unit='г'
        )
        image = Image.new('RGB', (10, 10), (210, 100, 40))
        output = io.BytesIO()
        image.save(output, format='PNG')
        self.image = ('data:image/png;base64,'
                      + base64.b64encode(output.getvalue()).decode())

    def login_as(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def make_recipe(self, name, amount):
        response = self.client.post('/api/recipes/', {
            'name': name,
            'text': 'Тестовое описание',
            'image': self.image,
            'cooking_time': 10,
            'ingredients': [{'id': self.ingredient.pk, 'amount': amount}],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def test_shopping_list_sums_ingredients(self):
        self.login_as(self.author)
        first = self.make_recipe('Первый', 5)
        second = self.make_recipe('Второй', 10)
        for pk in (first, second):
            response = self.client.post(f'/api/recipes/{pk}/shopping_cart/')
            self.assertEqual(response.status_code, 201)
        response = self.client.get('/api/recipes/download_shopping_cart/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'Сахар (г) — 15')

    def test_only_author_can_edit_recipe_and_short_link_stays_stable(self):
        self.login_as(self.author)
        pk = self.make_recipe('Исходное название', 1)
        link = self.client.get(f'/api/recipes/{pk}/get-link/').data
        self.login_as(self.reader)
        response = self.client.patch(
            f'/api/recipes/{pk}/', {'name': 'Чужое название'}, format='json'
        )
        self.assertEqual(response.status_code, 403)
        self.login_as(self.author)
        response = self.client.patch(f'/api/recipes/{pk}/', {
            'name': 'Новое название',
            'text': 'Новое описание',
            'cooking_time': 15,
            'ingredients': [{'id': self.ingredient.pk, 'amount': 2}],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.client.get(f'/api/recipes/{pk}/get-link/').data, link
        )
