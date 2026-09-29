from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utilizador


@admin.register(Utilizador)
class UtilizadorAdmin(UserAdmin):
    list_display = ('username', 'email', 'nome_completo', 'email_verificado', 'estado_assinatura', 'date_joined')
    list_filter = ('email_verificado', 'estado_assinatura')
    search_fields = ('username', 'email', 'nome_completo', 'telefone')
    fieldsets = UserAdmin.fieldsets + (('Cofrinho AO', {'fields': ('nome_completo', 'telefone', 'email_verificado', 'estado_assinatura')}),)
