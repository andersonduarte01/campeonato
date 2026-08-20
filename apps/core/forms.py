from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Usuario, UsuarioFederacao
from apps.equipe.models import Equipe

_INPUT    = 'form-input'
_SELECT   = 'form-select'
_CHECKBOX = 'form-checkbox'


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={
            'class': _INPUT, 'autofocus': True, 'placeholder': 'seu@email.com',
        }),
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': _INPUT, 'placeholder': '••••••••'}),
    )


class AlterarSenhaForm(forms.Form):
    senha_atual = forms.CharField(
        label='Senha atual',
        widget=forms.PasswordInput(attrs={'class': _INPUT}),
    )
    senha_nova = forms.CharField(
        label='Nova senha',
        widget=forms.PasswordInput(attrs={'class': _INPUT}),
    )
    senha_nova2 = forms.CharField(
        label='Confirme a nova senha',
        widget=forms.PasswordInput(attrs={'class': _INPUT}),
    )

    def clean_senha_nova(self):
        # Aplica os AUTH_PASSWORD_VALIDATORS configurados em settings.
        senha = self.cleaned_data.get('senha_nova', '')
        validate_password(senha)
        return senha

    def clean_senha_nova2(self):
        s1 = self.cleaned_data.get('senha_nova')
        s2 = self.cleaned_data.get('senha_nova2')
        if s1 and s2 and s1 != s2:
            raise ValidationError('As senhas não coincidem.')
        return s2


class UsuarioEditForm(forms.ModelForm):
    class Meta:
        model   = Usuario
        fields  = ('nome', 'is_active')
        widgets = {
            'nome': forms.TextInput(attrs={'class': _INPUT}),
        }
        labels = {'is_active': 'Conta ativa'}


class UsuarioFederacaoForm(forms.ModelForm):
    """Vincula ou edita o papel de um usuário em uma federação."""
    class Meta:
        model   = UsuarioFederacao
        fields  = ('papel', 'ativo')
        widgets = {
            'papel': forms.Select(attrs={'class': _SELECT}),
        }


class UsuarioCriarForm(forms.Form):
    """Cria ou vincula um usuário à federação.

    Contas novas nascem sem senha (set_unusable_password); um e-mail de
    convite é enviado ao endereço informado com link para definir a
    senha (fluxo padrão de PasswordReset).
    """
    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={'class': _INPUT, 'placeholder': 'usuario@email.com'}),
    )
    nome = forms.CharField(
        label='Nome completo',
        widget=forms.TextInput(attrs={'class': _INPUT}),
        required=False,
    )
    papel = forms.ChoiceField(
        label='Papel',
        choices=UsuarioFederacao.PAPEL_CHOICES,
        widget=forms.Select(attrs={'class': _SELECT, 'id': 'id_papel'}),
    )
    equipe = forms.ModelChoiceField(
        label='Clube gerenciado',
        queryset=Equipe.objects.none(),
        required=False,
        empty_label='— selecione o clube —',
        widget=forms.Select(attrs={'class': _SELECT}),
    )

    def __init__(self, *args, papeis=None, federacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if papeis is not None:
            self.fields['papel'].choices = [
                (p, l) for p, l in UsuarioFederacao.PAPEL_CHOICES if p in papeis
            ]
        if federacao is not None:
            self.fields['equipe'].queryset = Equipe.objects.filter(
                federacao=federacao,
            ).exclude(situacao=Equipe.SITUACAO_DESFILIADO).order_by('nome_equipe')


class UsuarioAdminEditForm(forms.Form):
    """Edita dados do usuário e seu papel na federação."""
    nome = forms.CharField(
        label='Nome completo',
        widget=forms.TextInput(attrs={'class': _INPUT}),
    )
    papel = forms.ChoiceField(
        label='Papel',
        choices=UsuarioFederacao.PAPEL_CHOICES,
        widget=forms.Select(attrs={'class': _SELECT, 'id': 'id_papel'}),
    )
    equipe = forms.ModelChoiceField(
        label='Clube gerenciado',
        queryset=Equipe.objects.none(),
        required=False,
        empty_label='— selecione o clube —',
        widget=forms.Select(attrs={'class': _SELECT}),
    )
    ativo_vinculo = forms.BooleanField(
        label='Vínculo ativo nesta federação',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': _CHECKBOX}),
    )
    conta_ativa = forms.BooleanField(
        label='Conta ativa (acesso ao sistema)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': _CHECKBOX}),
    )

    def __init__(self, *args, papeis=None, federacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if papeis is not None:
            self.fields['papel'].choices = [
                (p, l) for p, l in UsuarioFederacao.PAPEL_CHOICES if p in papeis
            ]
        if federacao is not None:
            self.fields['equipe'].queryset = Equipe.objects.filter(
                federacao=federacao,
            ).exclude(situacao=Equipe.SITUACAO_DESFILIADO).order_by('nome_equipe')


# ── Formulários do admin do Django ─────────────────────────────────────────

class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Senha', widget=forms.PasswordInput(attrs={'class': _INPUT}),
    )
    password2 = forms.CharField(
        label='Confirme a senha', widget=forms.PasswordInput(attrs={'class': _INPUT}),
    )

    class Meta:
        model  = Usuario
        fields = ('email', 'nome')

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError('As senhas não coincidem.')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model  = Usuario
        fields = ('email', 'password', 'nome', 'is_active', 'is_admin')
