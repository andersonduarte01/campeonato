def notificacoes_nao_lidas(request):
    if request.user.is_authenticated:
        from .models import Notificacao
        count = Notificacao.objects.filter(usuario=request.user, lida=False).count()
        return {'notificacoes_count': count}
    return {'notificacoes_count': 0}
