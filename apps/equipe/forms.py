from django import forms
from .models import Equipe, Atleta


class EquipeForm(forms.ModelForm):
    class Meta:
        model = Equipe
        fields = ('nome_equipe', 'escudo')
        widgets = {
            'nome_equipe': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da equipe'}),
        }


class AtletaForm(forms.ModelForm):
    class Meta:
        model = Atleta
        fields = ('nome', 'foto', 'equipe', 'data_nascimento', 'posicao')
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'data_nascimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'posicao': forms.Select(attrs={'class': 'form-select'}),
            'equipe': forms.Select(attrs={'class': 'form-select'}),
        }
