"""
Utilitários de controle de acesso por perfil de usuário.

Grupos disponíveis (use como *GRUPO na assinatura do decorator):
  APENAS_ADMIN       — somente Administrador
  PODE_ORGANIZAR     — Admin + Organizador
  PODE_GERIR_EQUIPE  — Admin + Organizador + Delegado
  PODE_LANCAMENTO    — Admin + Organizador + Árbitro
  PODE_LANCAMENTO_DELE — Admin + Organizador + Árbitro + Delegado
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import Usuario

# ---------------------------------------------------------------------------
# Grupos de perfis — tuplas prontas para uso com *splat
# ---------------------------------------------------------------------------
APENAS_ADMIN         = (Usuario.ADMIN,)
PODE_ORGANIZAR       = (Usuario.ADMIN, Usuario.ORGANIZADOR)
PODE_GERIR_EQUIPE    = (Usuario.ADMIN, Usuario.ORGANIZADOR, Usuario.DELEGADO)
PODE_LANCAMENTO      = (Usuario.ADMIN, Usuario.ORGANIZADOR, Usuario.ARBITRO)
PODE_LANCAMENTO_DELE = (Usuario.ADMIN, Usuario.ORGANIZADOR, Usuario.ARBITRO, Usuario.DELEGADO)


def _tem_perfil(user, perfis):
    """Retorna True se o usuário é is_admin OU tem o perfil na lista."""
    return user.is_admin or user.perfil in perfis


# ---------------------------------------------------------------------------
# Decorator para function-based views
# ---------------------------------------------------------------------------

def requer_perfil(*perfis):
    """
    Restringe uma FBV a usuários com um dos perfis indicados.
    Já inclui verificação de login — não precisa combinar com @login_required.

    Uso:
        @requer_perfil(*PODE_ORGANIZAR)
        def minha_view(request, ...):
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('core:login')
            if not _tem_perfil(request.user, perfis):
                messages.error(
                    request,
                    f'Acesso negado. Esta ação requer perfil: '
                    f'{", ".join(p.capitalize() for p in perfis)}.',
                )
                return redirect('core:index')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Mixin para class-based views
# ---------------------------------------------------------------------------

class PerfilRequiredMixin:
    """
    Mixin para CBVs. Defina perfis_permitidos na subclasse.
    Deve vir antes de LoginRequiredMixin na MRO.

    Uso:
        class MinhaView(PerfilRequiredMixin, LoginRequiredMixin, ListView):
            perfis_permitidos = PODE_ORGANIZAR
    """
    perfis_permitidos: tuple = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        if not _tem_perfil(request.user, self.perfis_permitidos):
            messages.error(
                request,
                f'Acesso negado. Esta ação requer perfil: '
                f'{", ".join(p.capitalize() for p in self.perfis_permitidos)}.',
            )
            return redirect('core:index')
        return super().dispatch(request, *args, **kwargs)
