from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index_view, name='index'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),

    # Alterar senha
    path('auth/alterar-senha/', views.alterar_senha_view, name='alterar_senha'),

    # Recuperação de senha por e-mail (Django built-in)
    path('auth/recuperar-senha/', auth_views.PasswordResetView.as_view(
        template_name='core/password_reset.html',
        email_template_name='core/password_reset_email.html',
        subject_template_name='core/password_reset_subject.txt',
    ), name='password_reset'),
    path('auth/recuperar-senha/enviado/', auth_views.PasswordResetDoneView.as_view(
        template_name='core/password_reset_done.html',
    ), name='password_reset_done'),
    path('auth/recuperar-senha/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='core/password_reset_confirm.html',
    ), name='password_reset_confirm'),
    path('auth/recuperar-senha/concluido/', auth_views.PasswordResetCompleteView.as_view(
        template_name='core/password_reset_complete.html',
    ), name='password_reset_complete'),

    # Gestão de usuários
    path('usuarios/', views.usuarios_lista_view, name='usuarios_lista'),
    path('usuarios/<int:pk>/editar/', views.usuario_editar_view, name='usuario_editar'),
    path('usuarios/<int:pk>/toggle-ativo/', views.usuario_toggle_ativo_view, name='usuario_toggle_ativo'),
]
