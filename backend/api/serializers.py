import base64
import binascii
import uuid

from django.contrib.auth.password_validation import validate_password
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework import serializers

from .models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                     ShoppingCart, Subscription, User)


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image/'):
            try:
                header, encoded = data.split(';base64,', 1)
                extension = header.split('/')[-1].lower()
                if extension == 'jpeg':
                    extension = 'jpg'
                if extension not in ('png', 'jpg', 'gif', 'webp'):
                    raise ValueError('Unsupported image format')
                content = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                raise serializers.ValidationError('Некорректное изображение.')
            data = ContentFile(content, name=f'{uuid.uuid4().hex}.{extension}')
        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'avatar')

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated
                    and Subscription.objects.filter(user=request.user,
                                                    author=obj).exists())

    def get_avatar(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(
            obj.avatar.url) if request else obj.avatar.url


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=True, allow_blank=False,
                                       max_length=150)
    last_name = serializers.CharField(required=True, allow_blank=False,
                                      max_length=150)

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'password')

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Этот адрес уже используется.')
        return value

    def validate_username(self, value):
        if value.lower() == 'me':
            raise serializers.ValidationError('Это имя зарезервировано.')
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class UserWithRecipesSerializer(UserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='recipes.count', read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count')

    def get_recipes(self, obj):
        recipes = obj.recipes.all()
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit') if request else None
        if limit is not None:
            try:
                limit = int(limit)
            except ValueError:
                raise serializers.ValidationError(
                    {'recipes_limit': 'Укажите целое число.'}
                )
            if limit < 0:
                raise serializers.ValidationError(
                    {'recipes_limit': 'Число должно быть неотрицательным.'}
                )
            recipes = recipes[:limit]
        return RecipeMinifiedSerializer(recipes, many=True,
                                        context=self.context).data


class RecipeReadSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        source='recipe_ingredients', many=True, read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('id', 'author', 'ingredients', 'is_favorited',
                  'is_in_shopping_cart', 'name', 'image', 'text',
                  'cooking_time')

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated
                    and Favorite.objects.filter(user=request.user,
                                                recipe=obj).exists())

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated
                    and ShoppingCart.objects.filter(user=request.user,
                                                    recipe=obj).exists())


class RecipeIngredientInputSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField(min_value=1)


class RecipeWriteSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientInputSerializer(many=True)
    image = Base64ImageField(required=False)

    class Meta:
        model = Recipe
        fields = ('ingredients', 'image', 'name', 'text', 'cooking_time')
        extra_kwargs = {
            'name': {'allow_blank': False},
            'text': {'allow_blank': False},
            'cooking_time': {'min_value': 1},
        }

    def validate(self, attrs):
        if self.instance is None and 'image' not in attrs:
            raise serializers.ValidationError({'image': 'Обязательное поле.'})
        if self.instance is not None:
            required = ('ingredients', 'name', 'text', 'cooking_time')
            missing = {field: 'Обязательное поле.' for field in required
                       if field not in attrs}
            if missing:
                raise serializers.ValidationError(missing)
        if 'ingredients' in attrs:
            items = attrs['ingredients']
            if not items:
                raise serializers.ValidationError(
                    {'ingredients': 'Добавьте хотя бы один ингредиент.'}
                )
            ids = [item['id'].pk for item in items]
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError(
                    {'ingredients': 'Ингредиенты не должны повторяться.'}
                )
        return attrs

    @staticmethod
    def set_ingredients(recipe, items):
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(recipe=recipe, ingredient=item['id'],
                             amount=item['amount']) for item in items
        ])

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop('ingredients')
        recipe = Recipe.objects.create(**validated_data)
        self.set_ingredients(recipe, items)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop('ingredients', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if items is not None:
            instance.recipe_ingredients.all().delete()
            self.set_ingredients(instance, items)
        return instance

    def to_representation(self, instance):
        return RecipeReadSerializer(instance, context=self.context).data
