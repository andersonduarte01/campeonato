from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView

from apps.core.permissions import PerfilRequiredMixin, PODE_ORGANIZAR
from .models import FormatoCompeticao, CriterioClassificacao
from .forms import FormatoCompeticaoForm, CriterioClassificacaoForm
from ..competicao.models import Competicao


class FormatoCompeticaoAdd(PerfilRequiredMixin, CreateView):
    perfis_permitidos = PODE_ORGANIZAR
    form_class = FormatoCompeticaoForm
    model = FormatoCompeticao
    template_name = 'criterios/formatoadd.html'
    success_url = reverse_lazy('competicao:competicao_lista')

    def form_valid(self, form):
        competicao = get_object_or_404(Competicao, pk=self.kwargs['pk'])

        if competicao.formato:
            messages.warning(self.request, message=f"O formato para a competição '{competicao}' já existe.")
            self.object = competicao.formato
            return self.form_invalid(form)

        formato_competicao = form.save()
        competicao.formato = formato_competicao
        competicao.save()

        self.object = formato_competicao
        messages.success(self.request, message=f"Formato para a competição '{competicao}' criado com sucesso!")

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        competicao = get_object_or_404(Competicao, pk=self.kwargs['pk'])
        contexto['competicao'] = competicao
        return contexto


class CriterioClassificacaoAdd(PerfilRequiredMixin, CreateView):
    perfis_permitidos = PODE_ORGANIZAR
    form_class = CriterioClassificacaoForm
    model = CriterioClassificacao
    template_name = 'criterios/criteriosadd.html'
    success_url = reverse_lazy('competicao:competicao_lista')

    def form_valid(self, form):
        competicao = get_object_or_404(Competicao, pk=self.kwargs['pk'])

        if competicao.criterio_classificacao:
            messages.warning(self.request, message=f"Os critérios para a competição '{competicao}' já existem.")
            self.object = competicao.criterio_classificacao
            return self.form_invalid(form)

        criterios_competicao = form.save()
        competicao.criterio_classificacao = criterios_competicao
        competicao.save()

        self.object = criterios_competicao
        messages.success(self.request, message=f"Critérios para a competição '{competicao}' criados com sucesso!")

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        competicao = get_object_or_404(Competicao, pk=self.kwargs['pk'])
        contexto['competicao'] = competicao
        return contexto
