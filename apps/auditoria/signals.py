"""Signals que gravam AuditoriaEvento em pontos-chave.

Usa signals do Django (post_save / pre_save) para não invadir o código
das views/services. Detecta transições comparando estado antigo vs novo
via pre_save cacheado.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .dominio.registrar import registrar_evento


# ---------------------------------------------------------------------------
# Competicao.status — transição de estado
# ---------------------------------------------------------------------------

@receiver(pre_save, sender='competicao.Competicao')
def _cache_status_competicao(sender, instance, **kwargs):
    if not instance.pk:
        instance._status_antigo = None
        return
    try:
        instance._status_antigo = sender.objects.only('status').get(pk=instance.pk).status
    except sender.DoesNotExist:
        instance._status_antigo = None


@receiver(post_save, sender='competicao.Competicao')
def _log_competicao_transicao(sender, instance, created, **kwargs):
    antigo = getattr(instance, '_status_antigo', None)
    if antigo is None or antigo == instance.status:
        return
    registrar_evento(
        tipo='competicao_transicao',
        federacao=instance.federacao,
        objeto=instance,
        dados={'de': antigo, 'para': instance.status},
    )


# ---------------------------------------------------------------------------
# Jogo.status — passa a finalizado/homologado/anulado
# ---------------------------------------------------------------------------

@receiver(pre_save, sender='competicao.Jogo')
def _cache_status_jogo(sender, instance, **kwargs):
    if not instance.pk:
        instance._status_antigo = None
        return
    try:
        instance._status_antigo = sender.objects.only('status').get(pk=instance.pk).status
    except sender.DoesNotExist:
        instance._status_antigo = None


@receiver(post_save, sender='competicao.Jogo')
def _log_jogo_transicao(sender, instance, created, **kwargs):
    antigo = getattr(instance, '_status_antigo', None)
    if antigo is None or antigo == instance.status:
        return
    interesses = {'finalizado', 'homologado', 'anulado'}
    if instance.status not in interesses and antigo not in interesses:
        return
    federacao = None
    if instance.rodada_id:
        federacao = instance.rodada.competicao.federacao
    registrar_evento(
        tipo='jogo_status',
        federacao=federacao,
        objeto=instance,
        dados={'de': antigo, 'para': instance.status,
               'placar': f'{instance.gols_casa}x{instance.gols_fora}'},
    )


# ---------------------------------------------------------------------------
# Sumula — encerrada / homologada / reaberta
# ---------------------------------------------------------------------------

@receiver(pre_save, sender='competicao.Sumula')
def _cache_status_sumula(sender, instance, **kwargs):
    if not instance.pk:
        instance._status_antigo = None
        return
    try:
        instance._status_antigo = sender.objects.only('status').get(pk=instance.pk).status
    except sender.DoesNotExist:
        instance._status_antigo = None


@receiver(post_save, sender='competicao.Sumula')
def _log_sumula_transicao(sender, instance, created, **kwargs):
    antigo = getattr(instance, '_status_antigo', None)
    if antigo is None or antigo == instance.status:
        return
    from apps.competicao.models import Sumula
    mapa = {
        Sumula.STATUS_ENCERRADA: 'sumula_encerrada',
        Sumula.STATUS_HOMOLOGADA: 'sumula_homologada',
        Sumula.STATUS_ABERTA: 'sumula_reaberta' if antigo == Sumula.STATUS_ENCERRADA else None,
    }
    tipo = mapa.get(instance.status)
    if not tipo:
        return
    federacao = None
    if instance.jogo_id and instance.jogo.rodada_id:
        federacao = instance.jogo.rodada.competicao.federacao
    registrar_evento(
        tipo=tipo,
        federacao=federacao,
        usuario=instance.homologada_por if instance.status == Sumula.STATUS_HOMOLOGADA else None,
        objeto=instance,
        dados={'de': antigo, 'para': instance.status, 'jogo_id': instance.jogo_id},
    )


# ---------------------------------------------------------------------------
# Transferencia — aprovada / rejeitada / cancelada
# ---------------------------------------------------------------------------

@receiver(pre_save, sender='registro.Transferencia')
def _cache_status_transferencia(sender, instance, **kwargs):
    if not instance.pk:
        instance._status_antigo = None
        return
    try:
        instance._status_antigo = sender.objects.only('status').get(pk=instance.pk).status
    except sender.DoesNotExist:
        instance._status_antigo = None


@receiver(post_save, sender='registro.Transferencia')
def _log_transferencia_transicao(sender, instance, created, **kwargs):
    antigo = getattr(instance, '_status_antigo', None)
    if antigo is None or antigo == instance.status:
        return
    from apps.registro.models import Transferencia
    mapa = {
        Transferencia.STATUS_APROVADA: 'transferencia_aprovada',
        Transferencia.STATUS_REJEITADA: 'transferencia_rejeitada',
        Transferencia.STATUS_CANCELADA: 'transferencia_cancelada',
    }
    tipo = mapa.get(instance.status)
    if not tipo:
        return
    federacao = None
    if instance.atleta_id and instance.atleta.equipe_id:
        federacao = instance.atleta.equipe.federacao
    registrar_evento(
        tipo=tipo,
        federacao=federacao,
        usuario=instance.solicitado_por,
        objeto=instance,
        dados={
            'atleta_id': instance.atleta_id,
            'atleta_nome': instance.atleta.nome if instance.atleta_id else None,
            'clube_origem_id': instance.clube_origem_id,
            'clube_destino_id': instance.clube_destino_id,
            'tipo': instance.tipo,
        },
    )
