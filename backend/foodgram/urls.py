from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path
from django.views.static import serve
from rest_framework.routers import DefaultRouter

from api.views import (IngredientViewSet, RecipeViewSet, UserViewSet,
                       login_view, logout_view, short_link_redirect)

router = DefaultRouter()
router.register('users', UserViewSet, basename='users')
router.register('recipes', RecipeViewSet, basename='recipes')
router.register('ingredients', IngredientViewSet, basename='ingredients')


def frontend(request):
    index = settings.FRONTEND_BUILD / 'index.html'
    if not index.exists():
        raise Http404('Сначала соберите фронтенд.')
    return FileResponse(index.open('rb'), content_type='text/html')


def docs(request, path='redoc.html'):
    return serve(
        request, path, document_root=settings.BASE_DIR.parent / 'docs')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/login/', login_view),
    path('api/auth/token/logout/', logout_view),
    path('api/docs/', docs),
    path('api/docs/<path:path>', docs),
    path('api/', include(router.urls)),
    re_path(r'^s/(?P<code>[0-9a-z]+)/$', short_link_redirect),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(
        r'^(?P<path>(favicon|logo192|logo512)\.png|'
        r'manifest\.json|robots\.txt)$',
        serve, {'document_root': settings.FRONTEND_BUILD},
    ),
    path('', frontend),
    re_path(r'^(?!api/|admin/|media/|static/).+', frontend),
]
