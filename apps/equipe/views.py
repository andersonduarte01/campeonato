import datetime

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from apps.core.permissao import (
    PermissaoFederacaoMixin,
    PODE_SECRETARIAR,
    PODE_DIRIGIR,
    TODOS_INTERNOS,
    requer_papel,
)
from apps.registro.models import HistoricoClube, RegistroFederativo
from .forms import AtletaForm, EquipeForm, EquipeDirigenteForm
from .models import Atleta, Equipe


class EquipeListView(PermissaoFederacaoMixin, ListView):
    model                = Equipe
    template_name        = 'equipe/lista.html'
    context_object_name  = 'equipes'

    def get_queryset(self):
        return (
            Equipe.objects
            .filter(federacao=self.request.federacao)
            .exclude(situacao=Equipe.SITUACAO_DESFILIADO)
            .order_by('nome_equipe')
        )


class EquipeCreateView(PermissaoFederacaoMixin, SuccessMessageMixin, CreateView):
    papeis_permitidos = PODE_SECRETARIAR
    model             = Equipe
    form_class        = EquipeForm
    template_name     = 'equipe/form.html'
    success_url       = reverse_lazy('equipe:lista')
    success_message   = 'Equipe criada com sucesso!'

    def form_valid(self, form):
        form.instance.federacao = self.request.federacao
        vinculo = getattr(self.request, 'vinculo', None)
        if vinculo and vinculo.papel in PODE_SECRETARIAR:
            form.instance.situacao = Equipe.SITUACAO_FILIADO
        else:
            form.instance.situacao = Equipe.SITUACAO_REGULARIZACAO
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nova Equipe'
        return ctx


class EquipeUpdateView(PermissaoFederacaoMixin, SuccessMessageMixin, UpdateView):
    papeis_permitidos = PODE_SECRETARIAR
    model             = Equipe
    form_class        = EquipeForm
    template_name     = 'equipe/form.html'
    success_url       = reverse_lazy('equipe:lista')
    success_message   = 'Equipe atualizada com sucesso!'

    def get_queryset(self):
        return Equipe.objects.filter(federacao=self.request.federacao)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object.nome_equipe}'
        return ctx


class EquipeDirigenteUpdateView(PermissaoFederacaoMixin, SuccessMessageMixin, UpdateView):
    papeis_permitidos = PODE_DIRIGIR
    model             = Equipe
    form_class        = EquipeDirigenteForm
    template_name     = 'equipe/dirigente_form.html'
    success_message   = 'Dados do clube atualizados com sucesso!'

    def get_queryset(self):
        equipe = getattr(self.request.vinculo, 'equipe', None)
        if not equipe:
            return Equipe.objects.none()
        return Equipe.objects.filter(pk=equipe.pk, federacao=self.request.federacao)

    def get_success_url(self):
        return reverse_lazy('equipe:detalhe', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object.nome_equipe}'
        return ctx


class EquipeDesativarView(PermissaoFederacaoMixin, View):
    papeis_permitidos = PODE_SECRETARIAR

    def post(self, request, pk):
        equipe = get_object_or_404(Equipe, pk=pk, federacao=request.federacao)
        equipe.situacao = Equipe.SITUACAO_DESFILIADO
        equipe.save(update_fields=['situacao'])
        messages.success(request, f'Equipe "{equipe.nome_equipe}" desativada com sucesso.')
        return redirect('equipe:lista')


class EquipeDetailView(PermissaoFederacaoMixin, DetailView):
    model               = Equipe
    template_name       = 'equipe/detalhe.html'
    context_object_name = 'equipe'

    def get_queryset(self):
        return Equipe.objects.filter(federacao=self.request.federacao)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['atletas'] = self.object.equipe_jogador.order_by('posicao', 'nome')
        vinculo = self.request.vinculo
        pode = False
        e_secretario = False
        if vinculo:
            if vinculo.papel in PODE_SECRETARIAR:
                pode = True
                e_secretario = True
            elif vinculo.papel in PODE_DIRIGIR and getattr(vinculo, 'equipe', None) == self.object:
                pode = True
        ctx['pode_editar_tecnico'] = pode
        ctx['e_secretario'] = e_secretario
        return ctx


@requer_papel(*TODOS_INTERNOS)
def equipe_tecnico_editar_view(request, pk):
    equipe  = get_object_or_404(Equipe, pk=pk, federacao=request.federacao)
    vinculo = request.vinculo
    pode    = False
    if vinculo:
        if vinculo.papel in PODE_SECRETARIAR:
            pode = True
        elif vinculo.papel in PODE_DIRIGIR and getattr(vinculo, 'equipe', None) == equipe:
            pode = True
    if not pode:
        messages.error(request, 'Sem permissão para editar o técnico.')
        return redirect('equipe:detalhe', pk=pk)
    if request.method == 'POST':
        equipe.tecnico = request.POST.get('tecnico', '').strip() or None
        equipe.save(update_fields=['tecnico'])
        messages.success(request, 'Técnico atualizado.')
    return redirect('equipe:detalhe', pk=pk)


class AtletaCreateView(PermissaoFederacaoMixin, SuccessMessageMixin, CreateView):
    papeis_permitidos = PODE_DIRIGIR
    model             = Atleta
    form_class        = AtletaForm
    template_name     = 'equipe/atleta_form.html'
    success_message   = 'Atleta adicionado com sucesso!'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        vinculo = getattr(self.request, 'vinculo', None)
        kwargs['papel'] = vinculo.papel if vinculo else None
        return kwargs

    def form_valid(self, form):
        form.instance.equipe_id = self.kwargs['equipe_pk']
        response = super().form_valid(form)
        vinculo = getattr(self.request, 'vinculo', None)
        if vinculo and vinculo.papel in PODE_SECRETARIAR:
            hoje = datetime.date.today()
            reg = RegistroFederativo.objects.create(
                federacao=self.request.federacao,
                atleta=self.object,
                data_filiacao=hoje,
            )
            HistoricoClube.objects.create(
                atleta=self.object,
                equipe=self.object.equipe,
                tipo=HistoricoClube.TIPO_TITULAR,
                data_entrada=hoje,
            )
            messages.info(self.request, f'Registro federativo {reg.numero_federativo} gerado automaticamente.')
        return response

    def get_success_url(self):
        return reverse_lazy('equipe:detalhe', kwargs={'pk': self.object.equipe.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['equipe'] = get_object_or_404(
            Equipe, pk=self.kwargs['equipe_pk'], federacao=self.request.federacao,
        )
        ctx['titulo'] = 'Adicionar Atleta'
        return ctx


class AtletaUpdateView(PermissaoFederacaoMixin, SuccessMessageMixin, UpdateView):
    papeis_permitidos = PODE_DIRIGIR
    model             = Atleta
    form_class        = AtletaForm
    template_name     = 'equipe/atleta_form.html'
    success_message   = 'Atleta atualizado com sucesso!'

    def get_queryset(self):
        return Atleta.objects.filter(equipe__federacao=self.request.federacao)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['federacao'] = self.request.federacao
        vinculo = getattr(self.request, 'vinculo', None)
        kwargs['papel'] = vinculo.papel if vinculo else None
        return kwargs

    def get_success_url(self):
        return reverse_lazy('equipe:detalhe', kwargs={'pk': self.object.equipe.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['equipe'] = self.object.equipe
        ctx['titulo'] = f'Editar: {self.object.nome}'
        return ctx


class AtletaDeleteView(PermissaoFederacaoMixin, DeleteView):
    papeis_permitidos   = PODE_DIRIGIR
    model               = Atleta
    template_name       = 'equipe/confirmar_exclusao_atleta.html'
    context_object_name = 'atleta'

    def get_queryset(self):
        return Atleta.objects.filter(equipe__federacao=self.request.federacao)

    def get_success_url(self):
        return reverse_lazy('equipe:detalhe', kwargs={'pk': self.object.equipe.pk})
