from django.contrib import admin
from .models import (
    Competicao, Jogo, Rodada, Gol, Cartao, InscricaoAtleta, Classificacao,
    Fase, Grupo, ClassificacaoGrupo, ConfrontoMatamate, Suspensao,
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
