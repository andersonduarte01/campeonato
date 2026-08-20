from ..models import AuditoriaEvento


def registrar_evento(
    *, tipo, federacao=None, usuario=None, objeto=None,
    dados=None, ip=None, user_agent=None,
):
    """Cria um AuditoriaEvento. Falha silenciosa (não quebra o fluxo
    principal) — a auditoria é observabilidade, não regra de negócio.
    """
    kwargs = {
        'tipo': tipo,
        'federacao': federacao,
        'usuario': usuario,
        'dados': dados or {},
        'ip': ip,
        'user_agent': (user_agent or '')[:500],
    }
    if objeto is not None:
        opts = objeto._meta
        kwargs['objeto_tipo'] = f'{opts.app_label}.{opts.model_name}'
        kwargs['objeto_id'] = objeto.pk
    try:
        return AuditoriaEvento.objects.create(**kwargs)
    except Exception:
        # Não propaga: auditoria não deve quebrar a operação principal.
        return None


def extrair_request(request):
    """Extrai (ip, user_agent) de um request. Aceita None."""
    if request is None:
        return None, None
    ip = None
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        ip = xff.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    ua = request.META.get('HTTP_USER_AGENT', '')
    return ip, ua
