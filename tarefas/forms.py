from django import forms
from django.db.models import Q

from .models import Categoria, Disciplina, Origem, Pessoa, Preferencias, Prioridade, Projeto, Status, Tarefa

FORMATO_DATA_HORA = "%Y-%m-%dT%H:%M"  # formato do <input type="datetime-local">

# Campos que vêm do Google: somente leitura nos itens sincronizados.
CAMPOS_DO_GOOGLE = ["titulo", "categoria", "prazo", "prazo_hora", "disciplina", "inicio", "fim", "link_reuniao"]


def pessoa_eu():
    """A Pessoa que representa o dono (decisão: "Eu" como solicitante das próprias demandas)."""
    return Pessoa.objects.filter(nome__iexact="Eu").first()


class FiltroTarefasForm(forms.Form):
    """
    Filtros da tela Tarefas, lidos da URL (?categoria=trabalho&q=...).
    Valor inválido é descartado (vira "sem filtro") em vez de quebrar a página.
    """

    STATUS_ABERTAS, STATUS_TODAS = "", "todas"
    ORDENS = [("prazo", "Prazo"), ("prioridade", "Prioridade"), ("recentes", "Mais recentes")]

    q = forms.CharField(required=False, max_length=100, label="Buscar")
    categoria = forms.ChoiceField(
        required=False, label="Categoria", choices=[("", "Todas as categorias"), *Categoria.choices]
    )
    status = forms.ChoiceField(
        required=False, label="Status", choices=[(STATUS_ABERTAS, "Abertas"), (STATUS_TODAS, "Todas"), *Status.choices]
    )
    prioridade = forms.ChoiceField(
        required=False, label="Prioridade", choices=[("", "Qualquer prioridade"), *Prioridade.choices]
    )
    solicitante = forms.ModelChoiceField(Pessoa.objects.all(), required=False, empty_label="Qualquer solicitante")
    projeto = forms.ModelChoiceField(Projeto.objects.all(), required=False, empty_label="Qualquer projeto")
    disciplina = forms.ModelChoiceField(Disciplina.objects.all(), required=False, empty_label="Qualquer disciplina")
    ordem = forms.ChoiceField(required=False, label="Ordenar por", choices=ORDENS)

    def __init__(self, dados, *args, **kwargs):
        super().__init__(dados, *args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "input input-sm"
        self.fields["q"].widget.attrs.update({"placeholder": "Buscar no título e nas observações…", "type": "search"})

    def filtros(self):
        """Só os filtros válidos. Os inválidos somem, cada um isoladamente."""
        self.is_valid()
        validos = {}
        for nome in self.fields:
            if nome in self.errors:
                continue
            valor = self.cleaned_data.get(nome)
            if valor not in (None, ""):
                validos[nome] = valor
        return validos


class TarefaForm(forms.ModelForm):
    class Meta:
        model = Tarefa
        fields = [
            "titulo",
            "categoria",
            "solicitante",
            "disciplina",
            "projeto",
            "status",
            "prioridade",
            "prazo",
            "prazo_hora",
            "inicio",
            "fim",
            "link_reuniao",
            "observacoes",
        ]
        labels = {
            "titulo": "Título",
            "solicitante": "Solicitante",
            "disciplina": "Disciplina",
            "projeto": "Projeto",
            "status": "Status",
            "prioridade": "Prioridade",
            "prazo": "Prazo",
            "prazo_hora": "Hora",
            "inicio": "Início",
            "fim": "Fim",
            "link_reuniao": "Link da reunião",
            "observacoes": "Observações",
        }
        widgets = {
            "categoria": forms.RadioSelect,
            "prazo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "prazo_hora": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=FORMATO_DATA_HORA),
            "fim": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=FORMATO_DATA_HORA),
            "observacoes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        t = self.instance
        self.fields["categoria"].choices = Categoria.choices  # sem a opção vazia "-----"

        # Seletores mostram só ativos (mais o atual, se tiver sido desativado depois).
        self.fields["solicitante"].queryset = Pessoa.objects.filter(Q(ativo=True) | Q(pk=t.solicitante_id))
        self.fields["disciplina"].queryset = Disciplina.objects.filter(Q(ativo=True) | Q(pk=t.disciplina_id))
        self.fields["projeto"].queryset = Projeto.objects.filter(Q(ativo=True) | Q(pk=t.projeto_id))
        self.fields["projeto"].empty_label = "Nenhum"
        self.fields["disciplina"].empty_label = "Nenhuma"

        # "Cancelada" só aparece se a tarefa já estiver cancelada (cancelar é pelo menu).
        self.fields["status"].choices = [
            (v, r) for v, r in Status.choices if v != Status.CANCELADA or t.status == Status.CANCELADA
        ]
        for nome in ("inicio", "fim"):
            self.fields[nome].input_formats = [FORMATO_DATA_HORA]

        for campo in self.fields.values():
            if not isinstance(campo.widget, forms.RadioSelect):
                campo.widget.attrs.setdefault("class", "input")

        # Itens do Google: o Django ignora o que vier do navegador nesses campos.
        if t.pk and t.origem != Origem.MANUAL:
            for nome in CAMPOS_DO_GOOGLE:
                self.fields[nome].disabled = True

    def clean(self):
        dados = super().clean()
        categoria = dados.get("categoria")
        # Campos escondidos continuam sendo enviados; limpa os que não valem para a categoria.
        if categoria != Categoria.TRABALHO:
            dados["solicitante"] = None
        if categoria != Categoria.FACULDADE:
            dados["disciplina"] = None
        if categoria != Categoria.REUNIAO:
            dados["inicio"] = dados["fim"] = None
            dados["link_reuniao"] = ""
        return dados


class PessoaForm(forms.ModelForm):
    class Meta:
        model = Pessoa
        fields = ["nome", "cor", "ativo"]
        labels = {"nome": "Nome", "cor": "Cor", "ativo": "Ativa (aparece nos seletores)"}
        widgets = {"cor": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome"].widget.attrs["class"] = "input"
        self.fields["cor"].widget.attrs["class"] = "input input-cor"
        if not self.instance.pk:
            self.initial.setdefault("cor", "#8b5cf6")


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = ["nome", "categoria", "ativo"]
        labels = {"nome": "Nome", "categoria": "Categoria", "ativo": "Ativo (aparece nos seletores)"}
        widgets = {"categoria": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome"].widget.attrs["class"] = "input"
        self.fields["categoria"].choices = [c for c in Categoria.choices if c[0] != Categoria.REUNIAO]
        if not self.instance.pk:
            self.initial.setdefault("categoria", Categoria.PESSOAL)


class PreferenciasNotificacaoForm(forms.ModelForm):
    class Meta:
        model = Preferencias
        fields = [
            "avisar_reuniao",
            "minutos_antes_reuniao",
            "avisar_prazos",
            "hora_aviso_prazos",
            "avisar_atrasadas",
            "avisar_classroom",
            "avisar_resumo",
        ]
        widgets = {"hora_aviso_prazos": forms.TimeInput(attrs={"type": "time"}, format="%H:%M")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["minutos_antes_reuniao"].min_value = 1
        self.fields["minutos_antes_reuniao"].max_value = 120
        self.fields["minutos_antes_reuniao"].widget.attrs.update({"class": "input input-sm w-20", "min": 1, "max": 120})
        self.fields["hora_aviso_prazos"].widget.attrs["class"] = "input input-sm w-28"
