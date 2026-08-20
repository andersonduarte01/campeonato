from django.db import transaction
from django.utils import timezone

from .excecoes import RegraVioladaError
from .wo import WOService


class DesistenciaService:
    """Registra a desistência de uma equipe em uma fase.

    Marca a participação como inativa (`ativo=False`, `desistiu_em=<agora>`),
    preserva o histórico e aplica W.O. em todos os jogos futuros da equipe
    naquela fase (jogos ainda não finalizados e não anulados).
    """

    @transaction.atomic
    def registrar(self, fase, equipe):
        from ..models import Jogo, ParticipacaoFase

        try:
            participacao = ParticipacaoFase.objects.get(fase=fase, equipe=equipe)
        except ParticipacaoFase.DoesNotExist:
            raise RegraVioladaError('Esta equipe não participa desta fase.')
        if not participacao.ativo:
            raise RegraVioladaError('Esta equipe já foi registrada como desistente.')

        participacao.ativo = False
        participacao.desistiu_em = timezone.now()
        participacao.save(update_fields=['ativo', 'desistiu_em'])

        jogos_futuros = Jogo.objects.filter(
            rodada__fase=fase, status__in=[Jogo.STATUS_AGENDADO, Jogo.STATUS_EM_ANDAMENTO],
        ).filter(
            models_q_equipe(equipe),
        )

        aplicados = 0
        wo_service = WOService()
        for jogo in jogos_futuros:
            if jogo.equipe_casa_id == equipe.pk:
                vencedor = jogo.equipe_fora
            else:
                vencedor = jogo.equipe_casa
            wo_service.declarar(jogo, vencedor)
            aplicados += 1
        return aplicados


def models_q_equipe(equipe):
    from django.db.models import Q
    return Q(equipe_casa=equipe) | Q(equipe_fora=equipe)
