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

## Etapa 2: Protótipo visual (2026-10-29)

- **Direção visual** (o pedido foi "tecnológica, vibrante") → **escuro com gradiente azul → violeta → rosa, superfícies de vidro e brilho na cor da categoria**, mas **texto nunca brilha** e o brilho aparece só no hover, no foco e em sinais → uso diário pede leitura confortável; neon em tudo cansa a vista.
- **Cores de destaque** → **vermelho só para urgente, atrasada e "agora"; âmbar para alta; média e baixa sem marca** → se tudo é destaque, nada é.
- **Fonte** → **Inter variável, arquivo local em `static/fonts/`** (licença OFL) → funciona offline; números de largura fixa para horários.
- **Excluir tarefa** (não previsto na especificação) → **menu ⋯ no card + Desfazer no toast, sem caixa "tem certeza?"** → desfazer é tão seguro quanto confirmar e mais rápido. **Itens do Google são cancelados, não excluídos**: apagar faria o sync trazê-los de volta.
- **Responsivo** → **container queries** (o layout reage à largura da área do app, não da janela) → o mesmo CSS serve para desktop, celular e a simulação de 390px do protótipo.
- **JS do protótipo** → **estado → render** (os dados numa lista; a tela é sempre redesenhada a partir dela) → mesmo raciocínio do app, onde o banco é o estado e o Django/HTMX redesenha.

## Funcionalidade nova: Relatórios semanais (planejada para a etapa 5.1)

- **Relatório semanal salvo** → **foto congelada** (`RelatorioSemanal` com uma cópia dos dados em JSON, gerada toda segunda) em vez de recalcular do banco → o que foi enviado ao gestor continua igual mesmo se eu editar ou excluir tarefas depois.
- **Uma foto por semana, recortes como filtro** → os recortes (categoria, solicitante, projeto, disciplina) são aplicados na exportação → não precisa de uma foto por combinação de filtro.
- **PDF montado na hora a partir da foto** → melhorias no visual valem também para semanas antigas; a foto guarda dados, não o arquivo.
- **Semana atual exportável como "parcial"** → dá para mandar o relatório na sexta, antes de a semana congelar.
- **Observações no PDF** → **só se marcar na exportação** (desmarcado por padrão) → evita mandar anotação privada sem querer.
- **Semana** → **segunda a domingo** → padrão de trabalho (ISO).

## Etapa 2: Visual aplicado ao app (2026-10-29)

- **Tailwind sem Node** → **django-tailwind-cli 4.8.2 com o executável standalone do Tailwind 4.3.3 (versão fixa)** → nada de Node.js nas duas máquinas; versão fixa para as duas gerarem o mesmo CSS (o padrão "latest" mudaria sem aviso).
- **CSS gerado fora do Git** → **`static/css/tailwind.css` e o executável no `.gitignore`**; cada máquina roda `tailwind build` → evita commits de arquivo gerado e conflitos; custo: um comando a mais ao clonar (documentado no README).
- **Classes utilitárias x componentes** → **utilitárias para layout e espaçamento; classes próprias (`@layer components`) para peças repetidas com efeitos** (card, botão, chip, vidro, circuito) → efeitos do protótipo em utilitárias viravam 30 classes ilegíveis repetidas em cada card; assim o app fica idêntico ao protótipo aprovado.
- **Tokens de cor** → **variáveis CSS trocadas por `data-theme` + `@theme inline` do Tailwind** → as mesmas classes (`bg-surface`, `text-trabalho`) funcionam nos dois temas.
- **Tema salvo** → **`localStorage` + script mínimo no `<head>`** antes de desenhar a página → não "pisca" o tema errado ao abrir; preferência por aparelho, suficiente para um usuário.
- **HTMX** → **arquivo local em `static/js/` (2.0.11)** → funciona offline.
- **Menu com telas futuras** → **itens esmaecidos com "Em breve"** em vez de links quebrados.
- **Página de bloqueio do axes** → **template próprio** (o padrão é texto puro) e explica como liberar.

## Agenda da empresa (planejada para a etapa 4)

- **Reuniões da agenda da empresa (Invoga)** → **agendas fixas no `.env` (`GOOGLE_AGENDAS_EXTRAS=Invoga=email`)** em vez de escolher na tela → simples; trocar ou adicionar empresa é editar uma linha. O ID da agenda principal de uma conta é o próprio e-mail, então a mesma informação identifica a agenda e "quem sou eu" nos convidados.
- **Filtro da agenda da empresa** → **tudo, menos recusados** → atende "tudo que for marcado" sem mostrar reuniões já recusadas. A regra "aceito por mim" da agenda pessoal não serve aqui: os convidados são o e-mail da empresa, não a conta pessoal.
- **Novo campo `agenda_id` na Tarefa** → guarda de qual agenda veio → etiqueta "Invoga" e o sync só cancela eventos das agendas que acompanha.
- **Duplicatas entre agendas** → **`id_externo` = `iCalUID`** (igual em todas as agendas) → a mesma reunião nas duas agendas vira uma tarefa só.
- **Agenda removida do `.env`** → **eventos ficam como histórico** → o Kairos parou de acompanhar a agenda; as reuniões não deixaram de existir.

## Etapa 3, bloco 1: Tela Hoje (2026-10-30)

- **Ordenar por prioridade guardada como texto** (alfabético poria "urgente" no fim) → **`Case`/`When` (CASE WHEN do SQL) converte em peso na consulta** em vez de tabela de prioridades com chave estrangeira → mesma ideia (texto → número), sem mudar o modelo nem criar tabela para 4 valores fixos.
- **Onde ficam as consultas** → **`tarefas/consultas.py`**, não dentro das views → cada regra ("atrasada", "próximos 7 dias") num lugar só e testável isoladamente.
- **Card de tarefa** → **um `partialdef` reutilizado nas três seções** → o HTMX vai pedir só esse pedaço ao atualizar um card.
- **Filtro por categoria** → **link com `?categoria=` na URL**; valor desconhecido é ignorado → dá para favoritar/compartilhar o filtro e não quebra com entrada inválida.
- **Números no CSS da linha do tempo** → **formatados em Python com ponto** → o template em pt-BR escreveria "1,5", que o CSS não entende.
- **Dados de exemplo** → **comando `dados_exemplo` que só roda no `dev.sqlite3`** e não roda duas vezes → dá para ver as telas no notebook sem risco de sujar o banco real.
