from abc import ABC, abstractmethod


class TipoFaseStrategy(ABC):
    """Estratégia de geração de jogos para um tipo de fase.

    Implementações levantam RegraVioladaError quando a operação não é
    permitida e retornam contagens para as views montarem mensagens.
    """

    @abstractmethod
    def gerar_jogos(self, *args, **kwargs):
        ...


def circulo_inicial(equipes):
    """Lista de equipes pronta para o algoritmo do círculo (folga = None)."""
    equipes = list(equipes)
    if len(equipes) % 2:
        equipes.append(None)
    return equipes


def rotacionar(circulo):
    return [circulo[0]] + [circulo[-1]] + circulo[1:-1]


def criar_jogos_da_rodada(rodada, circulo, turno, numero_no_turno=1):
    """Cria os jogos de uma rodada a partir do círculo já rotacionado.

    A posição 0 do círculo é fixa (nunca gira) no método do círculo — sem
    correção, o time ali sempre cairia como mandante no par i=0 em todas
    as rodadas de um turno único, jogando 100% dos jogos em casa. Para
    equilibrar, o par i=0 tem mando invertido nas rodadas pares do turno
    (a correção padrão documentada para esse viés do método do círculo).
    Os demais times já ficam balanceados pela rotação natural do círculo.
    """
    from ...models import Jogo

    for i in range(len(circulo) // 2):
        casa, fora = circulo[i], circulo[-(i + 1)]
        if casa and fora:
            if turno == 1:
                casa, fora = fora, casa
            if i == 0 and numero_no_turno % 2 == 0:
                casa, fora = fora, casa
            Jogo.objects.create(rodada=rodada, equipe_casa=casa, equipe_fora=fora)
