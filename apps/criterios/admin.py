from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import CriterioClassificacao, FormatoCompeticao


@admin.register(FormatoCompeticao)
class FormatoCompeticaoAdmin(UnfoldModelAdmin):
    list_display = ['nome', 'federacao', 'qtd_times', 'pontos_por_vitoria', 'pontos_por_empate']
    list_filter = ['federacao']
    search_fields = ['nome']


@admin.register(CriterioClassificacao)
class CriterioClassificacaoAdmin(UnfoldModelAdmin):
    list_display = ['nome', 'federacao', 'confronto_direto', 'vitorias', 'saldo_gols', 'gols_pro', 'gol_fora', 'menor_vermelho', 'menor_amarelo']
    list_filter = ['federacao']
    search_fields = ['nome']
