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


def criar_jogos_da_rodada(rodada, circulo, turno):
    from ...models import Jogo

    for i in range(len(circulo) // 2):
        casa, fora = circulo[i], circulo[-(i + 1)]
        if casa and fora:
            if turno == 1:
                casa, fora = fora, casa
            Jogo.objects.create(rodada=rodada, equipe_casa=casa, equipe_fora=fora)
