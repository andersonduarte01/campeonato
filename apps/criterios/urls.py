from django.urls import path
from . import views

app_name = 'criterios'

urlpatterns = [
    # Biblioteca de formatos
    path('formatos/', views.FormatoLista.as_view(), name='formato_lista'),
    path('formatos/add/', views.FormatoAdd.as_view(), name='formato_add'),
    path('formatos/<int:pk>/edit/', views.FormatoEdit.as_view(), name='formato_edit'),

    # Criar e vincular formato diretamente a uma competição
    path('formato/add/<int:pk>/', views.FormatoAdd.as_view(), name='formato_add_comp'),
    # Vincular formato existente a uma competição
    path('formato/vincular/<int:pk>/', views.VincularFormato.as_view(), name='formato_vincular'),

    # Biblioteca de critérios
    path('criterios/', views.CriterioLista.as_view(), name='criterio_lista'),
    path('criterios/add/', views.CriterioAdd.as_view(), name='criterio_add'),
    path('criterios/<int:pk>/edit/', views.CriterioEdit.as_view(), name='criterio_edit'),

    # Criar e vincular critério diretamente a uma competição
    path('adicionar/<int:pk>/', views.CriterioAdd.as_view(), name='criterio_add_comp'),
    # Vincular critério existente a uma competição
    path('criterio/vincular/<int:pk>/', views.VincularCriterio.as_view(), name='criterio_vincular'),
]
