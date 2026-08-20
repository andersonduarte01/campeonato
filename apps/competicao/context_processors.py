def notificacoes_nao_lidas(request):
    return {'notificacoes_count': 0}


def is_admin_op(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'is_admin_op': False, 'is_arbitro_only': False, 'is_dirigente_only': False,
                'is_secretario_only': False}
    superadmin = getattr(user, 'is_admin', False)
    vinculo = getattr(request, 'vinculo', None)
    papel = vinculo.papel if vinculo else ''
    return {
        'is_admin_op':        superadmin or papel == 'ADMIN',
        'is_arbitro_only':    (not superadmin) and papel == 'ARB',
        'is_dirigente_only':  (not superadmin) and papel == 'DIR',
        'is_secretario_only': (not superadmin) and papel == 'SEC',
    }
