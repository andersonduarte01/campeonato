from django.db.models import Sum


def aplicar_criterios(competicao, classificacoes, grupo=None):
    """Sort a standings list respecting the competition's CriterioClassificacao.

    Works for both Classificacao (general) and ClassificacaoGrupo objects since
    both expose the same numeric fields (pontos, vitorias, saldo_gols, gols_pro).
    Pass grupo= to compute away-goals within a specific group.
    """
    criterio = getattr(competicao, 'criterio_classificacao', None)
    items = list(classificacoes)
    if not items:
        return items

    # Pre-compute away goals in a single query when criterion is active
    gols_fora_map = {}
    if criterio and criterio.gol_fora:
        from .models import Jogo
        equipe_ids = [c.equipe_id for c in items]
        qs = Jogo.objects.filter(
            finalizado=True, anulado=False, equipe_fora_id__in=equipe_ids,
        )
        if grupo:
            qs = qs.filter(rodada__grupo=grupo)
        else:
            qs = qs.filter(rodada__competicao=competicao)
        for row in qs.values('equipe_fora').annotate(t=Sum('gols_fora')):
            gols_fora_map[row['equipe_fora']] = row['t'] or 0

    def sort_key(cl):
        key = [-cl.pontos]
        if criterio:
            if criterio.vitorias:
                key.append(-cl.vitorias)
            if criterio.saldo_gols:
                key.append(-cl.saldo_gols)
            if criterio.gol_fora:
                key.append(-(gols_fora_map.get(cl.equipe_id, 0)))
        else:
            # Default tie-break order
            key.extend([-cl.vitorias, -cl.saldo_gols])
        key.append(-cl.gols_pro)
        return tuple(key)

    return sorted(items, key=sort_key)
