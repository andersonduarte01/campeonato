from django.db import transaction

from ..excecoes import RegraVioladaError
from .base import TipoFaseStrategy

CAPACIDADE_ETAPA = {
    'oitavas': 16,
    'quartas': 8,
    'semifinal': 4,
    'terceiro': 2,
    'final': 2,
}


class MataMataStrategy(TipoFaseStrategy):
    """Confrontos knockout a partir de uma lista ordenada de equipes.

    Emparelhamento por seed: 1 x N, 2 x N-1, etc.
    """

    @transaction.atomic
    def gerar_jogos(self, etapa, equipes):
        """Cria os confrontos da etapa. Retorna o nº de confrontos criados."""
        from ...models import ConfrontoMatamate, Jogo, Rodada

        if ConfrontoMatamate.objects.filter(etapa=etapa).exists():
            raise RegraVioladaError('Esta etapa já possui confrontos gerados.')

        n = len(equipes)
        if n < 2:
            raise RegraVioladaError('São necessárias pelo menos 2 equipes.')
        if n % 2:
            raise RegraVioladaError(
                f'Número ímpar de classificados ({n}). Ajuste os classificados por grupo.'
            )
        capacidade = CAPACIDADE_ETAPA.get(etapa.tipo)
        if capacidade and n != capacidade:
            raise RegraVioladaError(
                f"'{etapa.get_tipo_display()}' exige {capacidade} equipes, "
                f"mas {n} foram classificadas."
            )

        pares = [(equipes[i], equipes[n - 1 - i]) for i in range(n // 2)]

        rodada_ida = Rodada.objects.create(competicao=etapa.competicao, etapa=etapa, numero=1)
        rodada_volta = None
        if etapa.ida_e_volta:
            rodada_volta = Rodada.objects.create(competicao=etapa.competicao, etapa=etapa, numero=2)

        for ordem, (mandante, visitante) in enumerate(pares, start=1):
            jogo_ida = Jogo.objects.create(
                rodada=rodada_ida, equipe_casa=mandante, equipe_fora=visitante,
            )
            jogo_volta = None
            if etapa.ida_e_volta:
                jogo_volta = Jogo.objects.create(
                    rodada=rodada_volta, equipe_casa=visitante, equipe_fora=mandante,
                )
            ConfrontoMatamate.objects.create(
                etapa=etapa,
                equipe_mandante=mandante,
                equipe_visitante=visitante,
                jogo_ida=jogo_ida,
                jogo_volta=jogo_volta,
                ordem=ordem,
            )

        return len(pares)
