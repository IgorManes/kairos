from django.urls import path

from . import views

urlpatterns = [
    path("", views.hoje, name="hoje"),
    path("tarefas/<int:pk>/status/", views.mudar_status, name="mudar_status"),
    path("tarefas/<int:pk>/excluir/", views.excluir, name="excluir"),
    path("tarefas/restaurar/", views.restaurar, name="restaurar"),
]
