from django.urls import path, re_path

from . import views, views_cadastros as cad, views_google

urlpatterns = [
    path("", views.hoje, name="hoje"),
    path("tarefas/", views.tarefas, name="tarefas"),
    path("quadro/", views.quadro, name="quadro"),
    path("tarefas/nova/", views.tarefa_form, name="nova_tarefa"),
    path("tarefas/rapida/", views.criar_rapida, name="criar_rapida"),
    path("tarefas/<int:pk>/editar/", views.tarefa_form, name="editar_tarefa"),
    path("tarefas/<int:pk>/status/", views.mudar_status, name="mudar_status"),
    path("tarefas/<int:pk>/excluir/", views.excluir, name="excluir"),
    path("tarefas/restaurar/", views.restaurar, name="restaurar"),
    path("pessoas/", cad.pessoas, name="pessoas"),
    path("projetos/", cad.projetos, name="projetos"),
    path("mais/", cad.mais, name="mais"),
    path("configuracoes/", views_google.configuracoes, name="configuracoes"),
    path("sincronizar/", views_google.sincronizar, name="sincronizar"),
    path("google/conectar/", views_google.conectar_google, name="conectar_google"),
    path("google/desconectar/", views_google.desconectar_google, name="desconectar_google"),
    path("preferencias/concluir-ao-entregar/", views_google.preferencia_concluir_ao_entregar, name="pref_concluir"),
    # Só "pessoa" ou "projeto"; qualquer outra coisa é 404.
    re_path(r"^(?P<tipo>pessoa|projeto)/novo/$", cad.formulario, name="novo_cadastro"),
    re_path(r"^(?P<tipo>pessoa|projeto)/(?P<pk>\d+)/editar/$", cad.formulario, name="editar_cadastro"),
    re_path(r"^(?P<tipo>pessoa|projeto)/(?P<pk>\d+)/ativo/$", cad.alternar_ativo, name="alternar_ativo"),
]
