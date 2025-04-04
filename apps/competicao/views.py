from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from .forms import CompeticaoForm, AssociarEquipeForm
from ..competicao.models import Competicao
from ..equipe.models import Equipe
from .gerador_de_jogos import gerar_jogos_round_robin


class CompeticaoCreate(SuccessMessageMixin, CreateView):
    form_class = CompeticaoForm
    model = Competicao
    success_message = 'Competição criada com sucesso!'
    template_name = 'competicao/criarcompeticao.html'
    success_url = reverse_lazy('competicao:competicao_lista')


class CompeticoesLista(ListView):
    template_name = 'competicao/competicoes.html'
    context_object_name = 'competicoes'

    def get_queryset(self):
        return Competicao.objects.all()


def remover_equipe_view(request, pk, equipe_id):
    competicao = get_object_or_404(Competicao, pk=pk)
    equipe = get_object_or_404(Equipe, pk=equipe_id)

    if competicao.equipes.filter(id=equipe.id).exists():
        competicao.equipes.remove(equipe)
        messages.success(request, message=f"{equipe.nome_equipe} foi removida(o) da competição!")
    else:
        messages.warning(request, message="Esta equipe não está na competição.")

    return redirect(reverse("competicao:buscar_equipes_view", kwargs={"pk": pk}))


def buscar_equipes(request):
    search = request.GET.get('search', '')  # Pega o termo de pesquisa
    equipes = Equipe.objects.filter(nome_equipe__icontains=search)  # Filtra as equipes pelo nome
    equipes_data = [{'id': equipe.id, 'nome_equipe': equipe.nome_equipe} for equipe in equipes]  # Prepara os dados
    return JsonResponse({'equipes': equipes_data})  # Retorna os dados no formato JSON


def associar_equipe_view(request, pk):
    """View que associa uma equipe a uma competição"""
    competicao = get_object_or_404(Competicao, pk=pk)

    if request.method == "POST":
        form = AssociarEquipeForm(request.POST)

        if form.is_valid():
            equipe_id = form.cleaned_data["equipe_id"]
            equipe = get_object_or_404(Equipe, pk=equipe_id)

            # Verifica se a equipe já está na competição
            if not competicao.equipes.count() >= competicao.formato.qtd_times:
                if competicao.equipes.filter(id=equipe.id).exists():
                    messages.warning(request, message=f"{equipe} já está na competição.")
                else:
                    competicao.equipes.add(equipe)
                    competicao.save()
                    messages.success(request, message=f"{equipe} adicionad(o)a com sucesso!")
            else:
                messages.warning(request, message=f"A competição atingiu o número máximo de equipes({competicao.formato.qtd_times}).")

            return redirect(reverse(viewname="competicao:buscar_equipes_view", kwargs={"pk": pk}))

    else:
        form = AssociarEquipeForm()

    return render(request, template_name="competicao/buscar_equipe.html", context={"form": form, "competicao": competicao})


def criar_jogos_view(request, competicao_id):
    resultado = gerar_jogos_round_robin(competicao_id)

    if "erro" in resultado:
        messages.warning(request, resultado["erro"])
    else:
        messages.success(request, resultado["sucesso"])

    return redirect("competicao:competicao_lista")