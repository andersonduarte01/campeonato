from django.db import transaction

from .classificador import ClassificadorService
from .excecoes import RegraVioladaError
from .fases.mata_mata import MataMataStrategy


class AvancoService:
    """Avanço de classificados entre fases da competição."""

    @transaction.atomic
    def avancar(self, etapa_origem, etapa_destino):
        """Avança os vencedores da etapa de origem para a etapa de destino.

        Seeds na ordem dos confrontos da origem; emparelhamento 1xN, 2xN-1.
        Retorna o nº de confrontos criados.
        """
        from ..models import ConfrontoMatamate, EtapaKnockout

        if etapa_origem.competicao_id != etapa_destino.competicao_id:
            raise RegraVioladaError('As etapas pertencem a competições diferentes.')
        if etapa_destino.tipo == EtapaKnockout.TERCEIRO:
            raise RegraVioladaError(
                'A disputa de 3º lugar é montada com os perdedores das semifinais, '
                'não com os vencedores.'
            )
        if etapa_destino.ordem <= etapa_origem.ordem:
            raise RegraVioladaError('A etapa de destino deve ser posterior à etapa de origem.')
        if not etapa_origem.concluida:
            raise RegraVioladaError(
                f"'{etapa_origem.get_tipo_display()}' ainda não foi concluída. "
                'Defina o vencedor de todos os confrontos antes de avançar.'
            )
        if ConfrontoMatamate.objects.filter(etapa=etapa_destino).exists():
            raise RegraVioladaError('A etapa de destino já possui confrontos gerados.')

        vencedores = [
            c.vencedor
            for c in etapa_origem.confrontos.filter(
                tipo_confronto=ConfrontoMatamate.NORMAL,
            ).order_by('ordem')
        ]
        return MataMataStrategy().gerar_jogos(etapa_destino, vencedores)

    @transaction.atomic
    def avancar_de_grupos(self, competicao, etapa):
        """Avança os N melhores de cada grupo para o bracket knockout.

        Ordem de seed: todos os 1ºs colocados, depois todos os 2ºs, etc.
        Retorna o nº de confrontos criados.
        """
        from ..models import Jogo

        if Jogo.objects.filter(
            rodada__grupo__competicao=competicao, finalizado=False, anulado=False,
        ).exists():
            raise RegraVioladaError(
                'Há jogos da fase de grupos pendentes. Finalize-os antes de avançar.'
            )

        n = competicao.qtd_classificados_por_grupo
        classificados = ClassificadorService(competicao).classificados_dos_grupos(n)
        return MataMataStrategy().gerar_jogos(etapa, classificados)
