from django.db.models import F, Q, Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


def _stats_jogo(jogo_qs_casa, jogo_qs_fora, pts_vitoria=3, pts_empate=1):
    total = jogo_qs_casa.count() + jogo_qs_fora.count()
    vitorias = (
        jogo_qs_casa.filter(gols_casa__gt=F('gols_fora')).count()
        + jogo_qs_fora.filter(gols_fora__gt=F('gols_casa')).count()
    )
    empates = (
        jogo_qs_casa.filter(gols_casa=F('gols_fora')).count()
        + jogo_qs_fora.filter(gols_fora=F('gols_casa')).count()
    )
    gols_pro = (
        (jogo_qs_casa.aggregate(t=Sum('gols_casa'))['t'] or 0)
        + (jogo_qs_fora.aggregate(t=Sum('gols_fora'))['t'] or 0)
    )
    gols_contra = (
        (jogo_qs_casa.aggregate(t=Sum('gols_fora'))['t'] or 0)
        + (jogo_qs_fora.aggregate(t=Sum('gols_casa'))['t'] or 0)
    )
    return {
        'jogos': total,
        'vitorias': vitorias,
        'empates': empates,
        'derrotas': total - vitorias - empates,
        'gols_pro': gols_pro,
        'gols_contra': gols_contra,
        'saldo_gols': gols_pro - gols_contra,
        'pontos': vitorias * pts_vitoria + empates * pts_empate,
    }


def recalcular_classificacao(equipe, competicao):
    from .models import Jogo, Classificacao, Fase
    contabilizavel = Q(finalizado=True)
    filtro_base = Q(
        anulado=False,
        rodada__grupo__isnull=True,
        rodada__etapa__isnull=True,
    ) & contabilizavel
    qs_casa = Jogo.objects.filter(filtro_base, rodada__competicao=competicao, equipe_casa=equipe)
    qs_fora = Jogo.objects.filter(filtro_base, rodada__competicao=competicao, equipe_fora=equipe)
    stats = _stats_jogo(
        qs_casa, qs_fora,
        pts_vitoria=competicao.pontos_vitoria, pts_empate=competicao.pontos_empate,
    )
    stats['fase'] = Fase.objects.filter(competicao=competicao, tipo=Fase.LIGA).first()
    stats['tem_provisorio'] = (
        qs_casa.filter(status=Jogo.STATUS_PROVISORIO).exists()
        or qs_fora.filter(status=Jogo.STATUS_PROVISORIO).exists()
    )
    Classificacao.objects.update_or_create(
        equipe=equipe, competicao=competicao, defaults=stats,
    )


def recalcular_classificacao_grupo(equipe, grupo):
    from .models import Jogo, ClassificacaoGrupo
    competicao = grupo.competicao
    filtro_base = Q(anulado=False, finalizado=True)
    stats = _stats_jogo(
        Jogo.objects.filter(filtro_base, rodada__grupo=grupo, equipe_casa=equipe),
        Jogo.objects.filter(filtro_base, rodada__grupo=grupo, equipe_fora=equipe),
        pts_vitoria=competicao.pontos_vitoria, pts_empate=competicao.pontos_empate,
    )
    ClassificacaoGrupo.objects.update_or_create(
        equipe=equipe, grupo=grupo, defaults=stats,
    )


def _sincronizar_placar(jogo):
    from .models import Gol
    gols_casa = Gol.objects.filter(jogo=jogo, equipe=jogo.equipe_casa).count()
    gols_fora = Gol.objects.filter(jogo=jogo, equipe=jogo.equipe_fora).count()
    type(jogo).objects.filter(pk=jogo.pk).update(gols_casa=gols_casa, gols_fora=gols_fora)
    jogo.gols_casa = gols_casa
    jogo.gols_fora = gols_fora


def _verificar_suspensao(atleta, jogo):
    """
    Recalcula suspensões do atleta na competição com base na configuração
    de limite de amarelos e jogos de suspensão definidos na Competicao.
    """
    from .models import Cartao, Suspensao
    if not jogo.rodada_id:
        return
    competicao = jogo.rodada.competicao

    limite = competicao.limite_amarelos_suspensao or 3
    jogos_amarelo = competicao.jogos_suspensao_amarelos or 1
    jogos_vermelho = competicao.jogos_suspensao_vermelho or 1

    amarelos = Cartao.objects.filter(
        jogo__rodada__competicao=competicao, jogador=atleta, tipo=Cartao.AMARELO,
        jogo__anulado=False,
    ).count()
    vermelhos = Cartao.objects.filter(
        jogo__rodada__competicao=competicao, jogador=atleta, tipo=Cartao.VERMELHO,
        jogo__anulado=False,
    ).count()

    # Suspensões esperadas: 1 por ciclo de amarelos completo + 1 por vermelho
    susps_por_amarelo = amarelos // limite
    susps_por_vermelho = vermelhos

    existing = Suspensao.objects.filter(atleta=atleta, competicao=competicao, automatica=True)
    cumpridas = existing.filter(cumprida=True).count()
    pendentes = list(existing.filter(cumprida=False))
    total_atual = cumpridas + len(pendentes)

    # Cria novas suspensões por amarelos
    for _ in range(max(0, susps_por_amarelo - (cumpridas + len([p for p in pendentes if p.motivo == Suspensao.AMARELOS])))):
        Suspensao.objects.create(
            atleta=atleta, competicao=competicao,
            motivo=Suspensao.AMARELOS,
            rodadas_pendentes=jogos_amarelo,
            automatica=True,
        )
        from .notifications import notificar_suspensao_criada
        s = Suspensao.objects.filter(atleta=atleta, competicao=competicao, motivo=Suspensao.AMARELOS, cumprida=False).last()
        if s:
            notificar_suspensao_criada(s)

    # Cria novas suspensões por vermelho
    susps_vermelho_atuais = existing.filter(motivo=Suspensao.VERMELHO).count()
    for _ in range(max(0, susps_por_vermelho - susps_vermelho_atuais)):
        s = Suspensao.objects.create(
            atleta=atleta, competicao=competicao,
            motivo=Suspensao.VERMELHO,
            rodadas_pendentes=jogos_vermelho,
            automatica=True,
        )
        from .notifications import notificar_suspensao_criada
        notificar_suspensao_criada(s)


def _registrar_historico_posicao(rodada):
    """Grava snapshot das posições depois de cada resultado finalizado."""
    from .models import Classificacao, HistoricoClassificacao
    from .dominio.classificador import aplicar_criterios
    if rodada.grupo_id or rodada.etapa_id:
        return
    comp = rodada.competicao
    cl_raw = Classificacao.objects.filter(competicao=comp).select_related('equipe')
    cl_ordenado = aplicar_criterios(comp, cl_raw)
    for pos, entrada in enumerate(cl_ordenado, start=1):
        HistoricoClassificacao.objects.update_or_create(
            competicao=comp, equipe=entrada.equipe, rodada=rodada,
            defaults={'posicao': pos, 'pontos': entrada.pontos},
        )


@receiver(post_save, sender='competicao.Jogo')
def on_jogo_save(sender, instance, **kwargs):
    from .dominio.suspensoes import SuspensaoService
    from .models import ConfrontoMatamate
    from django.db.models import Q

    if instance.rodada:
        comp = instance.rodada.competicao
        if instance.rodada.grupo_id is None and instance.rodada.etapa_id is None:
            recalcular_classificacao(instance.equipe_casa, comp)
            recalcular_classificacao(instance.equipe_fora, comp)

        if instance.rodada.grupo:
            recalcular_classificacao_grupo(instance.equipe_casa, instance.rodada.grupo)
            recalcular_classificacao_grupo(instance.equipe_fora, instance.rodada.grupo)

        if instance.finalizado and not instance.anulado:
            _registrar_historico_posicao(instance.rodada)
            SuspensaoService().processar_cumprimento(instance)
            from .notifications import notificar_jogo_finalizado
            notificar_jogo_finalizado(instance)

    confronto = ConfrontoMatamate.objects.filter(
        Q(jogo_ida=instance) | Q(jogo_volta=instance)
    ).first()
    if confronto:
        confronto.atualizar_vencedor()


@receiver(post_save, sender='competicao.Gol')
@receiver(post_delete, sender='competicao.Gol')
def on_gol_change(sender, instance, **kwargs):
    jogo = instance.jogo
    _sincronizar_placar(jogo)
    if jogo.finalizado and not jogo.anulado and jogo.rodada:
        comp = jogo.rodada.competicao
        if jogo.rodada.grupo_id is None and jogo.rodada.etapa_id is None:
            recalcular_classificacao(jogo.equipe_casa, comp)
            recalcular_classificacao(jogo.equipe_fora, comp)
        if jogo.rodada.grupo:
            recalcular_classificacao_grupo(jogo.equipe_casa, jogo.rodada.grupo)
            recalcular_classificacao_grupo(jogo.equipe_fora, jogo.rodada.grupo)


@receiver(post_save, sender='competicao.Cartao')
@receiver(post_delete, sender='competicao.Cartao')
def on_cartao_change(sender, instance, **kwargs):
    _verificar_suspensao(instance.jogador, instance.jogo)
