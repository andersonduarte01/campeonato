from django.shortcuts import render
from django.views.generic import TemplateView
from ..competicao.models import Jogo


# Create your views here.

class Index(TemplateView):
    template_name = 'core/index.html'

