from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Competicao, Jogo, Rodada


@transaction.atomic
def gerar_jogos_round_robin(competicao_id):
    competicao = get_object_or_404(Competicao, pk=competicao_id)

    if Rodada.objects.filter(competicao=competicao).exists():
        return {"erro": "Esta competição já possui rodadas geradas."}

    equipes = list(competicao.equipes.all())

    if len(equipes) < 2:
        return {"erro": "É necessário pelo menos duas equipes para gerar jogos."}

    turno_unico = getattr(competicao.formato, 'turno_unico', True)
    ida_e_volta = getattr(competicao.formato, 'ida_e_volta', False)

    turnos = 1 if turno_unico and not ida_e_volta else 2

    if len(equipes) % 2:
        equipes.append(None)

    num_rodadas = len(equipes) - 1
    rodadas_criadas = 0
    offset = 0

    for turno in range(turnos):
        equipes_copia = equipes[:]
        for rodada_numero in range(1, num_rodadas + 1):
            rodada = Rodada.objects.create(
                competicao=competicao,
                numero=offset + rodada_numero,
            )
            rodadas_criadas += 1

            for i in range(len(equipes) // 2):
                equipe1 = equipes_copia[i]
                equipe2 = equipes_copia[-(i + 1)]

                if equipe1 and equipe2:
                    if turno == 1:
                        equipe1, equipe2 = equipe2, equipe1
                    Jogo.objects.create(
                        rodada=rodada,
                        equipe_casa=equipe1,
                        equipe_fora=equipe2,
                    )

            equipes_copia = [equipes_copia[0]] + [equipes_copia[-1]] + equipes_copia[1:-1]

        offset += num_rodadas

    return {"sucesso": f"{rodadas_criadas} rodadas geradas para {competicao.nome}."}


@transaction.atomic
def gerar_jogos_grupos(fase):
    """Round-robin within each group of a group-stage phase."""
    if not fase.grupos.exists():
        return {"erro": "Nenhum grupo definido nesta fase."}
    if Rodada.objects.filter(fase=fase).exists():
        return {"erro": "Esta fase já possui rodadas geradas."}

    rodadas_criadas = 0
    turnos = 2 if fase.ida_e_volta else 1

    for grupo in fase.grupos.prefetch_related('equipes').all():
        equipes = list(grupo.equipes.all())
        if len(equipes) < 2:
            continue
        if len(equipes) % 2:
            equipes.append(None)

        n = len(equipes) - 1
        offset = 0
        for turno in range(turnos):
            circulo = equipes[:]
            for r in range(1, n + 1):
                rodada = Rodada.objects.create(
                    competicao=fase.competicao, fase=fase, grupo=grupo, numero=offset + r,
                )
                rodadas_criadas += 1
                for i in range(len(equipes) // 2):
                    eq1, eq2 = circulo[i], circulo[-(i + 1)]
                    if eq1 and eq2:
                        if turno == 1:
                            eq1, eq2 = eq2, eq1
                        Jogo.objects.create(rodada=rodada, equipe_casa=eq1, equipe_fora=eq2)
                circulo = [circulo[0]] + [circulo[-1]] + circulo[1:-1]
            offset += n

    return {"sucesso": f"{rodadas_criadas} rodadas geradas para '{fase.nome}'."}


@transaction.atomic
def gerar_confrontos_mata_mata(fase, equipes):
    """Create knockout matchups from a seeded list of teams.
    Pairing: seed 1 vs seed N, seed 2 vs seed N-1, etc.
    """
    from .models import ConfrontoMatamate

    if ConfrontoMatamate.objects.filter(fase=fase).exists():
        return {"erro": "Esta fase já possui confrontos gerados."}

    n = len(equipes)
    if n < 2:
        return {"erro": "São necessárias pelo menos 2 equipes."}

    pares = [(equipes[i], equipes[n - 1 - i]) for i in range(n // 2)]

    rodada_ida = Rodada.objects.create(competicao=fase.competicao, fase=fase, numero=1)
    rodada_volta = None
    if fase.ida_e_volta:
        rodada_volta = Rodada.objects.create(competicao=fase.competicao, fase=fase, numero=2)

    for ordem, (mandante, visitante) in enumerate(pares, start=1):
        jogo_ida = Jogo.objects.create(rodada=rodada_ida, equipe_casa=mandante, equipe_fora=visitante)
        jogo_volta = None
        if fase.ida_e_volta:
            jogo_volta = Jogo.objects.create(
                rodada=rodada_volta, equipe_casa=visitante, equipe_fora=mandante,
            )
        ConfrontoMatamate.objects.create(
            fase=fase,
            equipe_mandante=mandante,
            equipe_visitante=visitante,
            jogo_ida=jogo_ida,
            jogo_volta=jogo_volta,
            ordem=ordem,
        )

    return {"sucesso": f"{len(pares)} confrontos gerados para '{fase.nome}'."}


@transaction.atomic
def avancar_classificados(fase_grupos, fase_mata_mata):
    """Advance the top N teams from each group into the knockout bracket.
    Seeding order: all 1st-place finishers then all 2nd-place, etc.
    """
    from .models import ClassificacaoGrupo

    n = fase_grupos.qtd_classificados_por_grupo
    classificados = []
    for pos in range(n):
        for grupo in fase_grupos.grupos.order_by('nome'):
            qs = ClassificacaoGrupo.objects.filter(grupo=grupo).order_by(
                '-pontos', '-saldo_gols', '-vitorias', '-gols_pro'
            )
            if pos < qs.count():
                classificados.append(qs[pos].equipe)

    return gerar_confrontos_mata_mata(fase_mata_mata, classificados)
