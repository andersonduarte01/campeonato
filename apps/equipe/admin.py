from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from apps.core.admin_mixins import TenantAwareAdminMixin
from .models import Atleta, Equipe


class AtletaInline(admin.TabularInline):
    model            = Atleta
    extra            = 0
    fields           = ('nome', 'posicao', 'situacao')
    readonly_fields  = ('nome', 'posicao', 'situacao')
    show_change_link = True
    can_delete       = False


@admin.register(Equipe)
class EquipeAdmin(TenantAwareAdminMixin, UnfoldModelAdmin):
    list_display  = ('nome_equipe', 'federacao', 'cidade', 'estado', 'cadastrado')
    list_filter   = ('federacao', 'estado')
    search_fields = ('nome_equipe', 'cidade')
    ordering      = ('federacao', 'nome_equipe')
    inlines       = [AtletaInline]


@admin.register(Atleta)
class AtletaAdmin(TenantAwareAdminMixin, UnfoldModelAdmin):
    tenant_lookup = 'equipe__federacao'
    list_display  = ('nome', 'equipe', 'posicao', 'situacao')
    list_filter   = ('situacao', 'posicao', 'equipe__federacao')
    search_fields = ('nome', 'equipe__nome_equipe')
    ordering      = ('equipe__nome_equipe', 'posicao', 'nome')
