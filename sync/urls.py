from django.urls import path

from .views import Sincronizar

urlpatterns = [path('', Sincronizar.as_view())]
