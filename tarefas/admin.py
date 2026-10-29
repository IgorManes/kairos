from django.contrib import admin

from .models import Disciplina, Pessoa, Projeto, Tarefa


@admin.register(Pessoa)
class PessoaAdmin(admin.ModelAdmin):
    list_display = ["nome", "ativo", "cor"]
    list_filter = ["ativo"]
    search_fields = ["nome"]


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = ["nome", "categoria", "ativo"]
    list_filter = ["categoria", "ativo"]
    search_fields = ["nome"]


@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ["nome", "classroom_id", "ativo"]
    list_filter = ["ativo"]
    search_fields = ["nome"]


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = [
        "titulo", "categoria", "status", "prioridade", "prazo",
        "solicitante", "origem",
    ]
    list_filter = ["categoria", "status", "prioridade", "origem", "solicitante"]
    search_fields = ["titulo", "observacoes"]
    date_hierarchy = "prazo"
    readonly_fields = ["concluida_em", "criado_em", "atualizado_em", "sincronizado_em"]
    fieldsets = [
        (None, {"fields": ["titulo", "categoria", "status", "prioridade", "observacoes"]}),
        ("Prazo e horário", {"fields": ["prazo", "prazo_hora", "inicio", "fim", "link_reuniao"]}),
        ("Vínculos", {"fields": ["solicitante", "projeto", "disciplina"]}),
        ("Google", {
            "classes": ["collapse"],
            "fields": ["origem", "id_externo", "link_externo", "descricao_externa", "sincronizado_em"],
        }),
        ("Datas", {"fields": ["criado_em", "atualizado_em", "concluida_em"]}),
    ]
