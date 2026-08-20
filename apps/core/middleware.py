import logging

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class FederacaoMiddleware(MiddlewareMixin):

    ROTAS_PUBLICAS = {
        'core:login',
        'core:logout',
        'core:password_reset',
        'core:password_reset_done',
        'core:password_reset_confirm',
        'core:password_reset_complete',
        'core:selecionar_federacao',
    }

    def process_request(self, request):
        request.federacao = None
        request.vinculo   = None
        request.tem_multiplas_federacoes = False

        # Admin do Django não precisa de contexto de federação
        if request.path.startswith('/admin/'):
            return

        # Rotas estáticas/media
        if request.path.startswith(('/static/', '/media/')):
            return

        try:
            match    = resolve(request.path_info)
            url_name = (
                f"{match.namespace}:{match.url_name}"
                if match.namespace else match.url_name
            )
            if url_name in self.ROTAS_PUBLICAS:
                return
        except Exception as exc:
            logger.warning('FederacaoMiddleware: erro ao resolver %s — %s', request.path_info, exc)
            return

        if not request.user.is_authenticated:
            return

        # Superusuário da plataforma (is_admin) não precisa de vínculo
        if request.user.is_admin:
            return

        federacao_id = request.session.get('federacao_id')

        if not federacao_id:
            return self._handle_sem_federacao(request)

        from .models import Federacao, UsuarioFederacao

        try:
            federacao = Federacao.objects.get(id=federacao_id)
        except Federacao.DoesNotExist:
            return self._limpar_sessao(request)

        if not federacao.ativa:
            return self._limpar_sessao(request)

        try:
            vinculo = UsuarioFederacao.objects.select_related('federacao').get(
                usuario=request.user,
                federacao=federacao,
                ativo=True,
            )
        except UsuarioFederacao.DoesNotExist:
            return self._limpar_sessao(request)

        request.federacao = federacao
        request.vinculo   = vinculo
        request.tem_multiplas_federacoes = (
            UsuarioFederacao.objects
            .filter(usuario=request.user, ativo=True)
            .count() > 1
        )

    # ------------------------------------------------------------------ #

    def _handle_sem_federacao(self, request):
        from .models import UsuarioFederacao

        vinculos = (
            UsuarioFederacao.objects
            .filter(usuario=request.user, ativo=True, federacao__ativa=True)
            .select_related('federacao')
        )

        if not vinculos.exists():
            logout(request)
            return redirect('core:login')

        if vinculos.count() == 1:
            vinculo = vinculos.first()
            request.session['federacao_id'] = vinculo.federacao.id
            request.federacao = vinculo.federacao
            request.vinculo   = vinculo
            return

        return redirect('core:selecionar_federacao')

    def _limpar_sessao(self, request):
        from .models import UsuarioFederacao

        request.session.pop('federacao_id', None)

        vinculos = UsuarioFederacao.objects.filter(
            usuario=request.user, ativo=True, federacao__ativa=True,
        )

        if not vinculos.exists():
            logout(request)
            return redirect('core:login')

        return redirect('core:selecionar_federacao')
