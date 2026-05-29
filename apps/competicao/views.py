from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, ListView, UpdateView, DetailView

from .forms import (
    CompeticaoForm, AssociarEquipeForm, JogoResultadoForm,
    GolForm, CartaoForm, InscricaoAtletaForm,
    FaseForm, GrupoForm, ConfrontoPenaltisForm,
)
from ..competicao.models import (
    Competicao, Rodada, Jogo, Classificacao, Gol, Cartao, InscricaoAtleta,
    Fase, Grupo, ClassificacaoGrupo, ConfrontoMatamate, Suspensao,
)
from ..equipe.models import Equipe, Atleta
from .gerador_de_jogos import (
    gerar_jogos_round_robin, gerar_jogos_grupos,
    gerar_confrontos_mata_mata, avancar_classificados,
)
from .utils import aplicar_criterios


# ---------------------------------------------------------------------------
# Competição
# ---------------------------------------------------------------------------

class CompeticaoCreate(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    form_class = CompeticaoForm
    model = Competicao
    success_message = 'Competição criada com sucesso!'
    template_name = 'competicao/criarcompeticao.html'
    success_url = reverse_lazy('competicao:competicao_lista')


class CompeticoesLista(LoginRequiredMixin, ListView):
    template_name = 'competicao/competicoes.html'
    context_object_name = 'competicoes'

    def get_queryset(self):
        return Competicao.objects.select_related('formato', 'criterio_classificacao').all()


@login_required
def remover_equipe_view(request, pk, equipe_id):
    competicao = get_object_or_404(Competicao, pk=pk)
    equipe = get_object_or_404(Equipe, pk=equipe_id)

    if competicao.equipes.filter(id=equipe.id).exists():
        competicao.equipes.remove(equipe)
        messages.success(request, f"{equipe.nome_equipe} foi removida da competição.")
    else:
        messages.warning(request, "Esta equipe não está na competição.")

    return redirect(reverse("competicao:buscar_equipes_view", kwargs={"pk": pk}))


@login_required
def buscar_equipes(request):
    search = request.GET.get('search', '')
    equipes = Equipe.objects.filter(nome_equipe__icontains=search).values('id', 'nome_equipe')
    return JsonResponse({'equipes': list(equipes)})


@login_required
def associar_equipe_view(request, pk):
    competicao = get_object_or_404(Competicao, pk=pk)

    if request.method == "POST":
        form = AssociarEquipeForm(request.POST)
        if form.is_valid():
            equipe_id = form.cleaned_data["equipe_id"]
            equipe = get_object_or_404(Equipe, pk=equipe_id)

            limite = competicao.formato.qtd_times if competicao.formato else None
            if limite and competicao.equipes.count() >= limite:
                messages.warning(request, f"Limite de {limite} equipes atingido.")
            elif competicao.equipes.filter(id=equipe.id).exists():
                messages.warning(request, f"{equipe} já está na competição.")
            else:
                competicao.equipes.add(equipe)
                messages.success(request, f"{equipe} adicionada com sucesso!")

            return redirect(reverse("competicao:buscar_equipes_view", kwargs={"pk": pk}))
    else:
        form = AssociarEquipeForm()

    return render(request, "competicao/buscar_equipe.html", {"form": form, "competicao": competicao})


@login_required
def criar_jogos_view(request, competicao_id):
    resultado = gerar_jogos_round_robin(competicao_id)

    if "erro" in resultado:
        messages.warning(request, resultado["erro"])
    else:
        messages.success(request, resultado["sucesso"])

    return redirect("competicao:competicao_lista")


# ---------------------------------------------------------------------------
# Classificação e rodadas
# ---------------------------------------------------------------------------

class ClassificacaoView(LoginRequiredMixin, DetailView):
    model = Competicao
    template_name = 'competicao/classificacao.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        comp = self.object
        classificacao_raw = (
            Classificacao.objects
            .filter(competicao=comp)
            .select_related('equipe')
        )
        ctx['classificacao'] = aplicar_criterios(comp, classificacao_raw)
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
            .prefetch_related('jogo_set__equipe_casa', 'jogo_set__equipe_fora')
            .order_by('numero')
        )
        # Group standings — sorted by configured criteria per group
        fases_grupos_data = []
        for fase in comp.fases.filter(tipo=Fase.GRUPOS):
            grupos_data = []
            for grupo in fase.grupos.all():
                cl = aplicar_criterios(
                    comp,
                    grupo.classificacao.select_related('equipe').all(),
                    grupo=grupo,
                )
                grupos_data.append({'grupo': grupo, 'classificacao': cl})
            fases_grupos_data.append({'fase': fase, 'grupos': grupos_data})
        ctx['fases_grupos_data'] = fases_grupos_data
        ctx['fases_mata_mata'] = comp.fases.filter(tipo=Fase.MATA_MATA)
        return ctx


class RodadasView(LoginRequiredMixin, DetailView):
    model = Competicao
    template_name = 'competicao/rodadas.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['rodadas'] = (
            Rodada.objects
            .filter(competicao=self.object)
            .select_related('fase', 'grupo')
            .prefetch_related(
                'jogo_set__equipe_casa',
                'jogo_set__equipe_fora',
                'jogo_set__gols__atleta',
                'jogo_set__gols__equipe',
            )
            .order_by('fase__ordem', 'grupo__nome', 'numero')
        )
        return ctx


class JogoUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Jogo
    form_class = JogoResultadoForm
    template_name = 'competicao/edit_jogo.html'
    success_message = 'Resultado salvo com sucesso!'

    def get_success_url(self):
        return reverse('competicao:jogo_detalhe', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['jogo'] = self.object
        return ctx


# ---------------------------------------------------------------------------
# Detalhe do jogo — gols e cartões inline
# ---------------------------------------------------------------------------

class JogoDetalheView(LoginRequiredMixin, DetailView):
    model = Jogo
    template_name = 'competicao/jogo_detalhe.html'
    context_object_name = 'jogo'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        jogo = self.object
        ctx['gols_casa'] = jogo.gols.filter(equipe=jogo.equipe_casa).select_related('atleta')
        ctx['gols_fora'] = jogo.gols.filter(equipe=jogo.equipe_fora).select_related('atleta')
        ctx['cartoes'] = jogo.cartoes.select_related('jogador__equipe').order_by('minuto')
        ctx['form_gol'] = GolForm(jogo=jogo)
        ctx['form_cartao'] = CartaoForm(jogo=jogo)
        ctx['atletas_casa'] = list(
            _atletas_por_equipe(jogo, jogo.equipe_casa)
            .values('id', 'nome')
        )
        ctx['atletas_fora'] = list(
            _atletas_por_equipe(jogo, jogo.equipe_fora)
            .values('id', 'nome')
        )
        # Suspended players warnings
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
        return ctx


def _atletas_por_equipe(jogo, equipe):
    from .forms import _atletas_do_jogo
    return _atletas_do_jogo(jogo).filter(equipe=equipe)


@login_required
def gol_criar_view(request, jogo_pk):
    jogo = get_object_or_404(Jogo, pk=jogo_pk)
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


@login_required
def gol_excluir_view(request, pk):
    gol = get_object_or_404(Gol, pk=pk)
    jogo_pk = gol.jogo_id
    if request.method == 'POST':
        gol.delete()
        messages.success(request, 'Gol removido.')
    return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo_pk}))


@login_required
def cartao_criar_view(request, jogo_pk):
    jogo = get_object_or_404(Jogo, pk=jogo_pk)
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


@login_required
def cartao_excluir_view(request, pk):
    cartao = get_object_or_404(Cartao, pk=pk)
    jogo_pk = cartao.jogo_id
    if request.method == 'POST':
        cartao.delete()
        messages.success(request, 'Cartão removido.')
    return redirect(reverse('competicao:jogo_detalhe', kwargs={'pk': jogo_pk}))


# ---------------------------------------------------------------------------
# Inscrição de atletas na competição
# ---------------------------------------------------------------------------

class InscricaoView(LoginRequiredMixin, DetailView):
    model = Competicao
    template_name = 'competicao/inscricao.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        competicao = self.object

        # Card counts and suspension status for all athletes in this competition
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
            })
        ctx['equipes_data'] = equipes_data
        ctx['amarelos_map'] = amarelos_map
        ctx['vermelhos_map'] = vermelhos_map
        ctx['suspensos_ids'] = suspensos_ids
        return ctx


@login_required
def inscricao_criar_view(request, competicao_pk, equipe_pk):
    competicao = get_object_or_404(Competicao, pk=competicao_pk)
    equipe = get_object_or_404(Equipe, pk=equipe_pk)

    if request.method == 'POST':
        form = InscricaoAtletaForm(request.POST, competicao=competicao, equipe=equipe)
        if form.is_valid():
            inscricao = form.save(commit=False)
            inscricao.competicao = competicao
            inscricao.save()
            messages.success(request, f'{inscricao.atleta.nome} inscrito com sucesso.')
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.warning(request, f'{err}')

    return redirect(reverse('competicao:inscricao', kwargs={'pk': competicao_pk}))


@login_required
def inscricao_excluir_view(request, pk):
    inscricao = get_object_or_404(InscricaoAtleta, pk=pk)
    competicao_pk = inscricao.competicao_id
    if request.method == 'POST':
        inscricao.delete()
        messages.success(request, f'{inscricao.atleta.nome} removido da inscrição.')
    return redirect(reverse('competicao:inscricao', kwargs={'pk': competicao_pk}))


# ---------------------------------------------------------------------------
# Suspensões
# ---------------------------------------------------------------------------

@login_required
def suspensao_cumprir_view(request, pk):
    suspensao = get_object_or_404(Suspensao, pk=pk)
    competicao_pk = suspensao.competicao_id
    if request.method == 'POST':
        Suspensao.objects.filter(pk=pk).update(cumprida=True)
        messages.success(request, f'Suspensão de {suspensao.atleta.nome} marcada como cumprida.')
    return redirect(reverse('competicao:inscricao', kwargs={'pk': competicao_pk}))


# ---------------------------------------------------------------------------
# Fases
# ---------------------------------------------------------------------------

class FasesView(LoginRequiredMixin, DetailView):
    model = Competicao
    template_name = 'competicao/fases.html'
    context_object_name = 'competicao'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['fases'] = self.object.fases.all()
        ctx['form'] = FaseForm()
        return ctx


@login_required
def fase_criar_view(request, competicao_pk):
    competicao = get_object_or_404(Competicao, pk=competicao_pk)
    if request.method == 'POST':
        form = FaseForm(request.POST)
        if form.is_valid():
            fase = form.save(commit=False)
            fase.competicao = competicao
            fase.save()
            messages.success(request, f"Fase '{fase.nome}' criada.")
        else:
            for errs in form.errors.values():
                for err in errs:
                    messages.warning(request, err)
    return redirect(reverse('competicao:fases', kwargs={'pk': competicao_pk}))


@login_required
def fase_excluir_view(request, pk):
    fase = get_object_or_404(Fase, pk=pk)
    competicao_pk = fase.competicao_id
    if request.method == 'POST':
        nome = fase.nome
        fase.delete()
        messages.success(request, f"Fase '{nome}' excluída.")
    return redirect(reverse('competicao:fases', kwargs={'pk': competicao_pk}))


# ---------------------------------------------------------------------------
# Grupos
# ---------------------------------------------------------------------------

class GruposFaseView(LoginRequiredMixin, DetailView):
    model = Fase
    template_name = 'competicao/grupos_fase.html'
    context_object_name = 'fase'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fase = self.object
        comp = fase.competicao

        grupos_data = []
        for grupo in fase.grupos.prefetch_related('equipes').all():
            cl = aplicar_criterios(
                comp,
                grupo.classificacao.select_related('equipe').all(),
                grupo=grupo,
            )
            grupos_data.append({'grupo': grupo, 'classificacao': cl})
        ctx['grupos_data'] = grupos_data

        ctx['form_grupo'] = GrupoForm()
        equipes_em_grupos_ids = fase.grupos.values_list('equipes__id', flat=True)
        ctx['equipes_disponiveis'] = (
            comp.equipes
            .exclude(pk__in=equipes_em_grupos_ids)
            .order_by('nome_equipe')
        )
        ctx['tem_rodadas'] = Rodada.objects.filter(fase=fase).exists()
        ctx['fases_mata_mata'] = Fase.objects.filter(competicao=comp, tipo=Fase.MATA_MATA)
        return ctx


@login_required
def grupo_criar_view(request, fase_pk):
    fase = get_object_or_404(Fase, pk=fase_pk)
    if request.method == 'POST':
        form = GrupoForm(request.POST)
        if form.is_valid():
            grupo = form.save(commit=False)
            grupo.fase = fase
            try:
                grupo.save()
                messages.success(request, f"Grupo '{grupo.nome}' criado.")
            except Exception:
                messages.warning(request, f"Grupo '{grupo.nome}' já existe nesta fase.")
        else:
            for errs in form.errors.values():
                for err in errs:
                    messages.warning(request, err)
    return redirect(reverse('competicao:grupos_fase', kwargs={'pk': fase_pk}))


@login_required
def grupo_excluir_view(request, pk):
    grupo = get_object_or_404(Grupo, pk=pk)
    fase_pk = grupo.fase_id
    if request.method == 'POST':
        grupo.delete()
        messages.success(request, 'Grupo excluído.')
    return redirect(reverse('competicao:grupos_fase', kwargs={'pk': fase_pk}))


@login_required
def grupo_atribuir_equipe_view(request, pk):
    grupo = get_object_or_404(Grupo, pk=pk)
    if request.method == 'POST':
        equipe_id = request.POST.get('equipe_id')
        equipe = get_object_or_404(Equipe, pk=equipe_id)
        grupo.equipes.add(equipe)
        messages.success(request, f'{equipe.nome_equipe} adicionada ao Grupo {grupo.nome}.')
    return redirect(reverse('competicao:grupos_fase', kwargs={'pk': grupo.fase_id}))


@login_required
def grupo_remover_equipe_view(request, pk, equipe_pk):
    grupo = get_object_or_404(Grupo, pk=pk)
    equipe = get_object_or_404(Equipe, pk=equipe_pk)
    if request.method == 'POST':
        grupo.equipes.remove(equipe)
        messages.success(request, f'{equipe.nome_equipe} removida do Grupo {grupo.nome}.')
    return redirect(reverse('competicao:grupos_fase', kwargs={'pk': grupo.fase_id}))


@login_required
def gerar_jogos_grupos_view(request, pk):
    fase = get_object_or_404(Fase, pk=pk, tipo=Fase.GRUPOS)
    if request.method == 'POST':
        resultado = gerar_jogos_grupos(fase)
        if 'erro' in resultado:
            messages.warning(request, resultado['erro'])
        else:
            messages.success(request, resultado['sucesso'])
    return redirect(reverse('competicao:grupos_fase', kwargs={'pk': pk}))


# ---------------------------------------------------------------------------
# Chaveamento (Mata-Mata)
# ---------------------------------------------------------------------------

class ChaveamentoView(LoginRequiredMixin, DetailView):
    model = Fase
    template_name = 'competicao/chaveamento.html'
    context_object_name = 'fase'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fase = self.object
        confrontos = list(
            fase.confrontos.select_related(
                'equipe_mandante', 'equipe_visitante', 'vencedor',
                'jogo_ida__equipe_casa', 'jogo_ida__equipe_fora',
                'jogo_volta__equipe_casa', 'jogo_volta__equipe_fora',
            ).order_by('ordem')
        )
        ctx['confrontos'] = confrontos
        ctx['tem_confrontos'] = bool(confrontos)
        ctx['penaltis_forms'] = {
            c.pk: ConfrontoPenaltisForm(instance=c)
            for c in confrontos
            if c.totalmente_jogado and c.vencedor is None
        }
        ctx['fases_grupos'] = Fase.objects.filter(competicao=fase.competicao, tipo=Fase.GRUPOS)
        return ctx


@login_required
def confronto_penaltis_view(request, pk):
    confronto = get_object_or_404(ConfrontoMatamate, pk=pk)
    if request.method == 'POST':
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
    return redirect(reverse('competicao:chaveamento', kwargs={'pk': confronto.fase_id}))


@login_required
def avancar_classificados_view(request, fase_grupos_pk, fase_mata_mata_pk):
    fase_grupos = get_object_or_404(Fase, pk=fase_grupos_pk, tipo=Fase.GRUPOS)
    fase_mata_mata = get_object_or_404(Fase, pk=fase_mata_mata_pk, tipo=Fase.MATA_MATA)
    if request.method == 'POST':
        resultado = avancar_classificados(fase_grupos, fase_mata_mata)
        if 'erro' in resultado:
            messages.warning(request, resultado['erro'])
        else:
            messages.success(request, resultado['sucesso'])
    return redirect(reverse('competicao:chaveamento', kwargs={'pk': fase_mata_mata_pk}))
