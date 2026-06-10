def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def registrar_auditoria(
    request,
    acao,
    descricao='',
    objeto=None,
    dados_anteriores=None,
    dados_novos=None,
):
    """
    Register an audit log entry. Never raises — a logging failure must never
    interrupt the main operation.
    """
    try:
        from .models import AuditLog
        log = AuditLog(
            acao=acao,
            descricao=descricao,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )
        if hasattr(request, 'user') and request.user.is_authenticated:
            log.usuario = request.user
            log.usuario_email = request.user.email
        if objeto is not None:
            log.modelo = f"{objeto.__class__._meta.app_label}.{objeto.__class__.__name__}"
            log.objeto_id = str(objeto.pk) if getattr(objeto, 'pk', None) else ''
            log.objeto_repr = str(objeto)[:300]
        if dados_anteriores is not None:
            log.dados_anteriores = dados_anteriores
        if dados_novos is not None:
            log.dados_novos = dados_novos
        log.save()
    except Exception:
        pass
