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

## Etapa 3, bloco 2: Concluir, desfazer e menu (2026-10-30)

- **Atualizar a tela após uma ação** → **o servidor devolve o painel do dia inteiro já redesenhado (HTMX troca o `#painel`)** em vez de mexer em cards com JS → a lógica fica toda no Python; o card muda de seção e contadores/resumo se atualizam juntos, sem duplicar regras no JS.
- **Resposta imediata ao concluir** → **o JS marca o card na hora e o HTMX troca o painel 450 ms depois** (`swap:450ms`) → a animação termina antes do card mudar de lugar; se o servidor der erro, a marcação é desfeita e aparece um toast.
- **Desfazer exclusão** → **antes de apagar, a tarefa vira um texto assinado com a `SECRET_KEY` (vale 10 min) que vai no botão "Desfazer"**; ao clicar, ela é recriada idêntica (mesmo id, mesmas datas) → sem "exclusão lógica" no modelo e sem processo em segundo plano; a assinatura impede forjar tarefas. O SQLite do Django nunca reaproveita ids, então o id original está livre.
- **Datas na cópia** → **ISO completo** → o serializador JSON do Django corta em milissegundos (o teste pegou).
- **Toast fora do painel** → **`hx-swap-oob`** → uma resposta atualiza dois lugares da página.
- **Menu ⋯** → **popover nativo + anchor positioning em CSS** → abrir, fechar ao clicar fora e Esc sem JS; o menu vira para cima se não couber.
- **Ações só por POST** → GET devolve 405; sem HTMX, redireciona para a página → nenhum link pode alterar dados por acidente.

## Etapa 3, bloco 3: Criar e editar (2026-10-30)

- **Formulário** → **`ModelForm`** → ao salvar ele roda o `clean()` do modelo, então as regras da etapa 1 valem aqui sem reescrever; os erros aparecem no campo certo.
- **Campos que só valem para uma categoria** → **aparecem/somem só com CSS (`:has()`)** e **o servidor limpa os que não valem** → campo escondido continua sendo enviado (trocar de Trabalho para Pessoal ainda mandaria a Ana); sem a limpeza o modelo recusaria.
- **Campos do Google no formulário** → **`disabled` no form do Django** → o Django ignora o que o navegador mandar e usa o valor do banco; esconder só na tela não impediria um envio forjado (há teste para isso).
- **"Eu" como solicitante** → **identificado pelo nome "Eu"**; a criação rápida o cria na primeira vez; o painel já vem com ele selecionado → segue a decisão da etapa 1 sem campo novo no modelo.
- **Erro de validação no painel** → **o servidor responde com `HX-Retarget`** para redesenhar o formulário no painel em vez de trocar o `#painel` → o mesmo formulário serve para sucesso e erro sem JS extra.
- **Filtro nas ações renomeado para `filtro`** → evitava conflito com o campo `categoria` da tarefa.
- **Classes utilitárias x componentes (de novo)** → utilitárias de display (`grid`) vencem regras de componente; em elementos que o CSS precisa esconder, só classes de componente → o print pegou o bug.

## Etapa 3, bloco 4: Tela Tarefas (2026-10-30)

- **Ações em mais de uma tela** → **as ações só avisam "tarefasMudaram" (`HX-Trigger`) e cada tela escuta e se recarrega pela própria URL** em vez de cada ação saber em que tela está e devolver o pedaço certo → ações desacopladas das telas; tela nova só precisa escutar o aviso. Custo: uma requisição a mais por ação (imperceptível num app local).
- **Criação rápida fora do painel que recarrega** → o campo não perde o foco nem a categoria; só o título é limpo após criar.
- **Herança de atributos do HTMX** → **`hx-disinherit="*"`** nas áreas que se recarregam → os botões de dentro não herdam o `hx-select` da área.
- **Filtros na URL** → **`Form` do Django validando o GET**; valor inválido é descartado individualmente → a página nunca quebra por URL editada à mão e os outros filtros continuam valendo.
- **Atualização dos filtros** → **`hx-get` + `hx-push-url`** (busca espera 350 ms sem digitar) → só a lista muda, o endereço acompanha (voltar e favoritos funcionam).
- **Busca sem acento** → **função `sem_acento()` em Python registrada no SQLite** a cada conexão → o SQLite sozinho só ignora maiúsculas em letras sem acento ("RELATÓRIO" não achava "relatório"); sem coluna extra no banco.
- **Paginação** → **50 por página, links mantêm os filtros** → lista continua rápida com o tempo.
- **Card compartilhado** → **`_card.html`** usado por Hoje e Tarefas; fora da Hoje mostra a data do prazo.
- **Sem JS, ações voltam sempre para a tela Hoje** → usar a página de origem informada pelo navegador permitiria redirecionar para fora do app.
