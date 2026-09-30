from django.urls import path

from . import views

urlpatterns = [
    path('registar/', views.Registar.as_view()),
    path('reenviar-codigo/', views.ReenviarCodigo.as_view()),
    path('verificar-email/', views.VerificarEmail.as_view()),
    path('login/', views.Login.as_view()),
    path('logout/', views.Logout.as_view()),
    path('eu/', views.Eu.as_view()),
    path('exportar/', views.ExportarDados.as_view()),
    path('eliminar-conta/', views.EliminarConta.as_view()),
    path('senha/pedir/', views.PedirReset.as_view()),
    path('senha/confirmar/', views.ConfirmarReset.as_view()),
]
