from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import AuditoriaEvento, ConsentimentoLGPD


@admin.register(ConsentimentoLGPD)
class ConsentimentoLGPDAdmin(UnfoldModelAdmin):
    list_display  = ('usuario', 'tipo', 'aceito', 'registrado_em', 'atualizado_em')
    list_filter   = ('tipo', 'aceito')
    search_fields = ('usuario__email',)
    readonly_fields = ('registrado_em', 'atualizado_em')


@admin.register(AuditoriaEvento)
class AuditoriaEventoAdmin(UnfoldModelAdmin):
    list_display  = ('registrado_em', 'tipo', 'federacao', 'usuario', 'objeto_tipo', 'objeto_id')
    list_filter   = ('tipo', 'federacao')
    search_fields = ('usuario__email', 'objeto_tipo')
    readonly_fields = (
        'federacao', 'usuario', 'tipo', 'objeto_tipo', 'objeto_id',
        'dados', 'ip', 'user_agent', 'registrado_em',
    )
    date_hierarchy = 'registrado_em'
