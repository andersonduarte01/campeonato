from django import forms
from .models import Equipe, Atleta

_INPUT   = 'input input-bordered w-full'
_SELECT  = 'select select-bordered w-full'


class EquipeForm(forms.ModelForm):
    class Meta:
        model = Equipe
        fields = (
            'nome_equipe', 'escudo',
            'cidade', 'estado', 'estadio', 'tecnico',
            'fundacao', 'cor_uniforme_principal', 'cor_uniforme_alternativo',
        )
        widgets = {
            'nome_equipe':             forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Nome da equipe'}),
            'escudo':                  forms.ClearableFileInput(attrs={'class': 'file-input file-input-bordered w-full'}),
            'cidade':                  forms.TextInput(attrs={'class': _INPUT}),
            'estado':                  forms.Select(attrs={'class': _SELECT}),
            'estadio':                 forms.TextInput(attrs={'class': _INPUT}),
            'tecnico':                 forms.TextInput(attrs={'class': _INPUT}),
            'fundacao':                forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
            'cor_uniforme_principal':  forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Ex: Azul e Branco'}),
            'cor_uniforme_alternativo':forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Ex: Branco'}),
        }


class AtletaForm(forms.ModelForm):
    class Meta:
        model = Atleta
        fields = (
            'nome', 'foto', 'equipe', 'data_nascimento', 'posicao',
            'pe_dominante', 'altura', 'peso', 'naturalidade', 'situacao',
        )
        widgets = {
            'nome':           forms.TextInput(attrs={'class': _INPUT}),
            'foto':           forms.ClearableFileInput(attrs={'class': 'file-input file-input-bordered w-full'}),
            'data_nascimento':forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
            'posicao':        forms.Select(attrs={'class': _SELECT}),
            'equipe':         forms.Select(attrs={'class': _SELECT}),
            'pe_dominante':   forms.Select(attrs={'class': _SELECT}),
            'altura':         forms.NumberInput(attrs={'class': _INPUT, 'step': '0.01', 'min': '1', 'max': '2.5', 'placeholder': '1.80'}),
            'peso':           forms.NumberInput(attrs={'class': _INPUT, 'step': '0.1', 'min': '30', 'max': '200', 'placeholder': '75.0'}),
            'naturalidade':   forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Cidade / Estado'}),
            'situacao':       forms.Select(attrs={'class': _SELECT}),
        }
