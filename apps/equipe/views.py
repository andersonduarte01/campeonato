from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView

from .forms import EquipeForm, AtletaForm
from .models import Equipe, Atleta


class EquipeListView(LoginRequiredMixin, ListView):
    model = Equipe
    template_name = 'equipe/lista.html'
    context_object_name = 'equipes'
    ordering = ['nome_equipe']


class EquipeCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Equipe
    form_class = EquipeForm
    template_name = 'equipe/form.html'
    success_url = reverse_lazy('equipe:lista')
    success_message = 'Equipe criada com sucesso!'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nova Equipe'
        return ctx


class EquipeUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Equipe
    form_class = EquipeForm
    template_name = 'equipe/form.html'
    success_url = reverse_lazy('equipe:lista')
    success_message = 'Equipe atualizada com sucesso!'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object.nome_equipe}'
        return ctx


class EquipeDeleteView(LoginRequiredMixin, DeleteView):
    model = Equipe
    template_name = 'equipe/confirmar_exclusao.html'
    success_url = reverse_lazy('equipe:lista')
    context_object_name = 'equipe'


class EquipeDetailView(LoginRequiredMixin, DetailView):
    model = Equipe
    template_name = 'equipe/detalhe.html'
    context_object_name = 'equipe'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['atletas'] = self.object.equipe_jogador.order_by('posicao', 'nome')
        return ctx


class AtletaCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Atleta
    form_class = AtletaForm
    template_name = 'equipe/atleta_form.html'
    success_message = 'Atleta adicionado com sucesso!'

    def get_initial(self):
        return {'equipe': self.kwargs.get('equipe_pk')}

    def get_success_url(self):
        return reverse_lazy('equipe:detalhe', kwargs={'pk': self.object.equipe.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['equipe'] = get_object_or_404(Equipe, pk=self.kwargs['equipe_pk'])
        ctx['titulo'] = 'Adicionar Atleta'
        return ctx


class AtletaUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Atleta
    form_class = AtletaForm
    template_name = 'equipe/atleta_form.html'
    success_message = 'Atleta atualizado com sucesso!'

    def get_success_url(self):
        return reverse_lazy('equipe:detalhe', kwargs={'pk': self.object.equipe.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['equipe'] = self.object.equipe
        ctx['titulo'] = f'Editar: {self.object.nome}'
        return ctx


class AtletaDeleteView(LoginRequiredMixin, DeleteView):
    model = Atleta
    template_name = 'equipe/confirmar_exclusao_atleta.html'
    context_object_name = 'atleta'

    def get_success_url(self):
        return reverse_lazy('equipe:detalhe', kwargs={'pk': self.object.equipe.pk})
