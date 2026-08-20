from functools import wraps

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from .models import Competicao


def _rotulos(statuses):
    labels = dict(Competicao.STATUS_CHOICES)
    return ' ou '.join(f'"{labels[s]}"' for s in statuses)


def por_pk(param='pk'):
    def obter(request, kwargs):
        return get_object_or_404(
            Competicao, pk=kwargs[param], federacao=request.federacao,
        )
    return obter


def por_relacao(model, caminho, param='pk'):
    """Localiza a Competicao navegando o caminho de FKs (ex.: 'rodada__competicao')."""
    def obter(request, kwargs):
        obj = get_object_or_404(
            model.objects.select_related(caminho),
            pk=kwargs[param],
            **{f'{caminho}__federacao': request.federacao},
        )
        for parte in caminho.split('__'):
            obj = getattr(obj, parte)
        return obj
    return obter


def requer_status(*status_permitidos, obter=None):
    """
    Bloqueia a view se a competição não estiver em um dos status permitidos.
    Deve vir DEPOIS de @requer_papel (decorator mais interno), pois assume
    usuário autenticado e request.federacao definida.
    """
    if obter is None:
        obter = por_pk()

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            competicao = obter(request, kwargs)
            if competicao.status not in status_permitidos:
                messages.warning(
                    request,
                    f'Operação indisponível com a competição em '
                    f'"{competicao.get_status_display()}" — requer '
                    f'{_rotulos(status_permitidos)}.',
                )
                return redirect(
                    reverse('competicao:classificacao', kwargs={'pk': competicao.pk})
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
