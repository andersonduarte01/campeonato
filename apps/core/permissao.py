from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse_lazy

from .models import UsuarioFederacao

# ---------------------------------------------------------------------------
# Grupos de papéis — prontos para uso com *splat
# ---------------------------------------------------------------------------
APENAS_ADMIN   = (UsuarioFederacao.ADMIN,)
PODE_SECRETARIAR = (UsuarioFederacao.ADMIN, UsuarioFederacao.SECRETARIO)
PODE_ARBITRAR  = (UsuarioFederacao.ADMIN, UsuarioFederacao.SECRETARIO, UsuarioFederacao.ARBITRO)
PODE_DIRIGIR   = (UsuarioFederacao.ADMIN, UsuarioFederacao.SECRETARIO, UsuarioFederacao.DIRIGENTE)
TODOS_INTERNOS = (UsuarioFederacao.ADMIN, UsuarioFederacao.SECRETARIO,
                  UsuarioFederacao.ARBITRO, UsuarioFederacao.DIRIGENTE)


# ---------------------------------------------------------------------------
# Mixin para class-based views
# ---------------------------------------------------------------------------
class PermissaoFederacaoMixin:
    """
    Garante autenticação + vínculo ativo com a federação da sessão.
    Defina `papeis_permitidos` para restringir por papel.

    Uso:
        class MinhaView(PermissaoFederacaoMixin, View):
            papeis_permitidos = PODE_SECRETARIAR
    """
    login_url         = reverse_lazy('core:login')
    papeis_permitidos: tuple | list | set = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(self.login_url)

        # Superusuário da plataforma passa direto
        if request.user.is_admin:
            return super().dispatch(request, *args, **kwargs)

        vinculo = getattr(request, 'vinculo', None)

        # Fallback seguro: middleware pode não ter rodado em alguns edge cases
        if vinculo is None:
            federacao = getattr(request, 'federacao', None)
            if federacao:
                vinculo = UsuarioFederacao.objects.filter(
                    usuario=request.user,
                    federacao=federacao,
                    ativo=True,
                ).first()

        if not vinculo:
            raise PermissionDenied('Usuário sem vínculo ativo com esta federação.')

        request.vinculo = vinculo

        if self.papeis_permitidos and vinculo.papel not in self.papeis_permitidos:
            raise PermissionDenied('Permissão insuficiente para este papel.')

        return super().dispatch(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Decorator para function-based views
# ---------------------------------------------------------------------------
def requer_papel(*papeis):
    """
    Restringe uma FBV a usuários com um dos papéis indicados na federação ativa.
    Já inclui verificação de login.

    Uso:
        @requer_papel(*PODE_SECRETARIAR)
        def minha_view(request):
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('core:login')

            if request.user.is_admin:
                return view_func(request, *args, **kwargs)

            vinculo = getattr(request, 'vinculo', None)
            if not vinculo or (papeis and vinculo.papel not in papeis):
                messages.error(request, 'Acesso negado. Permissão insuficiente.')
                return redirect('core:index')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
