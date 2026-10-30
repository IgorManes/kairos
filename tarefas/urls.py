from django.urls import path

from . import views

urlpatterns = [
    path("", views.hoje, name="hoje"),
    path("tarefas/nova/", views.tarefa_form, name="nova_tarefa"),
    path("tarefas/rapida/", views.criar_rapida, name="criar_rapida"),
    path("tarefas/<int:pk>/editar/", views.tarefa_form, name="editar_tarefa"),
    path("tarefas/<int:pk>/status/", views.mudar_status, name="mudar_status"),
    path("tarefas/<int:pk>/excluir/", views.excluir, name="excluir"),
    path("tarefas/restaurar/", views.restaurar, name="restaurar"),
]
