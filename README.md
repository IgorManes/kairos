# Kairos

App pessoal para organizar, num lugar só, as demandas do trabalho (e quem pediu cada uma), as reuniões aceitas no Google Agenda, as atividades da faculdade vindas do Google Classroom e os projetos pessoais.

Roda localmente no Windows, numa janela própria com ícone na área de trabalho.

> **Status:** em desenvolvimento (etapa 0: preparação do projeto). Veja o plano em [docs/ESPECIFICACAO.md](docs/ESPECIFICACAO.md).

## Tecnologias

- Python 3.13
- Django 5.2 LTS
- SQLite
- Templates HTML com Tailwind CSS e HTMX (a partir da etapa 2)

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

# 4. Conferir se está tudo certo
python manage.py check
```

Os dados (banco, token do Google, backups) ficam em `%LOCALAPPDATA%\Kairos\`, fora da pasta do código.

## Estrutura

```
config/     configurações do Django (settings, urls)
tarefas/    o app principal (modelos, telas, regras)
docs/       especificação e registro de decisões
```

## Desenvolvido com auxílio de IA

Este projeto foi desenvolvido com auxílio do Claude Code (IA da Anthropic). Eu defini os requisitos, revisei o código e tomei as decisões técnicas, registradas com os motivos em [docs/DECISOES.md](docs/DECISOES.md).
