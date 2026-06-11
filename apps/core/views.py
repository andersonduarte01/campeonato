from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import LoginForm, AlterarSenhaForm, UsuarioEditForm
from .models import Usuario
from .permissions import requer_perfil, APENAS_ADMIN


@login_required
def index_view(request):
    from apps.competicao.models import Competicao, Jogo, Gol
    from apps.equipe.models import Equipe, Atleta

    hoje = timezone.localdate()

    competicoes_ativas = Competicao.objects.filter(status='andamento').count()
    total_competicoes  = Competicao.objects.count()
    total_equipes      = Equipe.objects.count()
    total_atletas      = Atleta.objects.filter(situacao='APTO').count()
    partidas_hoje      = Jogo.objects.filter(data_hora__date=hoje).count()
    total_gols         = Gol.objects.count()

    proximas_partidas = (
        Jogo.objects
        .select_related('equipe_casa', 'equipe_fora', 'rodada__competicao')
        .filter(data_hora__gte=timezone.now(), finalizado=False, anulado=False)
        .order_by('data_hora')[:5]
    )

    ultimos_resultados = (
        Jogo.objects
        .select_related('equipe_casa', 'equipe_fora', 'rodada__competicao')
        .filter(finalizado=True)
        .order_by('-data_hora')[:6]
    )

    return render(request, 'core/index.html', {
        'competicoes_ativas': competicoes_ativas,
        'total_competicoes':  total_competicoes,
        'total_equipes':      total_equipes,
        'total_atletas':      total_atletas,
        'partidas_hoje':      partidas_hoje,
        'total_gols':         total_gols,
        'proximas_partidas':  proximas_partidas,
        'ultimos_resultados': ultimos_resultados,
    })


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

@requer_perfil(*APENAS_ADMIN)
def usuarios_lista_view(request):
    q = request.GET.get('q', '')
    qs = Usuario.objects.all().order_by('nome')
    if q:
        qs = qs.filter(nome__icontains=q) | qs.filter(email__icontains=q)
    return render(request, 'core/usuarios.html', {'usuarios': qs, 'q': q})


@requer_perfil(*APENAS_ADMIN)
def usuario_editar_view(request, pk):
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


@requer_perfil(*APENAS_ADMIN)
def usuario_toggle_ativo_view(request, pk):
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
