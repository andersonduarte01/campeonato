from django.contrib import admin
from .models import (
    RegistroFederativo, HistoricoClube,
    JanelaTransferencia, Transferencia,
    InfoClube, TipoDocumento, Documento,
)


@admin.register(RegistroFederativo)
class RegistroFederativoAdmin(admin.ModelAdmin):
    list_display  = ('numero_federativo', 'atleta', 'status', 'data_filiacao')
    list_filter   = ('status',)
    search_fields = ('numero_federativo', 'atleta__nome')
    readonly_fields = ('numero_federativo', 'criado_em', 'atualizado_em')


@admin.register(HistoricoClube)
class HistoricoClubeAdmin(admin.ModelAdmin):
    list_display  = ('atleta', 'equipe', 'tipo', 'data_entrada', 'data_saida')
    list_filter   = ('tipo',)
    search_fields = ('atleta__nome', 'equipe__nome_equipe')


@admin.register(JanelaTransferencia)
class JanelaTransferenciaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data_inicio', 'data_fim', 'ativa')
    list_filter  = ('ativa',)


@admin.register(Transferencia)
class TransferenciaAdmin(admin.ModelAdmin):
    list_display  = ('atleta', 'clube_origem', 'clube_destino', 'tipo', 'status', 'data_solicitacao')
    list_filter   = ('status', 'tipo')
    search_fields = ('atleta__nome',)
    readonly_fields = ('data_solicitacao', 'criado_em', 'atualizado_em')


@admin.register(InfoClube)
class InfoClubeAdmin(admin.ModelAdmin):
    list_display  = ('equipe', 'cnpj', 'situacao', 'presidente')
    list_filter   = ('situacao',)
    search_fields = ('equipe__nome_equipe', 'cnpj', 'razao_social')


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'entidade', 'obrigatorio', 'validade_meses')
    list_filter  = ('entidade', 'obrigatorio')


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display  = ('tipo', 'entidade_vinculada', 'status', 'data_vencimento', 'enviado_em')
    list_filter   = ('status', 'tipo__entidade')
    search_fields = ('atleta__nome', 'clube__nome_equipe')
    readonly_fields = ('enviado_em', 'atualizado_em')
