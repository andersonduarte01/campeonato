from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import models, transaction
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, ListView, UpdateView, DetailView

from .forms import (
    CompeticaoForm, AssociarEquipeForm, JogoResultadoForm, JogoConfigForm,
    GolForm, CartaoForm, InscricaoAtletaForm,
    EtapaKnockoutForm, GrupoForm, ConfrontoPenaltisForm,
    LocalForm,
    SumulaArbitragemForm, EscalacaoJogoForm, SubstituicaoJogoForm,
    OcorrenciaJogoForm, TemporadaForm, ApiKeyForm,
)
from ..competicao.models import (
    Competicao, Rodada, Jogo, Classificacao, Gol, Cartao,
    InscricaoAtleta, InscricaoEquipe,
    EtapaKnockout, Fase, Grupo, ClassificacaoGrupo, ConfrontoMatamate, Suspensao,
    ParticipacaoFase,
    Local, Sumula, EscalacaoJogo, SubstituicaoJogo, OcorrenciaJogo,
    HistoricoClassificacao, ApiKey, EscalacaoTatica, EscalacaoTaticaJogo,
)
from ..core.models import UsuarioFederacao
from ..equipe.models import Equipe, Atleta
from .dominio.avancos import AvancoService
from .dominio.classificador import aplicar_criterios
from .dominio.excecoes import RegraVioladaError, TransicaoInvalida
from .dominio.fases.grupos import GruposStrategy
from .dominio.fases.liga import LigaStrategy
from .dominio.desistencia import DesistenciaService
from .dominio.wo import WOService
from .decoradores import por_pk, por_relacao, requer_status
from .pdf_utils import render_pdf
from apps.core.permissao import PermissaoFederacaoMixin, requer_papel, APENAS_ADMIN, PODE_SECRETARIAR, PODE_DIRIGIR, PODE_ARBITRAR


# ---------------------------------------------------------------------------
# Competição
# ---------------------------------------------------------------------------

class CompeticaoCreate(PermissaoFederacaoMixin, SuccessMessageMixin, CreateView):
    papeis_permitidos = APENAS_ADMIN
    form_class = CompeticaoForm
    model = Competicao
    success_message = 'Competição criada com sucesso!'
    template_name = 'competicao/criarcompeticao.html'
    success_url = reverse_lazy('competicao:competicao_lista')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['federacao'] = self.request.federacao
        return kwargs

    def form_valid(self, form):
        form.instance.federacao = self.request.federacao
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.criterios.models import FormatoCompeticao, CriterioClassificacao
        ctx['tem_formatos'] = FormatoCompeticao.objects.filter(federacao=self.request.federacao).exists()
        ctx['tem_criterios'] = CriterioClassificacao.objects.filter(federacao=self.request.federacao).exists()
        return ctx


class CompeticoesLista(PermissaoFederacaoMixin, ListView):
    template_name = 'competicao/competicoes.html'
    context_object_name = 'competicoes'

    def get_queryset(self):
        return (
            Competicao.objects
            .filter(federacao=self.request.federacao)
            .select_related('formato', 'criterio_classificacao')
        )


@requer_papel(*APENAS_ADMIN)
@requer_status(Competicao.CONFIGURADA, Competicao.INSCRICOES)
def remover_equipe_view(request, pk, equipe_id):
    competicao = get_object_or_404(Competicao, pk=pk, federacao=request.federacao)
    equipe = get_object_or_404(Equipe, pk=equipe_id, federacao=request.federacao)
    deleted, _ = InscricaoEquipe.objects.filter(competicao=competicao, equipe=equipe).delete()
    if deleted:
        messages.success(request, f"{equipe.nome_equipe} foi removida da competição.")
    else:
        messages.warning(request, "Esta equipe não está na competição.")
    return redirect(reverse("competicao:buscar_equipes_view", kwargs={"pk": pk}))


@requer_papel()
def buscar_equipes(request):
    search = request.GET.get('search', '')
    equipes = Equipe.objects.filter(federacao=request.federacao, nome_equipe__icontains=search).values('id', 'nome_equipe')
    return JsonResponse({'equipes': list(equipes)})


@requer_papel(*APENAS_ADMIN)
@requer_status(Competicao.CONFIGURADA, Competicao.INSCRICOES)
def associar_equipe_view(request, pk):
    competicao = get_object_or_404(Competicao, pk=pk, federacao=request.federacao)
    if request.method == "POST":
        form = AssociarEquipeForm(request.POST)
        if form.is_valid():
            equipe_id = form.cleaned_data["equipe_id"]
            equipe = get_object_or_404(Equipe, pk=equipe_id, federacao=request.federacao)
            limite = competicao.formato.qtd_times if competicao.formato else None
            if limite and competicao.equipes.count() >= limite:
                messages.warning(request, f"Limite de {limite} equipes atingido.")
            elif InscricaoEquipe.objects.filter(competicao=competicao, equipe=equipe).exists():
                messages.warning(request, f"{equipe} já está na competição.")
            else:
                InscricaoEquipe.objects.create(competicao=competicao, equipe=equipe)
                messages.success(request, f"{equipe} adicionada com sucesso!")
            return redirect(reverse("competicao:buscar_equipes_view", kwargs={"pk": pk}))
    else:
        form = AssociarEquipeForm()
    return render(request, "competicao/buscar_equipe.html", {"form": form, "competicao": competicao})


@requer_papel(*APENAS_ADMIN)
def competicao_transicao_view(request, pk, acao):
    competicao = get_object_or_404(Competicao, pk=pk, federacao=request.federacao)
    if request.method == 'POST':
        try:
            competicao.transicionar(acao, force=request.POST.get('force') == '1')
            messages.success(request, f'Competição agora está em "{competicao.get_status_display()}".')
        except TransicaoInvalida as e:
            messages.warning(request, str(e))
    return redirect(reverse('competicao:classificacao', kwargs={'pk': pk}))


@requer_papel(*APENAS_ADMIN)
@requer_status(Competicao.INSCRICOES_ENCERRADAS, Competicao.ANDAMENTO,
               obter=por_pk('competicao_id'))
def criar_jogos_view(request, competicao_id):
    competicao = get_object_or_404(Competicao, pk=competicao_id, federacao=request.federacao)
    fmt = getattr(competicao, 'formato', None)
    if fmt is None:
        messages.error(request, "Configure um formato antes de gerar jogos.")
        return redirect(reverse("competicao:rodadas", kwargs={"pk": competicao_id}))
    if not fmt.pontos_corridos:
        messages.error(request, "Este formato não possui fase de pontos corridos. Use grupos ou chaveamento.")
        return redirect(reverse("competicao:rodadas", kwargs={"pk": competicao_id}))
    is_liga_pura = not fmt.mata_mata and not fmt.fase_grupos
    estrategia = LigaStrategy()
    try:
        if is_liga_pura:
            numero, total = estrategia.gerar_proxima_rodada(competicao)
            messages.success(request, f"Rodada {numero} de {total} gerada com sucesso.")
        else:
            rodadas = estrategia.gerar_jogos(competicao)
            messages.success(request, f"{rodadas} rodadas geradas para {competicao.nome}.")
    except RegraVioladaError as e:
        messages.warning(request, str(e))
    return redirect(reverse("competicao:rodadas", kwargs={"pk": competicao_id}))


# ---------------------------------------------------------------------------
# Classificação e rodadas
# ---------------------------------------------------------------------------

ACOES_TRANSICAO = {
    Competicao.CONFIGURADA: ('Concluir configuração', 'ti-settings-check'),
    Competicao.INSCRICOES: ('Abrir inscrições', 'ti-clipboard-plus'),
    Competicao.INSCRICOES_ENCERRADAS: ('Encerrar inscrições', 'ti-clipboard-off'),
    Competicao.ANDAMENTO: ('Iniciar competição', 'ti-player-play'),
    Competicao.FINALIZADO: ('Finalizar competição', 'ti-flag-check'),
    Competicao.CANCELADO: ('Cancelar competição', 'ti-ban'),
    Competicao.ARQUIVADO: ('Arquivar', 'ti-archive'),
}


def _rotulo_transicao(status_atual, destino):
    if status_atual == Competicao.INSCRICOES_ENCERRADAS and destino == Competicao.INSCRICOES:
        return ('Reabrir inscrições', 'ti-clipboard-plus')
    return ACOES_TRANSICAO[destino]


class ClassificacaoView(PermissaoFederacaoMixin, DetailView):
    model = Competicao

    def get_queryset(self):
        return Competicao.objects.filter(federacao=self.request.federacao)
    template_name = 'competicao/classificacao.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        comp = self.object
        classificacao_raw = Classificacao.objects.filter(competicao=comp).select_related('equipe')
        ctx['classificacao'] = aplicar_criterios(comp, classificacao_raw)
        ctx['tem_provisorio'] = Jogo.objects.filter(
            rodada__competicao=comp,
            status=Jogo.STATUS_PROVISORIO,
            anulado=False,
        ).exists()
        ctx['artilharia'] = (
            Gol.objects
            .filter(jogo__rodada__competicao=comp, tipo__in=['normal', 'penalti'])
            .values('atleta__id', 'atleta__nome', 'atleta__equipe__nome_equipe')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        ctx['rodadas'] = (
            Rodada.objects
            .filter(competicao=comp)
            .prefetch_related(
                'jogo_set__equipe_casa',
                'jogo_set__equipe_fora',
                'jogo_set__local',
            )
            .order_by('numero')
        )
        grupos_data = []
        for grupo in comp.grupos.prefetch_related('equipes').all():
            cl = aplicar_criterios(comp, grupo.classificacao.select_related('equipe').all(), grupo=grupo)
            grupos_data.append({'grupo': grupo, 'classificacao': cl})
        ctx['grupos_data'] = grupos_data
        ctx['etapas_knockout'] = comp.etapas.all()
        fmt = comp.formato
        ctx['is_liga_pura'] = bool(fmt and fmt.pontos_corridos and not fmt.mata_mata and not fmt.fase_grupos)
        jogos_fin = Jogo.objects.filter(
            rodada__competicao=comp, finalizado=True, anulado=False,
        ).select_related('equipe_casa', 'equipe_fora')
        forma_map = {
            item['equipe'].pk: item['forma']
            for item in _forma_recente(comp, jogos_fin)
        }
        for cls_item in ctx['classificacao']:
            cls_item.forma = forma_map.get(cls_item.equipe.pk, [])
        ctx['transicoes'] = [
            (s,) + _rotulo_transicao(comp.status, s)
            for s in comp.transicoes_disponiveis()
        ]
        fase_liga = Fase.objects.filter(competicao=comp, tipo=Fase.LIGA).first()
        zonas = list(fase_liga.zonas.all()) if fase_liga else []
        ctx['zonas'] = zonas
        for pos, cls_item in enumerate(ctx['classificacao'], start=1):
            cls_item.zona = next((z for z in zonas if z.contem(pos)), None)
        return ctx


class RodadasView(PermissaoFederacaoMixin, DetailView):
    model = Competicao

    def get_queryset(self):
        return Competicao.objects.filter(federacao=self.request.federacao)
    template_name = 'competicao/rodadas.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['rodadas'] = (
            Rodada.objects
            .filter(competicao=self.object)
            .select_related('etapa', 'grupo')
            .prefetch_related(
                'jogo_set__equipe_casa',
                'jogo_set__equipe_fora',
                'jogo_set__local',
                'jogo_set__arbitro__usuario',
                'jogo_set__gols__atleta',
                'jogo_set__gols__equipe',
            )
            .order_by('etapa__ordem', 'grupo__nome', 'numero')
        )
        ctx['locais'] = Local.objects.filter(federacao=self.request.federacao).order_by('nome')
        ctx['arbitros'] = UsuarioFederacao.objects.filter(
            federacao=self.request.federacao,
            papel=UsuarioFederacao.ARBITRO,
            ativo=True,
        ).select_related('usuario').order_by('usuario__nome')
        fmt = getattr(self.object, 'formato', None)
        is_liga_pura = bool(fmt and fmt.pontos_corridos and not fmt.mata_mata and not fmt.fase_grupos)
        ctx['is_liga_pura'] = is_liga_pura
        ctx['tem_pontos_corridos'] = bool(fmt and fmt.pontos_corridos)

        if is_liga_pura:
            equipes_count = self.object.equipes.count()
            if equipes_count >= 2:
                ne = equipes_count if equipes_count % 2 == 0 else equipes_count + 1
                turnos = 1 if (getattr(fmt, 'turno_unico', True) and not getattr(fmt, 'ida_e_volta', False)) else 2
                ctx['total_rodadas'] = (ne - 1) * turnos
            else:
                ctx['total_rodadas'] = 0

            ultima = (
                Rodada.objects
                .filter(competicao=self.object, grupo__isnull=True, etapa__isnull=True)
                .prefetch_related('jogo_set')
                .order_by('numero')
                .last()
            )
            if ultima:
                ctx['ultima_rodada_pk'] = ultima.pk
                jogos = list(ultima.jogo_set.all())
                ctx['pode_gerar_proxima'] = bool(
                    jogos and all(j.data_hora and j.local_id for j in jogos)
                )
            else:
                ctx['ultima_rodada_pk'] = None
                ctx['pode_gerar_proxima'] = True

        return ctx


class JogoUpdateView(PermissaoFederacaoMixin, SuccessMessageMixin, UpdateView):
    papeis_permitidos = PODE_SECRETARIAR
    model = Jogo
    form_class = JogoResultadoForm
    template_name = 'competicao/edit_jogo.html'
    success_message = 'Resultado provisório salvo.'

    def get_queryset(self):
        return Jogo.objects.filter(rodada__competicao__federacao=self.request.federacao)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['federacao'] = self.request.federacao
        return kwargs

    def get_success_url(self):
        return reverse('competicao:jogo_detalhe', kwargs={'pk': self.object.pk})

    def _sumula_bloqueia(self, jogo):
        try:
            return jogo.sumula.status in (Sumula.STATUS_ENCERRADA, Sumula.STATUS_HOMOLOGADA)
        except Sumula.DoesNotExist:
            return False

    def post(self, request, *args, **kwargs):
        jogo = self.get_object()
        if jogo.rodada_id and jogo.rodada.competicao.status != Competicao.ANDAMENTO:
            messages.warning(
                request,
                'Resultados só podem ser lançados com a competição em andamento.',
            )
            return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo.pk}))
        if self._sumula_bloqueia(jogo):
            messages.warning(
                request,
                'O placar está sob autoridade da súmula encerrada e não pode ser editado manualmente.',
            )
            return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo.pk}))
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        jogo = form.instance
        if jogo.status not in (Jogo.STATUS_FINALIZADO, Jogo.STATUS_HOMOLOGADO, Jogo.STATUS_ANULADO):
            jogo.status = Jogo.STATUS_PROVISORIO
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['jogo'] = self.object
        ctx['sumula_bloqueada'] = self._sumula_bloqueia(self.object)
        return ctx


@requer_papel(*PODE_SECRETARIAR)
def jogo_config_view(request, pk):
    jogo = get_object_or_404(
        Jogo.objects.select_related('equipe_casa', 'equipe_fora', 'rodada__competicao'),
        pk=pk, rodada__competicao__federacao=request.federacao,
    )
    if request.method == 'POST':
        form = JogoConfigForm(request.POST, instance=jogo, federacao=request.federacao)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuração do jogo salva.')
            next_url = request.POST.get('next', '').strip()
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': pk}))
    else:
        form = JogoConfigForm(instance=jogo, federacao=request.federacao)
    return render(request, 'competicao/jogo_config.html', {'jogo': jogo, 'form': form})


class JogoDetalheView(PermissaoFederacaoMixin, DetailView):
    model = Jogo

    def get_queryset(self):
        return Jogo.objects.filter(rodada__competicao__federacao=self.request.federacao)
    template_name = 'competicao/jogo_detalhe.html'
    context_object_name = 'jogo'

    def get_template_names(self):
        superadmin = getattr(self.request.user, 'is_admin', False)
        vinculo    = getattr(self.request, 'vinculo', None)
        if not superadmin and vinculo and vinculo.papel == 'ARB':
            return ['competicao/jogo_detalhe_arbitro.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        jogo = self.object
        ctx['gols_casa'] = jogo.gols.filter(equipe=jogo.equipe_casa).select_related('atleta')
        ctx['gols_fora'] = jogo.gols.filter(equipe=jogo.equipe_fora).select_related('atleta')
        ctx['cartoes'] = jogo.cartoes.select_related('jogador__equipe').order_by('minuto')
        ctx['form_gol'] = GolForm(jogo=jogo)
        ctx['form_cartao'] = CartaoForm(jogo=jogo)
        ctx['atletas_casa'] = list(_atletas_por_equipe(jogo, jogo.equipe_casa).values('id', 'nome'))
        ctx['atletas_fora'] = list(_atletas_por_equipe(jogo, jogo.equipe_fora).values('id', 'nome'))
        try:
            ctx['sumula'] = jogo.sumula
        except Sumula.DoesNotExist:
            ctx['sumula'] = None
        if jogo.rodada_id:
            atleta_ids = [a['id'] for a in ctx['atletas_casa'] + ctx['atletas_fora']]
            ctx['suspensos'] = list(
                Suspensao.objects.filter(
                    competicao=jogo.rodada.competicao,
                    cumprida=False,
                    atleta_id__in=atleta_ids,
                ).select_related('atleta__equipe')
            )
        else:
            ctx['suspensos'] = []
        if ctx['sumula']:
            ctx['substituicoes'] = ctx['sumula'].substituicoes.select_related('atleta_saiu', 'atleta_entrou', 'equipe')
            ctx['ocorrencias']   = ctx['sumula'].ocorrencias.all()
        else:
            ctx['substituicoes'] = []
            ctx['ocorrencias']   = []
        return ctx


def _atletas_por_equipe(jogo, equipe):
    from .forms import _atletas_do_jogo
    return _atletas_do_jogo(jogo).filter(equipe=equipe)


@requer_papel(*APENAS_ADMIN)
@requer_status(Competicao.INSCRICOES_ENCERRADAS, Competicao.ANDAMENTO)
def registrar_desistencia_view(request, pk, equipe_id):
    competicao = get_object_or_404(Competicao, pk=pk, federacao=request.federacao)
    equipe = get_object_or_404(Equipe, pk=equipe_id, federacao=request.federacao)
    fase = Fase.objects.filter(competicao=competicao, tipo=Fase.LIGA).first()
    if fase is None:
        messages.warning(request, 'A fase de liga desta competição ainda não foi gerada.')
        return redirect(reverse('competicao:classificacao', kwargs={'pk': pk}))
    if request.method == 'POST':
        try:
            aplicados = DesistenciaService().registrar(fase, equipe)
            messages.success(
                request,
                f'{equipe.nome_equipe} marcada como desistente. '
                f'{aplicados} jogo(s) declarado(s) W.O.',
            )
        except RegraVioladaError as e:
            messages.warning(request, str(e))
    return redirect(reverse('competicao:classificacao', kwargs={'pk': pk}))


@requer_papel(*PODE_SECRETARIAR)
@requer_status(Competicao.ANDAMENTO, obter=por_relacao(Jogo, 'rodada__competicao'))
def jogo_declarar_wo_view(request, pk):
    jogo = get_object_or_404(Jogo, pk=pk, rodada__competicao__federacao=request.federacao)
    if request.method == 'POST':
        vencedor_id = request.POST.get('vencedor')
        try:
            if str(jogo.equipe_casa_id) == vencedor_id:
                vencedor = jogo.equipe_casa
            elif str(jogo.equipe_fora_id) == vencedor_id:
                vencedor = jogo.equipe_fora
            else:
                raise RegraVioladaError('Selecione uma das equipes do jogo.')
            WOService().declarar(jogo, vencedor)
            messages.success(request, f'W.O. registrado — {vencedor} vence por 3x0.')
        except RegraVioladaError as e:
            messages.warning(request, str(e))
    return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': pk}))


@requer_papel(*PODE_SECRETARIAR)
@requer_status(Competicao.ANDAMENTO, obter=por_relacao(Jogo, 'rodada__competicao'))
def jogo_iniciar_view(request, pk):
    jogo = get_object_or_404(Jogo, pk=pk, rodada__competicao__federacao=request.federacao)
    if request.method == 'POST':
        if jogo.status != Jogo.STATUS_AGENDADO:
            messages.warning(request, 'Este jogo não pode ser iniciado.')
        else:
            jogo.status = Jogo.STATUS_EM_ANDAMENTO
            jogo.save(update_fields=['status'])
            messages.success(request, 'Partida iniciada — modo ao vivo ativado.')
    return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': pk}))


@requer_papel(*PODE_SECRETARIAR)
@requer_status(Competicao.ANDAMENTO, obter=por_relacao(Jogo, 'rodada__competicao'))
def jogo_homologar_view(request, pk):
    jogo = get_object_or_404(Jogo, pk=pk, rodada__competicao__federacao=request.federacao)
    if request.method == 'POST':
        if jogo.status not in (Jogo.STATUS_PROVISORIO, Jogo.STATUS_FINALIZADO):
            messages.warning(request, 'Apenas jogos com resultado registrado podem ser homologados.')
        else:
            try:
                sumula = jogo.sumula
                if sumula.status in (Sumula.STATUS_ENCERRADA, Sumula.STATUS_HOMOLOGADA):
                    from .signals import _sincronizar_placar
                    _sincronizar_placar(jogo)
                    jogo.refresh_from_db()
            except Sumula.DoesNotExist:
                pass
            jogo.status = Jogo.STATUS_HOMOLOGADO
            jogo.save(update_fields=['status'])
            messages.success(request, 'Jogo homologado com sucesso.')
    return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': pk}))


@requer_papel(*APENAS_ADMIN)
@requer_status(Competicao.ANDAMENTO, obter=por_relacao(Jogo, 'rodada__competicao'))
def jogo_anular_view(request, pk):
    jogo = get_object_or_404(Jogo, pk=pk, rodada__competicao__federacao=request.federacao)
    if request.method == 'POST':
        if jogo.status == Jogo.STATUS_ANULADO:
            messages.warning(request, 'Este jogo já está anulado.')
        else:
            jogo.status = Jogo.STATUS_ANULADO
            jogo.save(update_fields=['status'])
            messages.success(request, 'Jogo anulado.')
    return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': pk}))


def _arbitro_bloqueado_ao_vivo(request, jogo):
    # Durante o ao vivo quem registra é a secretaria; o árbitro lança os
    # dados oficiais (base da homologação) após o término da partida.
    if not jogo.em_andamento:
        return False
    if getattr(request.user, 'is_admin', False):
        return False
    vinculo = getattr(request, 'vinculo', None)
    return bool(vinculo and vinculo.papel == 'ARB')


_MSG_ARBITRO_AO_VIVO = ('Durante a partida ao vivo os eventos são registrados pela secretaria. '
                        'Ao final do jogo você poderá lançar os dados oficiais da súmula.')


@requer_papel(*PODE_ARBITRAR)
@requer_status(Competicao.ANDAMENTO,
               obter=por_relacao(Jogo, 'rodada__competicao', param='jogo_pk'))
def gol_criar_view(request, jogo_pk):
    jogo = get_object_or_404(Jogo, pk=jogo_pk, rodada__competicao__federacao=request.federacao)
    if _arbitro_bloqueado_ao_vivo(request, jogo):
        messages.warning(request, _MSG_ARBITRO_AO_VIVO)
        return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo_pk}))
    if request.method == 'POST':
        form = GolForm(request.POST, jogo=jogo)
        if form.is_valid():
            gol = form.save(commit=False)
            gol.jogo = jogo
            gol.save()
            messages.success(request, 'Gol registrado.')
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.warning(request, f'{field}: {err}')
    return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo_pk}))


@requer_papel(*PODE_ARBITRAR)
@requer_status(Competicao.ANDAMENTO, obter=por_relacao(Gol, 'jogo__rodada__competicao'))
def gol_excluir_view(request, pk):
    gol = get_object_or_404(Gol, pk=pk, jogo__rodada__competicao__federacao=request.federacao)
    jogo_pk = gol.jogo_id
    if _arbitro_bloqueado_ao_vivo(request, gol.jogo):
        messages.warning(request, _MSG_ARBITRO_AO_VIVO)
        return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo_pk}))
    if request.method == 'POST':
        gol.delete()
        messages.success(request, 'Gol removido.')
    return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo_pk}))


@requer_papel(*PODE_ARBITRAR)
@requer_status(Competicao.ANDAMENTO,
               obter=por_relacao(Jogo, 'rodada__competicao', param='jogo_pk'))
def cartao_criar_view(request, jogo_pk):
    jogo = get_object_or_404(Jogo, pk=jogo_pk, rodada__competicao__federacao=request.federacao)
    if _arbitro_bloqueado_ao_vivo(request, jogo):
        messages.warning(request, _MSG_ARBITRO_AO_VIVO)
        return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo_pk}))
    if request.method == 'POST':
        form = CartaoForm(request.POST, jogo=jogo)
        if form.is_valid():
            cartao = form.save(commit=False)
            cartao.jogo = jogo
            cartao.save()
            messages.success(request, 'Cartão registrado.')
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.warning(request, f'{field}: {err}')
    return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo_pk}))


@requer_papel(*PODE_ARBITRAR)
@requer_status(Competicao.ANDAMENTO, obter=por_relacao(Cartao, 'jogo__rodada__competicao'))
def cartao_excluir_view(request, pk):
    cartao = get_object_or_404(Cartao, pk=pk, jogo__rodada__competicao__federacao=request.federacao)
    jogo_pk = cartao.jogo_id
    if _arbitro_bloqueado_ao_vivo(request, cartao.jogo):
        messages.warning(request, _MSG_ARBITRO_AO_VIVO)
        return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo_pk}))
    if request.method == 'POST':
        cartao.delete()
        messages.success(request, 'Cartão removido.')
    return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo_pk}))


# ---------------------------------------------------------------------------
# Inscrição de atletas
# ---------------------------------------------------------------------------

class InscricaoView(PermissaoFederacaoMixin, DetailView):
    model = Competicao

    def get_queryset(self):
        return Competicao.objects.filter(federacao=self.request.federacao)
    template_name = 'competicao/inscricao.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        competicao = self.object
        amarelos_map = {
            row['jogador_id']: row['total']
            for row in Cartao.objects.filter(
                jogo__rodada__competicao=competicao, tipo=Cartao.AMARELO,
            ).values('jogador_id').annotate(total=Count('id'))
        }
        vermelhos_map = {
            row['jogador_id']: row['total']
            for row in Cartao.objects.filter(
                jogo__rodada__competicao=competicao, tipo=Cartao.VERMELHO,
            ).values('jogador_id').annotate(total=Count('id'))
        }
        suspensos_ids = set(
            Suspensao.objects.filter(competicao=competicao, cumprida=False)
            .values_list('atleta_id', flat=True)
        )
        inscricoes_equipe = {
            ie.equipe_id: ie
            for ie in InscricaoEquipe.objects.filter(competicao=competicao)
        }
        equipes_data = []
        for equipe in competicao.equipes.order_by('nome_equipe'):
            inscritos = (
                InscricaoAtleta.objects
                .filter(competicao=competicao, atleta__equipe=equipe)
                .select_related('atleta')
                .order_by('numero_camisa', 'atleta__nome')
            )
            form = InscricaoAtletaForm(competicao=competicao, equipe=equipe)
            equipes_data.append({
                'equipe': equipe,
                'inscritos': inscritos,
                'form': form,
                'inscricao_equipe': inscricoes_equipe.get(equipe.pk),
            })
        ctx['equipes_data'] = equipes_data
        ctx['amarelos_map'] = amarelos_map
        ctx['vermelhos_map'] = vermelhos_map
        ctx['suspensos_ids'] = suspensos_ids
        return ctx


@requer_papel(*PODE_DIRIGIR)
@requer_status(Competicao.INSCRICOES, obter=por_pk('competicao_pk'))
def inscricao_criar_view(request, competicao_pk, equipe_pk):
    from datetime import date
    competicao = get_object_or_404(Competicao, pk=competicao_pk, federacao=request.federacao)
    equipe = get_object_or_404(Equipe, pk=equipe_pk, federacao=request.federacao)
    vinculo = getattr(request, 'vinculo', None)
    is_dirigente = vinculo and vinculo.papel == UsuarioFederacao.DIRIGENTE and not getattr(request.user, 'is_admin', False)

    def _redirect_inscricao():
        if is_dirigente:
            return redirect(reverse('competicao:dirigente_inscricao', kwargs={'competicao_pk': competicao_pk}))
        return redirect(reverse('competicao:inscricao', kwargs={'pk': competicao_pk}))

    if request.method == 'POST':
        hoje = date.today()
        if competicao.data_abertura_inscricao and hoje < competicao.data_abertura_inscricao:
            messages.warning(request, f'Inscrições abertas a partir de {competicao.data_abertura_inscricao.strftime("%d/%m/%Y")}.')
            return _redirect_inscricao()
        if competicao.data_encerramento_inscricao and hoje > competicao.data_encerramento_inscricao:
            messages.warning(request, 'Prazo de inscrições encerrado.')
            return _redirect_inscricao()
        form = InscricaoAtletaForm(request.POST, competicao=competicao, equipe=equipe)
        if form.is_valid():
            if competicao.limite_atletas:
                total = InscricaoAtleta.objects.filter(competicao=competicao, atleta__equipe=equipe).count()
                if total >= competicao.limite_atletas:
                    messages.warning(request, f'Limite de {competicao.limite_atletas} atletas por equipe atingido.')
                    return _redirect_inscricao()
            inscricao = form.save(commit=False)
            inscricao.competicao = competicao
            inscricao.save()
            messages.success(request, f'{inscricao.atleta.nome} inscrito com sucesso.')
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.warning(request, err)
    return _redirect_inscricao()


@requer_papel(*PODE_DIRIGIR)
def inscricao_excluir_view(request, pk):
    inscricao = get_object_or_404(InscricaoAtleta, pk=pk, competicao__federacao=request.federacao)
    competicao_pk = inscricao.competicao_id
    vinculo = getattr(request, 'vinculo', None)
    is_dirigente = vinculo and vinculo.papel == UsuarioFederacao.DIRIGENTE and not getattr(request.user, 'is_admin', False)
    if request.method == 'POST':
        inscricao.delete()
        messages.success(request, f'{inscricao.atleta.nome} removido da inscrição.')
    if is_dirigente:
        return redirect(reverse('competicao:dirigente_inscricao', kwargs={'competicao_pk': competicao_pk}))
    return redirect(reverse('competicao:inscricao', kwargs={'pk': competicao_pk}))


@requer_papel(*PODE_SECRETARIAR)
def inscricao_toggle_taxa_view(request, pk):
    import datetime
    inscricao = get_object_or_404(InscricaoEquipe, pk=pk, competicao__federacao=request.federacao)
    if request.method == 'POST':
        inscricao.taxa_paga = not inscricao.taxa_paga
        inscricao.data_pagamento = datetime.date.today() if inscricao.taxa_paga else None
        inscricao.save(update_fields=['taxa_paga', 'data_pagamento'])
        status = 'paga' if inscricao.taxa_paga else 'pendente'
        messages.success(request, f'Taxa de {inscricao.equipe.nome_equipe} marcada como {status}.')
    return redirect(reverse('competicao:inscricao', kwargs={'pk': inscricao.competicao_id}))


# ---------------------------------------------------------------------------
# Suspensões
# ---------------------------------------------------------------------------

@requer_papel(*PODE_SECRETARIAR)
def suspensao_cumprir_view(request, pk):
    suspensao = get_object_or_404(Suspensao, pk=pk, competicao__federacao=request.federacao)
    competicao_pk = suspensao.competicao_id
    if request.method == 'POST':
        Suspensao.objects.filter(pk=pk).update(cumprida=True)
        messages.success(request, f'Suspensão de {suspensao.atleta.nome} marcada como cumprida.')
    return redirect(reverse('competicao:inscricao', kwargs={'pk': competicao_pk}))


# ---------------------------------------------------------------------------
# Etapas Knockout
# ---------------------------------------------------------------------------

class EtapasView(PermissaoFederacaoMixin, DetailView):
    model = Competicao

    def get_queryset(self):
        return Competicao.objects.filter(federacao=self.request.federacao)
    template_name = 'competicao/etapas.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['etapas'] = self.object.etapas.all()
        ctx['form'] = EtapaKnockoutForm()
        ctx['tipos_disponiveis'] = [
            t for t in EtapaKnockout.TIPO_CHOICES
            if not self.object.etapas.filter(tipo=t[0]).exists()
        ]
        return ctx


@requer_papel(*APENAS_ADMIN)
@requer_status(Competicao.INSCRICOES_ENCERRADAS, Competicao.ANDAMENTO,
               obter=por_pk('competicao_pk'))
def etapa_criar_view(request, competicao_pk):
    competicao = get_object_or_404(Competicao, pk=competicao_pk, federacao=request.federacao)
    if request.method == 'POST':
        form = EtapaKnockoutForm(request.POST)
        if form.is_valid():
            etapa = form.save(commit=False)
            etapa.competicao = competicao
            try:
                etapa.save()
                messages.success(request, f"Etapa '{etapa.get_tipo_display()}' criada.")
            except Exception:
                messages.warning(request, f"Etapa '{etapa.get_tipo_display()}' já existe nesta competição.")
        else:
            for errs in form.errors.values():
                for err in errs:
                    messages.warning(request, err)
    return redirect(reverse('competicao:etapas', kwargs={'pk': competicao_pk}))


@requer_papel(*APENAS_ADMIN)
def etapa_excluir_view(request, pk):
    etapa = get_object_or_404(EtapaKnockout, pk=pk, competicao__federacao=request.federacao)
    competicao_pk = etapa.competicao_id
    if request.method == 'POST':
        if Jogo.objects.filter(rodada__etapa=etapa, finalizado=True, anulado=False).exists():
            messages.warning(
                request,
                'Esta etapa possui jogos finalizados e não pode ser excluída. '
                'Anule os jogos antes, se necessário.',
            )
        else:
            with transaction.atomic():
                Rodada.objects.filter(etapa=etapa).delete()
                etapa.delete()
            messages.success(request, f"Etapa '{etapa.get_tipo_display()}' excluída.")
    return redirect(reverse('competicao:etapas', kwargs={'pk': competicao_pk}))


# ---------------------------------------------------------------------------
# Grupos
# ---------------------------------------------------------------------------

class GruposView(PermissaoFederacaoMixin, DetailView):
    model = Competicao

    def get_queryset(self):
        return Competicao.objects.filter(federacao=self.request.federacao)
    template_name = 'competicao/grupos.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        comp = self.object
        grupos_data = []
        for grupo in comp.grupos.prefetch_related('equipes').all():
            cl = aplicar_criterios(comp, grupo.classificacao.select_related('equipe').all(), grupo=grupo)
            grupos_data.append({'grupo': grupo, 'classificacao': cl})
        ctx['grupos_data'] = grupos_data
        ctx['form_grupo'] = GrupoForm()
        equipes_em_grupos_ids = comp.grupos.values_list('equipes__id', flat=True)
        ctx['equipes_disponiveis'] = comp.equipes.exclude(pk__in=equipes_em_grupos_ids).order_by('nome_equipe')
        ctx['tem_rodadas'] = Rodada.objects.filter(grupo__competicao=comp).exists()
        ctx['etapas_knockout'] = comp.etapas.all()
        return ctx


@requer_papel(*APENAS_ADMIN)
@requer_status(Competicao.INSCRICOES_ENCERRADAS, Competicao.ANDAMENTO,
               obter=por_pk('competicao_pk'))
def grupo_criar_view(request, competicao_pk):
    competicao = get_object_or_404(Competicao, pk=competicao_pk, federacao=request.federacao)
    if request.method == 'POST':
        form = GrupoForm(request.POST)
        if form.is_valid():
            grupo = form.save(commit=False)
            grupo.competicao = competicao
            try:
                grupo.save()
                messages.success(request, f"Grupo '{grupo.nome}' criado.")
            except Exception:
                messages.warning(request, f"Grupo '{grupo.nome}' já existe nesta competição.")
        else:
            for errs in form.errors.values():
                for err in errs:
                    messages.warning(request, err)
    return redirect(reverse('competicao:grupos', kwargs={'pk': competicao_pk}))


@requer_papel(*APENAS_ADMIN)
def grupo_excluir_view(request, pk):
    grupo = get_object_or_404(Grupo, pk=pk, competicao__federacao=request.federacao)
    competicao_pk = grupo.competicao_id
    if request.method == 'POST':
        if Jogo.objects.filter(rodada__grupo=grupo, finalizado=True, anulado=False).exists():
            messages.warning(
                request,
                'Este grupo possui jogos finalizados e não pode ser excluído. '
                'Anule os jogos antes, se necessário.',
            )
        else:
            with transaction.atomic():
                Rodada.objects.filter(grupo=grupo).delete()
                grupo.delete()
            messages.success(request, 'Grupo excluído.')
    return redirect(reverse('competicao:grupos', kwargs={'pk': competicao_pk}))


@requer_papel(*APENAS_ADMIN)
def grupo_atribuir_equipe_view(request, pk):
    grupo = get_object_or_404(Grupo, pk=pk, competicao__federacao=request.federacao)
    if request.method == 'POST':
        equipe_id = request.POST.get('equipe_id')
        equipe = get_object_or_404(grupo.competicao.equipes, pk=equipe_id)
        grupo.equipes.add(equipe)
        messages.success(request, f'{equipe.nome_equipe} adicionada ao Grupo {grupo.nome}.')
    return redirect(reverse('competicao:grupos', kwargs={'pk': grupo.competicao_id}))


@requer_papel(*APENAS_ADMIN)
def grupo_remover_equipe_view(request, pk, equipe_pk):
    grupo = get_object_or_404(Grupo, pk=pk, competicao__federacao=request.federacao)
    equipe = get_object_or_404(grupo.equipes, pk=equipe_pk)
    if request.method == 'POST':
        grupo.equipes.remove(equipe)
        messages.success(request, f'{equipe.nome_equipe} removida do Grupo {grupo.nome}.')
    return redirect(reverse('competicao:grupos', kwargs={'pk': grupo.competicao_id}))


@requer_papel(*APENAS_ADMIN)
@requer_status(Competicao.INSCRICOES_ENCERRADAS, Competicao.ANDAMENTO)
def gerar_jogos_grupos_view(request, pk):
    competicao = get_object_or_404(Competicao, pk=pk, federacao=request.federacao)
    if request.method == 'POST':
        try:
            rodadas = GruposStrategy().gerar_jogos(competicao)
            messages.success(request, f"{rodadas} rodadas geradas para '{competicao.nome}'.")
        except RegraVioladaError as e:
            messages.warning(request, str(e))
    return redirect(reverse('competicao:grupos', kwargs={'pk': pk}))


# ---------------------------------------------------------------------------
# Chaveamento (Mata-Mata)
# ---------------------------------------------------------------------------

class ChaveamentoView(PermissaoFederacaoMixin, DetailView):
    model = EtapaKnockout

    def get_queryset(self):
        return EtapaKnockout.objects.filter(competicao__federacao=self.request.federacao)
    template_name = 'competicao/chaveamento.html'
    context_object_name = 'etapa'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        etapa = self.object
        confrontos = list(
            etapa.confrontos.select_related(
                'equipe_mandante', 'equipe_visitante', 'vencedor',
                'jogo_ida__equipe_casa', 'jogo_ida__equipe_fora',
                'jogo_volta__equipe_casa', 'jogo_volta__equipe_fora',
            ).order_by('ordem')
        )
        normais = [c for c in confrontos if c.tipo_confronto != ConfrontoMatamate.TERCEIRO_LUGAR]
        ctx['confrontos'] = normais
        ctx['tem_confrontos'] = bool(normais)
        penaltis_disponiveis = etapa.competicao.penaltis_disponiveis
        ctx['penaltis_disponiveis'] = penaltis_disponiveis
        ctx['penaltis_forms'] = {
            c.pk: ConfrontoPenaltisForm(instance=c)
            for c in normais
            if penaltis_disponiveis and c.totalmente_jogado and c.vencedor is None
        }
        ctx['tem_grupos'] = etapa.competicao.grupos.exists()
        etapa_anterior = (
            EtapaKnockout.objects.filter(competicao=etapa.competicao, ordem__lt=etapa.ordem)
            .exclude(tipo=EtapaKnockout.TERCEIRO)
            .order_by('-ordem')
            .first()
        )
        ctx['etapa_anterior'] = etapa_anterior
        terceiro = next((c for c in confrontos if c.tipo_confronto == ConfrontoMatamate.TERCEIRO_LUGAR), None)
        ctx['terceiro_lugar'] = terceiro

        from .dominio.fases.mata_mata import CAPACIDADE_ETAPA
        tem_grupos = ctx['tem_grupos']
        if not normais and not etapa_anterior and not tem_grupos:
            capacidade = CAPACIDADE_ETAPA.get(etapa.tipo, 2)
            ctx['seeds_range'] = range(1, capacidade + 1)
            ctx['equipes_disponiveis'] = etapa.competicao.equipes.order_by('nome_equipe')
        return ctx


@requer_papel(*PODE_SECRETARIAR)
def confronto_penaltis_view(request, pk):
    confronto = get_object_or_404(ConfrontoMatamate, pk=pk, etapa__competicao__federacao=request.federacao)
    if request.method == 'POST':
        if not confronto.etapa.competicao.penaltis_disponiveis:
            messages.warning(request, 'A competição não prevê disputa por pênaltis.')
            return redirect(reverse('competicao:chaveamento', kwargs={'pk': confronto.etapa_id}))
        if not confronto.totalmente_jogado:
            messages.warning(request, 'Os jogos do confronto ainda não foram finalizados.')
            return redirect(reverse('competicao:chaveamento', kwargs={'pk': confronto.etapa_id}))
        if confronto.gols_mandante_total != confronto.gols_visitante_total:
            messages.warning(request, 'Pênaltis só podem ser registrados quando há empate no placar agregado.')
            return redirect(reverse('competicao:chaveamento', kwargs={'pk': confronto.etapa_id}))
        form = ConfrontoPenaltisForm(request.POST, instance=confronto)
        if form.is_valid():
            form.save()
            confronto.refresh_from_db()
            confronto.atualizar_vencedor()
            messages.success(request, 'Pênaltis registrados.')
        else:
            for errs in form.errors.values():
                for err in errs:
                    messages.warning(request, err)
    return redirect(reverse('competicao:chaveamento', kwargs={'pk': confronto.etapa_id}))


@requer_papel(*APENAS_ADMIN)
def avancar_classificados_view(request, competicao_pk, etapa_pk):
    competicao = get_object_or_404(Competicao, pk=competicao_pk, federacao=request.federacao)
    etapa = get_object_or_404(EtapaKnockout, pk=etapa_pk, competicao=competicao)
    if request.method == 'POST':
        try:
            confrontos = AvancoService().avancar_de_grupos(competicao, etapa)
            messages.success(
                request, f"{confrontos} confrontos gerados para '{etapa.get_tipo_display()}'.",
            )
        except RegraVioladaError as e:
            messages.warning(request, str(e))
    return redirect(reverse('competicao:chaveamento', kwargs={'pk': etapa_pk}))


@requer_papel(*APENAS_ADMIN)
def avancar_vencedores_view(request, origem_pk, destino_pk):
    origem = get_object_or_404(EtapaKnockout, pk=origem_pk, competicao__federacao=request.federacao)
    destino = get_object_or_404(EtapaKnockout, pk=destino_pk, competicao=origem.competicao)
    if request.method == 'POST':
        try:
            confrontos = AvancoService().avancar(origem, destino)
            messages.success(
                request, f"{confrontos} confrontos gerados para '{destino.get_tipo_display()}'.",
            )
        except RegraVioladaError as e:
            messages.warning(request, str(e))
    return redirect(reverse('competicao:chaveamento', kwargs={'pk': destino_pk}))


@requer_papel(*APENAS_ADMIN)
def terceiro_lugar_criar_view(request, etapa_pk):
    etapa = get_object_or_404(EtapaKnockout, pk=etapa_pk, competicao__federacao=request.federacao)
    if request.method == 'POST':
        eq1_id = request.POST.get('equipe_mandante')
        eq2_id = request.POST.get('equipe_visitante')
        if eq1_id and eq2_id and eq1_id != eq2_id:
            equipe_mandante = get_object_or_404(etapa.competicao.equipes, pk=eq1_id)
            equipe_visitante = get_object_or_404(etapa.competicao.equipes, pk=eq2_id)
            confronto, created = ConfrontoMatamate.objects.get_or_create(
                etapa=etapa,
                tipo_confronto=ConfrontoMatamate.TERCEIRO_LUGAR,
                defaults={'equipe_mandante': equipe_mandante, 'equipe_visitante': equipe_visitante, 'ordem': 0},
            )
            if created:
                rodada, _ = Rodada.objects.get_or_create(competicao=etapa.competicao, etapa=etapa, numero=99)
                jogo = Jogo.objects.create(rodada=rodada, equipe_casa=equipe_mandante, equipe_fora=equipe_visitante)
                confronto.jogo_ida = jogo
                confronto.save()
                messages.success(request, 'Disputa de 3º lugar criada.')
            else:
                messages.warning(request, 'Disputa de 3º lugar já existe para esta etapa.')
        else:
            messages.warning(request, 'Selecione duas equipes diferentes.')
    return redirect(reverse('competicao:chaveamento', kwargs={'pk': etapa_pk}))


@requer_papel(*APENAS_ADMIN)
def seeding_chaveamento_view(request, pk):
    """Gera confrontos da primeira fase knockout sem fase anterior nem grupos.

    modo=automatico: usa todas as equipes da competição em ordem alfabética.
    modo=manual:     usa as equipes na ordem definida pelo admin (seed 1…N).
    """
    from .dominio.fases.mata_mata import CAPACIDADE_ETAPA, MataMataStrategy

    etapa = get_object_or_404(EtapaKnockout, pk=pk, competicao__federacao=request.federacao)
    if request.method != 'POST':
        return redirect(reverse('competicao:chaveamento', kwargs={'pk': pk}))

    capacidade = CAPACIDADE_ETAPA.get(etapa.tipo)
    modo = request.POST.get('modo', 'manual')

    if modo == 'automatico':
        equipes = list(
            etapa.competicao.equipes.order_by('nome_equipe')[:capacidade]
        )
        if capacidade and len(equipes) != capacidade:
            messages.warning(
                request,
                f"São necessárias {capacidade} equipes para {etapa.get_tipo_display()}, "
                f"mas a competição tem {len(equipes)}.",
            )
            return redirect(reverse('competicao:chaveamento', kwargs={'pk': pk}))
    else:
        n = capacidade or 2
        equipe_ids = [request.POST.get(f'equipe_{i}') for i in range(1, n + 1)]
        if not all(equipe_ids):
            messages.warning(request, 'Selecione todas as posições do chaveamento.')
            return redirect(reverse('competicao:chaveamento', kwargs={'pk': pk}))
        if len(set(equipe_ids)) != len(equipe_ids):
            messages.warning(request, 'Não é permitido repetir equipes no chaveamento.')
            return redirect(reverse('competicao:chaveamento', kwargs={'pk': pk}))
        equipes = []
        for eid in equipe_ids:
            equipes.append(get_object_or_404(etapa.competicao.equipes, pk=eid))

    try:
        count = MataMataStrategy().gerar_jogos(etapa, equipes)
        messages.success(request, f'{count} confronto{"s" if count > 1 else ""} gerado{"s" if count > 1 else ""}.')
    except RegraVioladaError as e:
        messages.warning(request, str(e))

    return redirect(reverse('competicao:chaveamento', kwargs={'pk': pk}))


# ---------------------------------------------------------------------------
# Bracket Visual
# ---------------------------------------------------------------------------

class BracketView(PermissaoFederacaoMixin, DetailView):
    model = EtapaKnockout

    def get_queryset(self):
        return EtapaKnockout.objects.filter(competicao__federacao=self.request.federacao)
    template_name = 'competicao/bracket.html'
    context_object_name = 'etapa'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        confrontos = list(
            self.object.confrontos.select_related(
                'equipe_mandante', 'equipe_visitante', 'vencedor', 'jogo_ida', 'jogo_volta',
            ).order_by('ordem')
        )
        ctx['rodadas_bracket'] = _agrupar_bracket(confrontos)
        ctx['confrontos'] = confrontos
        return ctx


def _agrupar_bracket(confrontos):
    if not confrontos:
        return []
    rounds = []
    n = len(confrontos)
    idx = 0
    while n >= 1:
        rounds.append(confrontos[idx:idx + n])
        idx += n
        n = n // 2
        if n == 0:
            break
    return rounds


# ---------------------------------------------------------------------------
# Local
# ---------------------------------------------------------------------------

class LocalListView(PermissaoFederacaoMixin, ListView):
    model = Local

    template_name = 'competicao/local_lista.html'
    context_object_name = 'locais'

    def get_queryset(self):
        q = self.request.GET.get('q', '')
        qs = Local.objects.filter(federacao=self.request.federacao)
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(cidade__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = LocalForm()
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


@requer_papel(*PODE_SECRETARIAR)
def local_criar_view(request):
    if request.method == 'POST':
        form = LocalForm(request.POST)
        if form.is_valid():
            local = form.save(commit=False)
            local.federacao = request.federacao
            local.save()
            messages.success(request, f"Local '{local.nome}' criado com sucesso.")
        else:
            for errs in form.errors.values():
                for e in errs:
                    messages.warning(request, e)
    return redirect(reverse('competicao:local_lista'))


@requer_papel(*PODE_SECRETARIAR)
def local_editar_view(request, pk):
    local = get_object_or_404(Local, pk=pk, federacao=request.federacao)
    if request.method == 'POST':
        form = LocalForm(request.POST, instance=local)
        if form.is_valid():
            form.save()
            messages.success(request, f"Local '{local.nome}' atualizado.")
            return redirect(reverse('competicao:local_lista'))
    else:
        form = LocalForm(instance=local)
    return render(request, 'competicao/local_form.html', {'form': form, 'local': local})


@requer_papel(*PODE_SECRETARIAR)
def local_excluir_view(request, pk):
    local = get_object_or_404(Local, pk=pk, federacao=request.federacao)
    if request.method == 'POST':
        nome = local.nome
        local.delete()
        messages.success(request, f"Local '{nome}' excluído.")
    return redirect(reverse('competicao:local_lista'))


# ---------------------------------------------------------------------------
# Árbitro (simplificado)
# ---------------------------------------------------------------------------

class ArbitroListView(PermissaoFederacaoMixin, ListView):
    model = UsuarioFederacao
    template_name = 'competicao/arbitro_lista.html'
    context_object_name = 'arbitros'

    def get_queryset(self):
        q = self.request.GET.get('q', '')
        qs = (
            UsuarioFederacao.objects
            .filter(federacao=self.request.federacao, papel=UsuarioFederacao.ARBITRO, ativo=True)
            .select_related('usuario')
            .order_by('usuario__nome')
        )
        if q:
            qs = qs.filter(usuario__nome__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['total_jogos_count'] = Jogo.objects.filter(arbitro__isnull=False).count()
        return ctx


@requer_papel(*PODE_SECRETARIAR)
def arbitro_excluir_view(request, pk):
    arbitro = get_object_or_404(
        UsuarioFederacao, pk=pk, federacao=request.federacao, papel=UsuarioFederacao.ARBITRO,
    )
    if request.method == 'POST':
        arbitro.ativo = False
        arbitro.save(update_fields=['ativo'])
        messages.success(request, f"Árbitro '{arbitro.usuario.nome}' desativado com sucesso.")
    return redirect(reverse('competicao:arbitro_lista'))


@requer_papel()
def arbitro_detalhe_view(request, pk):
    arbitro = get_object_or_404(
        UsuarioFederacao, pk=pk, federacao=request.federacao, papel=UsuarioFederacao.ARBITRO,
    )
    jogos = (
        Jogo.objects.filter(arbitro=arbitro)
        .select_related('equipe_casa', 'equipe_fora', 'rodada__competicao')
        .order_by('-data_hora')[:20]
    )
    ctx = {
        'arbitro': arbitro,
        'jogos_arbitrados': jogos,
        'total_jogos': Jogo.objects.filter(arbitro=arbitro).count(),
    }
    return render(request, 'competicao/arbitro_detalhe.html', ctx)


# ---------------------------------------------------------------------------
# Estatísticas
# ---------------------------------------------------------------------------

class EstatisticasView(PermissaoFederacaoMixin, DetailView):
    model = Competicao

    def get_queryset(self):
        return Competicao.objects.filter(federacao=self.request.federacao)
    template_name = 'competicao/estatisticas.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        comp = self.object

        jogos_finalizados = Jogo.objects.filter(
            rodada__competicao=comp, finalizado=True, anulado=False,
        ).select_related('equipe_casa', 'equipe_fora')

        ctx['assistencias'] = (
            Gol.objects
            .filter(jogo__rodada__competicao=comp, assistencia__isnull=False)
            .values('assistencia__id', 'assistencia__nome', 'assistencia__equipe__nome_equipe')
            .annotate(total=Count('id'))
            .order_by('-total')[:15]
        )
        ctx['artilharia'] = (
            Gol.objects
            .filter(jogo__rodada__competicao=comp, tipo__in=['normal', 'penalti'])
            .values('atleta__id', 'atleta__nome', 'atleta__equipe__nome_equipe')
            .annotate(total=Count('id'))
            .order_by('-total')[:20]
        )
        ctx['gols_por_periodo'] = _gols_por_periodo(comp)
        ctx['forma_recente'] = _forma_recente(comp, jogos_finalizados)
        equipe1_id = self.request.GET.get('equipe1')
        equipe2_id = self.request.GET.get('equipe2')
        ctx['equipes'] = comp.equipes.order_by('nome_equipe')
        ctx['equipe1_id'] = equipe1_id
        ctx['equipe2_id'] = equipe2_id
        if equipe1_id and equipe2_id:
            ctx['h2h'] = _head_to_head(comp, int(equipe1_id), int(equipe2_id))
        ctx['cartoes_equipe'] = (
            Cartao.objects
            .filter(jogo__rodada__competicao=comp)
            .values('jogador__equipe__nome_equipe')
            .annotate(
                amarelos=Count('id', filter=Q(tipo=Cartao.AMARELO)),
                vermelhos=Count('id', filter=Q(tipo=Cartao.VERMELHO)),
            )
            .order_by('-vermelhos', '-amarelos')
        )
        return ctx


def _gols_por_periodo(comp):
    periodos = [
        ('1-15', 1, 15), ('16-30', 16, 30), ('31-45', 31, 45),
        ('46-60', 46, 60), ('61-75', 61, 75), ('76-90', 76, 90), ('91+', 91, 200),
    ]
    gols_qs = Gol.objects.filter(jogo__rodada__competicao=comp, jogo__finalizado=True, jogo__anulado=False)
    return [
        {'periodo': label, 'total': gols_qs.filter(minuto__gte=ini, minuto__lte=fim).count()}
        for label, ini, fim in periodos
    ]


def _forma_recente(comp, jogos_qs):
    equipes = comp.equipes.all()
    forma = {}
    for equipe in equipes:
        jogos = list(
            jogos_qs.filter(Q(equipe_casa=equipe) | Q(equipe_fora=equipe)).order_by('-data_hora', '-pk')[:5]
        )
        resultados = []
        for j in jogos:
            if j.equipe_casa == equipe:
                resultados.append('V' if j.gols_casa > j.gols_fora else ('D' if j.gols_casa < j.gols_fora else 'E'))
            else:
                resultados.append('V' if j.gols_fora > j.gols_casa else ('D' if j.gols_fora < j.gols_casa else 'E'))
        forma[equipe.pk] = {'equipe': equipe, 'forma': resultados}
    return forma.values()


def _head_to_head(comp, equipe1_id, equipe2_id):
    jogos = Jogo.objects.filter(
        rodada__competicao=comp, finalizado=True, anulado=False,
    ).filter(
        Q(equipe_casa_id=equipe1_id, equipe_fora_id=equipe2_id) |
        Q(equipe_casa_id=equipe2_id, equipe_fora_id=equipe1_id)
    ).select_related('equipe_casa', 'equipe_fora').order_by('data_hora')
    v1, v2, empates, gols1, gols2 = 0, 0, 0, 0, 0
    for j in jogos:
        g1, g2 = (j.gols_casa, j.gols_fora) if j.equipe_casa_id == equipe1_id else (j.gols_fora, j.gols_casa)
        gols1 += g1
        gols2 += g2
        if g1 > g2:
            v1 += 1
        elif g2 > g1:
            v2 += 1
        else:
            empates += 1
    return {
        'jogos': jogos,
        'equipe1': Equipe.objects.filter(pk=equipe1_id).first(),
        'equipe2': Equipe.objects.filter(pk=equipe2_id).first(),
        'v1': v1, 'v2': v2, 'empates': empates, 'gols1': gols1, 'gols2': gols2,
    }


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

@requer_papel()
def pdf_classificacao_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk)
    classificacao_raw = Classificacao.objects.filter(competicao=comp).select_related('equipe')
    classificacao = aplicar_criterios(comp, classificacao_raw)
    artilharia = (
        Gol.objects
        .filter(jogo__rodada__competicao=comp, tipo__in=['normal', 'penalti'])
        .values('atleta__nome', 'atleta__equipe__nome_equipe')
        .annotate(total=Count('id'))
        .order_by('-total')[:20]
    )
    grupos_data = []
    for grupo in comp.grupos.all():
        cl = aplicar_criterios(comp, grupo.classificacao.select_related('equipe').all(), grupo=grupo)
        grupos_data.append({'grupo': grupo, 'classificacao': cl})
    ctx = {'competicao': comp, 'classificacao': classificacao, 'artilharia': artilharia, 'grupos_data': grupos_data}
    try:
        nome = comp.nome.replace(' ', '_')[:40]
        return render_pdf('competicao/pdf_classificacao.html', ctx, filename=f'classificacao_{nome}.pdf')
    except RuntimeError:
        return render(request, 'competicao/pdf_classificacao.html', ctx)


@requer_papel()
def pdf_sumula_view(request, pk):
    jogo = get_object_or_404(Jogo, pk=pk)
    ctx = {
        'jogo': jogo,
        'gols_casa': jogo.gols.filter(equipe=jogo.equipe_casa).select_related('atleta', 'assistencia'),
        'gols_fora': jogo.gols.filter(equipe=jogo.equipe_fora).select_related('atleta', 'assistencia'),
        'cartoes': jogo.cartoes.select_related('jogador__equipe').order_by('minuto'),
    }
    try:
        return render_pdf('competicao/pdf_sumula.html', ctx, filename=f'sumula_jogo_{pk}.pdf')
    except RuntimeError:
        return render(request, 'competicao/pdf_sumula.html', ctx)


@requer_papel()
def pdf_elenco_view(request, competicao_pk, equipe_pk):
    competicao = get_object_or_404(Competicao, pk=competicao_pk)
    equipe = get_object_or_404(Equipe, pk=equipe_pk)
    inscricoes = InscricaoAtleta.objects.filter(
        competicao=competicao, atleta__equipe=equipe,
    ).select_related('atleta').order_by('numero_camisa', 'atleta__nome')
    ctx = {'competicao': competicao, 'equipe': equipe, 'inscricoes': inscricoes}
    try:
        nome_eq = equipe.nome_equipe.replace(' ', '_')[:30]
        return render_pdf('competicao/pdf_elenco.html', ctx, filename=f'elenco_{nome_eq}.pdf')
    except RuntimeError:
        return render(request, 'competicao/pdf_elenco.html', ctx)


@requer_papel()
def pdf_artilheiros_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk)
    artilharia = (
        Gol.objects
        .filter(jogo__rodada__competicao=comp, tipo__in=['normal', 'penalti'])
        .values('atleta__nome', 'atleta__equipe__nome_equipe')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    ctx = {'competicao': comp, 'artilharia': artilharia}
    try:
        nome = comp.nome.replace(' ', '_')[:40]
        return render_pdf('competicao/pdf_artilheiros.html', ctx, filename=f'artilheiros_{nome}.pdf')
    except RuntimeError:
        return render(request, 'competicao/pdf_artilheiros.html', ctx)


# ---------------------------------------------------------------------------
# API REST
# ---------------------------------------------------------------------------

from django.http import JsonResponse as _JsonResponse


def api_competicoes_view(request):
    comps = Competicao.objects.values('id', 'nome', 'status', 'modalidade', 'categoria', 'data_inicio', 'data_fim')
    return _JsonResponse({'competicoes': list(comps)})


def api_classificacao_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk)
    cl_raw = Classificacao.objects.filter(competicao=comp).select_related('equipe')
    cl = aplicar_criterios(comp, cl_raw)
    data = [
        {
            'pos': i + 1, 'equipe': c.equipe.nome_equipe,
            'pts': c.pontos, 'j': c.jogos, 'v': c.vitorias,
            'e': c.empates, 'd': c.derrotas,
            'gp': c.gols_pro, 'gc': c.gols_contra, 'sg': c.saldo_gols,
        }
        for i, c in enumerate(cl)
    ]
    return _JsonResponse({'competicao': comp.nome, 'classificacao': data})


def api_jogos_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk)
    jogos = Jogo.objects.filter(rodada__competicao=comp).select_related(
        'equipe_casa', 'equipe_fora', 'rodada__fase',
    ).order_by('data_hora')
    data = [
        {
            'id': j.pk,
            'equipe_casa': j.equipe_casa.nome_equipe,
            'equipe_fora': j.equipe_fora.nome_equipe,
            'gols_casa': j.gols_casa, 'gols_fora': j.gols_fora,
            'data_hora': j.data_hora.isoformat() if j.data_hora else None,
            'finalizado': j.finalizado, 'em_andamento': j.em_andamento,
        }
        for j in jogos
    ]
    return _JsonResponse({'competicao': comp.nome, 'jogos': data})


def api_artilheiros_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk)
    art = (
        Gol.objects
        .filter(jogo__rodada__competicao=comp, tipo__in=['normal', 'penalti'])
        .values('atleta__nome', 'atleta__equipe__nome_equipe')
        .annotate(gols=Count('id'))
        .order_by('-gols')[:20]
    )
    return _JsonResponse({'competicao': comp.nome, 'artilheiros': list(art)})


# ---------------------------------------------------------------------------
# Busca, Dashboard, Calendário
# ---------------------------------------------------------------------------

@requer_papel()
def busca_global_view(request):
    q = request.GET.get('q', '').strip()
    ctx = {'q': q}
    if len(q) >= 2:
        fed = request.federacao
        ctx['equipes'] = Equipe.objects.filter(federacao=fed, nome_equipe__icontains=q)[:8]
        ctx['atletas'] = Atleta.objects.filter(equipe__federacao=fed, nome__icontains=q).select_related('equipe')[:8]
        ctx['comps'] = Competicao.objects.filter(federacao=fed, nome__icontains=q)[:8]
    return render(request, 'competicao/busca_global.html', ctx)


@requer_papel()
def dashboard_view(request):
    vinculo = getattr(request, 'vinculo', None)
    is_superadmin = getattr(request.user, 'is_admin', False)
    if vinculo and not is_superadmin:
        if vinculo.papel == UsuarioFederacao.ARBITRO:
            return redirect('competicao:arbitro_dashboard')
        if vinculo.papel == UsuarioFederacao.DIRIGENTE:
            return redirect('competicao:dirigente_dashboard')

    import json
    from django.utils import timezone
    agora = timezone.now()
    ctx = {}
    fed = request.federacao
    from apps.registro.models import RegistroFederativo, Transferencia
    ctx['total_competicoes'] = Competicao.objects.filter(federacao=fed).count()
    ctx['total_equipes'] = Equipe.objects.filter(federacao=fed).count()
    ctx['total_atletas'] = Atleta.objects.filter(equipe__federacao=fed).count()
    clubes_reg   = Equipe.objects.filter(federacao=fed, situacao=Equipe.SITUACAO_REGULARIZACAO).count()
    atletas_pend = Atleta.objects.filter(equipe__federacao=fed, registro_federativo__isnull=True).count()
    transf_pend  = Transferencia.objects.filter(
        atleta__equipe__federacao=fed,
        status__in=['solicitada', 'em_analise'],
    ).count()
    ctx['clubes_regularizacao']     = clubes_reg
    ctx['atletas_sem_registro']     = atletas_pend
    ctx['transferencias_pendentes'] = transf_pend
    ctx['total_pendencias']         = clubes_reg + atletas_pend + transf_pend
    ctx['competicoes_andamento'] = Competicao.objects.filter(federacao=fed, status='andamento')
    ctx['proximos_jogos'] = Jogo.objects.filter(
        rodada__competicao__federacao=fed, finalizado=False, anulado=False, data_hora__gte=agora,
    ).select_related('equipe_casa', 'equipe_fora', 'rodada__competicao', 'local').order_by('data_hora')[:5]
    ctx['jogos_recentes'] = Jogo.objects.filter(
        rodada__competicao__federacao=fed, finalizado=True, anulado=False,
    ).select_related('equipe_casa', 'equipe_fora', 'rodada__competicao').order_by('-data_hora')[:5]
    artilheiros_list = list(
        Gol.objects
        .filter(jogo__rodada__competicao__federacao=fed, tipo__in=['normal', 'penalti'])
        .values('atleta__nome', 'atleta__equipe__nome_equipe')
        .annotate(total=Count('id'))
        .order_by('-total')[:8]
    )
    ctx['artilheiros_globais'] = artilheiros_list
    ctx['suspensoes_pendentes'] = Suspensao.objects.filter(
        competicao__federacao=fed, cumprida=False,
    ).select_related('atleta__equipe', 'competicao').order_by('-pk')[:8]
    gols_comp_qs = list(
        Gol.objects
        .filter(jogo__rodada__competicao__federacao=fed)
        .values('jogo__rodada__competicao__nome')
        .annotate(total=Count('id'))
        .order_by('-total')[:6]
    )
    ctx['chart_gols_comp_labels'] = json.dumps([r['jogo__rodada__competicao__nome'] or '—' for r in gols_comp_qs])
    ctx['chart_gols_comp_data'] = json.dumps([r['total'] for r in gols_comp_qs])
    ctx['jogos_finalizados'] = Jogo.objects.filter(rodada__competicao__federacao=fed, finalizado=True, anulado=False).count()
    ctx['jogos_andamento'] = Jogo.objects.filter(rodada__competicao__federacao=fed, em_andamento=True).count()
    ctx['jogos_agendados'] = Jogo.objects.filter(rodada__competicao__federacao=fed, finalizado=False, em_andamento=False, anulado=False).count()
    ctx['jogos_anulados'] = Jogo.objects.filter(rodada__competicao__federacao=fed, anulado=True).count()
    cartoes_qs = {r['tipo']: r['total'] for r in Cartao.objects.filter(jogo__rodada__competicao__federacao=fed).values('tipo').annotate(total=Count('id'))}
    ctx['chart_cartoes_amarelo'] = cartoes_qs.get('Amarelo', 0)
    ctx['chart_cartoes_vermelho'] = cartoes_qs.get('Vermelho', 0)
    ctx['chart_art_labels'] = json.dumps([r['atleta__nome'] for r in artilheiros_list])
    ctx['chart_art_data'] = json.dumps([r['total'] for r in artilheiros_list])
    return render(request, 'competicao/dashboard.html', ctx)


@requer_papel()
def jogos_todos_view(request):
    from django.utils import timezone
    agora = timezone.now()
    fed = request.federacao
    base = Jogo.objects.filter(
        rodada__competicao__federacao=fed,
    ).select_related('equipe_casa', 'equipe_fora', 'rodada__competicao', 'local')

    ao_vivo   = base.filter(em_andamento=True).order_by('data_hora')
    proximos  = base.filter(finalizado=False, anulado=False, em_andamento=False,
                            data_hora__gte=agora).order_by('data_hora')
    resultados = base.filter(finalizado=True, anulado=False).order_by('-data_hora')

    return render(request, 'competicao/jogos_todos.html', {
        'ao_vivo':    ao_vivo,
        'proximos':   proximos,
        'resultados': resultados,
    })


@requer_papel(*PODE_ARBITRAR)
def arbitro_dashboard_view(request):
    from django.utils import timezone
    agora = timezone.now()
    vinculo = request.vinculo

    base = Jogo.objects.filter(
        arbitro=vinculo,
        rodada__competicao__federacao=request.federacao,
    ).select_related('equipe_casa', 'equipe_fora', 'rodada__competicao', 'local')

    ao_vivo   = base.filter(em_andamento=True).order_by('data_hora')
    pendentes = base.filter(
        finalizado=False, anulado=False, em_andamento=False,
        data_hora__lt=agora, data_hora__isnull=False,
    ).order_by('data_hora')
    proximos  = base.filter(
        finalizado=False, anulado=False, em_andamento=False,
        data_hora__gte=agora,
    ).order_by('data_hora')
    historico = base.filter(finalizado=True, anulado=False).order_by('-data_hora')[:10]

    return render(request, 'competicao/arbitro_dashboard.html', {
        'ao_vivo':     ao_vivo,
        'pendentes':   pendentes,
        'proximos':    proximos,
        'historico':   historico,
        'total_jogos': base.filter(finalizado=True).count(),
    })


@requer_papel(*PODE_DIRIGIR)
def dirigente_dashboard_view(request):
    from django.utils import timezone
    agora = timezone.now()
    vinculo = request.vinculo
    equipe  = vinculo.equipe if vinculo else None

    if not equipe:
        return render(request, 'competicao/dirigente_sem_clube.html', {})

    atletas = equipe.equipe_jogador.order_by('nome')

    base_jogos = Jogo.objects.filter(
        Q(equipe_casa=equipe) | Q(equipe_fora=equipe),
        rodada__competicao__federacao=request.federacao,
    ).select_related('equipe_casa', 'equipe_fora', 'rodada__competicao', 'local', 'arbitro__usuario')

    proximos  = base_jogos.filter(
        finalizado=False, anulado=False, em_andamento=False,
    ).filter(
        Q(data_hora__isnull=True) | Q(data_hora__gte=agora),
    ).order_by('data_hora')[:3]

    ao_vivo   = base_jogos.filter(em_andamento=True).order_by('data_hora')

    historico = base_jogos.filter(finalizado=True, anulado=False).order_by('-data_hora')[:5]

    competicoes = (
        Competicao.objects
        .filter(
            federacao=request.federacao,
            inscricoes_equipes__equipe=equipe,
        )
        .distinct()
        .order_by('nome')
    )

    proximos_confirmados = set(
        EscalacaoTaticaJogo.objects.filter(
            jogo__in=proximos, equipe=equipe,
        ).values_list('jogo_id', flat=True)
    )

    atletas_sem_registro = atletas.filter(registro_federativo__isnull=True)
    atletas_suspensos    = atletas.filter(situacao='SUSPENSO')
    total_pendencias     = atletas_sem_registro.count() + atletas_suspensos.count()

    return render(request, 'competicao/dirigente_dashboard.html', {
        'equipe':      equipe,
        'atletas':     atletas,
        'proximos':    proximos,
        'ao_vivo':     ao_vivo,
        'historico':   historico,
        'competicoes': competicoes,
        'total_atletas':         atletas.count(),
        'total_jogos':           base_jogos.filter(finalizado=True).count(),
        'proximos_confirmados':  proximos_confirmados,
        'atletas_sem_registro':  atletas_sem_registro,
        'atletas_suspensos':     atletas_suspensos,
        'total_pendencias':      total_pendencias,
    })


@requer_papel(*PODE_DIRIGIR)
def atleta_situacao_view(request, pk):
    vinculo = request.vinculo
    equipe  = getattr(vinculo, 'equipe', None) if vinculo else None
    atleta  = get_object_or_404(Atleta, pk=pk, equipe=equipe)
    if request.method == 'POST' and atleta.situacao != 'SUSPENSO':
        nova = request.POST.get('situacao')
        if nova in ('APTO', 'LESIONADO', 'FORA'):
            atleta.situacao = nova
            atleta.save(update_fields=['situacao'])
    return redirect('competicao:dirigente_dashboard')


@requer_papel(*PODE_DIRIGIR)
def dirigente_jogos_view(request):
    vinculo = request.vinculo
    equipe  = getattr(vinculo, 'equipe', None) if vinculo else None
    if not equipe:
        messages.error(request, 'Seu perfil não está vinculado a nenhum clube.')
        return redirect('competicao:dirigente_dashboard')

    tab = request.GET.get('tab', 'agendados')
    if tab not in ('agendados', 'realizados'):
        tab = 'agendados'

    base_jogos = Jogo.objects.filter(
        Q(equipe_casa=equipe) | Q(equipe_fora=equipe),
        rodada__competicao__federacao=request.federacao,
    ).select_related('equipe_casa', 'equipe_fora', 'rodada__competicao', 'local', 'arbitro__usuario')

    if tab == 'realizados':
        jogos = base_jogos.filter(finalizado=True, anulado=False).order_by(
            F('data_hora').desc(nulls_last=True)
        )
    else:
        jogos = base_jogos.filter(
            finalizado=False, anulado=False, em_andamento=False,
        ).order_by(F('data_hora').asc(nulls_last=True))

    from django.core.paginator import Paginator
    paginator = Paginator(jogos, 10)
    page_obj  = paginator.get_page(request.GET.get('page'))

    jogos_confirmados = set()
    if tab == 'agendados':
        jogos_confirmados = set(
            EscalacaoTaticaJogo.objects.filter(
                jogo__in=page_obj.object_list, equipe=equipe,
            ).values_list('jogo_id', flat=True)
        )

    return render(request, 'competicao/dirigente_jogos.html', {
        'equipe':            equipe,
        'tab':               tab,
        'page_obj':          page_obj,
        'jogos_confirmados': jogos_confirmados,
    })


@requer_papel(*PODE_DIRIGIR)
def dirigente_escalacao_view(request):
    import json
    vinculo = request.vinculo
    equipe  = getattr(vinculo, 'equipe', None) if vinculo else None
    if not equipe:
        messages.error(request, 'Seu perfil não está vinculado a nenhum clube.')
        return redirect('competicao:dirigente_dashboard')

    todos_atletas = [
        {
            'id':      a.id,
            'nome':    a.nome,
            'posicao': a.posicao,
            'situacao':a.situacao,
            'foto':    a.foto.thumbnail.url if a.foto else None,
        }
        for a in equipe.equipe_jogador.order_by('posicao', 'nome')
    ]

    suspensos_ids = {str(a['id']) for a in todos_atletas if a['situacao'] == 'SUSPENSO'}

    try:
        et = equipe.escalacao_tatica
        posicoes_filtradas = {
            k: (v if v and str(v) not in suspensos_ids else None)
            for k, v in et.posicoes.items()
        }
        escalacao_salva = {'formacao': et.formacao, 'posicoes': posicoes_filtradas}
    except EscalacaoTatica.DoesNotExist:
        escalacao_salva = {}

    return render(request, 'competicao/dirigente_escalacao.html', {
        'equipe':         equipe,
        'atletas_json':   json.dumps(todos_atletas),
        'escalacao_json': json.dumps(escalacao_salva),
    })


@requer_papel(*PODE_DIRIGIR)
def escalacao_tatica_salvar_view(request):
    import json
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    vinculo = request.vinculo
    equipe  = getattr(vinculo, 'equipe', None) if vinculo else None
    if not equipe:
        return JsonResponse({'ok': False, 'erro': 'Sem equipe vinculada.'}, status=403)
    try:
        data = json.loads(request.body)
        suspensos_ids = {
            str(pk) for pk in Atleta.objects.filter(
                equipe=equipe, situacao='SUSPENSO',
            ).values_list('pk', flat=True)
        }
        posicoes = {
            k: (v if v and str(v) not in suspensos_ids else None)
            for k, v in data.get('posicoes', {}).items()
        }
        EscalacaoTatica.objects.update_or_create(
            equipe=equipe,
            defaults={
                'formacao': data.get('formacao', '4-3-3'),
                'posicoes': posicoes,
            },
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)


@requer_papel(*PODE_DIRIGIR)
def dirigente_escalacao_jogo_view(request, jogo_pk):
    import json
    vinculo = request.vinculo
    equipe  = getattr(vinculo, 'equipe', None) if vinculo else None
    if not equipe:
        messages.error(request, 'Seu perfil não está vinculado a nenhum clube.')
        return redirect('competicao:dirigente_dashboard')

    jogo = get_object_or_404(
        Jogo,
        pk=jogo_pk,
        rodada__competicao__federacao=request.federacao,
    )
    if jogo.equipe_casa != equipe and jogo.equipe_fora != equipe:
        messages.error(request, 'Este jogo não pertence ao seu clube.')
        return redirect('competicao:dirigente_dashboard')

    competicao = jogo.rodada.competicao

    inscritos_ids = set(
        InscricaoAtleta.objects
        .filter(competicao=competicao, atleta__equipe=equipe)
        .values_list('atleta_id', flat=True)
    )
    inscritos_ids_str = {str(i) for i in inscritos_ids}

    atletas_inscritos = equipe.equipe_jogador.filter(
        pk__in=inscritos_ids
    ).order_by('posicao', 'nome')

    camisa_map = {
        str(i.atleta_id): i.numero_camisa
        for i in InscricaoAtleta.objects.filter(competicao=competicao, atleta__equipe=equipe)
    }

    suspensos_ids = {str(a.pk) for a in atletas_inscritos if a.situacao == 'SUSPENSO'}

    # Escalação confirmada para este jogo, ou padrão filtrada
    try:
        etj = EscalacaoTaticaJogo.objects.get(jogo=jogo, equipe=equipe)
        posicoes_filtradas = {
            k: (v if v and str(v) not in suspensos_ids else None)
            for k, v in etj.posicoes.items()
        }
        escalacao_inicial = {'formacao': etj.formacao, 'posicoes': posicoes_filtradas, 'confirmado': True}
    except EscalacaoTaticaJogo.DoesNotExist:
        try:
            et = equipe.escalacao_tatica
            posicoes_filtradas = {
                k: (v if v and str(v) in inscritos_ids_str and str(v) not in suspensos_ids else None)
                for k, v in et.posicoes.items()
            }
            escalacao_inicial = {'formacao': et.formacao, 'posicoes': posicoes_filtradas, 'confirmado': False}
        except EscalacaoTatica.DoesNotExist:
            escalacao_inicial = {'confirmado': False}

    todos_atletas = [
        {
            'id':      str(a.pk),
            'nome':    a.nome,
            'posicao': a.posicao,
            'situacao': a.situacao,
            'foto':    a.foto.thumbnail.url if a.foto else '',
            'camisa':  camisa_map.get(str(a.pk)),
        }
        for a in atletas_inscritos
    ]

    from django.utils import timezone
    agora = timezone.now()
    bloqueado = jogo.finalizado or jogo.em_andamento or (
        jogo.data_hora is not None and jogo.data_hora <= agora
    )

    return render(request, 'competicao/dirigente_escalacao_jogo.html', {
        'equipe':         equipe,
        'jogo':           jogo,
        'competicao':     competicao,
        'atletas_json':   json.dumps(todos_atletas),
        'escalacao_json': json.dumps(escalacao_inicial),
        'bloqueado':      bloqueado,
    })


@requer_papel(*PODE_DIRIGIR)
def escalacao_tatica_jogo_salvar_view(request, jogo_pk):
    import json
    from django.utils import timezone
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    vinculo = request.vinculo
    equipe  = getattr(vinculo, 'equipe', None) if vinculo else None
    if not equipe:
        return JsonResponse({'ok': False, 'erro': 'Sem equipe vinculada.'}, status=403)

    jogo = get_object_or_404(Jogo, pk=jogo_pk, rodada__competicao__federacao=request.federacao)
    if jogo.equipe_casa != equipe and jogo.equipe_fora != equipe:
        return JsonResponse({'ok': False, 'erro': 'Jogo não pertence ao clube.'}, status=403)

    agora = timezone.now()
    bloqueado = jogo.finalizado or jogo.em_andamento or (
        jogo.data_hora is not None and jogo.data_hora <= agora
    )
    if bloqueado:
        return JsonResponse({'ok': False, 'erro': 'Jogo já iniciado. Escalação não pode ser modificada.'}, status=403)

    try:
        data = json.loads(request.body)
        suspensos_ids = {
            str(pk) for pk in Atleta.objects.filter(
                equipe=equipe, situacao='SUSPENSO',
            ).values_list('pk', flat=True)
        }
        posicoes = {
            k: (v if v and str(v) not in suspensos_ids else None)
            for k, v in data.get('posicoes', {}).items()
        }
        EscalacaoTaticaJogo.objects.update_or_create(
            jogo=jogo,
            equipe=equipe,
            defaults={
                'formacao':       data.get('formacao', '4-3-3'),
                'posicoes':       posicoes,
                'confirmado_por': request.user,
            },
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)


@requer_papel(*PODE_DIRIGIR)
def dirigente_inscricao_view(request, competicao_pk):
    vinculo = request.vinculo
    equipe  = getattr(vinculo, 'equipe', None) if vinculo else None
    if not equipe:
        messages.error(request, 'Seu perfil não está vinculado a nenhum clube.')
        return redirect('competicao:dirigente_dashboard')

    competicao = get_object_or_404(
        Competicao,
        pk=competicao_pk,
        federacao=request.federacao,
        inscricoes_equipes__equipe=equipe,
    )

    inscritos = (
        InscricaoAtleta.objects
        .filter(competicao=competicao, atleta__equipe=equipe)
        .select_related('atleta')
        .order_by('numero_camisa', 'atleta__nome')
    )

    amarelos_map = {
        row['jogador_id']: row['total']
        for row in Cartao.objects.filter(
            jogo__rodada__competicao=competicao, tipo=Cartao.AMARELO,
        ).values('jogador_id').annotate(total=Count('id'))
    }
    vermelhos_map = {
        row['jogador_id']: row['total']
        for row in Cartao.objects.filter(
            jogo__rodada__competicao=competicao, tipo=Cartao.VERMELHO,
        ).values('jogador_id').annotate(total=Count('id'))
    }
    suspensos_ids = set(
        Suspensao.objects.filter(competicao=competicao, cumprida=False)
        .values_list('atleta_id', flat=True)
    )

    form = InscricaoAtletaForm(competicao=competicao, equipe=equipe)

    from datetime import date
    hoje = date.today()
    inscricoes_abertas = True
    aviso_prazo = None
    if competicao.data_abertura_inscricao and hoje < competicao.data_abertura_inscricao:
        inscricoes_abertas = False
        aviso_prazo = f'Inscrições abertas a partir de {competicao.data_abertura_inscricao.strftime("%d/%m/%Y")}.'
    elif competicao.data_encerramento_inscricao and hoje > competicao.data_encerramento_inscricao:
        inscricoes_abertas = False
        aviso_prazo = 'Prazo de inscrições encerrado.'

    limite_atingido = False
    if competicao.limite_atletas:
        limite_atingido = inscritos.count() >= competicao.limite_atletas

    return render(request, 'competicao/dirigente_inscricao.html', {
        'competicao':        competicao,
        'equipe':            equipe,
        'inscritos':         inscritos,
        'form':              form,
        'amarelos_map':      amarelos_map,
        'vermelhos_map':     vermelhos_map,
        'suspensos_ids':     suspensos_ids,
        'inscricoes_abertas': inscricoes_abertas,
        'aviso_prazo':       aviso_prazo,
        'limite_atingido':   limite_atingido,
    })


@requer_papel()
def calendario_view(request):
    from django.utils import timezone
    from datetime import timedelta
    competicao_id = request.GET.get('competicao')
    periodo = request.GET.get('periodo')
    qs = Jogo.objects.filter(rodada__competicao__federacao=request.federacao, data_hora__isnull=False).select_related(
        'equipe_casa', 'equipe_fora', 'rodada__competicao', 'local',
    ).order_by('data_hora')
    if competicao_id:
        qs = qs.filter(rodada__competicao_id=competicao_id)
    agora = timezone.now()
    if periodo == 'hoje':
        qs = qs.filter(data_hora__date=agora.date())
    elif periodo == 'semana':
        qs = qs.filter(data_hora__date__gte=agora.date(), data_hora__date__lte=(agora + timedelta(days=7)).date())
    elif periodo == 'mes':
        qs = qs.filter(data_hora__year=agora.year, data_hora__month=agora.month)
    return render(request, 'competicao/calendario.html', {
        'jogos': qs,
        'competicoes': Competicao.objects.filter(federacao=request.federacao).order_by('nome'),
        'competicao_id': competicao_id,
        'periodo': periodo,
    })


# ---------------------------------------------------------------------------
# Área Pública
# ---------------------------------------------------------------------------

class PublicClassificacaoView(DetailView):
    model = Competicao
    template_name = 'competicao/public_classificacao.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        comp = self.object
        classificacao_raw = Classificacao.objects.filter(competicao=comp).select_related('equipe')
        ctx['classificacao'] = aplicar_criterios(comp, classificacao_raw)
        ctx['tem_provisorio'] = Jogo.objects.filter(
            rodada__competicao=comp,
            status=Jogo.STATUS_PROVISORIO,
            anulado=False,
        ).exists()
        ctx['artilharia'] = (
            Gol.objects
            .filter(jogo__rodada__competicao=comp, tipo__in=['normal', 'penalti'])
            .values('atleta__nome', 'atleta__equipe__nome_equipe')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        ctx['jogos_recentes'] = Jogo.objects.filter(
            rodada__competicao=comp, finalizado=True, anulado=False,
        ).select_related('equipe_casa', 'equipe_fora').order_by('-data_hora')[:5]
        ctx['proximos_jogos'] = Jogo.objects.filter(
            rodada__competicao=comp, finalizado=False, anulado=False,
        ).select_related('equipe_casa', 'equipe_fora', 'local').order_by('data_hora')[:5]
        return ctx


def portal_clube_view(request, pk):
    equipe = get_object_or_404(Equipe, pk=pk)
    jogos_qs = Jogo.objects.filter(
        Q(equipe_casa=equipe) | Q(equipe_fora=equipe), finalizado=True
    ).select_related('equipe_casa', 'equipe_fora', 'rodada__competicao')
    ctx = {
        'equipe': equipe,
        'total_jogos': jogos_qs.count(),
        'total_gols': Gol.objects.filter(equipe=equipe).count(),
        'total_amarelos': Cartao.objects.filter(atleta__equipe=equipe, tipo='Amarelo').count(),
        'total_vermelhos': Cartao.objects.filter(atleta__equipe=equipe, tipo='Vermelho').count(),
        'competicoes': Competicao.objects.filter(equipes=equipe).distinct().order_by('-data_inicio'),
        'inscricoes': InscricaoAtleta.objects.filter(
            competicao__equipes=equipe, atleta__equipe=equipe
        ).select_related('atleta', 'competicao').distinct().order_by('numero_camisa'),
        'jogos_recentes': jogos_qs.order_by('-data_hora')[:10],
    }
    return render(request, 'portal/clube.html', ctx)


def portal_atleta_view(request, pk):
    atleta = get_object_or_404(Atleta.objects.select_related('equipe'), pk=pk)
    ctx = {
        'atleta': atleta,
        'total_gols': Gol.objects.filter(atleta=atleta).count(),
        'total_amarelos': Cartao.objects.filter(atleta=atleta, tipo='Amarelo').count(),
        'total_vermelhos': Cartao.objects.filter(atleta=atleta, tipo='Vermelho').count(),
        'total_assistencias': Gol.objects.filter(assistencia=atleta).count(),
        'competicoes': InscricaoAtleta.objects.filter(atleta=atleta).select_related('competicao').order_by('-competicao__data_inicio'),
        'gols_recentes': Gol.objects.filter(atleta=atleta).select_related('jogo__equipe_casa', 'jogo__equipe_fora', 'equipe').order_by('-jogo__data_hora')[:10],
    }
    return render(request, 'portal/atleta.html', ctx)


def portal_arbitro_view(request, pk):
    arbitro = get_object_or_404(UsuarioFederacao, pk=pk, papel=UsuarioFederacao.ARBITRO)
    jogos = Jogo.objects.filter(arbitro=arbitro).select_related(
        'equipe_casa', 'equipe_fora', 'rodada__competicao'
    ).order_by('-data_hora')
    ctx = {
        'arbitro': arbitro,
        'total_jogos': jogos.count(),
        'jogos_recentes': jogos[:10],
    }
    return render(request, 'portal/arbitro.html', ctx)


# ---------------------------------------------------------------------------
# Microsite Público (H)
# ---------------------------------------------------------------------------

def microsite_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk)
    from .dominio.classificador import aplicar_criterios
    cl_raw = Classificacao.objects.filter(competicao=comp).select_related('equipe')
    classificacao = aplicar_criterios(comp, cl_raw)
    grupos_data = []
    for grupo in comp.grupos.all():
        cl = aplicar_criterios(comp, grupo.classificacao.select_related('equipe').all(), grupo=grupo)
        grupos_data.append({'grupo': grupo, 'classificacao': cl})
    artilharia = (
        Gol.objects
        .filter(jogo__rodada__competicao=comp, tipo__in=['normal', 'penalti'])
        .values('atleta__id', 'atleta__nome', 'atleta__equipe__nome_equipe')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )
    ctx = {
        'competicao': comp,
        'classificacao': classificacao,
        'grupos_data': grupos_data,
        'etapas_knockout': comp.etapas.all(),
        'artilharia': artilharia,
        'jogos_recentes': Jogo.objects.filter(
            rodada__competicao=comp, finalizado=True, anulado=False,
        ).select_related('equipe_casa', 'equipe_fora').order_by('-data_hora')[:8],
        'proximos_jogos': Jogo.objects.filter(
            rodada__competicao=comp, finalizado=False, anulado=False,
        ).select_related('equipe_casa', 'equipe_fora', 'local').order_by('data_hora')[:8],
        'equipes': comp.equipes.order_by('nome_equipe'),
    }
    return render(request, 'competicao/microsite.html', ctx)


def widget_classificacao_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk)
    from .dominio.classificador import aplicar_criterios
    cl_raw = Classificacao.objects.filter(competicao=comp).select_related('equipe')
    classificacao = aplicar_criterios(comp, cl_raw)
    return render(request, 'competicao/widget_classificacao.html', {
        'competicao': comp,
        'classificacao': classificacao,
    })


# ---------------------------------------------------------------------------
# Súmula Digital (A)
# ---------------------------------------------------------------------------

def _eh_secretario(request):
    # O registro da súmula é atribuição do árbitro; a secretaria apenas
    # visualiza e homologa (os dados do árbitro são a base oficial).
    if getattr(request.user, 'is_admin', False):
        return False
    vinculo = getattr(request, 'vinculo', None)
    return bool(vinculo and vinculo.papel == 'SEC')


_MSG_SECRETARIO_SUMULA = ('O registro da súmula é atribuição do árbitro. '
                          'A secretaria pode visualizar e homologar após o encerramento.')


@requer_papel(*PODE_ARBITRAR)
@requer_status(Competicao.ANDAMENTO,
               obter=por_relacao(Jogo, 'rodada__competicao', param='jogo_pk'))
def sumula_view(request, jogo_pk):
    jogo = get_object_or_404(Jogo, pk=jogo_pk, rodada__competicao__federacao=request.federacao)
    sumula, _ = Sumula.objects.get_or_create(jogo=jogo)
    pode_editar = sumula.pode_editar() and not _eh_secretario(request)
    equipes = [jogo.equipe_casa, jogo.equipe_fora]
    escalacao_data = [
        (
            eq,
            EscalacaoJogoForm(sumula=sumula, equipe=eq),
            sumula.escalacao.filter(equipe=eq).select_related('atleta'),
        )
        for eq in equipes
    ]
    subs_data = [
        (eq, SubstituicaoJogoForm(sumula=sumula, equipe=eq))
        for eq in equipes
    ]
    ctx = {
        'jogo': jogo,
        'sumula': sumula,
        'form_arb': SumulaArbitragemForm(instance=sumula, federacao=request.federacao),
        'form_ocorrencia': OcorrenciaJogoForm(),
        'escalacao_data': escalacao_data,
        'subs_data': subs_data,
        'substituicoes': sumula.substituicoes.select_related('atleta_saiu', 'atleta_entrou', 'equipe').all(),
        'ocorrencias': sumula.ocorrencias.all(),
        'pode_editar': pode_editar,
    }
    return render(request, 'competicao/sumula.html', ctx)


@requer_papel(*PODE_ARBITRAR)
def sumula_salvar_arbitragem_view(request, pk):
    sumula = get_object_or_404(Sumula, pk=pk, jogo__rodada__competicao__federacao=request.federacao)
    if _eh_secretario(request):
        messages.warning(request, _MSG_SECRETARIO_SUMULA)
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))
    if not sumula.pode_editar():
        messages.warning(request, 'Súmula não pode ser editada neste status.')
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))
    if request.method == 'POST':
        form = SumulaArbitragemForm(request.POST, instance=sumula, federacao=request.federacao)
        if form.is_valid():
            sumula = form.save(commit=False)
            if sumula.status == Sumula.STATUS_RASCUNHO:
                sumula.status = Sumula.STATUS_ABERTA
            sumula.save()
            messages.success(request, 'Arbitragem salva.')
        else:
            for errs in form.errors.values():
                for e in errs:
                    messages.warning(request, e)
    return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))


@requer_papel(*PODE_ARBITRAR)
def escalacao_adicionar_view(request, sumula_pk, equipe_pk):
    sumula = get_object_or_404(Sumula, pk=sumula_pk, jogo__rodada__competicao__federacao=request.federacao)
    equipe = get_object_or_404(Equipe, pk=equipe_pk)
    if _eh_secretario(request):
        messages.warning(request, _MSG_SECRETARIO_SUMULA)
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))
    if not sumula.pode_editar():
        messages.warning(request, 'Súmula não pode ser editada.')
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))
    if request.method == 'POST':
        form = EscalacaoJogoForm(request.POST, sumula=sumula, equipe=equipe)
        if form.is_valid():
            e = form.save(commit=False)
            e.sumula = sumula
            e.equipe = equipe
            e.save()
            messages.success(request, f'{e.atleta.nome} adicionado à escalação.')
        else:
            for errs in form.errors.values():
                for e in errs:
                    messages.warning(request, e)
    return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))


@requer_papel(*PODE_ARBITRAR)
def escalacao_remover_view(request, pk):
    esc = get_object_or_404(EscalacaoJogo, pk=pk, sumula__jogo__rodada__competicao__federacao=request.federacao)
    jogo_pk = esc.sumula.jogo_id
    if _eh_secretario(request):
        messages.warning(request, _MSG_SECRETARIO_SUMULA)
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': jogo_pk}))
    if not esc.sumula.pode_editar():
        messages.warning(request, 'Súmula não pode ser editada.')
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': jogo_pk}))
    if request.method == 'POST':
        nome = esc.atleta.nome
        esc.delete()
        messages.success(request, f'{nome} removido da escalação.')
    return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': jogo_pk}))


@requer_papel(*PODE_ARBITRAR)
def substituicao_adicionar_view(request, sumula_pk, equipe_pk):
    sumula = get_object_or_404(Sumula, pk=sumula_pk, jogo__rodada__competicao__federacao=request.federacao)
    equipe = get_object_or_404(Equipe, pk=equipe_pk)
    if _eh_secretario(request):
        messages.warning(request, _MSG_SECRETARIO_SUMULA)
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))
    if not sumula.pode_editar():
        messages.warning(request, 'Súmula não pode ser editada.')
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))
    if request.method == 'POST':
        form = SubstituicaoJogoForm(request.POST, sumula=sumula, equipe=equipe)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.sumula = sumula
            sub.equipe = equipe
            sub.save()
            messages.success(request, f"Substituição {sub.minuto}' registrada.")
        else:
            for errs in form.errors.values():
                for e in errs:
                    messages.warning(request, e)
    return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))


@requer_papel(*PODE_ARBITRAR)
def substituicao_remover_view(request, pk):
    sub = get_object_or_404(SubstituicaoJogo, pk=pk, sumula__jogo__rodada__competicao__federacao=request.federacao)
    jogo_pk = sub.sumula.jogo_id
    if _eh_secretario(request):
        messages.warning(request, _MSG_SECRETARIO_SUMULA)
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': jogo_pk}))
    if request.method == 'POST':
        sub.delete()
        messages.success(request, 'Substituição removida.')
    return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': jogo_pk}))


@requer_papel(*PODE_ARBITRAR)
def ocorrencia_adicionar_view(request, sumula_pk):
    sumula = get_object_or_404(Sumula, pk=sumula_pk, jogo__rodada__competicao__federacao=request.federacao)
    if _eh_secretario(request):
        messages.warning(request, _MSG_SECRETARIO_SUMULA)
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))
    if not sumula.pode_editar():
        messages.warning(request, 'Súmula não pode ser editada.')
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))
    if request.method == 'POST':
        form = OcorrenciaJogoForm(request.POST)
        if form.is_valid():
            oc = form.save(commit=False)
            oc.sumula = sumula
            oc.save()
            messages.success(request, 'Ocorrência registrada.')
        else:
            for errs in form.errors.values():
                for e in errs:
                    messages.warning(request, e)
    return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))


@requer_papel(*PODE_ARBITRAR)
def ocorrencia_remover_view(request, pk):
    oc = get_object_or_404(OcorrenciaJogo, pk=pk, sumula__jogo__rodada__competicao__federacao=request.federacao)
    jogo_pk = oc.sumula.jogo_id
    if _eh_secretario(request):
        messages.warning(request, _MSG_SECRETARIO_SUMULA)
        return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': jogo_pk}))
    if request.method == 'POST':
        oc.delete()
        messages.success(request, 'Ocorrência removida.')
    return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': jogo_pk}))


def _confronto_com_penaltis(jogo):
    confronto = ConfrontoMatamate.objects.filter(
        Q(jogo_ida=jogo) | Q(jogo_volta=jogo),
    ).first()
    if confronto is None:
        return False
    return (
        confronto.penaltis_mandante is not None
        and confronto.penaltis_visitante is not None
    )


@requer_papel(*PODE_ARBITRAR)
def sumula_encerrar_view(request, pk):
    sumula = get_object_or_404(Sumula, pk=pk, jogo__rodada__competicao__federacao=request.federacao)
    if request.method == 'POST':
        if sumula.pode_encerrar():
            jogo = sumula.jogo
            if jogo.exige_desempate() and not _confronto_com_penaltis(jogo):
                comp = jogo.rodada.competicao
                if comp.penaltis_disponiveis:
                    messages.warning(
                        request,
                        'Placar empatado e a competição não permite empate. '
                        'Registre os pênaltis antes de encerrar a súmula.',
                    )
                else:
                    messages.warning(
                        request,
                        'Placar empatado e a competição não permite empate. '
                        'Nenhum desempate configurado — ajuste o placar.',
                    )
                return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))
            sumula.status = Sumula.STATUS_ENCERRADA
            sumula.save(update_fields=['status'])
            if jogo.status != Jogo.STATUS_FINALIZADO and jogo.status != Jogo.STATUS_HOMOLOGADO:
                jogo.status = Jogo.STATUS_FINALIZADO
                jogo.save(update_fields=['status'])
            from .notifications import notificar_sumula_encerrada
            notificar_sumula_encerrada(sumula)
            messages.success(request, 'Súmula encerrada. Resultado preliminar publicado; aguardando homologação.')
        else:
            messages.warning(request, f'Não é possível encerrar a súmula no status "{sumula.get_status_display()}".')
    return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))


@requer_papel(*PODE_SECRETARIAR)
def sumula_homologar_view(request, pk):
    sumula = get_object_or_404(Sumula, pk=pk, jogo__rodada__competicao__federacao=request.federacao)
    if request.method == 'POST':
        if sumula.pode_homologar():
            from django.utils import timezone
            sumula.status = Sumula.STATUS_HOMOLOGADA
            sumula.homologada_por = request.user
            sumula.homologada_em = timezone.now()
            sumula.save(update_fields=['status', 'homologada_por', 'homologada_em'])
            jogo = sumula.jogo
            jogo.status = Jogo.STATUS_HOMOLOGADO
            jogo.save(update_fields=['status'])
            from .notifications import notificar_sumula_homologada
            notificar_sumula_homologada(sumula)
            messages.success(request, 'Súmula homologada com sucesso.')
        else:
            messages.warning(request, f'Não é possível homologar no status "{sumula.get_status_display()}".')
    return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))


@requer_papel(*PODE_SECRETARIAR)
def sumula_reabrir_view(request, pk):
    sumula = get_object_or_404(Sumula, pk=pk, jogo__rodada__competicao__federacao=request.federacao)
    if request.method == 'POST':
        if sumula.pode_reabrir():
            sumula.status = Sumula.STATUS_ABERTA
            sumula.save(update_fields=['status'])
            jogo = sumula.jogo
            if jogo.status in (Jogo.STATUS_FINALIZADO, Jogo.STATUS_HOMOLOGADO):
                jogo.status = Jogo.STATUS_EM_ANDAMENTO
                jogo.save(update_fields=['status'])
            messages.success(request, 'Súmula reaberta para edição. O resultado saiu da classificação até novo encerramento.')
        else:
            messages.warning(request, 'Não é possível reabrir esta súmula.')
    return redirect(reverse('competicao:sumula', kwargs={'jogo_pk': sumula.jogo_id}))


# ---------------------------------------------------------------------------
# Temporadas (D)
# ---------------------------------------------------------------------------

@requer_papel(*APENAS_ADMIN)
def temporada_lista_view(request):
    from apps.core.models import Temporada
    temporadas = Temporada.objects.filter(federacao=request.federacao)
    form = TemporadaForm()
    return render(request, 'competicao/temporadas.html', {
        'temporadas': temporadas,
        'form': form,
    })


@requer_papel(*APENAS_ADMIN)
def temporada_criar_view(request):
    from apps.core.models import Temporada
    if request.method == 'POST':
        form = TemporadaForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            t, created = Temporada.objects.get_or_create(
                federacao=request.federacao, ano=d['ano'],
                defaults={'nome': d['nome'], 'ativa': d.get('ativa', False)},
            )
            if created:
                if t.ativa:
                    Temporada.objects.filter(federacao=request.federacao, ativa=True).exclude(pk=t.pk).update(ativa=False)
                messages.success(request, f"Temporada '{t.nome}' criada.")
            else:
                messages.warning(request, f'Já existe uma temporada para o ano {d["ano"]}.')
        else:
            for errs in form.errors.values():
                for e in errs:
                    messages.warning(request, e)
    return redirect(reverse('competicao:temporada_lista'))


@requer_papel(*APENAS_ADMIN)
def temporada_ativar_view(request, pk):
    from apps.core.models import Temporada
    t = get_object_or_404(Temporada, pk=pk, federacao=request.federacao)
    if request.method == 'POST':
        Temporada.objects.filter(federacao=request.federacao, ativa=True).update(ativa=False)
        t.ativa = True
        t.save(update_fields=['ativa'])
        messages.success(request, f"Temporada '{t.nome}' definida como ativa.")
    return redirect(reverse('competicao:temporada_lista'))


# ---------------------------------------------------------------------------
# Estatísticas avançadas (I) — Fair Play + Histórico de Posição
# ---------------------------------------------------------------------------

@requer_papel()
def estatisticas_fairplay_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk, federacao=request.federacao)
    fair_play = (
        Cartao.objects
        .filter(jogo__rodada__competicao=comp)
        .values('jogador__equipe__id', 'jogador__equipe__nome_equipe')
        .annotate(
            amarelos=Count('id', filter=Q(tipo=Cartao.AMARELO)),
            vermelhos=Count('id', filter=Q(tipo=Cartao.VERMELHO)),
        )
        .annotate(
            pontos_fair_play=models.ExpressionWrapper(
                models.F('amarelos') * 1 + models.F('vermelhos') * 3,
                output_field=models.IntegerField()
            )
        )
        .order_by('pontos_fair_play')
    )
    atletas_fair_play = (
        Cartao.objects
        .filter(jogo__rodada__competicao=comp)
        .values('jogador__id', 'jogador__nome', 'jogador__equipe__nome_equipe')
        .annotate(
            amarelos=Count('id', filter=Q(tipo=Cartao.AMARELO)),
            vermelhos=Count('id', filter=Q(tipo=Cartao.VERMELHO)),
        )
        .order_by('-vermelhos', '-amarelos')[:20]
    )
    return render(request, 'competicao/fairplay.html', {
        'competicao': comp,
        'fair_play': fair_play,
        'atletas_fair_play': atletas_fair_play,
        'suspensoes': Suspensao.objects.filter(
            competicao=comp,
        ).select_related('atleta__equipe').order_by('-pk'),
    })


@requer_papel()
def historico_posicoes_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk, federacao=request.federacao)
    equipes = comp.equipes.order_by('nome_equipe')
    rodadas = Rodada.objects.filter(competicao=comp, grupo__isnull=True, etapa__isnull=True).order_by('numero')
    historico = HistoricoClassificacao.objects.filter(
        competicao=comp,
    ).select_related('equipe', 'rodada').order_by('rodada__numero', 'posicao')
    historico_por_equipe = {}
    for h in historico:
        historico_por_equipe.setdefault(h.equipe_id, {})[h.rodada.numero] = h.posicao
    dados_chart = []
    for equipe in equipes:
        serie = [historico_por_equipe.get(equipe.pk, {}).get(r.numero) for r in rodadas]
        if any(p is not None for p in serie):
            dados_chart.append({'equipe': equipe.nome_equipe, 'posicoes': serie})
    import json
    return render(request, 'competicao/historico_posicoes.html', {
        'competicao': comp,
        'rodadas': rodadas,
        'dados_chart_json': json.dumps(dados_chart),
        'labels_json': json.dumps([f'R{r.numero}' for r in rodadas]),
    })


# ---------------------------------------------------------------------------
# API REST (F) — autenticada por ApiKey
# ---------------------------------------------------------------------------

import functools
from django.utils import timezone as _tz


def _requer_api_key(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        chave = (
            request.headers.get('X-Api-Key')
            or request.GET.get('api_key')
        )
        if not chave:
            return JsonResponse({'erro': 'API key obrigatória'}, status=401)
        try:
            key_obj = ApiKey.objects.select_related('federacao').get(chave=chave, ativa=True)
        except ApiKey.DoesNotExist:
            return JsonResponse({'erro': 'API key inválida ou inativa'}, status=403)
        ApiKey.objects.filter(pk=key_obj.pk).update(ultimo_uso=_tz.now())
        request.api_federacao = key_obj.federacao
        return view_func(request, *args, **kwargs)
    return wrapper


@_requer_api_key
def api_v2_competicoes_view(request):
    comps = Competicao.objects.filter(
        federacao=request.api_federacao
    ).values('id', 'nome', 'status', 'modalidade', 'categoria', 'data_inicio', 'data_fim', 'slug')
    return JsonResponse({'competicoes': list(comps)})


@_requer_api_key
def api_v2_classificacao_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk, federacao=request.api_federacao)
    from .dominio.classificador import aplicar_criterios
    cl_raw = Classificacao.objects.filter(competicao=comp).select_related('equipe')
    cl = aplicar_criterios(comp, cl_raw)
    data = [
        {
            'pos': i + 1, 'equipe_id': c.equipe.pk, 'equipe': c.equipe.nome_equipe,
            'pts': c.pontos, 'j': c.jogos, 'v': c.vitorias,
            'e': c.empates, 'd': c.derrotas,
            'gp': c.gols_pro, 'gc': c.gols_contra, 'sg': c.saldo_gols,
        }
        for i, c in enumerate(cl)
    ]
    return JsonResponse({'competicao_id': comp.pk, 'competicao': comp.nome, 'classificacao': data})


@_requer_api_key
def api_v2_jogos_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk, federacao=request.api_federacao)
    jogos = Jogo.objects.filter(rodada__competicao=comp).select_related(
        'equipe_casa', 'equipe_fora', 'rodada__fase', 'local', 'arbitro__usuario',
    ).order_by('data_hora')
    data = [
        {
            'id': j.pk,
            'equipe_casa': j.equipe_casa.nome_equipe,
            'equipe_fora': j.equipe_fora.nome_equipe,
            'gols_casa': j.gols_casa, 'gols_fora': j.gols_fora,
            'data_hora': j.data_hora.isoformat() if j.data_hora else None,
            'local': j.local.nome if j.local else None,
            'etapa': j.rodada.etapa.nome if j.rodada and j.rodada.etapa_id else None,
            'finalizado': j.finalizado, 'em_andamento': j.em_andamento,
            'sumula_status': j.sumula.status if hasattr(j, 'sumula') else None,
        }
        for j in jogos
    ]
    return JsonResponse({'competicao_id': comp.pk, 'competicao': comp.nome, 'jogos': data})


@_requer_api_key
def api_v2_artilheiros_view(request, pk):
    comp = get_object_or_404(Competicao, pk=pk, federacao=request.api_federacao)
    art = (
        Gol.objects
        .filter(jogo__rodada__competicao=comp, tipo__in=['normal', 'penalti'])
        .values('atleta__id', 'atleta__nome', 'atleta__equipe__nome_equipe')
        .annotate(gols=Count('id'))
        .order_by('-gols')[:20]
    )
    return JsonResponse({'competicao_id': comp.pk, 'artilheiros': list(art)})


@_requer_api_key
def api_v2_sumula_view(request, jogo_pk):
    jogo = get_object_or_404(Jogo, pk=jogo_pk, rodada__competicao__federacao=request.api_federacao)
    try:
        s = jogo.sumula
    except Sumula.DoesNotExist:
        return JsonResponse({'erro': 'Súmula não encontrada'}, status=404)
    escalacao = list(s.escalacao.select_related('atleta', 'equipe').values(
        'atleta__nome', 'atleta__id', 'equipe__nome_equipe', 'tipo', 'numero_camisa', 'capitao'
    ))
    subs = list(s.substituicoes.select_related('atleta_saiu', 'atleta_entrou', 'equipe').values(
        'minuto', 'atleta_saiu__nome', 'atleta_entrou__nome', 'equipe__nome_equipe'
    ))
    return JsonResponse({
        'sumula_id': s.pk, 'status': s.status,
        'jogo_id': jogo.pk,
        'escalacao': escalacao,
        'substituicoes': subs,
        'ocorrencias': list(s.ocorrencias.values('tipo', 'descricao', 'minuto')),
    })


@requer_papel(*PODE_SECRETARIAR)
def api_keys_view(request):
    chaves = ApiKey.objects.filter(federacao=request.federacao).order_by('-criada_em')
    form = ApiKeyForm()
    return render(request, 'competicao/api_keys.html', {'chaves': chaves, 'form': form})


@requer_papel(*PODE_SECRETARIAR)
def api_key_criar_view(request):
    if request.method == 'POST':
        form = ApiKeyForm(request.POST)
        if form.is_valid():
            key = form.save(commit=False)
            key.federacao = request.federacao
            key.save()
            messages.success(request, f'Chave "{key.nome}" criada: {key.chave}')
        else:
            for errs in form.errors.values():
                for e in errs:
                    messages.warning(request, e)
    return redirect(reverse('competicao:api_keys'))


@requer_papel(*PODE_SECRETARIAR)
def api_key_revogar_view(request, pk):
    key = get_object_or_404(ApiKey, pk=pk, federacao=request.federacao)
    if request.method == 'POST':
        key.ativa = False
        key.save(update_fields=['ativa'])
        messages.success(request, f'Chave "{key.nome}" revogada.')
    return redirect(reverse('competicao:api_keys'))
