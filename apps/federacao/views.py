import datetime

from django.contrib import messages
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from apps.equipe.models import Atleta, Equipe
from apps.competicao.models import Arbitro

from .forms import (
    RegistroFederativoForm, HistoricoClubeForm,
    JanelaTransferenciaForm, TransferenciaForm,
    InfoClubeForm, TipoDocumentoForm, DocumentoForm, DocumentoAprovarForm,
)
from .models import (
    RegistroFederativo, HistoricoClube,
    JanelaTransferencia, Transferencia,
    InfoClube, TipoDocumento, Documento,
)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Federativo
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def dashboard_federativo(request):
    hoje = datetime.date.today()
    ctx = {
        'total_registros':    RegistroFederativo.objects.count(),
        'atletas_sem_reg':    Atleta.objects.filter(registro_federativo__isnull=True).count(),
        'transferencias_pend': Transferencia.objects.filter(
            status__in=[Transferencia.STATUS_SOLICITADA, Transferencia.STATUS_EM_ANALISE]
        ).count(),
        'janela_ativa':       JanelaTransferencia.objects.filter(
            ativa=True, data_inicio__lte=hoje, data_fim__gte=hoje,
        ).first(),
        'docs_pendentes':     Documento.objects.filter(status=Documento.STATUS_PENDENTE).count(),
        'docs_vencidos':      Documento.objects.filter(
            status=Documento.STATUS_APROVADO, data_vencimento__lt=hoje,
        ).count(),
        'clubes_filiados':    InfoClube.objects.filter(situacao=InfoClube.SITUACAO_FILIADO).count(),
        'clubes_sem_perfil':  Equipe.objects.filter(info_clube__isnull=True).count(),
        'ultimas_transf':     Transferencia.objects.select_related(
            'atleta', 'clube_origem', 'clube_destino',
        ).order_by('-criado_em')[:5],
        'docs_recentes':      Documento.objects.select_related('tipo', 'atleta', 'clube').order_by('-enviado_em')[:5],
    }
    return render(request, 'federacao/dashboard.html', ctx)


# ─────────────────────────────────────────────────────────────────────────────
# 1. REGISTRO FEDERATIVO
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def registro_lista(request):
    q    = request.GET.get('q', '').strip()
    st   = request.GET.get('status', '')
    regs = (
        RegistroFederativo.objects
        .select_related('atleta__equipe')
        .order_by('numero_federativo')
    )
    if q:
        regs = regs.filter(atleta__nome__icontains=q)
    if st:
        regs = regs.filter(status=st)

    atletas_sem_reg = Atleta.objects.filter(
        registro_federativo__isnull=True,
    ).select_related('equipe').order_by('nome')

    return render(request, 'federacao/registro_lista.html', {
        'registros':       regs,
        'atletas_sem_reg': atletas_sem_reg,
        'q':               q,
        'status_atual':    st,
        'status_choices':  RegistroFederativo.STATUS_CHOICES,
    })


@login_required
def registro_criar(request):
    form = RegistroFederativoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        reg = form.save()
        # Cria histórico de clube inicial
        HistoricoClube.objects.create(
            atleta=reg.atleta,
            equipe=reg.atleta.equipe,
            tipo=HistoricoClube.TIPO_TITULAR,
            data_entrada=reg.data_filiacao,
        )
        messages.success(request, f'Registro {reg.numero_federativo} criado com sucesso.')
        return redirect('federacao:registro_detalhe', pk=reg.pk)
    return render(request, 'federacao/registro_form.html', {'form': form, 'titulo': 'Novo Registro Federativo'})


@login_required
def registro_editar(request, pk):
    reg  = get_object_or_404(RegistroFederativo, pk=pk)
    form = RegistroFederativoForm(request.POST or None, instance=reg)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Registro atualizado.')
        return redirect('federacao:registro_detalhe', pk=pk)
    return render(request, 'federacao/registro_form.html', {'form': form, 'reg': reg, 'titulo': 'Editar Registro Federativo'})


@login_required
def registro_detalhe(request, pk):
    reg       = get_object_or_404(RegistroFederativo.objects.select_related('atleta__equipe'), pk=pk)
    historico = HistoricoClube.objects.filter(atleta=reg.atleta).select_related('equipe').order_by('-data_entrada')
    docs      = Documento.objects.filter(atleta=reg.atleta).select_related('tipo').order_by('-enviado_em')
    transfs   = Transferencia.objects.filter(atleta=reg.atleta).select_related(
        'clube_origem', 'clube_destino',
    ).order_by('-criado_em')
    return render(request, 'federacao/registro_detalhe.html', {
        'reg': reg, 'historico': historico, 'docs': docs, 'transfs': transfs,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 2. TRANSFERÊNCIAS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def transferencia_lista(request):
    st     = request.GET.get('status', '')
    q      = request.GET.get('q', '').strip()
    hoje   = datetime.date.today()
    janela = JanelaTransferencia.objects.filter(
        ativa=True, data_inicio__lte=hoje, data_fim__gte=hoje,
    ).first()

    qs = Transferencia.objects.select_related(
        'atleta__equipe', 'clube_origem', 'clube_destino', 'janela',
    ).order_by('-criado_em')
    if st:
        qs = qs.filter(status=st)
    if q:
        qs = qs.filter(atleta__nome__icontains=q)

    return render(request, 'federacao/transferencia_lista.html', {
        'transferencias':  qs,
        'janela_ativa':    janela,
        'status_atual':    st,
        'status_choices':  Transferencia.STATUS_CHOICES,
        'q':               q,
    })


@login_required
def transferencia_criar(request):
    form = TransferenciaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        transf = form.save(commit=False)
        transf.solicitado_por = request.user
        transf.save()
        messages.success(request, 'Transferência solicitada com sucesso.')
        return redirect('federacao:transferencia_lista')
    return render(request, 'federacao/transferencia_form.html', {'form': form, 'titulo': 'Solicitar Transferência'})


@login_required
def transferencia_detalhe(request, pk):
    t = get_object_or_404(
        Transferencia.objects.select_related(
            'atleta__equipe', 'clube_origem', 'clube_destino', 'janela', 'solicitado_por',
        ), pk=pk,
    )
    return render(request, 'federacao/transferencia_detalhe.html', {'transf': t})


@login_required
def transferencia_acao(request, pk, acao):
    t = get_object_or_404(Transferencia, pk=pk)
    if request.method == 'POST':
        if acao == 'analisar' and t.status == Transferencia.STATUS_SOLICITADA:
            t.status = Transferencia.STATUS_EM_ANALISE
            t.save()
            messages.info(request, 'Transferência marcada como em análise.')
        elif acao == 'aprovar' and t.status in (Transferencia.STATUS_SOLICITADA, Transferencia.STATUS_EM_ANALISE):
            t.aprovar(usuario=request.user)
            messages.success(request, f'Transferência de {t.atleta.nome} aprovada.')
        elif acao == 'rejeitar' and t.status in (Transferencia.STATUS_SOLICITADA, Transferencia.STATUS_EM_ANALISE):
            t.rejeitar()
            messages.warning(request, 'Transferência rejeitada.')
        elif acao == 'cancelar' and t.status not in (Transferencia.STATUS_APROVADA, Transferencia.STATUS_REJEITADA):
            t.cancelar()
            messages.warning(request, 'Transferência cancelada.')
        else:
            messages.error(request, 'Ação inválida para o status atual.')
    return redirect('federacao:transferencia_detalhe', pk=pk)


# ─────────────────────────────────────────────────────────────────────────────
# Janelas de Transferência
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def janela_lista(request):
    janelas = JanelaTransferencia.objects.order_by('-data_inicio')
    form    = JanelaTransferenciaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Janela criada com sucesso.')
        return redirect('federacao:janela_lista')
    return render(request, 'federacao/janela_lista.html', {'janelas': janelas, 'form': form})


@login_required
def janela_editar(request, pk):
    janela = get_object_or_404(JanelaTransferencia, pk=pk)
    form   = JanelaTransferenciaForm(request.POST or None, instance=janela)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Janela atualizada.')
        return redirect('federacao:janela_lista')
    return render(request, 'federacao/janela_form.html', {'form': form, 'janela': janela})


# ─────────────────────────────────────────────────────────────────────────────
# 3. PERFIL FEDERATIVO DO CLUBE
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def clube_lista(request):
    q      = request.GET.get('q', '').strip()
    sit    = request.GET.get('situacao', '')
    clubes = (
        InfoClube.objects
        .select_related('equipe')
        .order_by('equipe__nome_equipe')
    )
    if q:
        clubes = clubes.filter(equipe__nome_equipe__icontains=q)
    if sit:
        clubes = clubes.filter(situacao=sit)

    sem_perfil = Equipe.objects.filter(info_clube__isnull=True).order_by('nome_equipe')

    return render(request, 'federacao/clube_lista.html', {
        'clubes':          clubes,
        'sem_perfil':      sem_perfil,
        'q':               q,
        'situacao_atual':  sit,
        'situacao_choices': InfoClube.SITUACAO_CHOICES,
    })


@login_required
def clube_criar(request):
    equipe_pk = request.GET.get('equipe')
    initial   = {}
    if equipe_pk:
        equipe = get_object_or_404(Equipe, pk=equipe_pk)
        initial['equipe'] = equipe
    form = InfoClubeForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        info = form.save()
        messages.success(request, f'Perfil federativo de {info.equipe.nome_equipe} criado.')
        return redirect('federacao:clube_detalhe', pk=info.pk)
    return render(request, 'federacao/clube_form.html', {'form': form, 'titulo': 'Novo Perfil Federativo'})


@login_required
def clube_editar(request, pk):
    info = get_object_or_404(InfoClube, pk=pk)
    form = InfoClubeForm(request.POST or None, instance=info)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Perfil atualizado.')
        return redirect('federacao:clube_detalhe', pk=pk)
    return render(request, 'federacao/clube_form.html', {'form': form, 'info': info, 'titulo': 'Editar Perfil Federativo'})


@login_required
def clube_detalhe(request, pk):
    info  = get_object_or_404(InfoClube.objects.select_related('equipe'), pk=pk)
    docs  = Documento.objects.filter(clube=info.equipe).select_related('tipo').order_by('-enviado_em')
    hist  = HistoricoClube.objects.filter(equipe=info.equipe).select_related('atleta').order_by('-data_entrada')
    return render(request, 'federacao/clube_detalhe.html', {
        'info': info, 'docs': docs, 'historico': hist,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 4. DOCUMENTOS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def documento_lista(request):
    st     = request.GET.get('status', '')
    ent    = request.GET.get('entidade', '')
    q      = request.GET.get('q', '').strip()

    docs = (
        Documento.objects
        .select_related('tipo', 'clube', 'atleta', 'arbitro', 'aprovado_por')
        .order_by('-enviado_em')
    )
    if st:
        docs = docs.filter(status=st)
    if ent:
        docs = docs.filter(tipo__entidade=ent)

    return render(request, 'federacao/documento_lista.html', {
        'documentos':       docs,
        'status_atual':     st,
        'entidade_atual':   ent,
        'status_choices':   Documento.STATUS_CHOICES,
        'entidade_choices': TipoDocumento.ENTIDADE_CHOICES,
    })


@login_required
def documento_upload(request):
    equipe_pk = request.GET.get('clube')
    atleta_pk = request.GET.get('atleta')
    initial   = {}
    if equipe_pk:
        initial['clube'] = get_object_or_404(Equipe, pk=equipe_pk)
    if atleta_pk:
        initial['atleta'] = get_object_or_404(Atleta, pk=atleta_pk)

    form = DocumentoForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        doc = form.save()
        messages.success(request, f'Documento "{doc.tipo.nome}" enviado e aguardando aprovação.')
        return redirect('federacao:documento_lista')
    return render(request, 'federacao/documento_form.html', {'form': form})


@login_required
def documento_aprovar(request, pk):
    doc  = get_object_or_404(Documento, pk=pk)
    form = DocumentoAprovarForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        decisao = form.cleaned_data['decisao']
        obs     = form.cleaned_data.get('observacoes', '')
        if obs:
            doc.observacoes = (doc.observacoes + '\n' + obs).strip()
        if decisao == 'aprovado':
            doc.status       = Documento.STATUS_APROVADO
            doc.aprovado_por = request.user
            doc.data_aprovacao = timezone.now()
            messages.success(request, 'Documento aprovado.')
        else:
            doc.status = Documento.STATUS_REJEITADO
            messages.warning(request, 'Documento rejeitado.')
        doc.save()
        return redirect('federacao:documento_lista')

    return render(request, 'federacao/documento_aprovar.html', {'doc': doc, 'form': form})


# ─────────────────────────────────────────────────────────────────────────────
# Tipos de Documento
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def tipo_documento_lista(request):
    tipos = TipoDocumento.objects.annotate(
        total_docs=Count('documentos'),
    ).order_by('entidade', 'nome')
    form  = TipoDocumentoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Tipo de documento criado.')
        return redirect('federacao:tipo_documento_lista')
    return render(request, 'federacao/tipo_documento_lista.html', {'tipos': tipos, 'form': form})


@login_required
def tipo_documento_editar(request, pk):
    tipo = get_object_or_404(TipoDocumento, pk=pk)
    form = TipoDocumentoForm(request.POST or None, instance=tipo)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Tipo de documento atualizado.')
        return redirect('federacao:tipo_documento_lista')
    return render(request, 'federacao/tipo_documento_form.html', {'form': form, 'tipo': tipo})
