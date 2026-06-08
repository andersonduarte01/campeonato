from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError

from ..core.models import Usuario


_INPUT  = 'input input-bordered w-full'
_SELECT = 'select select-bordered w-full'


class UsuarioEditForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ('nome', 'perfil', 'is_active')
        widgets = {
            'nome':   forms.TextInput(attrs={'class': _INPUT}),
            'perfil': forms.Select(attrs={'class': _SELECT}),
        }
        labels = {
            'is_active': 'Conta ativa',
        }


class AlterarSenhaForm(forms.Form):
    senha_atual = forms.CharField(
        label='Senha atual',
        widget=forms.PasswordInput(attrs={'class': _INPUT}),
    )
    senha_nova = forms.CharField(
        label='Nova senha',
        widget=forms.PasswordInput(attrs={'class': _INPUT}),
        min_length=6,
    )
    senha_nova2 = forms.CharField(
        label='Confirme a nova senha',
        widget=forms.PasswordInput(attrs={'class': _INPUT}),
    )

    def clean_senha_nova2(self):
        s1 = self.cleaned_data.get('senha_nova')
        s2 = self.cleaned_data.get('senha_nova2')
        if s1 and s2 and s1 != s2:
            raise ValidationError('As senhas não coincidem.')
        return s2


class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label='Senha', widget=forms.PasswordInput(attrs={'class': _INPUT}))
    password2 = forms.CharField(label='Confirme a senha', widget=forms.PasswordInput(attrs={'class': _INPUT}))

    class Meta:
        model = Usuario
        fields = ('email', 'nome')

    def __init__(self, *args, **kwargs):
        super(UserCreationForm, self).__init__(*args, **kwargs)
        self.fields['nome'].label = "Nome"

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Senhas não coincidem.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = Usuario
        fields = ('email', 'password', 'nome', 'is_active', 'is_admin')


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={'class': _INPUT, 'autofocus': True, 'placeholder': 'seu@email.com'}),
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': _INPUT, 'placeholder': '••••••••'}),
    )
