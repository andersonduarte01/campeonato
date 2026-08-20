import datetime

from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect

from apps.core.permissao import requer_papel, APENAS_ADMIN, PODE_SECRETARIAR, PODE_DIRIGIR

from apps.equipe.models import Atleta, Equipe

from .dominio.excecoes import RegraVioladaError
from .dominio.transferencias import TransferenciaService
from .forms import (
    RegistroFederativoForm,
    JanelaTransferenciaForm, TransferenciaForm,
)
from .models import (
    RegistroFederativo, HistoricoClube,
    JanelaTransferencia, Transferencia,
)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Federativo
# ─────────────────────────────────────────────────────────────────────────────

@requer_papel(*PODE_SECRETARIAR)
def dashboard_federativo(request):
    hoje = datetime.date.today()
    fed  = request.federacao
    ctx = {
        'total_registros':    RegistroFederativo.objects.filter(federacao=fed).count(),
        'atletas_sem_reg':    Atleta.objects.filter(
            equipe__federacao=fed, registro_federativo__isnull=True,
        ).count(),
        'transferencias_pend': Transferencia.objects.filter(
            atleta__equipe__federacao=fed,
            status__in=[Transferencia.STATUS_SOLICITADA, Transferencia.STATUS_EM_ANALISE],
        ).count(),
        'janela_ativa':       JanelaTransferencia.objects.filter(
            federacao=fed, ativa=True, data_inicio__lte=hoje, data_fim__gte=hoje,
        ).first(),
        'clubes_filiados':    Equipe.objects.filter(
            federacao=fed, situacao=Equipe.SITUACAO_FILIADO,
        ).count(),
        'clubes_regularizacao': Equipe.objects.filter(
            federacao=fed, situacao=Equipe.SITUACAO_REGULARIZACAO,
        ).count(),
        'clubes_regularizacao_lista': Equipe.objects.filter(
            federacao=fed, situacao=Equipe.SITUACAO_REGULARIZACAO,
        ).order_by('nome_equipe'),
        'ultimas_transf':     Transferencia.objects.filter(
            atleta__equipe__federacao=fed,
        ).select_related('atleta', 'clube_origem', 'clube_destino').order_by('-criado_em')[:5],
    }
    return render(request, 'registro/dashboard.html', ctx)


# ─────────────────────────────────────────────────────────────────────────────
# 1. REGISTRO FEDERATIVO
# ─────────────────────────────────────────────────────────────────────────────

@requer_papel(*PODE_SECRETARIAR)
def registro_lista(request):
    q    = request.GET.get('q', '').strip()
    st   = request.GET.get('status', '')
    regs = (
        RegistroFederativo.objects
        .filter(federacao=request.federacao)
        .select_related('atleta__equipe')
        .order_by('numero_federativo')
    )
    if q:
        regs = regs.filter(atleta__nome__icontains=q)
    if st:
        regs = regs.filter(status=st)

    atletas_sem_reg = Atleta.objects.filter(
        equipe__federacao=request.federacao,
        registro_federativo__isnull=True,
    ).select_related('equipe').order_by('nome')

    return render(request, 'registro/registro_lista.html', {
        'registros':       regs,
        'atletas_sem_reg': atletas_sem_reg,
        'q':               q,
        'status_atual':    st,
        'status_choices':  RegistroFederativo.STATUS_CHOICES,
    })


@requer_papel(*PODE_SECRETARIAR)
def registro_criar(request):
    form = RegistroFederativoForm(request.POST or None, federacao=request.federacao)
    if request.method == 'POST' and form.is_valid():
        reg = form.save(commit=False)
        reg.federacao = request.federacao
        reg.save()
        HistoricoClube.objects.create(
            atleta=reg.atleta,
            equipe=reg.atleta.equipe,
            tipo=HistoricoClube.TIPO_TITULAR,
            data_entrada=reg.data_filiacao,
        )
        messages.success(request, f'Registro {reg.numero_federativo} criado com sucesso.')
        return redirect('registro:registro_detalhe', pk=reg.pk)
    return render(request, 'registro/registro_form.html', {'form': form, 'titulo': 'Novo Registro Federativo'})


@requer_papel(*PODE_SECRETARIAR)
def registro_editar(request, pk):
    reg  = get_object_or_404(RegistroFederativo, pk=pk, federacao=request.federacao)
    form = RegistroFederativoForm(request.POST or None, instance=reg, federacao=request.federacao)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Registro atualizado.')
        return redirect('registro:registro_detalhe', pk=pk)
    return render(request, 'registro/registro_form.html', {'form': form, 'reg': reg, 'titulo': 'Editar Registro Federativo'})


@requer_papel(*PODE_SECRETARIAR)
def registro_detalhe(request, pk):
    reg = get_object_or_404(
        RegistroFederativo.objects.select_related('atleta__equipe'),
        pk=pk, federacao=request.federacao,
    )
    historico = HistoricoClube.objects.filter(atleta=reg.atleta).select_related('equipe').order_by('-data_entrada')
    transfs   = Transferencia.objects.filter(atleta=reg.atleta).select_related(
        'clube_origem', 'clube_destino',
    ).order_by('-criado_em')
    return render(request, 'registro/registro_detalhe.html', {
        'reg': reg, 'historico': historico, 'transfs': transfs,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 2. TRANSFERÊNCIAS
# ─────────────────────────────────────────────────────────────────────────────

@requer_papel(*PODE_DIRIGIR)
def transferencia_lista(request):
    st     = request.GET.get('status', '')
    q      = request.GET.get('q', '').strip()
    hoje   = datetime.date.today()
    janela = JanelaTransferencia.objects.filter(
        federacao=request.federacao,
        ativa=True, data_inicio__lte=hoje, data_fim__gte=hoje,
    ).first()

    qs = Transferencia.objects.filter(
        atleta__equipe__federacao=request.federacao,
    ).select_related(
        'atleta__equipe', 'clube_origem', 'clube_destino', 'janela',
    ).order_by('-criado_em')
    if st:
        qs = qs.filter(status=st)
    if q:
        qs = qs.filter(atleta__nome__icontains=q)

    return render(request, 'registro/transferencia_lista.html', {
        'transferencias':  qs,
        'janela_ativa':    janela,
        'status_atual':    st,
        'status_choices':  Transferencia.STATUS_CHOICES,
        'q':               q,
    })


@requer_papel(*PODE_DIRIGIR)
def transferencia_criar(request):
    hoje = datetime.date.today()
    janela_aberta = JanelaTransferencia.objects.filter(
        federacao=request.federacao, ativa=True,
        data_inicio__lte=hoje, data_fim__gte=hoje,
    ).first()
    if not janela_aberta:
        messages.error(request, 'Não há janela de transferência aberta no momento.')
        return redirect('registro:transferencia_lista')
    form = TransferenciaForm(request.POST or None, federacao=request.federacao)
    atleta_equipe_map = {
        str(a.pk): a.equipe_id
        for a in form.fields['atleta'].queryset
    }
    if request.method == 'POST' and form.is_valid():
        transf = form.save(commit=False)
        transf.solicitado_por = request.user
        transf.save()
        messages.success(request, 'Transferência solicitada com sucesso.')
        return redirect('registro:transferencia_lista')
    return render(request, 'registro/transferencia_form.html', {
        'form': form,
        'atleta_equipe_map': atleta_equipe_map,
    })


@requer_papel(*PODE_DIRIGIR)
def transferencia_detalhe(request, pk):
    t = get_object_or_404(
        Transferencia.objects.select_related(
            'atleta__equipe', 'clube_origem', 'clube_destino', 'janela', 'solicitado_por',
        ),
        pk=pk, atleta__equipe__federacao=request.federacao,
    )
    return render(request, 'registro/transferencia_detalhe.html', {'transf': t})


def _get_transferencia(pk, federacao):
    return get_object_or_404(
        Transferencia, pk=pk, atleta__equipe__federacao=federacao,
    )


@requer_papel(*PODE_SECRETARIAR)
def transferencia_analisar(request, pk):
    if request.method != 'POST':
        return redirect('registro:transferencia_detalhe', pk=pk)
    t = _get_transferencia(pk, request.federacao)
    try:
        TransferenciaService().marcar_em_analise(t)
        messages.info(request, 'Transferência marcada como em análise.')
    except RegraVioladaError as e:
        messages.warning(request, str(e))
    return redirect('registro:transferencia_detalhe', pk=pk)


@requer_papel(*APENAS_ADMIN)
def transferencia_aprovar(request, pk):
    if request.method != 'POST':
        return redirect('registro:transferencia_detalhe', pk=pk)
    t = _get_transferencia(pk, request.federacao)
    try:
        TransferenciaService().aprovar(t, usuario=request.user)
        messages.success(request, f'Transferência de {t.atleta.nome} aprovada.')
    except RegraVioladaError as e:
        messages.warning(request, str(e))
    return redirect('registro:transferencia_detalhe', pk=pk)


@requer_papel(*PODE_SECRETARIAR)
def transferencia_rejeitar(request, pk):
    if request.method != 'POST':
        return redirect('registro:transferencia_detalhe', pk=pk)
    t = _get_transferencia(pk, request.federacao)
    try:
        TransferenciaService().rejeitar(t)
        messages.warning(request, 'Transferência rejeitada.')
    except RegraVioladaError as e:
        messages.warning(request, str(e))
    return redirect('registro:transferencia_detalhe', pk=pk)


@requer_papel(*PODE_SECRETARIAR)
def transferencia_cancelar(request, pk):
    if request.method != 'POST':
        return redirect('registro:transferencia_detalhe', pk=pk)
    t = _get_transferencia(pk, request.federacao)
    try:
        TransferenciaService().cancelar(t)
        messages.warning(request, 'Transferência cancelada.')
    except RegraVioladaError as e:
        messages.warning(request, str(e))
    return redirect('registro:transferencia_detalhe', pk=pk)


# ─────────────────────────────────────────────────────────────────────────────
# Janelas de Transferência
# ─────────────────────────────────────────────────────────────────────────────

@requer_papel(*PODE_SECRETARIAR)
def janela_lista(request):
    janelas = JanelaTransferencia.objects.filter(
        federacao=request.federacao,
    ).order_by('-data_inicio')
    form = JanelaTransferenciaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        janela = form.save(commit=False)
        janela.federacao = request.federacao
        janela.save()
        messages.success(request, 'Janela criada com sucesso.')
        return redirect('registro:janela_lista')
    return render(request, 'registro/janela_lista.html', {'janelas': janelas, 'form': form})


@requer_papel(*APENAS_ADMIN)
def janela_editar(request, pk):
    janela = get_object_or_404(JanelaTransferencia, pk=pk, federacao=request.federacao)
    form   = JanelaTransferenciaForm(request.POST or None, instance=janela)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Janela atualizada.')
        return redirect('registro:janela_lista')
    return render(request, 'registro/janela_form.html', {'form': form, 'janela': janela})
