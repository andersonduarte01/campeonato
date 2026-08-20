from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin

from .forms import UserChangeForm, UserCreationForm
from .models import Federacao, Usuario, UsuarioFederacao


@admin.register(Federacao)
class FederacaoAdmin(UnfoldModelAdmin):
    list_display  = ('nome', 'sigla', 'slug', 'email', 'ativa', 'criada_em')
    list_filter   = ('ativa',)
    search_fields = ('nome', 'sigla', 'slug', 'email', 'cnpj')
    prepopulated_fields = {'slug': ('nome',)}


class UsuarioFederacaoInline(admin.TabularInline):
    model  = UsuarioFederacao
    extra  = 1
    fields = ('federacao', 'papel', 'equipe', 'ativo')
    autocomplete_fields = ('equipe',)


@admin.register(UsuarioFederacao)
class UsuarioFederacaoAdmin(UnfoldModelAdmin):
    list_display  = ('usuario', 'federacao', 'papel', 'equipe', 'ativo', 'data_vinculo')
    list_filter   = ('papel', 'ativo', 'federacao')
    search_fields = ('usuario__email', 'usuario__nome', 'federacao__nome')
    autocomplete_fields = ('equipe',)


class UserAdmin(UnfoldModelAdmin, BaseUserAdmin):
    form      = UserChangeForm
    add_form  = UserCreationForm
    list_display  = ('email', 'nome', 'is_admin', 'is_active', 'cadastrado_em')
    list_filter   = ('is_admin', 'is_active')
    search_fields = ('email', 'nome')
    ordering      = ('email',)
    filter_horizontal = ()
    inlines       = [UsuarioFederacaoInline]
    fieldsets = (
        (None,                    {'fields': ('email', 'password')}),
        ('Informações pessoais',  {'fields': ('nome',)}),
        ('Permissões',            {'fields': ('is_admin', 'is_active')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('email', 'nome', 'password1', 'password2'),
        }),
    )


admin.site.register(Usuario, UserAdmin)
