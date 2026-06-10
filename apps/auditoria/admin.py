from django.contrib import admin
from .models import AuditLog, ConsentimentoLGPD


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ('criado_em', 'acao', 'usuario_email', 'modelo', 'objeto_repr', 'ip_address')
    list_filter   = ('acao', 'modelo')
    search_fields = ('usuario_email', 'descricao', 'objeto_repr', 'ip_address')
    readonly_fields = ('usuario', 'usuario_email', 'acao', 'modelo', 'objeto_id',
                       'objeto_repr', 'descricao', 'dados_anteriores', 'dados_novos',
                       'ip_address', 'user_agent', 'criado_em')
    date_hierarchy = 'criado_em'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ConsentimentoLGPD)
class ConsentimentoLGPDAdmin(admin.ModelAdmin):
    list_display  = ('usuario', 'tipo', 'aceito', 'registrado_em', 'atualizado_em')
    list_filter   = ('tipo', 'aceito')
    search_fields = ('usuario__email',)
    readonly_fields = ('registrado_em', 'atualizado_em')
