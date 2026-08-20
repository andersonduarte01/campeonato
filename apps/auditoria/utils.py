from django.conf import settings


def get_client_ip(request):
    """Retorna o IP do cliente.

    Só respeita X-Forwarded-For se settings.USE_X_FORWARDED_HOST=True
    (indicativo de que o app está atrás de um proxy confiável). Caso
    contrário, usa REMOTE_ADDR — evita spoof do IP registrado no
    consentimento LGPD.
    """
    if getattr(settings, 'USE_X_FORWARDED_HOST', False):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
