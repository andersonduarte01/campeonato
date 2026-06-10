from django.contrib.auth.signals import user_logged_in, user_logged_out


def _on_logged_in(sender, request, user, **kwargs):
    from .utils import registrar_auditoria
    registrar_auditoria(
        request, 'login',
        descricao=f'Login realizado por {user.email}',
        objeto=user,
    )


def _on_logged_out(sender, request, user, **kwargs):
    if user is None:
        return
    from .utils import registrar_auditoria
    registrar_auditoria(
        request, 'logout',
        descricao=f'Logout realizado por {user.email}',
        objeto=user,
    )


user_logged_in.connect(_on_logged_in)
user_logged_out.connect(_on_logged_out)
