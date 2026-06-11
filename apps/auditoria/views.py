import json

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from apps.core.permissions import requer_perfil, APENAS_ADMIN
from .models import AuditLog, ConsentimentoLGPD
from .utils import registrar_auditoria, get_client_ip


# ---------------------------------------------------------------------------
# Audit Log — administração
# ---------------------------------------------------------------------------

@requer_perfil(*APENAS_ADMIN)
def audit_log_lista_view(request):
    qs = AuditLog.objects.select_related('usuario').order_by('-criado_em')

    acao     = request.GET.get('acao', '')
    modelo   = request.GET.get('modelo', '')
    q        = request.GET.get('q', '')
    data_de  = request.GET.get('data_de', '')
    data_ate = request.GET.get('data_ate', '')

    if acao:
        qs = qs.filter(acao=acao)
    if modelo:
        qs = qs.filter(modelo__icontains=modelo)
    if q:
        qs = qs.filter(
            Q(descricao__icontains=q) |
            Q(objeto_repr__icontains=q) |
            Q(usuario_email__icontains=q)
        )
    if data_de:
        qs = qs.filter(criado_em__date__gte=data_de)
    if data_ate:
        qs = qs.filter(criado_em__date__lte=data_ate)

    paginator = Paginator(qs, 50)
    page      = request.GET.get('page', 1)
    logs      = paginator.get_page(page)

    modelos_distintos = (
        AuditLog.objects.values_list('modelo', flat=True)
        .exclude(modelo='').distinct().order_by('modelo')
    )

    return render(request, 'auditoria/log_lista.html', {
        'logs':               logs,
        'acao_filtro':        acao,
        'modelo_filtro':      modelo,
        'q':                  q,
        'data_de':            data_de,
        'data_ate':           data_ate,
        'acao_choices':       AuditLog.ACAO_CHOICES,
        'modelos_distintos':  modelos_distintos,
        'total':              qs.count(),
    })


@requer_perfil(*APENAS_ADMIN)
def audit_log_detalhe_view(request, pk):
    log = get_object_or_404(AuditLog, pk=pk)
    return render(request, 'auditoria/log_detalhe.html', {'log': log})


# ---------------------------------------------------------------------------
# LGPD — acessível por todos os usuários autenticados
# ---------------------------------------------------------------------------

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
        registrar_auditoria(
            request, 'editar',
            descricao='Consentimentos LGPD atualizados pelo titular',
            objeto=usuario,
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

    total_logs = AuditLog.objects.filter(usuario=usuario).count()

    return render(request, 'auditoria/lgpd_dashboard.html', {
        'tipo_choices_state': tipo_choices_state,
        'total_logs':         total_logs,
    })


@login_required
def lgpd_exportar_dados_view(request):
    usuario = request.user

    consentimentos = list(
        ConsentimentoLGPD.objects.filter(usuario=usuario)
        .values('tipo', 'aceito', 'registrado_em', 'atualizado_em')
    )
    logs = list(
        AuditLog.objects.filter(usuario=usuario)
        .values('acao', 'modelo', 'objeto_repr', 'descricao', 'ip_address', 'criado_em')
        .order_by('-criado_em')[:200]
    )

    dados = {
        'exportado_em': timezone.now().isoformat(),
        'usuario': {
            'id':            usuario.pk,
            'email':         usuario.email,
            'nome':          usuario.nome,
            'perfil':        usuario.perfil,
            'cadastrado_em': str(usuario.cadastrado_em),
        },
        'consentimentos_lgpd': [
            {k: str(v) for k, v in c.items()} for c in consentimentos
        ],
        'registros_auditoria': [
            {k: str(v) for k, v in log.items()} for log in logs
        ],
    }

    registrar_auditoria(
        request, 'exportar',
        descricao='Exportação de dados pessoais LGPD solicitada pelo titular',
        objeto=usuario,
    )

    payload = json.dumps(dados, ensure_ascii=False, indent=2)
    response = HttpResponse(payload, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="dados_pessoais_{usuario.pk}.json"'
    return response


@login_required
def lgpd_anonimizar_view(request):
    if request.method == 'POST':
        if request.POST.get('confirmacao', '') == 'CONFIRMAR':
            usuario = request.user
            registrar_auditoria(
                request, 'excluir',
                descricao='Anonimização de dados pessoais solicitada pelo titular (LGPD)',
                objeto=usuario,
            )
            pk = usuario.pk
            usuario.email    = f'anonimizado_{pk}@champs.invalid'
            usuario.nome     = f'Usuário Anonimizado #{pk}'
            usuario.is_active = False
            usuario.save(update_fields=['email', 'nome', 'is_active'])
            logout(request)
            messages.success(request, 'Seus dados foram anonimizados. Conta desativada.')
            return redirect(reverse('core:login'))
        messages.error(request, 'Confirmação incorreta. Nenhuma ação foi realizada.')
        return redirect(reverse('auditoria:lgpd_dashboard'))

    return render(request, 'auditoria/lgpd_anonimizar.html')
