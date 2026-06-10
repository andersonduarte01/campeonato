from django.contrib import admin
from .models import (
    Competicao, Jogo, Rodada, Gol, Cartao, InscricaoAtleta, Classificacao,
    Fase, Grupo, ClassificacaoGrupo, ConfrontoMatamate, Suspensao,
    Local, Arbitro, EscalacaoJogo, Substituicao, ArbitrosJogo,
    SumulaDigital, OcorrenciaSumula, AnexoSumula, AssinaturaDigital,
    ProcessoDesportivo, Julgamento, RecursoDesportivo,
    LancamentoFinanceiro, Publicacao,
)


class GolInline(admin.TabularInline):
    model = Gol
    extra = 0
    raw_id_fields = ['atleta']


class CartaoInline(admin.TabularInline):
    model = Cartao
    extra = 0


@admin.register(Jogo)
class JogoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'data_hora', 'gols_casa', 'gols_fora', 'finalizado', 'anulado')
    list_filter = ('finalizado', 'anulado', 'rodada__competicao')
    inlines = [GolInline, CartaoInline]


@admin.register(Competicao)
class CompeticaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data_inicio', 'data_fim')
    filter_horizontal = ('equipes',)


@admin.register(Rodada)
class RodadaAdmin(admin.ModelAdmin):
    list_display = ('competicao', 'fase', 'grupo', 'numero')
    list_filter = ('competicao', 'fase')


@admin.register(InscricaoAtleta)
class InscricaoAtletaAdmin(admin.ModelAdmin):
    list_display = ('atleta', 'competicao', 'numero_camisa')
    list_filter = ('competicao',)
    search_fields = ('atleta__nome',)


@admin.register(Gol)
class GolAdmin(admin.ModelAdmin):
    list_display = ('atleta', 'equipe', 'jogo', 'minuto', 'tipo')
    list_filter = ('tipo', 'jogo__rodada__competicao')


@admin.register(Classificacao)
class ClassificacaoAdmin(admin.ModelAdmin):
    list_display = ('equipe', 'competicao', 'pontos', 'jogos', 'vitorias', 'empates', 'derrotas', 'saldo_gols')
    list_filter = ('competicao',)
    ordering = ('competicao', '-pontos')


class GrupoInline(admin.TabularInline):
    model = Grupo
    extra = 0
    filter_horizontal = ('equipes',)


@admin.register(Fase)
class FaseAdmin(admin.ModelAdmin):
    list_display = ('nome', 'competicao', 'tipo', 'ordem', 'ida_e_volta', 'concluida')
    list_filter = ('competicao', 'tipo')
    ordering = ('competicao', 'ordem')
    inlines = [GrupoInline]


@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'fase')
    list_filter = ('fase__competicao', 'fase')
    filter_horizontal = ('equipes',)


@admin.register(ClassificacaoGrupo)
class ClassificacaoGrupoAdmin(admin.ModelAdmin):
    list_display = ('equipe', 'grupo', 'pontos', 'jogos', 'vitorias', 'empates', 'derrotas', 'saldo_gols')
    list_filter = ('grupo__fase__competicao', 'grupo__fase', 'grupo')
    ordering = ('grupo', '-pontos')


@admin.register(Suspensao)
class SuspensaoAdmin(admin.ModelAdmin):
    list_display = ('atleta', 'competicao', 'motivo', 'cumprida')
    list_filter = ('competicao', 'cumprida', 'motivo')
    list_editable = ('cumprida',)
    search_fields = ('atleta__nome',)


@admin.register(ConfrontoMatamate)
class ConfrontoMatamateAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'fase', 'ordem', 'vencedor')
    list_filter = ('fase__competicao', 'fase')
    raw_id_fields = ('jogo_ida', 'jogo_volta')


@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cidade', 'capacidade')
    search_fields = ('nome', 'cidade')


@admin.register(Arbitro)
class ArbitroAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'disponibilidade', 'ativo', 'taxa_por_partida')
    list_filter = ('ativo', 'categoria', 'disponibilidade')
    search_fields = ('nome', 'cpf')
    fieldsets = (
        ('Identificação', {'fields': ('nome', 'cpf', 'data_nascimento', 'foto')}),
        ('Categoria e Status', {'fields': ('categoria', 'disponibilidade', 'ativo')}),
        ('Certificações', {'fields': ('certificacoes', 'observacao')}),
        ('Custos Operacionais', {'fields': ('taxa_por_partida', 'diaria', 'alimentacao', 'hospedagem', 'deslocamento')}),
    )


@admin.register(ArbitrosJogo)
class ArbitrosJogoAdmin(admin.ModelAdmin):
    list_display = ('arbitro', 'tipo', 'jogo')
    list_filter = ('tipo',)


class EscalacaoInline(admin.TabularInline):
    model = EscalacaoJogo
    extra = 0


class SubstituicaoInline(admin.TabularInline):
    model = Substituicao
    extra = 0


class OcorrenciaInline(admin.TabularInline):
    model = OcorrenciaSumula
    extra = 0


class AnexoInline(admin.TabularInline):
    model = AnexoSumula
    extra = 0


class AssinaturaInline(admin.TabularInline):
    model = AssinaturaDigital
    extra = 0
    readonly_fields = ('assinado_em', 'ip_address', 'user_agent')


@admin.register(SumulaDigital)
class SumulaDigitalAdmin(admin.ModelAdmin):
    list_display  = ('jogo', 'condicao_climatica', 'condicao_campo', 'finalizada', 'finalizada_em')
    list_filter   = ('finalizada', 'condicao_climatica', 'condicao_campo')
    readonly_fields = ('hash_integridade', 'finalizada_em', 'criada_em', 'atualizada_em')
    inlines       = [OcorrenciaInline, AnexoInline, AssinaturaInline]


class JulgamentoInline(admin.StackedInline):
    model = Julgamento
    extra = 0
    readonly_fields = ('julgado_em',)


class RecursoInline(admin.TabularInline):
    model = RecursoDesportivo
    extra = 0
    readonly_fields = ('criado_em', 'decidido_em')


@admin.register(ProcessoDesportivo)
class ProcessoDesportivoAdmin(admin.ModelAdmin):
    list_display   = ('numero', 'tipo', 'status', 'denunciante', 'competicao', 'criado_em')
    list_filter    = ('status', 'tipo')
    search_fields  = ('numero', 'denunciante', 'descricao')
    readonly_fields = ('numero', 'criado_em', 'atualizado_em')
    inlines        = [JulgamentoInline, RecursoInline]


@admin.register(RecursoDesportivo)
class RecursoDesportivoAdmin(admin.ModelAdmin):
    list_display  = ('processo', 'recorrente', 'status', 'criado_em')
    list_filter   = ('status',)
    readonly_fields = ('criado_em', 'decidido_em')


@admin.register(LancamentoFinanceiro)
class LancamentoFinanceiroAdmin(admin.ModelAdmin):
    list_display   = ('numero', 'tipo', 'categoria', 'descricao', 'valor', 'data_vencimento', 'status')
    list_filter    = ('tipo', 'status', 'categoria', 'forma_pagamento')
    search_fields  = ('numero', 'descricao', 'numero_referencia')
    readonly_fields = ('numero', 'criado_em', 'atualizado_em')
    list_editable  = ('status',)
    date_hierarchy = 'data_vencimento'


@admin.register(Publicacao)
class PublicacaoAdmin(admin.ModelAdmin):
    list_display   = ('titulo', 'tipo', 'publicado', 'destaque', 'publicado_em')
    list_filter    = ('tipo', 'publicado', 'destaque')
    search_fields  = ('titulo', 'resumo', 'conteudo')
    readonly_fields = ('slug', 'criado_em', 'atualizado_em')
    list_editable  = ('publicado', 'destaque')
    prepopulated_fields = {}
    date_hierarchy = 'criado_em'
