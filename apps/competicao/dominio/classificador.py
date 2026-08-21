from django.db.models import Count, F, Sum

from apps.criterios.models import CRITERIOS_PADRAO


def _ordem_ativa(criterio):
    """Chaves de critério ativas, na ordem de prioridade configurada.

    Funciona tanto com uma instância real de CriterioClassificacao quanto
    com o SimpleNamespace reconstruído a partir do snapshot congelado —
    por isso usa getattr() em vez de depender de um método do model.
    """
    ordem = getattr(criterio, 'ordem_criterios', None) or CRITERIOS_PADRAO
    return [c for c in ordem if c in CRITERIOS_PADRAO and getattr(criterio, c, False)]


class ClassificadorService:
    """Ordena tabelas de classificação respeitando o CriterioClassificacao
    efetivo da competição (snapshot quando existir).

    A ordem de aplicação dos critérios de desempate é configurável por
    competição (via `ordem_criterios`) — não é fixa. Cada critério ativo é
    aplicado em cascata: só desempata quem ainda estiver empatado depois
    dos critérios de maior prioridade.
    """

    def __init__(self, competicao):
        self.competicao = competicao

    def ordenar(self, classificacoes, grupo=None):
        """Ordena Classificacao (geral) ou ClassificacaoGrupo."""
        criterio = self.competicao.criterio_efetivo
        items = list(classificacoes)
        if not items:
            return items

        if not criterio:
            return sorted(items, key=lambda c: (-c.pontos, -c.vitorias, -c.saldo_gols, -c.gols_pro))

        ordem = _ordem_ativa(criterio)
        ctx = self._build_ctx(items, criterio, grupo)

        by_points = sorted(items, key=lambda c: -c.pontos)
        result = []
        i = 0
        while i < len(by_points):
            j = i
            while j < len(by_points) and by_points[j].pontos == by_points[i].pontos:
                j += 1
            group = by_points[i:j]
            if len(group) > 1:
                group = self._resolver_empate(group, ordem, ctx, grupo)
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

    def _chave_criterio(self, chave, item, ctx, h2h):
        """Valor de ordenação (menor = melhor) de um item para um critério."""
        if chave == 'confronto_direto':
            d = h2h[item.equipe_id]
            return (-d['pts'], -d['sg'], -d['gp'])
        if chave == 'vitorias':
            return (-item.vitorias,)
        if chave == 'saldo_gols':
            return (-item.saldo_gols,)
        if chave == 'gols_pro':
            return (-item.gols_pro,)
        if chave == 'gol_fora':
            return (-ctx['gols_fora'].get(item.equipe_id, 0),)
        if chave == 'menor_vermelho':
            return (ctx['vermelhos'].get(item.equipe_id, 0),)
        if chave == 'menor_amarelo':
            return (ctx['amarelos'].get(item.equipe_id, 0),)
        return (0,)

    def _resolver_empate(self, items, ordem, ctx, grupo):
        """Aplica os critérios ativos em cascata, na ordem configurada.

        Cada critério só desempata quem ainda está empatado nos critérios
        de prioridade mais alta já aplicados — igual a uma mini-liga: o
        confronto direto, por exemplo, é recalculado só entre quem chegar
        empatado até a vez dele, não entre o grupo inteiro do início.
        """
        if len(items) <= 1 or not ordem:
            return items

        chave, resto = ordem[0], ordem[1:]
        h2h = self._computar_h2h(items, grupo) if chave == 'confronto_direto' else None
        keyfunc = lambda item: self._chave_criterio(chave, item, ctx, h2h)

        ordenado = sorted(items, key=keyfunc)
        resultado = []
        i = 0
        while i < len(ordenado):
            j = i
            while j < len(ordenado) and keyfunc(ordenado[j]) == keyfunc(ordenado[i]):
                j += 1
            subgrupo = ordenado[i:j]
            if len(subgrupo) > 1:
                subgrupo = self._resolver_empate(subgrupo, resto, ctx, grupo)
            resultado.extend(subgrupo)
            i = j
        return resultado


def aplicar_criterios(competicao, classificacoes, grupo=None):
    return ClassificadorService(competicao).ordenar(classificacoes, grupo=grupo)
