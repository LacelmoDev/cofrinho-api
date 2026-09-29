from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def saude(_request):
    return JsonResponse({'estado': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/saude/', saude),
    path('api/auth/', include('contas.urls')),
    path('api/sync/', include('sync.urls')),
]
