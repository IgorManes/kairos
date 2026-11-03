"""Rotas do mini-site do gestor (internet, via Funnel). Só isto existe lá: qualquer outro endereço é 404."""

from django.urls import path

from tarefas import views_gestor

urlpatterns = [
    path("", views_gestor.painel, name="gestor_painel"),
    path("entrar/", views_gestor.entrar, name="gestor_entrar"),
    path("sair/", views_gestor.sair, name="gestor_sair"),
]
