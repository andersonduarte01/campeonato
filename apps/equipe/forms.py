from django import forms
from .models import Equipe, Atleta

_INPUT  = 'form-input'
_SELECT = 'form-select'


class EquipeForm(forms.ModelForm):
    class Meta:
        model  = Equipe
        fields = (
            'nome_equipe', 'sigla', 'escudo',
            'cidade', 'estado', 'estadio', 'tecnico',
            'fundacao', 'data_filiacao', 'situacao',
            'cor_uniforme_principal', 'cor_uniforme_alternativo',
            'telefone', 'instagram', 'facebook',
        )
        widgets = {
            'nome_equipe':              forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Nome da equipe'}),
            'sigla':                    forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Ex: FLU'}),
            'escudo':                   forms.ClearableFileInput(attrs={'class': 'form-file'}),
            'cidade':                   forms.TextInput(attrs={'class': _INPUT}),
            'estado':                   forms.Select(attrs={'class': _SELECT}),
            'estadio':                  forms.TextInput(attrs={'class': _INPUT}),
            'tecnico':                  forms.TextInput(attrs={'class': _INPUT}),
            'fundacao':                 forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'data_filiacao':            forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'situacao':                 forms.Select(attrs={'class': _SELECT}),
            'cor_uniforme_principal':   forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Ex: Azul e Branco'}),
            'cor_uniforme_alternativo': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Ex: Branco'}),
            'telefone':                 forms.TextInput(attrs={'class': _INPUT, 'placeholder': '(00) 00000-0000'}),
            'instagram':                forms.TextInput(attrs={'class': _INPUT, 'placeholder': '@usuario'}),
            'facebook':                 forms.TextInput(attrs={'class': _INPUT}),
        }


class EquipeDirigenteForm(forms.ModelForm):
    """Campos que o dirigente pode editar na própria equipe."""
    class Meta:
        model  = Equipe
        fields = (
            'escudo', 'tecnico', 'estadio',
            'cidade', 'estado', 'fundacao',
            'cor_uniforme_principal', 'cor_uniforme_alternativo',
            'telefone', 'instagram', 'facebook',
        )
        widgets = {
            'escudo':                   forms.ClearableFileInput(attrs={'class': 'form-file'}),
            'tecnico':                  forms.TextInput(attrs={'class': _INPUT}),
            'estadio':                  forms.TextInput(attrs={'class': _INPUT}),
            'cidade':                   forms.TextInput(attrs={'class': _INPUT}),
            'estado':                   forms.Select(attrs={'class': _SELECT}),
            'fundacao':                 forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'cor_uniforme_principal':   forms.TextInput(attrs={'class': _INPUT}),
            'cor_uniforme_alternativo': forms.TextInput(attrs={'class': _INPUT}),
            'telefone':                 forms.TextInput(attrs={'class': _INPUT}),
            'instagram':                forms.TextInput(attrs={'class': _INPUT}),
            'facebook':                 forms.TextInput(attrs={'class': _INPUT}),
        }


class AtletaForm(forms.ModelForm):
    class Meta:
        model  = Atleta
        fields = (
            'nome', 'foto', 'data_nascimento', 'posicao',
            'pe_dominante', 'altura', 'peso', 'naturalidade', 'situacao',
        )
        widgets = {
            'nome':            forms.TextInput(attrs={'class': _INPUT}),
            'foto':            forms.ClearableFileInput(attrs={'class': 'form-file'}),
            'data_nascimento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': _INPUT}),
            'posicao':         forms.Select(attrs={'class': _SELECT}),
            'equipe':          forms.Select(attrs={'class': _SELECT}),
            'pe_dominante':    forms.Select(attrs={'class': _SELECT}),
            'altura':          forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': '1', 'max': '2.5', 'placeholder': '1.80'}),
            'peso':            forms.NumberInput(attrs={'class': _INPUT, 'step': '0.1', 'min': '30', 'max': '200', 'placeholder': '75.0'}),
            'naturalidade':    forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Cidade / Estado'}),
            'situacao':        forms.Select(attrs={'class': _SELECT}),
        }

    def __init__(self, *args, federacao=None, papel=None, **kwargs):
        super().__init__(*args, **kwargs)
        if papel == 'DIR':
            self.fields.pop('situacao', None)
