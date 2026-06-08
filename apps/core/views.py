from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView

from .forms import LoginForm, AlterarSenhaForm, UsuarioEditForm
from .models import Usuario


def _is_admin(user):
    return user.is_admin or user.perfil == Usuario.ADMIN


class Index(TemplateView):
    template_name = 'core/index.html'


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:index')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next', '/')
                return redirect(next_url)
            else:
                messages.error(request, 'E-mail ou senha inválidos.')
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('core:login')


# ---------------------------------------------------------------------------
# Gestão de usuários (admin only)
# ---------------------------------------------------------------------------

@login_required
def usuarios_lista_view(request):
    if not _is_admin(request.user):
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('core:index')
    q = request.GET.get('q', '')
    qs = Usuario.objects.all().order_by('nome')
    if q:
        qs = qs.filter(nome__icontains=q) | qs.filter(email__icontains=q)
    return render(request, 'core/usuarios.html', {'usuarios': qs, 'q': q})


@login_required
def usuario_editar_view(request, pk):
    if not _is_admin(request.user):
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('core:index')
    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        form = UsuarioEditForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, f'Usuário {usuario.email} atualizado.')
            return redirect('core:usuarios_lista')
    else:
        form = UsuarioEditForm(instance=usuario)
    return render(request, 'core/usuario_editar.html', {'form': form, 'usuario': usuario})


@login_required
def usuario_toggle_ativo_view(request, pk):
    if not _is_admin(request.user):
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('core:index')
    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=['is_active'])
        status = 'ativado' if usuario.is_active else 'desativado'
        messages.success(request, f'Usuário {usuario.email} {status}.')
    return redirect('core:usuarios_lista')


# ---------------------------------------------------------------------------
# Alterar senha
# ---------------------------------------------------------------------------

@login_required
def alterar_senha_view(request):
    if request.method == 'POST':
        form = AlterarSenhaForm(request.POST)
        if form.is_valid():
            if not request.user.check_password(form.cleaned_data['senha_atual']):
                form.add_error('senha_atual', 'Senha atual incorreta.')
            else:
                request.user.set_password(form.cleaned_data['senha_nova'])
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Senha alterada com sucesso.')
                return redirect('core:index')
    else:
        form = AlterarSenhaForm()
    return render(request, 'core/alterar_senha.html', {'form': form})
