import datetime
import logging

from django.db import transaction

from .excecoes import RegraVioladaError

logger = logging.getLogger(__name__)


class TransferenciaService:
    """Operações de transferência com integridade transacional.

    Substitui os métodos aprovar/rejeitar/cancelar que ficavam no modelo
    Transferencia. A criação de HistoricoClube + fechamento do anterior +
    atualização de atleta.equipe roda em uma única transação — se
    qualquer passo falhar, nada é gravado.
    """

    @transaction.atomic
    def aprovar(self, transferencia, *, usuario=None, ignorar_janela=False):
        from ..models import HistoricoClube, Transferencia

        if transferencia.status not in (
            Transferencia.STATUS_SOLICITADA, Transferencia.STATUS_EM_ANALISE,
        ):
            raise RegraVioladaError(
                f'Transferência com status "{transferencia.get_status_display()}" '
                'não pode ser aprovada.'
            )
        if not ignorar_janela:
            self._validar_janela_aberta(transferencia)

        hoje = datetime.date.today()
        transferencia.status = Transferencia.STATUS_APROVADA
        transferencia.data_aprovacao = hoje
        transferencia.save(update_fields=['status', 'data_aprovacao'])

        # Transferência internacional entra sem histórico anterior no
        # sistema — nada a fechar.
        if transferencia.tipo != Transferencia.TIPO_INTERNACIONAL:
            abertos = list(HistoricoClube.objects.filter(
                atleta=transferencia.atleta, data_saida=None,
            ))
            if len(abertos) > 1:
                logger.warning(
                    'Atleta %s tinha %d históricos abertos antes da transferência %s; '
                    'todos serão fechados.',
                    transferencia.atleta_id, len(abertos), transferencia.pk,
                )
            for h in abertos:
                h.data_saida = hoje
                h.save(update_fields=['data_saida'])

        tipo_hist = (
            HistoricoClube.TIPO_EMPRESTADO
            if transferencia.tipo == Transferencia.TIPO_EMPRESTIMO
            else HistoricoClube.TIPO_TITULAR
        )
        HistoricoClube.objects.create(
            atleta=transferencia.atleta,
            equipe=transferencia.clube_destino,
            tipo=tipo_hist,
            data_entrada=hoje,
        )

        transferencia.atleta.equipe = transferencia.clube_destino
        transferencia.atleta.save(update_fields=['equipe'])
        return transferencia

    @transaction.atomic
    def rejeitar(self, transferencia):
        from ..models import Transferencia

        if transferencia.status not in (
            Transferencia.STATUS_SOLICITADA, Transferencia.STATUS_EM_ANALISE,
        ):
            raise RegraVioladaError(
                f'Transferência com status "{transferencia.get_status_display()}" '
                'não pode ser rejeitada.'
            )
        transferencia.status = Transferencia.STATUS_REJEITADA
        transferencia.save(update_fields=['status'])
        return transferencia

    @transaction.atomic
    def cancelar(self, transferencia):
        from ..models import Transferencia

        if transferencia.status in (
            Transferencia.STATUS_APROVADA, Transferencia.STATUS_REJEITADA,
        ):
            raise RegraVioladaError(
                f'Transferência com status "{transferencia.get_status_display()}" '
                'não pode ser cancelada.'
            )
        transferencia.status = Transferencia.STATUS_CANCELADA
        transferencia.save(update_fields=['status'])
        return transferencia

    @transaction.atomic
    def marcar_em_analise(self, transferencia):
        from ..models import Transferencia

        if transferencia.status != Transferencia.STATUS_SOLICITADA:
            raise RegraVioladaError(
                'Só transferências solicitadas podem ir para análise.'
            )
        transferencia.status = Transferencia.STATUS_EM_ANALISE
        transferencia.save(update_fields=['status'])
        return transferencia

    def _validar_janela_aberta(self, transferencia):
        janela = transferencia.janela
        if janela is None:
            raise RegraVioladaError(
                'Transferência sem janela associada não pode ser aprovada.'
            )
        hoje = datetime.date.today()
        if not (janela.ativa and janela.data_inicio <= hoje <= janela.data_fim):
            raise RegraVioladaError(
                f'A janela "{janela.nome}" não está aberta na data de aprovação.'
            )
