from django.db.models import F, Q, Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


# ---------------------------------------------------------------------------
# Helpers de recálculo
# ---------------------------------------------------------------------------

def _stats_jogo(jogo_qs_casa, jogo_qs_fora):
    """Calcula stats a partir de querysets de jogos como mandante e visitante."""
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
        'pontos': vitorias * 3 + empates,
    }


def recalcular_classificacao(equipe, competicao):
    from .models import Jogo, Classificacao
    base = dict(finalizado=True, anulado=False)
    stats = _stats_jogo(
        Jogo.objects.filter(rodada__competicao=competicao, equipe_casa=equipe, **base),
        Jogo.objects.filter(rodada__competicao=competicao, equipe_fora=equipe, **base),
    )
    Classificacao.objects.update_or_create(
        equipe=equipe, competicao=competicao, defaults=stats,
    )


def recalcular_classificacao_grupo(equipe, grupo):
    from .models import Jogo, ClassificacaoGrupo
    base = dict(finalizado=True, anulado=False)
    stats = _stats_jogo(
        Jogo.objects.filter(rodada__grupo=grupo, equipe_casa=equipe, **base),
        Jogo.objects.filter(rodada__grupo=grupo, equipe_fora=equipe, **base),
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
    """Recompute suspension records for an athlete after a card change."""
    from .models import Cartao, Suspensao
    if not jogo.rodada_id:
        return
    competicao = jogo.rodada.competicao

    amarelos = Cartao.objects.filter(
        jogo__rodada__competicao=competicao, jogador=atleta, tipo=Cartao.AMARELO,
    ).count()
    vermelhos = Cartao.objects.filter(
        jogo__rodada__competicao=competicao, jogador=atleta, tipo=Cartao.VERMELHO,
    ).count()

    expected = (amarelos // 3) + vermelhos
    existing = Suspensao.objects.filter(atleta=atleta, competicao=competicao)
    cumpridas = existing.filter(cumprida=True).count()
    pendentes = list(existing.filter(cumprida=False))
    total = cumpridas + len(pendentes)

    delta = expected - total
    if delta > 0:
        motivo = Suspensao.VERMELHO if vermelhos > 0 else Suspensao.AMARELOS
        for _ in range(delta):
            Suspensao.objects.create(atleta=atleta, competicao=competicao, motivo=motivo)
    elif delta < 0:
        for s in pendentes[:abs(delta)]:
            s.delete()


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

@receiver(post_save, sender='competicao.Jogo')
def on_jogo_save(sender, instance, **kwargs):
    from .models import ConfrontoMatamate

    # 1. Classificação geral (liga / pontos corridos)
    if instance.rodada:
        comp = instance.rodada.competicao
        recalcular_classificacao(instance.equipe_casa, comp)
        recalcular_classificacao(instance.equipe_fora, comp)

        # 2. Classificação de grupo
        if instance.rodada.grupo:
            recalcular_classificacao_grupo(instance.equipe_casa, instance.rodada.grupo)
            recalcular_classificacao_grupo(instance.equipe_fora, instance.rodada.grupo)

    # 3. Vencedor do confronto mata-mata
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
        recalcular_classificacao(jogo.equipe_casa, comp)
        recalcular_classificacao(jogo.equipe_fora, comp)
        if jogo.rodada.grupo:
            recalcular_classificacao_grupo(jogo.equipe_casa, jogo.rodada.grupo)
            recalcular_classificacao_grupo(jogo.equipe_fora, jogo.rodada.grupo)


@receiver(post_save, sender='competicao.Cartao')
@receiver(post_delete, sender='competicao.Cartao')
def on_cartao_change(sender, instance, **kwargs):
    _verificar_suspensao(instance.jogador, instance.jogo)


@receiver(post_save, sender='competicao.Suspensao')
def on_suspensao_criada(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import Notificacao
    from django.contrib.auth import get_user_model
    User = get_user_model()
    admins = User.objects.filter(
        is_active=True,
    ).filter(Q(is_admin=True) | Q(perfil='admin') | Q(perfil='organizador'))
    msg = f"Suspensão: {instance.atleta.nome} ({instance.get_motivo_display()}) — {instance.competicao.nome}"
    for u in admins:
        Notificacao.objects.create(usuario=u, mensagem=msg, tipo=Notificacao.SUSPENSAO)


@receiver(post_save, sender='competicao.Jogo')
def on_jogo_finalizado_notificacao(sender, instance, **kwargs):
    if not (instance.finalizado and instance.rodada_id):
        return
    from .models import Notificacao
    from django.contrib.auth import get_user_model
    User = get_user_model()
    admins = User.objects.filter(
        is_active=True,
    ).filter(Q(is_admin=True) | Q(perfil='admin') | Q(perfil='organizador'))
    msg = (
        f"Resultado: {instance.equipe_casa.nome_equipe} {instance.gols_casa}"
        f" x {instance.gols_fora} {instance.equipe_fora.nome_equipe}"
        f" — {instance.rodada.competicao.nome}"
    )
    try:
        from django.urls import reverse
        url = reverse('competicao:jogo_detalhe', kwargs={'pk': instance.pk})
    except Exception:
        url = None
    for u in admins:
        Notificacao.objects.get_or_create(
            usuario=u, mensagem=msg, tipo=Notificacao.RESULTADO,
            defaults={'url': url},
        )
