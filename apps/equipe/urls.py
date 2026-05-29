from django.urls import path
from . import views

app_name = 'equipe'

urlpatterns = [
    path('', views.EquipeListView.as_view(), name='lista'),
    path('nova/', views.EquipeCreateView.as_view(), name='criar'),
    path('<int:pk>/', views.EquipeDetailView.as_view(), name='detalhe'),
    path('<int:pk>/editar/', views.EquipeUpdateView.as_view(), name='editar'),
    path('<int:pk>/excluir/', views.EquipeDeleteView.as_view(), name='excluir'),
    path('<int:equipe_pk>/atleta/novo/', views.AtletaCreateView.as_view(), name='atleta_criar'),
    path('atleta/<int:pk>/editar/', views.AtletaUpdateView.as_view(), name='atleta_editar'),
    path('atleta/<int:pk>/excluir/', views.AtletaDeleteView.as_view(), name='atleta_excluir'),
]