from django.contrib.auth import authenticate
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                     ShoppingCart, Subscription, User)
from .serializers import (Base64ImageField, IngredientSerializer,
                          RecipeMinifiedSerializer, RecipeReadSerializer,
                          RecipeWriteSerializer, UserCreateSerializer,
                          UserSerializer, UserWithRecipesSerializer)


def encode_base36(number):
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    result = ''
    while number:
        number, remainder = divmod(number, 36)
        result = alphabet[remainder] + result
    return result or '0'


def short_link_redirect(request, code):
    try:
        recipe_id = int(code, 36)
    except ValueError:
        raise ValidationError('Некорректная ссылка.')
    get_object_or_404(Recipe, pk=recipe_id)
    return HttpResponseRedirect(f'/recipes/{recipe_id}')


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class UserViewSet(mixins.ListModelMixin, mixins.CreateModelMixin,
                  mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.all().order_by('id')

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ('me', 'avatar', 'set_password',
                           'subscriptions', 'subscribe'):
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def create(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = UserCreateSerializer(user).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=('get',))
    def me(self, request):
        return Response(UserSerializer(request.user,
                                       context={'request': request}).data)

    @action(detail=False, methods=('put', 'delete'), url_path='me/avatar')
    def avatar(self, request):
        user = request.user
        if request.method == 'DELETE':
            if user.avatar:
                user.avatar.delete(save=False)
                user.avatar = None
                user.save(update_fields=['avatar'])
            return Response(status=status.HTTP_204_NO_CONTENT)
        field = Base64ImageField()
        if 'avatar' not in request.data:
            raise ValidationError({'avatar': 'Обязательное поле.'})
        avatar = field.run_validation(request.data['avatar'])
        if user.avatar:
            user.avatar.delete(save=False)
        user.avatar = avatar
        user.save(update_fields=['avatar'])
        return Response(
            {'avatar': request.build_absolute_uri(user.avatar.url)})

    @action(detail=False, methods=('post',))
    def set_password(self, request):
        current = request.data.get('current_password')
        new = request.data.get('new_password')
        if not current or not new:
            raise ValidationError({'detail': 'Укажите оба пароля.'})
        if not request.user.check_password(current):
            raise ValidationError({'current_password': 'Неверный пароль.'})
        from django.contrib.auth.password_validation import validate_password
        validate_password(new, request.user)
        request.user.set_password(new)
        request.user.save(update_fields=['password'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=('get',))
    def subscriptions(self, request):
        authors = User.objects.filter(
            followers__user=request.user
        ).order_by('id')
        page = self.paginate_queryset(authors)
        serializer = UserWithRecipesSerializer(
            page if page is not None else authors, many=True,
            context={'request': request}
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=('post', 'delete'))
    def subscribe(self, request, pk=None):
        author = self.get_object()
        if request.method == 'POST':
            if author == request.user:
                raise ValidationError('Нельзя подписаться на себя.')
            subscription, created = Subscription.objects.get_or_create(
                user=request.user, author=author
            )
            if not created:
                raise ValidationError('Вы уже подписаны на этого автора.')
            return Response(UserWithRecipesSerializer(
                author, context={'request': request}
            ).data, status=status.HTTP_201_CREATED)
        deleted, _ = Subscription.objects.filter(
            user=request.user, author=author
        ).delete()
        if not deleted:
            raise ValidationError('Подписка не найдена.')
        return Response(status=status.HTTP_204_NO_CONTENT)


class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return (request.method in permissions.SAFE_METHODS
                or obj.author == request.user)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.select_related('author').prefetch_related(
        'recipe_ingredients__ingredient'
    )
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return RecipeWriteSerializer
        return RecipeReadSerializer

    def get_permissions(self):
        if self.action in ('partial_update', 'destroy'):
            return [permissions.IsAuthenticated(), IsAuthorOrReadOnly()]
        if self.action in ('create', 'favorite', 'shopping_cart',
                           'download_shopping_cart'):
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != 'list':
            return queryset
        params = self.request.query_params
        author = params.get('author')
        if author is not None:
            queryset = queryset.filter(author_id=author)
        if params.get('is_favorited') == '1':
            if not self.request.user.is_authenticated:
                return queryset.none()
            queryset = queryset.filter(favorites__user=self.request.user)
        if params.get('is_in_shopping_cart') == '1':
            if not self.request.user.is_authenticated:
                return queryset.none()
            queryset = queryset.filter(shopping_carts__user=self.request.user)
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=('get',), url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        link = request.build_absolute_uri(f'/s/{encode_base36(recipe.pk)}/')
        return Response({'short-link': link})

    @staticmethod
    def update_relation(request, recipe, model):
        if request.method == 'POST':
            obj, created = model.objects.get_or_create(
                user=request.user, recipe=recipe
            )
            if not created:
                raise ValidationError('Рецепт уже добавлен.')
            return Response(RecipeMinifiedSerializer(
                recipe, context={'request': request}
            ).data, status=status.HTTP_201_CREATED)
        deleted, _ = model.objects.filter(
            user=request.user, recipe=recipe
        ).delete()
        if not deleted:
            raise ValidationError('Рецепт не найден в списке.')
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=('post', 'delete'))
    def favorite(self, request, pk=None):
        return self.update_relation(request, self.get_object(), Favorite)

    @action(detail=True, methods=('post', 'delete'))
    def shopping_cart(self, request, pk=None):
        return self.update_relation(request, self.get_object(), ShoppingCart)

    @action(detail=False, methods=('get',))
    def download_shopping_cart(self, request):
        rows = RecipeIngredient.objects.filter(
            recipe__shopping_carts__user=request.user
        ).values('ingredient__name', 'ingredient__measurement_unit').annotate(
            total=Sum('amount')
        ).order_by('ingredient__name', 'ingredient__measurement_unit')
        lines = [f"{row['ingredient__name']} "
                 f"({row['ingredient__measurement_unit']}) — {row['total']}"
                 for row in rows]
        response = HttpResponse('\n'.join(lines),
                                content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = (
            'attachment; filename="shopping-list.txt"'
        )
        return response


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    email = request.data.get('email')
    password = request.data.get('password')
    if not email or not password:
        raise ValidationError({'detail': 'Укажите адрес почты и пароль.'})
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        raise ValidationError(
            {'non_field_errors': ['Неверные учётные данные.']})
    user = authenticate(request, username=user.username, password=password)
    if user is None:
        raise ValidationError(
            {'non_field_errors': ['Неверные учётные данные.']})
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'auth_token': token.key})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
