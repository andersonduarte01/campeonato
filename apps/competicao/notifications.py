"""
Notificações por email do CHAMPS.

Cada função recebe o objeto de domínio e envia emails assíncronos via
django.core.mail. Para produção configure EMAIL_BACKEND no settings.py.
"""
from django.core.mail import send_mail
from django.conf import settings


_FROM = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@champs.com.br')


def _send(assunto, corpo, destinatarios):
    validos = [e for e in destinatarios if e]
    if not validos:
        return
    try:
        send_mail(assunto, corpo, _FROM, validos, fail_silently=True)
    except Exception:
        pass


def notificar_jogo_finalizado(jogo):
    if not jogo.rodada_id:
        return
    comp = jogo.rodada.competicao
    fed  = comp.federacao
    data = jogo.data_hora.strftime('%d/%m/%Y %H:%M') if jogo.data_hora else '—'
    corpo = (
        f"Resultado registrado em {comp.nome}\n\n"
        f"{jogo.equipe_casa.nome_equipe} {jogo.gols_casa} x {jogo.gols_fora} {jogo.equipe_fora.nome_equipe}\n"
        f"Data: {data}\n\n"
        f"Acesse o sistema da {fed.nome} para mais detalhes."
    )
    destinatarios = []
    if jogo.arbitro:
        destinatarios.append(jogo.arbitro.usuario.email)
    if fed.email:
        destinatarios.append(fed.email)
    _send(f"[{fed.sigla}] Resultado: {jogo.equipe_casa} x {jogo.equipe_fora}", corpo, destinatarios)


def notificar_suspensao_criada(suspensao):
    fed   = suspensao.competicao.federacao
    atleta = suspensao.atleta
    rodadas = suspensao.rodadas_pendentes
    motivo  = suspensao.get_motivo_display()
    corpo = (
        f"Suspensão gerada automaticamente.\n\n"
        f"Atleta: {atleta.nome}\n"
        f"Motivo: {motivo}\n"
        f"Competição: {suspensao.competicao.nome}\n"
        f"Rodadas pendentes: {rodadas}\n\n"
        f"Acesse o sistema para mais informações."
    )
    destinatarios = []
    if fed.email:
        destinatarios.append(fed.email)
    _send(
        f"[{fed.sigla}] Suspensão: {atleta.nome} ({motivo})",
        corpo,
        destinatarios,
    )


def notificar_sumula_encerrada(sumula):
    fed  = sumula.jogo.rodada.competicao.federacao if sumula.jogo.rodada_id else None
    if not fed:
        return
    comp = sumula.jogo.rodada.competicao
    corpo = (
        f"Súmula #{sumula.pk} encerrada pelo árbitro e aguarda homologação.\n\n"
        f"Partida: {sumula.jogo}\n"
        f"Competição: {comp.nome}\n\n"
        f"Acesse o sistema para homologar."
    )
    destinatarios = [fed.email] if fed.email else []
    _send(f"[{fed.sigla}] Súmula #{sumula.pk} aguarda homologação", corpo, destinatarios)


def notificar_sumula_homologada(sumula):
    jogo = sumula.jogo
    if not jogo.rodada_id:
        return
    comp = jogo.rodada.competicao
    fed  = comp.federacao
    corpo = (
        f"Súmula #{sumula.pk} homologada.\n\n"
        f"Partida: {jogo}\n"
        f"Resultado: {jogo.equipe_casa.nome_equipe} {jogo.gols_casa} x {jogo.gols_fora} {jogo.equipe_fora.nome_equipe}\n"
        f"Competição: {comp.nome}\n\n"
        f"O resultado é oficial."
    )
    destinatarios = [fed.email] if fed.email else []
    if jogo.arbitro:
        destinatarios.append(jogo.arbitro.usuario.email)
    _send(f"[{fed.sigla}] Súmula #{sumula.pk} homologada", corpo, destinatarios)


def notificar_transferencia_aprovada(transferencia):
    fed = transferencia.atleta.equipe.federacao
    corpo = (
        f"Transferência aprovada.\n\n"
        f"Atleta: {transferencia.atleta.nome}\n"
        f"Origem: {transferencia.clube_origem.nome_equipe}\n"
        f"Destino: {transferencia.clube_destino.nome_equipe}\n"
        f"Tipo: {transferencia.get_tipo_display()}\n"
    )
    destinatarios = [fed.email] if fed.email else []
    if transferencia.solicitado_por:
        destinatarios.append(transferencia.solicitado_por.email)
    _send(f"[{fed.sigla}] Transferência aprovada: {transferencia.atleta.nome}", corpo, destinatarios)


def notificar_transferencia_rejeitada(transferencia):
    fed = transferencia.atleta.equipe.federacao
    corpo = (
        f"Transferência rejeitada.\n\n"
        f"Atleta: {transferencia.atleta.nome}\n"
        f"Origem: {transferencia.clube_origem.nome_equipe}\n"
        f"Destino: {transferencia.clube_destino.nome_equipe}\n"
    )
    destinatarios = []
    if transferencia.solicitado_por:
        destinatarios.append(transferencia.solicitado_por.email)
    _send(f"[{fed.sigla}] Transferência rejeitada: {transferencia.atleta.nome}", corpo, destinatarios)
