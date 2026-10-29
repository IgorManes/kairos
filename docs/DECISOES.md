# Registro de decisões

Formato: contexto → escolha → motivo.

## Etapa 0: Preparação (2026-10-29)

- **Nome do app** → **Kairos** → nome curto; usado na pasta de dados (`%LOCALAPPDATA%\Kairos\`), na janela e no ícone.
- **Versão do Python** (a especificação pedia 3.12; o PC tinha só 3.13) → **Python 3.13** → já instalado e suportado por todas as bibliotecas previstas. O que importa é ter a mesma versão nas duas máquinas.
- **Versão do Django** (6.1 traz template partials, úteis com HTMX) → **Django 5.2 LTS + django-template-partials** → o django-axes (proteção do login) não declara nem testa suporte à 6.1 (só até a 6.0). Não vale arriscar um componente de segurança. A 5.2 tem suporte até abr/2028, e o django-template-partials é o mesmo recurso que entrou no Django 6.0, então a migração futura é simples.
- **Leitura do .env** → **python-dotenv** → só carrega as variáveis; o settings lê com `os.environ`. Simples e suficiente para poucas variáveis (django-environ seria exagero).
- **SECRET_KEY ausente** → **o app não sobe (erro claro)** → uma chave padrão no código ficaria pública no GitHub e permitiria forjar sessões de login. Falhar cedo é melhor que rodar inseguro em silêncio.
- **DEBUG ausente no .env** → **padrão False** → se esquecer de configurar, fica no modo seguro.
- **Nome do pacote de configuração** → **`config`** (e app `tarefas`) → evita a confusão `kairos/kairos/` e separa configuração de lógica.
- **Dados fora do código** → **`%LOCALAPPDATA%\Kairos\`**, nome do banco no `.env` (`kairos.sqlite3` no PC de casa, `dev.sqlite3` no notebook) → evita commit acidental de dados e separa testes dos dados reais.

## Etapa 1: Modelos, regras e login (2026-10-29)

- **Fim de linha nas duas máquinas** → **`.gitattributes` com `* text=auto`** (CRLF para `.ps1`/`.bat`) → a regra fica no repositório, então as duas máquinas se comportam igual, sem diferenças falsas de "arquivo alterado".
- **Como saber se a tarefa "acabou de ser concluída"** → **`concluida_em` serve de memória**: se está vazio e o status é concluída, grava a hora; se já está preenchido, não mexe → evita uma consulta extra ao banco a cada gravação.
- **Unicidade de `origem` + `id_externo`** → **restrição única só quando `id_externo` está preenchido** → tarefas manuais têm o campo vazio e não podem conflitar entre si.
- **Apagar Disciplina com tarefas** (não definido na especificação) → **`PROTECT`** → disciplinas nunca são apagadas, só desativadas pelo sync; o bloqueio só pega acidentes.
- **`inicio`/`fim` fora de reunião** → **erro de validação** → a especificação diz "só para reuniões".
- **Onde ficam as regras** → **`clean()` do modelo** (forms e admin chamam) → regras num lugar só; a sincronização também vai chamar `full_clean()`.
- **Login obrigatório** → **`LoginRequiredMiddleware`** (Django 5.1+) em vez de `LoginRequiredMixin` em cada tela → protegido por padrão; uma tela nova esquecida não fica aberta.
- **Força bruta** → **django-axes: 5 erros bloqueiam o IP por 1 hora** → bloquear por usuário permitiria que alguém te trancasse fora de propósito.
- **Sessão** → **30 dias** → uso diário sem pedir login toda hora.
- **Demandas de trabalho que eu mesmo identifico** (melhorias) → **cadastrar a mim mesmo como Pessoa ("Eu") e usar como solicitante**, mantendo o solicitante obrigatório → toda demanda continua com "quem pediu" preenchido; filtros e contagens por pessoa ficam completos e não dá para confundir iniciativa própria com esquecimento.
