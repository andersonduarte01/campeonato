import json

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone

from apps.core.permissao import PODE_SECRETARIAR, requer_papel

from .models import AuditoriaEvento, ConsentimentoLGPD
from .utils import get_client_ip


@login_required
def lgpd_dashboard_view(request):
    usuario = request.user

    if request.method == 'POST':
        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')[:500]
        for tipo, _ in ConsentimentoLGPD.TIPO_CHOICES:
            aceito = tipo in request.POST
            ConsentimentoLGPD.objects.update_or_create(
                usuario=usuario, tipo=tipo,
                defaults={'aceito': aceito, 'ip_address': ip, 'user_agent': ua},
            )
        messages.success(request, 'Consentimentos atualizados.')
        return redirect(reverse('auditoria:lgpd_dashboard'))

    consentimentos_qs = {c.tipo: c for c in ConsentimentoLGPD.objects.filter(usuario=usuario)}
    tipo_choices_state = []
    for tipo, label in ConsentimentoLGPD.TIPO_CHOICES:
        obj = consentimentos_qs.get(tipo)
        tipo_choices_state.append({
            'tipo':        tipo,
            'label':       label,
            'aceito':      obj.aceito if obj else False,
            'atualizado':  obj.atualizado_em if obj else None,
        })

    return render(request, 'auditoria/lgpd_dashboard.html', {
        'tipo_choices_state': tipo_choices_state,
    })


@login_required
def lgpd_exportar_dados_view(request):
    usuario = request.user

    consentimentos = list(
        ConsentimentoLGPD.objects.filter(usuario=usuario)
        .values('tipo', 'aceito', 'registrado_em', 'atualizado_em')
    )
    vinculos = list(
        usuario.usuariofederacao_set.select_related('federacao')
        .values('federacao__nome', 'papel', 'ativo', 'data_vinculo')
    )

    dados = {
        'exportado_em': timezone.now().isoformat(),
        'usuario': {
            'id':            usuario.pk,
            'email':         usuario.email,
            'nome':          usuario.nome,
            'cadastrado_em': str(usuario.cadastrado_em),
        },
        'vinculos_federacoes': [
            {k: str(v) for k, v in v_.items()} for v_ in vinculos
        ],
        'consentimentos_lgpd': [
            {k: str(v) for k, v in c.items()} for c in consentimentos
        ],
    }

    payload = json.dumps(dados, ensure_ascii=False, indent=2)
    response = HttpResponse(payload, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="dados_pessoais_{usuario.pk}.json"'
    return response


@requer_papel(*PODE_SECRETARIAR)
def eventos_lista_view(request):
    qs = AuditoriaEvento.objects.filter(federacao=request.federacao)
    tipo = request.GET.get('tipo', '').strip()
    if tipo:
        qs = qs.filter(tipo=tipo)
    qs = qs.select_related('usuario').order_by('-registrado_em')
    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'auditoria/eventos_lista.html', {
        'page': page,
        'tipo_atual': tipo,
    })


@login_required
def lgpd_anonimizar_view(request):
    if request.method == 'POST':
        if request.POST.get('confirmacao', '') == 'CONFIRMAR':
            usuario = request.user
            pk = usuario.pk
            usuario.email    = f'anonimizado_{pk}@champs.invalid'
            usuario.nome     = f'Usuário Anonimizado #{pk}'
            usuario.is_active = False
            # Rotaciona a senha para hash inválido — invalida logins
            # anteriores E é_password_correct passa a falhar sempre.
            usuario.set_unusable_password()
            usuario.save(update_fields=['email', 'nome', 'is_active', 'password'])
            # Invalida todas as sessões do usuário em outros dispositivos.
            _invalidar_sessoes(usuario)
            logout(request)
            messages.success(request, 'Seus dados foram anonimizados. Conta desativada.')
            return redirect(reverse('core:login'))
        messages.error(request, 'Confirmação incorreta. Nenhuma ação foi realizada.')
        return redirect(reverse('auditoria:lgpd_dashboard'))

    return render(request, 'auditoria/lgpd_anonimizar.html')


def _invalidar_sessoes(usuario):
    """Apaga todas as django.contrib.sessions do usuário informado."""
    from django.contrib.sessions.models import Session
    for sess in Session.objects.iterator():
        try:
            data = sess.get_decoded()
        except Exception:
            continue
        if str(data.get('_auth_user_id')) == str(usuario.pk):
            sess.delete()
