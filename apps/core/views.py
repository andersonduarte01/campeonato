from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm


class ConviteUsuarioForm(PasswordResetForm):
    """Convite = reset de senha, mas aceita usuários sem senha utilizável
    (contas recém-criadas via set_unusable_password)."""

    def get_users(self, email):
        active_users = Usuario._default_manager.filter(
            email__iexact=email, is_active=True,
        )
        return (u for u in active_users)
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AlterarSenhaForm, LoginForm, UsuarioCriarForm, UsuarioAdminEditForm
from .models import Usuario, UsuarioFederacao
from .permissao import APENAS_ADMIN, PODE_SECRETARIAR, requer_papel


def _enviar_convite(request, email):
    """Dispara o e-mail padrão de reset de senha usado como 'defina sua senha'."""
    form = ConviteUsuarioForm({'email': email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name='core/email_convite_usuario.txt',
            subject_template_name='core/email_convite_subject.txt',
            html_email_template_name='core/email_convite_usuario.html',
        )
        return True
    return False


# ---------------------------------------------------------------------------
# Helpers de permissão para gestão de usuários
# ---------------------------------------------------------------------------

def _is_admin_op(request):
    """True se o operador é superusuário ou tem papel ADMIN na federação."""
    if request.user.is_admin:
        return True
    vinculo = getattr(request, 'vinculo', None)
    return bool(vinculo and vinculo.papel == UsuarioFederacao.ADMIN)


def _papeis_para_operador(request):
    """Papéis que o operador pode atribuir a outros usuários."""
    if _is_admin_op(request):
        return [p for p, _ in UsuarioFederacao.PAPEL_CHOICES]
    return [UsuarioFederacao.ARBITRO, UsuarioFederacao.DIRIGENTE]


def _pode_gerir_vinculo(request, vinculo):
    """Secretário só pode gerir vínculos de ARB e DIR."""
    if _is_admin_op(request):
        return True
    return vinculo.papel in (UsuarioFederacao.ARBITRO, UsuarioFederacao.DIRIGENTE)


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:index')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
            )
            if user is not None:
                login(request, user)
                return redirect(request.GET.get('next', 'core:index'))
            messages.error(request, 'E-mail ou senha inválidos.')
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('core:login')


# ---------------------------------------------------------------------------
# Seleção de federação (usuários com múltiplos vínculos)
# ---------------------------------------------------------------------------

@login_required(login_url='core:login')
def selecionar_federacao_view(request):
    vinculos = (
        UsuarioFederacao.objects
        .filter(usuario=request.user, ativo=True, federacao__ativa=True)
        .select_related('federacao')
        .order_by('federacao__nome')
    )

    if not vinculos.exists():
        messages.error(request, 'Você não possui vínculo com nenhuma federação ativa.')
        logout(request)
        return redirect('core:login')

    if request.method == 'POST':
        federacao_id = request.POST.get('federacao_id')
        vinculo = vinculos.filter(federacao_id=federacao_id).first()
        if vinculo:
            request.session['federacao_id'] = vinculo.federacao.id
            return redirect('core:index')
        messages.error(request, 'Federação inválida.')

    return render(request, 'core/selecionar_federacao.html', {'vinculos': vinculos})


# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------

@login_required(login_url='core:login')
def index_view(request):
    return redirect('competicao:dashboard')


# ---------------------------------------------------------------------------
# Gestão de usuários (admin da federação)
# ---------------------------------------------------------------------------

@requer_papel(*PODE_SECRETARIAR)
def usuarios_lista_view(request):
    q  = request.GET.get('q', '').strip()
    qs = (
        UsuarioFederacao.objects
        .filter(federacao=request.federacao)
        .select_related('usuario')
        .order_by('usuario__nome')
    )
    if q:
        qs = qs.filter(usuario__nome__icontains=q) | qs.filter(usuario__email__icontains=q)
    return render(request, 'core/usuarios.html', {
        'vinculos': qs,
        'q': q,
        'is_admin_op': _is_admin_op(request),
    })


@requer_papel(*PODE_SECRETARIAR)
def usuario_criar_view(request):
    papeis = _papeis_para_operador(request)
    form = UsuarioCriarForm(request.POST or None, papeis=papeis, federacao=request.federacao)
    if request.method == 'POST' and form.is_valid():
        email  = form.cleaned_data['email']
        nome   = form.cleaned_data.get('nome', '').strip()
        papel  = form.cleaned_data['papel']
        equipe = form.cleaned_data.get('equipe')

        usuario, criado = Usuario.objects.get_or_create(
            email=email,
            defaults={'nome': nome or email.split('@')[0]},
        )
        if criado:
            # Conta nova nasce sem senha utilizável; usuário define via e-mail
            usuario.set_unusable_password()
            usuario.save()

        vinculo, novo_vinculo = UsuarioFederacao.objects.get_or_create(
            usuario=usuario, federacao=request.federacao,
            defaults={'papel': papel, 'equipe': equipe},
        )
        if not novo_vinculo:
            vinculo.papel = papel
            vinculo.ativo = True
            vinculo.equipe = equipe
            vinculo.save(update_fields=['papel', 'ativo', 'equipe'])

        if criado:
            _enviar_convite(request, email)
            messages.success(
                request,
                f'Usuário {email} criado e convite enviado por e-mail. '
                'Ele deve seguir o link recebido para definir a senha.',
            )
        else:
            messages.success(request, f'Usuário {email} vinculado à {request.federacao.nome}.')
        return redirect('core:usuarios_lista')

    return render(request, 'core/usuario_criar.html', {
        'form': form,
        'is_admin_op': _is_admin_op(request),
    })


@requer_papel()
def usuario_editar_view(request, pk):
    vinculo = get_object_or_404(
        UsuarioFederacao, usuario__pk=pk, federacao=request.federacao,
    )
    editando_proprio_perfil = vinculo.usuario == request.user
    if not editando_proprio_perfil and not _pode_gerir_vinculo(request, vinculo):
        messages.error(request, 'Secretários só podem editar árbitros e dirigentes.')
        return redirect('core:usuarios_lista')

    usuario = vinculo.usuario
    # Ao editar o próprio perfil, o campo papel fica fixo (impede auto-promoção)
    papeis = _papeis_para_operador(request) if not editando_proprio_perfil else [vinculo.papel]

    # Destino após salvar: volta para lista (admins/sec) ou painel próprio (outros papéis)
    def _redirect_pos_save():
        if _is_admin_op(request) or not editando_proprio_perfil:
            return redirect('core:usuarios_lista')
        return redirect('competicao:dashboard')

    if request.method == 'POST':
        post_data = request.POST.copy()
        if editando_proprio_perfil:
            post_data['papel'] = vinculo.papel
        form = UsuarioAdminEditForm(post_data, papeis=papeis, federacao=request.federacao)
        if form.is_valid():
            usuario.nome = form.cleaned_data['nome']
            if not editando_proprio_perfil:
                usuario.is_active = form.cleaned_data['conta_ativa']
                vinculo.papel = form.cleaned_data['papel']
                vinculo.ativo = form.cleaned_data['ativo_vinculo']
                vinculo.equipe = form.cleaned_data.get('equipe')
                vinculo.save(update_fields=['papel', 'ativo', 'equipe'])
            usuario.save(update_fields=['nome', 'is_active'])
            messages.success(request, 'Perfil atualizado com sucesso.')
            return _redirect_pos_save()
    else:
        form = UsuarioAdminEditForm(initial={
            'nome':          usuario.nome,
            'papel':         vinculo.papel,
            'equipe':        vinculo.equipe_id,
            'ativo_vinculo': vinculo.ativo,
            'conta_ativa':   usuario.is_active,
        }, papeis=papeis, federacao=request.federacao)

    # Ao editar o próprio perfil: oculta campos de controle (ativo/conta)
    if editando_proprio_perfil:
        form.fields['ativo_vinculo'].widget = form.fields['ativo_vinculo'].hidden_widget()
        form.fields['conta_ativa'].widget   = form.fields['conta_ativa'].hidden_widget()
        form.fields['papel'].widget.attrs['disabled'] = True

    return render(request, 'core/usuario_editar.html', {
        'form': form,
        'usuario': usuario,
        'vinculo': vinculo,
        'is_admin_op': _is_admin_op(request),
        'editando_proprio_perfil': editando_proprio_perfil,
    })


@requer_papel(*PODE_SECRETARIAR)
def usuario_toggle_ativo_view(request, pk):
    vinculo = get_object_or_404(
        UsuarioFederacao, usuario__pk=pk, federacao=request.federacao,
    )
    if not _pode_gerir_vinculo(request, vinculo):
        messages.error(request, 'Secretários só podem gerir árbitros e dirigentes.')
        return redirect('core:usuarios_lista')
    if request.method == 'POST':
        vinculo.ativo = not vinculo.ativo
        vinculo.save(update_fields=['ativo'])
        status = 'ativado' if vinculo.ativo else 'desativado'
        messages.success(request, f'Vínculo de {vinculo.usuario.email} {status}.')
    return redirect('core:usuarios_lista')


@requer_papel(*PODE_SECRETARIAR)
def usuario_remover_vinculo_view(request, pk):
    vinculo = get_object_or_404(
        UsuarioFederacao, usuario__pk=pk, federacao=request.federacao,
    )
    if not _pode_gerir_vinculo(request, vinculo):
        messages.error(request, 'Secretários só podem remover árbitros e dirigentes.')
        return redirect('core:usuarios_lista')
    if vinculo.usuario == request.user:
        messages.error(request, 'Você não pode remover o seu próprio vínculo.')
        return redirect('core:usuarios_lista')
    if request.method == 'POST':
        usuario = vinculo.usuario
        email = usuario.email
        vinculo.delete()
        outros_vinculos = UsuarioFederacao.objects.filter(usuario=usuario).exists()
        if not outros_vinculos:
            usuario.is_active = False
            usuario.save(update_fields=['is_active'])
            messages.success(request, f'{email} removido desta federação e conta desativada (sem outros vínculos).')
        else:
            messages.success(request, f'{email} removido desta federação.')
    return redirect('core:usuarios_lista')


# ---------------------------------------------------------------------------
# Alterar senha
# ---------------------------------------------------------------------------

@login_required(login_url='core:login')
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
