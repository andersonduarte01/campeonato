from django.shortcuts import get_object_or_404
from .models import Competicao, Jogo, Equipe, Rodada


def gerar_jogos_round_robin(competicao_id):
    competicao = get_object_or_404(Competicao, pk=competicao_id)
    equipes = list(competicao.equipes.all())

    if len(equipes) < 2:
        return {"erro": "É necessário pelo menos duas equipes para gerar jogos."}

    if len(equipes) % 2:
        equipes.append(None)  # Adiciona um "Bye" se o número for ímpar

    num_rodadas = len(equipes) - 1

    equipes_copia = equipes[:]  # Copia para não modificar a original

    for rodada_numero in range(1, num_rodadas + 1):
        # Cria uma nova rodada
        rodada = Rodada.objects.create(
            competicao=competicao,
            numero=rodada_numero
        )

        for i in range(len(equipes) // 2):
            equipe1 = equipes_copia[i]
            equipe2 = equipes_copia[-(i + 1)]

            if equipe1 and equipe2:  # Ignorar rodadas com "Bye"
                jogo = Jogo.objects.create(
                    rodada=rodada,  # Associa o jogo à rodada
                    equipe_casa=equipe1,
                    equipe_fora=equipe2,
                    data_hora=None,  # Você pode definir uma data/hora mais tarde
                )

        equipes_copia = [equipes_copia[0]] + [equipes_copia[-1]] + equipes_copia[1:-1]


    rods = Rodada.objects.filter(competicao=competicao).count()

    return {"sucesso": f"{rods} rodadas geradas para a competição {competicao.nome}."}

