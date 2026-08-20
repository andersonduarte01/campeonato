"""Mixins para tornar o Django admin tenant-aware.

O modelo de tenant do CHAMPS separa:
- SUPERADMIN da plataforma: Usuario.is_admin=True — enxerga todas as
  federações no admin do Django. Usado pela equipe da Anthropic/CHAMPS
  para suporte.
- ADMIN da federação: UsuarioFederacao.papel='ADMIN' — não é is_admin
  na conta Django; NÃO entra no /admin/ (não é is_staff).

Este mixin garante que, mesmo se um is_admin=True eventualmente logar
com um "chapéu" de federação (session['federacao_id'] populado), o admin
mostre só dados da federação corrente — evitando vazamento acidental.
Superadmin sem federação no session vê tudo (comportamento atual).
"""


class TenantAwareAdminMixin:
    """Filtra queryset e valida save por request.federacao.

    Aplicar em ModelAdmin de modelos que têm FK para core.Federacao
    (direta ou via ``tenant_lookup`` para modelos indiretos).
    """

    #: Nome do lookup do queryset para chegar em federacao.
    #: - 'federacao' para modelos com FK direta.
    #: - 'rodada__competicao__federacao' para modelos aninhados.
    tenant_lookup = 'federacao'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        fed = getattr(request, 'federacao', None)
        # Superadmin sem sessão de federação: acesso irrestrito.
        if fed is None and getattr(request.user, 'is_admin', False):
            return qs
        if fed is None:
            return qs.none()
        return qs.filter(**{self.tenant_lookup: fed})

    def save_model(self, request, obj, form, change):
        # Se o modelo tem campo direto 'federacao' e o operador está no
        # contexto de uma federação, força o valor para evitar cross-tenant.
        if self.tenant_lookup == 'federacao':
            fed = getattr(request, 'federacao', None)
            if fed is not None and not getattr(obj, 'federacao_id', None):
                obj.federacao = fed
        super().save_model(request, obj, form, change)
