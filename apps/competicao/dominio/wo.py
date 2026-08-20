from django.db import transaction

from .excecoes import RegraVioladaError


class WOService:
    """Declara uma partida por W.O. (não-comparecimento)."""

    PLACAR_REGULAMENTAR = (3, 0)

    @transaction.atomic
    def declarar(self, jogo, vencedor):
        """`vencedor` deve ser jogo.equipe_casa ou jogo.equipe_fora."""
        from ..models import Cartao, Gol, Jogo

        if jogo.status == Jogo.STATUS_HOMOLOGADO:
            raise RegraVioladaError('Jogo já homologado não pode ser declarado W.O.')
        if jogo.status == Jogo.STATUS_ANULADO:
            raise RegraVioladaError('Jogo anulado não pode ser declarado W.O.')
        if vencedor not in (jogo.equipe_casa, jogo.equipe_fora):
            raise RegraVioladaError('Vencedor deve ser uma das equipes do jogo.')

        Gol.objects.filter(jogo=jogo).delete()
        Cartao.objects.filter(jogo=jogo).delete()

        gc, gf = self.PLACAR_REGULAMENTAR
        if vencedor == jogo.equipe_casa:
            jogo.gols_casa, jogo.gols_fora = gc, gf
            jogo.resultado_tipo = Jogo.RESULTADO_WO_FORA
        else:
            jogo.gols_casa, jogo.gols_fora = gf, gc
            jogo.resultado_tipo = Jogo.RESULTADO_WO_CASA
        jogo.status = Jogo.STATUS_FINALIZADO
        jogo.save()
        return jogo
