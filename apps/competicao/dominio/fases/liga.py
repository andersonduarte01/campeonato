from django.db import transaction

from ..excecoes import RegraVioladaError
from .base import TipoFaseStrategy, circulo_inicial, criar_jogos_da_rodada, rotacionar


def _turnos(formato):
    turno_unico = getattr(formato, 'turno_unico', True)
    ida_e_volta = getattr(formato, 'ida_e_volta', False)
    return 1 if turno_unico and not ida_e_volta else 2


class LigaStrategy(TipoFaseStrategy):
    """Round-robin de pontos corridos (algoritmo do círculo)."""

    @transaction.atomic
    def gerar_jogos(self, competicao):
        """Gera todas as rodadas de uma vez. Retorna o nº de rodadas criadas."""
        from ...models import Fase, ParticipacaoFase, Rodada

        if Rodada.objects.filter(
            competicao=competicao, grupo__isnull=True, etapa__isnull=True,
        ).exists():
            raise RegraVioladaError('Esta competição já possui rodadas geradas.')

        equipes = list(competicao.equipes.order_by('id'))
        if len(equipes) < 2:
            raise RegraVioladaError('É necessário pelo menos duas equipes para gerar jogos.')

        fase = Fase.obter_ou_criar(competicao, Fase.LIGA)
        for seed, equipe in enumerate(equipes, start=1):
            ParticipacaoFase.objects.get_or_create(
                fase=fase, equipe=equipe, defaults={'seed': seed, 'ativo': True},
            )

        turnos = _turnos(competicao.formato)
        circulo = circulo_inicial(equipes)
        num_rodadas = len(circulo) - 1
        rodadas_criadas = 0
        offset = 0

        for turno in range(turnos):
            atual = circulo[:]
            for numero in range(1, num_rodadas + 1):
                rodada = Rodada.objects.create(competicao=competicao, numero=offset + numero)
                rodadas_criadas += 1
                criar_jogos_da_rodada(rodada, atual, turno, numero_no_turno=numero)
                atual = rotacionar(atual)
            offset += num_rodadas

        return rodadas_criadas

    @transaction.atomic
    def gerar_proxima_rodada(self, competicao):
        """Gera apenas a próxima rodada da liga. Retorna (numero, total)."""
        from ...models import Fase, ParticipacaoFase, Rodada

        fase = Fase.objects.filter(competicao=competicao, tipo=Fase.LIGA).first()
        participacoes = list(
            ParticipacaoFase.objects.filter(fase=fase).order_by('seed').select_related('equipe')
        ) if fase else []
        if participacoes:
            equipes = [p.equipe for p in participacoes]
        else:
            equipes = list(competicao.equipes.order_by('id'))
        if len(equipes) < 2:
            raise RegraVioladaError('É necessário pelo menos duas equipes para gerar jogos.')

        turnos = _turnos(competicao.formato)
        circulo = circulo_inicial(equipes)
        num_rodadas = len(circulo) - 1
        total = num_rodadas * turnos

        existentes = Rodada.objects.filter(
            competicao=competicao, grupo__isnull=True, etapa__isnull=True,
        ).count()
        if existentes >= total:
            raise RegraVioladaError('Todas as rodadas já foram geradas.')

        proxima = existentes + 1
        turno, rotacoes = divmod(proxima - 1, num_rodadas)
        atual = circulo[:]
        for _ in range(rotacoes):
            atual = rotacionar(atual)

        rodada = Rodada.objects.create(competicao=competicao, numero=proxima)
        criar_jogos_da_rodada(rodada, atual, turno, numero_no_turno=rotacoes + 1)
        return proxima, total
