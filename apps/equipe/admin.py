from django.contrib import admin
from .models import Equipe, Atleta

@admin.register(Equipe)
class EquipeAdmin(admin.ModelAdmin):
    list_display = ("id", "nome_equipe", "cadastrado", "atualizado")  # Colunas visíveis na lista
    search_fields = ("nome_equipe",)  # Campo de busca
    list_filter = ("cadastrado",)  # Filtro lateral
    ordering = ("nome_equipe",)  # Ordenação padrão


class AtletaAdmin(admin.ModelAdmin):
    list_display = ('nome_equipe', 'nome', 'posicao', 'data_nascimento')

admin.site.register(Atleta, AtletaAdmin)