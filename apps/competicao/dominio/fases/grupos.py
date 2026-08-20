from django.db import transaction

from ..excecoes import RegraVioladaError
from .base import TipoFaseStrategy, circulo_inicial, criar_jogos_da_rodada, rotacionar


class GruposStrategy(TipoFaseStrategy):
    """Round-robin dentro de cada grupo da competição."""

    @transaction.atomic
    def gerar_jogos(self, competicao):
        """Gera as rodadas de todos os grupos. Retorna o nº de rodadas criadas."""
        from ...models import Rodada

        if not competicao.grupos.exists():
            raise RegraVioladaError('Nenhum grupo definido nesta competição.')
        if Rodada.objects.filter(grupo__competicao=competicao).exists():
            raise RegraVioladaError('Esta competição já possui rodadas de grupos geradas.')

        turnos = 2 if competicao.grupos_ida_e_volta else 1
        rodadas_criadas = 0

        for grupo in competicao.grupos.prefetch_related('equipes'):
            equipes = list(grupo.equipes.all())
            if len(equipes) < 2:
                continue

            circulo = circulo_inicial(equipes)
            num_rodadas = len(circulo) - 1
            offset = 0
            for turno in range(turnos):
                atual = circulo[:]
                for numero in range(1, num_rodadas + 1):
                    rodada = Rodada.objects.create(
                        competicao=competicao, grupo=grupo, numero=offset + numero,
                    )
                    rodadas_criadas += 1
                    criar_jogos_da_rodada(rodada, atual, turno)
                    atual = rotacionar(atual)
                offset += num_rodadas

        return rodadas_criadas
