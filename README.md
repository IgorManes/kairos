# Kairos

App pessoal para organizar, num lugar só, as demandas do trabalho (e quem pediu cada uma), as reuniões aceitas no Google Agenda, as atividades da faculdade vindas do Google Classroom e os projetos pessoais.

Roda localmente no Windows, numa janela própria com ícone na área de trabalho.

> **Status:** em desenvolvimento. Prontos: telas (Hoje, Tarefas, Quadro, Pessoas, Projetos), sincronização com Google Agenda e Classroom, relatórios semanais em PDF. Próxima etapa: janela própria, atalho e backup. Veja o plano em [docs/ESPECIFICACAO.md](docs/ESPECIFICACAO.md).

## Tecnologias

- Python 3.13
- Django 5.2 LTS
- SQLite
- Templates HTML com Tailwind CSS 4 (executável standalone) e HTMX 2
- django-axes (proteção do login)

## Como rodar (desenvolvimento)

Pré-requisito: Python 3.13 instalado.

```powershell
# 1. Criar e ativar o ambiente virtual
py -3.13 -m venv venv
venv\Scripts\activate

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. Configurar o .env
copy .env.example .env
# gere uma chave e cole em DJANGO_SECRET_KEY:
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

# 4. Criar o banco e o usuário
python manage.py migrate
python manage.py createsuperuser

# 5. Gerar o CSS (baixa o Tailwind na primeira vez; não precisa de Node)
python manage.py tailwind build

# 6. Rodar (desenvolvimento)
python manage.py runserver
```

Durante o desenvolvimento, `python manage.py tailwind watch` (em outro terminal) regera o CSS a cada mudança nos templates.

Os dados (banco, token do Google, backups) ficam em `%LOCALAPPDATA%\Kairos\`, fora da pasta do código.

## Estrutura

```
config/     configurações do Django (settings, urls)
tarefas/    o app principal (modelos, telas, regras)
docs/       especificação e registro de decisões
```

## Desenvolvido com auxílio de IA

Este projeto foi desenvolvido com auxílio do Claude Code (IA da Anthropic). Eu defini os requisitos, revisei o código e tomei as decisões técnicas, registradas com os motivos em [docs/DECISOES.md](docs/DECISOES.md).
