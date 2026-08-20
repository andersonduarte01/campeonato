from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from apps.core.admin_mixins import TenantAwareAdminMixin
from .models import (
    RegistroFederativo, HistoricoClube,
    JanelaTransferencia, Transferencia,
)


@admin.register(RegistroFederativo)
class RegistroFederativoAdmin(TenantAwareAdminMixin, UnfoldModelAdmin):
    list_display  = ('numero_federativo', 'atleta', 'federacao', 'status', 'data_filiacao')
    list_filter   = ('federacao', 'status')
    search_fields = ('numero_federativo', 'atleta__nome')
    readonly_fields = ('numero_federativo', 'criado_em', 'atualizado_em')


@admin.register(HistoricoClube)
class HistoricoClubeAdmin(TenantAwareAdminMixin, UnfoldModelAdmin):
    tenant_lookup = 'equipe__federacao'
    list_display  = ('atleta', 'equipe', 'tipo', 'data_entrada', 'data_saida')
    list_filter   = ('tipo',)
    search_fields = ('atleta__nome', 'equipe__nome_equipe')


@admin.register(JanelaTransferencia)
class JanelaTransferenciaAdmin(TenantAwareAdminMixin, UnfoldModelAdmin):
    list_display = ('nome', 'federacao', 'data_inicio', 'data_fim', 'ativa')
    list_filter  = ('federacao', 'ativa')
    search_fields = ('nome',)


@admin.register(Transferencia)
class TransferenciaAdmin(TenantAwareAdminMixin, UnfoldModelAdmin):
    tenant_lookup = 'atleta__equipe__federacao'
    list_display  = ('atleta', 'clube_origem', 'clube_destino', 'tipo', 'status', 'data_solicitacao')
    list_filter   = ('status', 'tipo')
    search_fields = ('atleta__nome',)
    readonly_fields = ('data_solicitacao', 'criado_em', 'atualizado_em')
