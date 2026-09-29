from django.contrib import admin

from .models import Categoria, Meta, Transacao

for modelo in (Categoria, Transacao, Meta):
    admin.site.register(modelo)
