from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.permissao import PermissaoFederacaoMixin, PODE_SECRETARIAR
from apps.competicao.models import Competicao
from .forms import CriterioClassificacaoForm, FormatoCompeticaoForm
from .models import CriterioClassificacao, FormatoCompeticao


# ── Formato ──────────────────────────────────────────────────────────────────

class FormatoLista(PermissaoFederacaoMixin, ListView):
    papeis_permitidos = PODE_SECRETARIAR
    model = FormatoCompeticao
    template_name = 'criterios/formato_lista.html'
    context_object_name = 'formatos'

    def get_queryset(self):
        return FormatoCompeticao.objects.filter(federacao=self.request.federacao)


class FormatoAdd(PermissaoFederacaoMixin, SuccessMessageMixin, CreateView):
    papeis_permitidos = PODE_SECRETARIAR
    model = FormatoCompeticao
    form_class = FormatoCompeticaoForm
    template_name = 'criterios/formatoadd.html'
    success_message = 'Formato criado com sucesso!'

    def form_valid(self, form):
        form.instance.federacao = self.request.federacao
        response = super().form_valid(form)
        pk = self.kwargs.get('pk')
        if pk:
            competicao = get_object_or_404(Competicao, pk=pk, federacao=self.request.federacao)
            competicao.formato = self.object
            competicao.save(update_fields=['formato'])
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')
        if pk:
            ctx['competicao'] = get_object_or_404(Competicao, pk=pk, federacao=self.request.federacao)
        return ctx

    def get_success_url(self):
        pk = self.kwargs.get('pk')
        if pk:
            return reverse_lazy('competicao:competicao_lista')
        return reverse_lazy('criterios:formato_lista')


def _avisar_snapshot(request, obj, rotulo):
    em_uso = obj.competicoes.filter(
        status__in=(Competicao.INSCRICOES_ENCERRADAS, Competicao.ANDAMENTO),
    ).count()
    if em_uso:
        messages.info(
            request,
            f'Este {rotulo} está em uso por {em_uso} competição(ões) já lançada(s). '
            'As regras dessas competições foram congeladas no encerramento das '
            'inscrições e não serão afetadas por esta alteração.',
        )


class FormatoEdit(PermissaoFederacaoMixin, SuccessMessageMixin, UpdateView):
    papeis_permitidos = PODE_SECRETARIAR
    model = FormatoCompeticao
    form_class = FormatoCompeticaoForm
    template_name = 'criterios/formatoadd.html'
    success_message = 'Formato atualizado com sucesso!'
    success_url = reverse_lazy('criterios:formato_lista')

    def get_queryset(self):
        return FormatoCompeticao.objects.filter(federacao=self.request.federacao)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        _avisar_snapshot(request, self.object, 'formato')
        return response


# ── Critério ──────────────────────────────────────────────────────────────────

class CriterioLista(PermissaoFederacaoMixin, ListView):
    papeis_permitidos = PODE_SECRETARIAR
    model = CriterioClassificacao
    template_name = 'criterios/criterio_lista.html'
    context_object_name = 'criterios'

    def get_queryset(self):
        return CriterioClassificacao.objects.filter(federacao=self.request.federacao)


class CriterioAdd(PermissaoFederacaoMixin, SuccessMessageMixin, CreateView):
    papeis_permitidos = PODE_SECRETARIAR
    model = CriterioClassificacao
    form_class = CriterioClassificacaoForm
    template_name = 'criterios/criteriosadd.html'
    success_message = 'Critério criado com sucesso!'

    def form_valid(self, form):
        form.instance.federacao = self.request.federacao
        response = super().form_valid(form)
        pk = self.kwargs.get('pk')
        if pk:
            competicao = get_object_or_404(Competicao, pk=pk, federacao=self.request.federacao)
            competicao.criterio_classificacao = self.object
            competicao.save(update_fields=['criterio_classificacao'])
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')
        if pk:
            ctx['competicao'] = get_object_or_404(Competicao, pk=pk, federacao=self.request.federacao)
        return ctx

    def get_success_url(self):
        pk = self.kwargs.get('pk')
        if pk:
            return reverse_lazy('competicao:competicao_lista')
        return reverse_lazy('criterios:criterio_lista')


class CriterioEdit(PermissaoFederacaoMixin, SuccessMessageMixin, UpdateView):
    papeis_permitidos = PODE_SECRETARIAR
    model = CriterioClassificacao
    form_class = CriterioClassificacaoForm
    template_name = 'criterios/criteriosadd.html'
    success_message = 'Critério atualizado com sucesso!'
    success_url = reverse_lazy('criterios:criterio_lista')

    def get_queryset(self):
        return CriterioClassificacao.objects.filter(federacao=self.request.federacao)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        _avisar_snapshot(request, self.object, 'critério')
        return response


# ── Vincular existente a uma competição ──────────────────────────────────────

class VincularFormato(PermissaoFederacaoMixin, View):
    papeis_permitidos = PODE_SECRETARIAR
    template_name = 'criterios/vincular_formato.html'

    def _competicao(self, pk):
        return get_object_or_404(Competicao, pk=pk, federacao=self.request.federacao)

    def get(self, request, pk):
        competicao = self._competicao(pk)
        formatos = FormatoCompeticao.objects.filter(federacao=request.federacao).order_by('nome')
        return self._render(request, competicao, formatos)

    def post(self, request, pk):
        competicao = self._competicao(pk)
        formato_id = request.POST.get('formato_id')
        if formato_id:
            formato = get_object_or_404(FormatoCompeticao, pk=formato_id, federacao=request.federacao)
            competicao.formato = formato
            competicao.save(update_fields=['formato'])
            messages.success(request, f'Formato "{formato.nome}" vinculado com sucesso!')
        else:
            messages.error(request, 'Selecione um formato.')
            formatos = FormatoCompeticao.objects.filter(federacao=request.federacao).order_by('nome')
            return self._render(request, competicao, formatos)
        return redirect('competicao:competicao_lista')

    def _render(self, request, competicao, formatos):
        from django.shortcuts import render
        return render(request, self.template_name, {
            'competicao': competicao,
            'formatos': formatos,
        })


class VincularCriterio(PermissaoFederacaoMixin, View):
    papeis_permitidos = PODE_SECRETARIAR
    template_name = 'criterios/vincular_criterio.html'

    def _competicao(self, pk):
        return get_object_or_404(Competicao, pk=pk, federacao=self.request.federacao)

    def get(self, request, pk):
        competicao = self._competicao(pk)
        criterios = CriterioClassificacao.objects.filter(federacao=request.federacao).order_by('nome')
        return self._render(request, competicao, criterios)

    def post(self, request, pk):
        competicao = self._competicao(pk)
        criterio_id = request.POST.get('criterio_id')
        if criterio_id:
            criterio = get_object_or_404(CriterioClassificacao, pk=criterio_id, federacao=request.federacao)
            competicao.criterio_classificacao = criterio
            competicao.save(update_fields=['criterio_classificacao'])
            messages.success(request, f'Critério "{criterio.nome}" vinculado com sucesso!')
        else:
            messages.error(request, 'Selecione um critério.')
            criterios = CriterioClassificacao.objects.filter(federacao=request.federacao).order_by('nome')
            return self._render(request, competicao, criterios)
        return redirect('competicao:competicao_lista')

    def _render(self, request, competicao, criterios):
        from django.shortcuts import render
        return render(request, self.template_name, {
            'competicao': competicao,
            'criterios': criterios,
        })
