from django.db import transaction


class SuspensaoService:
    """Regras de cumprimento de suspensão."""

    @transaction.atomic
    def processar_cumprimento(self, jogo):
        """Decrementa `rodadas_pendentes` de cada suspensão pendente cujo
        atleta pertence a uma das equipes do jogo e não foi escalado.
        Marca `cumprida=True` quando `rodadas_pendentes` chega a 0.

        Retorna a quantidade de suspensões afetadas.
        """
        from ..models import EscalacaoJogo, Suspensao

        if not jogo.rodada_id:
            return 0
        competicao = jogo.rodada.competicao
        escalados_ids = set(
            EscalacaoJogo.objects.filter(sumula__jogo=jogo).values_list(
                'atleta_id', flat=True,
            )
        )
        pendentes = Suspensao.objects.filter(
            competicao=competicao,
            cumprida=False,
            atleta__equipe__in=[jogo.equipe_casa_id, jogo.equipe_fora_id],
        ).exclude(
            atleta_id__in=escalados_ids,
        ).exclude(jogos_cumpridos=jogo)

        afetadas = 0
        for susp in pendentes:
            susp.rodadas_pendentes = max(0, susp.rodadas_pendentes - 1)
            if susp.rodadas_pendentes == 0:
                susp.cumprida = True
            susp.save(update_fields=['rodadas_pendentes', 'cumprida'])
            susp.jogos_cumpridos.add(jogo)
            afetadas += 1
        return afetadas
