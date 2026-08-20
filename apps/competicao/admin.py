from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from .models import (
    Competicao, Jogo, Rodada, Gol, Cartao,
    InscricaoAtleta, InscricaoEquipe, Classificacao,
    EtapaKnockout, Grupo, ClassificacaoGrupo, ConfrontoMatamate, Suspensao,
    Local,
)


class GolInline(admin.TabularInline):
    model = Gol
    extra = 0
    raw_id_fields = ['atleta']


class CartaoInline(admin.TabularInline):
    model = Cartao
    extra = 0


@admin.register(Jogo)
class JogoAdmin(UnfoldModelAdmin):
    list_display = ('__str__', 'data_hora', 'gols_casa', 'gols_fora', 'finalizado', 'anulado')
    list_filter = ('finalizado', 'anulado', 'rodada__competicao')
    inlines = [GolInline, CartaoInline]


@admin.register(Competicao)
class CompeticaoAdmin(UnfoldModelAdmin):
    list_display = ('nome', 'federacao', 'status', 'data_inicio', 'data_fim')
    list_filter = ('federacao', 'status', 'modalidade')


@admin.register(Rodada)
class RodadaAdmin(UnfoldModelAdmin):
    list_display = ('competicao', 'etapa', 'grupo', 'numero')
    list_filter = ('competicao', 'etapa')


@admin.register(InscricaoEquipe)
class InscricaoEquipeAdmin(UnfoldModelAdmin):
    list_display = ('equipe', 'competicao', 'taxa_paga', 'data_pagamento', 'data_inscricao')
    list_filter = ('competicao', 'taxa_paga')
    list_editable = ('taxa_paga',)
    search_fields = ('equipe__nome_equipe',)


@admin.register(InscricaoAtleta)
class InscricaoAtletaAdmin(UnfoldModelAdmin):
    list_display = ('atleta', 'competicao', 'numero_camisa')
    list_filter = ('competicao',)
    search_fields = ('atleta__nome',)


@admin.register(Gol)
class GolAdmin(UnfoldModelAdmin):
    list_display = ('atleta', 'equipe', 'jogo', 'minuto', 'tipo')
    list_filter = ('tipo', 'jogo__rodada__competicao')


@admin.register(Classificacao)
class ClassificacaoAdmin(UnfoldModelAdmin):
    list_display = ('equipe', 'competicao', 'pontos', 'jogos', 'vitorias', 'empates', 'derrotas', 'saldo_gols')
    list_filter = ('competicao',)
    ordering = ('competicao', '-pontos')


@admin.register(EtapaKnockout)
class EtapaKnockoutAdmin(UnfoldModelAdmin):
    list_display = ('get_tipo_display', 'competicao', 'ordem', 'ida_e_volta', 'concluida')
    list_filter = ('competicao', 'tipo')
    ordering = ('competicao', 'ordem')


@admin.register(Grupo)
class GrupoAdmin(UnfoldModelAdmin):
    list_display = ('nome', 'competicao')
    list_filter = ('competicao',)
    filter_horizontal = ('equipes',)


@admin.register(ClassificacaoGrupo)
class ClassificacaoGrupoAdmin(UnfoldModelAdmin):
    list_display = ('equipe', 'grupo', 'pontos', 'jogos', 'vitorias', 'empates', 'derrotas', 'saldo_gols')
    list_filter = ('grupo__competicao', 'grupo')
    ordering = ('grupo', '-pontos')


@admin.register(Suspensao)
class SuspensaoAdmin(UnfoldModelAdmin):
    list_display = ('atleta', 'competicao', 'motivo', 'cumprida')
    list_filter = ('competicao', 'cumprida', 'motivo')
    list_editable = ('cumprida',)
    search_fields = ('atleta__nome',)


@admin.register(ConfrontoMatamate)
class ConfrontoMatamateAdmin(UnfoldModelAdmin):
    list_display = ('__str__', 'etapa', 'ordem', 'vencedor')
    list_filter = ('etapa__competicao', 'etapa')
    raw_id_fields = ('jogo_ida', 'jogo_volta')


@admin.register(Local)
class LocalAdmin(UnfoldModelAdmin):
    list_display = ('nome', 'federacao', 'cidade', 'capacidade')
    list_filter = ('federacao',)
    search_fields = ('nome', 'cidade')
