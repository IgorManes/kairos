from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


# --- Listas de escolha -----------------------------------------------------
# No banco fica o código curto (1º valor); na tela aparece o rótulo (2º).


class Categoria(models.TextChoices):
    TRABALHO = "trabalho", "Trabalho"
    FACULDADE = "faculdade", "Faculdade"
    PESSOAL = "pessoal", "Pessoal"
    REUNIAO = "reuniao", "Reunião"


# Projeto usa as mesmas categorias, menos Reunião.
CATEGORIAS_PROJETO = [c for c in Categoria.choices if c[0] != Categoria.REUNIAO]


class Status(models.TextChoices):
    A_FAZER = "a_fazer", "A fazer"
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    AGUARDANDO = "aguardando", "Aguardando"
    CONCLUIDA = "concluida", "Concluída"
    CANCELADA = "cancelada", "Cancelada"


class Prioridade(models.TextChoices):
    BAIXA = "baixa", "Baixa"
    MEDIA = "media", "Média"
    ALTA = "alta", "Alta"
    URGENTE = "urgente", "Urgente"


class Origem(models.TextChoices):
    MANUAL = "manual", "Manual"
    GOOGLE_AGENDA = "google_agenda", "Google Agenda"
    GOOGLE_CLASSROOM = "google_classroom", "Google Classroom"


validar_cor = RegexValidator(
    r"^#[0-9a-fA-F]{6}$", "Use o formato #RRGGBB (ex.: #3b82f6)."
)


# --- Tabelas de apoio ------------------------------------------------------


class Pessoa(models.Model):
    """Quem pede demandas no trabalho."""

    nome = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    cor = models.CharField(max_length=7, blank=True, validators=[validar_cor])

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Projeto(models.Model):
    """Agrupa tarefas, principalmente pessoais."""

    nome = models.CharField(max_length=100)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS_PROJETO)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Disciplina(models.Model):
    """Turma do Classroom (criada pela sincronização)."""

    nome = models.CharField(max_length=200)
    classroom_id = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


# --- Tarefa ----------------------------------------------------------------


class Tarefa(models.Model):
    titulo = models.CharField(max_length=200)
    observacoes = models.TextField(blank=True)  # só local, o sync nunca mexe
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.A_FAZER
    )
    prioridade = models.CharField(
        max_length=20, choices=Prioridade.choices, default=Prioridade.MEDIA
    )

    prazo = models.DateField(null=True, blank=True)
    prazo_hora = models.TimeField(null=True, blank=True)
    inicio = models.DateTimeField(null=True, blank=True)  # só reuniões
    fim = models.DateTimeField(null=True, blank=True)  # só reuniões
    link_reuniao = models.URLField(blank=True)

    # PROTECT: não deixa apagar uma pessoa/disciplina que tem tarefas.
    solicitante = models.ForeignKey(
        Pessoa, on_delete=models.PROTECT, null=True, blank=True,
        related_name="tarefas",
    )
    projeto = models.ForeignKey(
        Projeto, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tarefas",
    )
    disciplina = models.ForeignKey(
        Disciplina, on_delete=models.PROTECT, null=True, blank=True,
        related_name="tarefas",
    )

    # Campos da sincronização com o Google
    origem = models.CharField(
        max_length=20, choices=Origem.choices, default=Origem.MANUAL
    )
    id_externo = models.CharField(max_length=255, blank=True)
    # Só Google Agenda: de qual agenda veio ("primary" ou o e-mail da agenda da empresa).
    agenda_id = models.CharField(max_length=255, blank=True)
    # Só Classroom: última situação da entrega vista (NEW, CREATED, TURNED_IN, RETURNED,
    # RECLAIMED_BY_STUDENT). O sync só mexe no status quando ela MUDA.
    estado_entrega = models.CharField(max_length=30, blank=True)
    link_externo = models.URLField(max_length=500, blank=True)
    descricao_externa = models.TextField(blank=True)  # sobrescrito a cada sync
    sincronizado_em = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    concluida_em = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["prazo", "-criado_em"]
        constraints = [
            # Impede importar o mesmo item do Google duas vezes.
            # Só vale quando id_externo está preenchido (tarefas manuais
            # têm id_externo vazio e não podem conflitar entre si).
            models.UniqueConstraint(
                fields=["origem", "id_externo"],
                condition=~Q(id_externo=""),
                name="tarefa_origem_id_externo_unico",
            ),
        ]

    def __str__(self):
        return self.titulo

    def clean(self):
        """Regras que valem para toda tarefa (forms e admin chamam isto)."""
        erros = {}
        trabalho = self.categoria == Categoria.TRABALHO
        reuniao = self.categoria == Categoria.REUNIAO

        if trabalho and not self.solicitante_id:
            erros["solicitante"] = "Tarefa de trabalho precisa de solicitante."
        if not trabalho and self.solicitante_id:
            erros["solicitante"] = "Só tarefas de trabalho têm solicitante."

        if reuniao and not self.inicio:
            erros["inicio"] = "Reunião precisa de horário de início."
        if not reuniao and (self.inicio or self.fim):
            erros["inicio"] = "Início e fim são só para reuniões."
        if self.inicio and self.fim and self.fim < self.inicio:
            erros["fim"] = "O fim não pode ser antes do início."

        if self.disciplina_id and self.categoria != Categoria.FACULDADE:
            erros["disciplina"] = "Disciplina só em tarefas de faculdade."

        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        # concluida_em funciona como memória do estado anterior:
        # se já está preenchido, a tarefa já estava concluída; não mexe.
        if self.status == Status.CONCLUIDA:
            if self.concluida_em is None:
                self.concluida_em = timezone.now()
        else:
            self.concluida_em = None

        # Se salvar só alguns campos incluindo o status, grava concluida_em junto.
        campos = kwargs.get("update_fields")
        if campos is not None and "status" in campos:
            kwargs["update_fields"] = set(campos) | {"concluida_em"}
        super().save(*args, **kwargs)

    @property
    def atrasada(self):
        """Calculado na hora (não é salvo): prazo passou e está em aberto."""
        if self.prazo is None:
            return False
        encerrada = self.status in (Status.CONCLUIDA, Status.CANCELADA)
        return not encerrada and self.prazo < timezone.localdate()

    @property
    def etiqueta_agenda(self):
        """Nome da agenda de empresa (ex.: "Invoga"); vazio para a agenda principal."""
        from django.conf import settings

        return next((a["nome"] for a in settings.GOOGLE_AGENDAS if a["id"] == self.agenda_id), "")

    @property
    def dias_atraso(self):
        """Quantos dias passou do prazo (0 se não está atrasada)."""
        if not self.atrasada:
            return 0
        return (timezone.localdate() - self.prazo).days


class EstadoSync(models.Model):
    """
    Estado da sincronização de cada fonte do Google (uma linha por agenda e,
    na etapa 5, uma para o Classroom). Mostrado na tela de Configurações.
    """

    fonte = models.CharField(max_length=255, unique=True)  # ex.: "agenda:primary"
    sync_token = models.TextField(blank=True)  # marca do Google para pedir só o que mudou
    ultimo_completo_em = models.DateTimeField(null=True, blank=True)  # 1 sync completo por dia
    ultimo_sync_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(blank=True)
    ultimo_erro_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "estado de sincronização"
        verbose_name_plural = "estados de sincronização"

    def __str__(self):
        return self.fonte


class Preferencias(models.Model):
    """Configurações do dono. Uma linha só (singleton): use Preferencias.atual()."""

    concluir_ao_entregar = models.BooleanField(
        default=True, help_text="Concluir a tarefa quando a atividade for entregue no Classroom."
    )

    class Meta:
        verbose_name = verbose_name_plural = "preferências"

    def __str__(self):
        return "Preferências"

    @classmethod
    def atual(cls):
        objeto, _ = cls.objects.get_or_create(pk=1)
        return objeto
