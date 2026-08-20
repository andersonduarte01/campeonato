from django.db.models import Count, F, Sum


class ClassificadorService:
    """Ordena tabelas de classificação respeitando o CriterioClassificacao
    efetivo da competição (snapshot quando existir)."""

    def __init__(self, competicao):
        self.competicao = competicao

    def ordenar(self, classificacoes, grupo=None):
        """Ordena Classificacao (geral) ou ClassificacaoGrupo, com
        confronto direto como primeiro desempate quando habilitado."""
        criterio = self.competicao.criterio_efetivo
        items = list(classificacoes)
        if not items:
            return items

        ctx = self._build_ctx(items, criterio, grupo)

        if not criterio:
            return sorted(items, key=lambda c: (-c.pontos, -c.vitorias, -c.saldo_gols, -c.gols_pro))

        by_points = sorted(items, key=lambda c: -c.pontos)
        result = []
        i = 0
        while i < len(by_points):
            j = i
            while j < len(by_points) and by_points[j].pontos == by_points[i].pontos:
                j += 1
            group = by_points[i:j]
            if len(group) > 1:
                group = self._resolver_empate(group, criterio, ctx, grupo)
            result.extend(group)
            i = j

        return result

    def classificados_dos_grupos(self, n):
        """Top-N de cada grupo, na ordem de seed: 1ºs colocados, depois 2ºs, etc."""
        from ..models import ClassificacaoGrupo

        tabelas = [
            self.ordenar(
                ClassificacaoGrupo.objects.filter(grupo=grupo).select_related('equipe'),
                grupo=grupo,
            )
            for grupo in self.competicao.grupos.order_by('nome')
        ]
        return [
            tabela[pos].equipe
            for pos in range(n)
            for tabela in tabelas
            if pos < len(tabela)
        ]

    def _build_ctx(self, items, criterio, grupo):
        from ..models import Cartao, Jogo

        ctx = {'gols_fora': {}, 'vermelhos': {}, 'amarelos': {}}
        if not criterio or not items:
            return ctx

        equipe_ids = [c.equipe_id for c in items]

        if criterio.gol_fora:
            qs = Jogo.objects.filter(finalizado=True, anulado=False, equipe_fora_id__in=equipe_ids)
            qs = qs.filter(rodada__grupo=grupo) if grupo else qs.filter(rodada__competicao=self.competicao)
            for row in qs.values('equipe_fora').annotate(t=Sum('gols_fora')):
                ctx['gols_fora'][row['equipe_fora']] = row['t'] or 0

        if criterio.menor_vermelho or criterio.menor_amarelo:
            base = Cartao.objects.filter(jogo__rodada__competicao=self.competicao)
            if grupo:
                base = base.filter(jogo__rodada__grupo=grupo)
            if criterio.menor_vermelho:
                for row in base.filter(tipo=Cartao.VERMELHO).values(
                    equipe_id=F('jogador__equipe')
                ).annotate(total=Count('id')):
                    ctx['vermelhos'][row['equipe_id']] = row['total']
            if criterio.menor_amarelo:
                for row in base.filter(tipo=Cartao.AMARELO).values(
                    equipe_id=F('jogador__equipe')
                ).annotate(total=Count('id')):
                    ctx['amarelos'][row['equipe_id']] = row['total']

        return ctx

    def _computar_h2h(self, items, grupo):
        from ..models import Jogo

        equipe_ids = {c.equipe_id for c in items}
        h2h = {eid: {'pts': 0, 'sg': 0, 'gp': 0} for eid in equipe_ids}

        qs = Jogo.objects.filter(
            finalizado=True, anulado=False,
            equipe_casa_id__in=equipe_ids,
            equipe_fora_id__in=equipe_ids,
        )
        qs = qs.filter(rodada__grupo=grupo) if grupo else qs.filter(rodada__competicao=self.competicao)

        for j in qs:
            gc, gf = j.gols_casa, j.gols_fora
            casa, fora = j.equipe_casa_id, j.equipe_fora_id
            if casa not in equipe_ids or fora not in equipe_ids:
                continue
            h2h[casa]['gp'] += gc
            h2h[fora]['gp'] += gf
            h2h[casa]['sg'] += gc - gf
            h2h[fora]['sg'] += gf - gc
            if gc > gf:
                h2h[casa]['pts'] += 3
            elif gc == gf:
                h2h[casa]['pts'] += 1
                h2h[fora]['pts'] += 1
            else:
                h2h[fora]['pts'] += 3

        return h2h

    @staticmethod
    def _sort_restante(items, criterio, ctx):
        def key(cl):
            k = []
            if criterio.vitorias:
                k.append(-cl.vitorias)
            if criterio.saldo_gols:
                k.append(-cl.saldo_gols)
            if criterio.gols_pro:
                k.append(-cl.gols_pro)
            if criterio.gol_fora:
                k.append(-(ctx['gols_fora'].get(cl.equipe_id, 0)))
            if criterio.menor_vermelho:
                k.append(ctx['vermelhos'].get(cl.equipe_id, 0))
            if criterio.menor_amarelo:
                k.append(ctx['amarelos'].get(cl.equipe_id, 0))
            k.append(-cl.gols_pro)
            return tuple(k)
        return sorted(items, key=key)

    def _resolver_empate(self, items, criterio, ctx, grupo):
        if not criterio or len(items) <= 1:
            return items

        if criterio.confronto_direto:
            h2h = self._computar_h2h(items, grupo)
            items = sorted(items, key=lambda c: (
                -h2h[c.equipe_id]['pts'],
                -h2h[c.equipe_id]['sg'],
                -h2h[c.equipe_id]['gp'],
            ))
            result = []
            i = 0
            while i < len(items):
                j = i
                while j < len(items) and h2h[items[j].equipe_id] == h2h[items[i].equipe_id]:
                    j += 1
                sub = items[i:j]
                if len(sub) > 1:
                    sub = self._sort_restante(sub, criterio, ctx)
                result.extend(sub)
                i = j
            return result

        return self._sort_restante(items, criterio, ctx)


def aplicar_criterios(competicao, classificacoes, grupo=None):
    return ClassificadorService(competicao).ordenar(classificacoes, grupo=grupo)
