# Registro de decisões

Formato de cada item: **contexto → escolha → motivo**. As seções abaixo estão em ordem cronológica, etapa por etapa; este topo é o resumo para quem está chegando.

## Comece por aqui

As decisões que mais explicam o projeto:

1. **Django + HTMX, servidor como fonte da verdade:** o HTMX troca pedaços de HTML gerados pelo Django; nenhuma regra de negócio duplicada em JavaScript.
2. **Ações desacopladas das telas:** cada ação só dispara o aviso `dadosMudaram`; cada tela escuta e se recarrega com os próprios filtros (o Quadro funcionou sem mudar nenhuma ação).
3. **Regras num lugar só:** `clean()` do modelo (usado por formulários, admin e sync) e consultas em `consultas.py`, testáveis isoladamente.
4. **Sync com o Google só leitura, incremental e idempotente:** `syncToken` na Agenda, "só grava o que mudou" no Classroom, diferença de conjuntos para apagados, campos do dono nunca sobrescritos.
5. **Reagir à mudança, não ao estado:** o sync só mexe no status quando algo muda no Google, para nunca brigar com uma decisão do dono.
6. **Relatório como foto congelada (JSON):** o que foi enviado ao gestor nunca muda.
7. **Desfazer sem lixo no banco:** cópia assinada com a `SECRET_KEY` dentro do botão "Desfazer".
8. **Nada a instalar quando o Windows já tem:** PDF e ícone pelo Edge; bandeja e notificações pelo `NotifyIcon`; "iniciar com o Windows" pelo Registro.
9. **A janela é só uma moldura:** o app é um site Django; o pywebview só o envolve (abre caminho para o celular via Tailscale).
10. **Custo zero e privacidade:** Google sem faturamento (sem cartão, sem cobrança possível), dados só no PC, segredos fora do Git.

## Lições aprendidas

Problemas que só apareceram com testes, prints ou dados reais — e o que cada um ensinou:

- **Conferir o visual com prints** pegou cards vazando de colunas, títulos cortados no meio da palavra, campos escondidos que apareciam e reuniões sobrepostas. Testes automáticos não veem layout.
- **Dados reais revelam regras que faltavam:** reuniões passadas acumulando, reuniões no mesmo horário, 23 "atividades" antigas do Classroom que não eram pendências.
- **Testar sync em sequência, não uma vez só:** a regra do "marco zero" funcionava no 1º sync e falhava no 2º (ignorar = não salvar, e no sync seguinte a atividade parecia nova).
- **Ler a documentação antes de codar:** evento apagado chega sem `iCalUID` (mudou o identificador); prazos do Classroom vêm em UTC; a mesma permissão tem dois nomes.
- **Nunca engolir erro em silêncio:** um `except: pass` escondeu por que o login do Google falhava.
- **Nomes colidem:** a animação `pulse` foi sobrescrita pela do Tailwind; o filtro `categoria` colidia com o campo da tarefa.
- **Windows tem suas regras:** PowerShell 5.1 lê `.ps1` sem BOM no padrão antigo; o Windows não apaga arquivo aberto; WinForms só aceita a própria thread; handles de 64 bits no `ctypes`.
- **Banco tem suas regras:** erro de chave duplicada "envenena" a transação (ponto de salvamento resolve); o JSON do Django corta datas em milissegundos; o SQLite não ignora acentos.
- **Confirmar o que está rodando:** um teste de integração "falhou" porque uma versão antiga do app ainda estava aberta.

## Índice

- [Etapa 0: Preparação (2026-10-29)](#etapa-0-preparação-2026-10-29)
- [Etapa 1: Modelos, regras e login (2026-10-29)](#etapa-1-modelos-regras-e-login-2026-10-29)
- [Etapa 2: Protótipo visual (2026-10-29)](#etapa-2-protótipo-visual-2026-10-29)
- [Funcionalidade nova: Relatórios semanais (planejada para a etapa 5.1)](#funcionalidade-nova-relatórios-semanais-planejada-para-a-etapa-51)
- [Etapa 2: Visual aplicado ao app (2026-10-29)](#etapa-2-visual-aplicado-ao-app-2026-10-29)
- [Agenda da empresa (planejada para a etapa 4)](#agenda-da-empresa-planejada-para-a-etapa-4)
- [Etapa 3, bloco 1: Tela Hoje (2026-10-30)](#etapa-3-bloco-1-tela-hoje-2026-10-30)
- [Etapa 3, bloco 2: Concluir, desfazer e menu (2026-10-30)](#etapa-3-bloco-2-concluir-desfazer-e-menu-2026-10-30)
- [Etapa 3, bloco 3: Criar e editar (2026-10-30)](#etapa-3-bloco-3-criar-e-editar-2026-10-30)
- [Etapa 3, bloco 4: Tela Tarefas (2026-10-30)](#etapa-3-bloco-4-tela-tarefas-2026-10-30)
- [Etapa 3, bloco 5: Pessoas e Projetos (2026-10-30)](#etapa-3-bloco-5-pessoas-e-projetos-2026-10-30)
- [Etapa 3, bloco 6: Quadro (2026-10-30)](#etapa-3-bloco-6-quadro-2026-10-30)
- [Etapa 4: Google Agenda (2026-10-30)](#etapa-4-google-agenda-2026-10-30)
- [Etapa 4: sync automático e Configurações (2026-10-30)](#etapa-4-sync-automático-e-configurações-2026-10-30)
- [Etapa 5: Google Classroom (2026-10-30)](#etapa-5-google-classroom-2026-10-30)
- [Etapa 5.1: Relatórios semanais (2026-10-30)](#etapa-51-relatórios-semanais-2026-10-30)
- [Etapa 6: Kairos como aplicativo (2026-10-30)](#etapa-6-kairos-como-aplicativo-2026-10-30)
- [Etapa 6.1: Bandeja, iniciar com o Windows e notificações (2026-10-30)](#etapa-61-bandeja-iniciar-com-o-windows-e-notificações-2026-10-30)

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

## Etapa 3, bloco 5: Pessoas e Projetos (2026-10-30)

- **Duas telas iguais** → **funções genéricas que recebem o modelo e o formulário** (`views_cadastros.py`) e um template só → Pessoas e Projetos não duplicam código; um terceiro cadastro seria uma entrada na configuração.
- **Excluir pessoa/projeto pela interface** → **não existe; só desativar (com Desfazer)** → a especificação manda desativar pessoas; excluir projeto desvincularia todas as tarefas em silêncio. O admin fica como reserva para casos raros.
- **URLs dos cadastros** → **`re_path` aceitando só `pessoa|projeto`** → tipo inventado vira 404 em vez de erro 500.
- **Aviso de mudança renomeado para `dadosMudaram`** → renomear uma pessoa também muda os cards das tarefas; todas as listas escutam o mesmo aviso.
- **"Ver tarefas"** → **link para a tela Tarefas com o filtro na URL** → reaproveita o bloco 4 em vez de criar outra lista.
- **Celular** → **página "Mais"** com as telas que não cabem na barra inferior (4 itens) → nenhuma tela fica inacessível no celular.

## Etapa 3, bloco 6: Quadro (2026-10-30)

- **Coluna "Concluída"** → **só os últimos 7 dias** → sem limite ela cresce para sempre; histórico completo fica na tela Tarefas (status "Todas").
- **Mudar de coluna** → **botões ← → no card (anterior/próximo calculados na consulta)**, reaproveitando a ação de mudar status com Desfazer → a especificação pede botões antes de arrastar; nenhuma ação nova foi necessária, o Quadro só escuta `dadosMudaram`.
- **Celular** → **colunas lado a lado com rolagem horizontal e encaixe (scroll-snap)** → uma coluna por vez, com a próxima aparecendo na borda.
- **Largura** → **o Quadro usa a largura toda**; as outras telas mantêm largura máxima (linhas longas cansam a leitura).
- **Card em coluna estreita** → itens de grade com `min-width: 0` (senão não encolhem e vazam) e **prioridade só como bandeira** (texto fica para leitor de tela) → o print pegou o vazamento e o título espremido.
- **Mover entre colunas** (os botões ← → discretos não pareciam botões) → **arrastar e soltar nativo do HTML + botões visíveis** → arrastar no computador; os botões ficam para celular e teclado (arrastar nativo não funciona por toque). Sem biblioteca: ao soltar, o JS chama a mesma ação de mudar status (Desfazer e toast vêm junto).
- **Movimento dos cards** (protótipo aprovado tinha; o app só "pulava") → **View Transitions do navegador via `hx-swap="... transition:true"`**, com `view-transition-name` por card → o navegador anima cada card da posição antiga até a nova, inclusive entre colunas, sem calcular posições em JS. Na troca de tema os nomes são desligados (senão os cards ficariam fora do efeito de círculo).
- **Contadores** → **animam do valor antigo ao novo** (JS anota antes da troca e anima depois).
- **Animação do circuito parada** → a animação se chamava `pulse`, mesmo nome de uma animação embutida do Tailwind, que substituiu a nossa → renomeada para `circuito-pulso`. Lição: nomes de `@keyframes` próprios com prefixo do projeto.

## Etapa 4: Google Agenda (2026-10-30)

- **Frequência do sync** (especificação dizia 15 min; o dono queria menos atraso) → **Agenda a cada 1 min com sync incremental (`syncToken`) + ao abrir/voltar para o app + botão; Classroom a cada 5 min** → praticamente tempo real com custo desprezível. Aviso em tempo real do Google (webhook) exigiria endereço público com HTTPS; o app roda local.
- **Custo** → **projeto do Google Cloud sem conta de faturamento** → sem cartão o Google não tem como cobrar; uso estimado é ~0,3% (Agenda) e ~0,1% (Classroom) dos limites gratuitos diários. Estouro de cota vira erro 429, tratado com espera crescente (backoff exponencial).
- **Identificador do evento** (planejado: `iCalUID`) → **`id` do evento** → no sync incremental um evento apagado pode chegar só com `id` e status; pelo `iCalUID` não daria para achar qual cancelar. Para um mesmo convite o Google usa o mesmo `id` nas agendas, então a deduplicação continua.
- **Janela de datas x sync incremental** → **1 sync completo por dia** (limitado à janela) + incrementais por token → o incremental não aceita janela e só manda o que mudou; sem o completo diário, uma reunião marcada para daqui a 70 dias nunca entraria quando chegasse a 60.
- **Reuniões apagadas no Google** → **diferença de conjuntos no sync completo** (o que o Kairos tem da agenda na janela − o que o Google mandou = apagadas → canceladas), com `set` → O(n + m) em vez de O(n × m).
- **Token vencido (HTTP 410)** → descarta e refaz completo, como a documentação manda.
- **Regras da agenda da empresa** → o convidado "eu" é o marcado com `self` (o Google o define como "a agenda desta cópia"), com o e-mail da agenda como garantia.
- **Dia inteiro** → **não vira reunião** (feriados e férias poluiriam a linha do tempo).
- **Sync nunca reabre reunião cancelada** → se o dono cancelou no Kairos, a decisão dele vale.
- **Lote atômico** → cada agenda é aplicada numa transação: ou entra inteira ou nada.
- **Uma agenda com erro não para as outras** → erro registrado no `EstadoSync` para a tela de Configurações.
- **Decisões como funções puras** (`deve_importar`, `campos_do_evento`) e um "Google de mentira" nos testes → cada regra testada sem rede nem credenciais.
- **Login** → **só com `sincronizar --conectar`**; o sync automático nunca abre o navegador por conta própria (se a autorização cair, avisa).
- **Reuniões no mesmo horário se sobrepunham na linha do tempo** (apareceu com os dados reais) → **algoritmo guloso de colunas**: ordena por início, agrupa em blocos de sobreposição, cada reunião vai para a 1ª coluna livre e o bloco divide a largura → mesma ideia de "quantas salas preciso?"; calculado no servidor junto com a posição vertical. Reuniões estreitas viram compactas (ícone do Meet no canto).

## Etapa 4: sync automático e Configurações (2026-10-30)

- **Quem dispara o sync automático** → **a própria página aberta (HTMX: 3 s após abrir, a cada 60 s e ao voltar para o app)**, com intervalo mínimo no servidor (auto 50 s, foco 15 s, botão sempre) e uma trava para um sync por vez → atende "enquanto o app está aberto" sem processo extra; na etapa 6.1 (bandeja) o mesmo `sincronizar_tudo()` será chamado por um relógio do app.
- **Relógio separado do indicador** → o elemento que dispara não é o que a resposta substitui; senão o "load" do elemento novo dispararia de novo em laço.
- **Tela só pisca quando há novidade** → o servidor só manda `dadosMudaram` se algo foi criado, atualizado ou cancelado.
- **Lógica de "sincronizar tudo" num lugar só** (`google/servico.py`) → comando, botão, relógio e (depois) bandeja chamam a mesma função.
- **Conectar pela tela** → abre o navegador **deste PC** numa thread; limitação conhecida: acessando pelo celular (futuro), o navegador abriria no PC de casa.
- **Desconectar** → revoga no Google, apaga o `token.json` e zera os tokens de sync (ao reconectar, começa completo); reuniões importadas continuam.
- **Reuniões que já terminaram** (dados reais mostraram acumulando como "A fazer") → **saem da lista de abertas, sem mudar o status**; aparecem em "Todas" → "concluída" significa "eu fiz", o que o sync não tem como saber; marcar sozinho poluiria os relatórios semanais e quebraria a regra "status é do dono".

## Etapa 5: Google Classroom (2026-10-30)

- **Escopos** → `classroom.courses.readonly` + `classroom.coursework.me.readonly` (confirmados na documentação; o segundo cobre atividades e as minhas entregas) → mínimo necessário, só leitura.
- **Token antigo sem as permissões novas** → o Kairos compara os escopos gravados no `token.json` com os que pede e mostra "Reconecte a conta Google" → em vez de um erro 403 confuso na primeira chamada ao Classroom.
- **Sem sync incremental no Classroom** → lê tudo a cada 5 min (1 + 2 consultas por turma); **só grava o que mudou** (compara uma "foto" dos campos) → sem isso o banco seria reescrito e a tela "piscaria" a cada 5 min.
- **Prazo em UTC** → convertido para o fuso local; campos zerados não vêm no JSON (`{"hours": 3}` = 03:00) → sem conversão, prazos de 23:59 cairiam no dia seguinte.
- **Concluir ao entregar** (especificação: "configurável") → **reage à mudança da entrega, não ao estado**: guarda a última situação vista (`estado_entrega`) e só conclui quando ela vira entregue/devolvida (e reabre se o envio for cancelado) → se o dono reabrir a tarefa, o sync não a conclui de novo a cada 5 min. Chave nas Configurações (`Preferencias`, uma linha só), ligada por padrão.
- **Primeira importação** → atividades já entregues chegam concluídas (a entrega "mudou" de nada para entregue) → não aparecem como atrasadas.
- **Turma arquivada** → Disciplina inativa; as atividades dela não são buscadas nem canceladas.
- **Atividade apagada pelo professor** → cancelada pela diferença de conjuntos, só para turmas ativas.
- **Id da atividade** → `turma:atividade` → o id é único dentro da turma; o prefixo garante unicidade geral.
- **Permissão com dois nomes** (o console gravou `classroom.student-submissions.me.readonly` no lugar de `classroom.coursework.me.readonly`; o token veio com o nome novo) → **tabela de equivalentes**: qualquer um dos nomes vale → o Kairos pedia para reconectar para sempre por causa de um apelido.
- **Token grava as permissões CONCEDIDAS, não as pedidas** → a tela de consentimento deixa desmarcar caixas; gravando as pedidas, o Kairos acharia que tem acesso e não teria.
- **Erro no login em segundo plano era descartado em silêncio** (`except: pass`) → agora aparece nas Configurações → foi por isso que as primeiras tentativas falharam sem explicação.
- **O que entra do Classroom** (a 1ª importação trouxe 14 vencidas, algumas de 2025, e 9 "atividades" sem prazo que eram avisos/materiais; o dono disse que a única pendência real era a de 3/11) → atividade nova não entregue: **com prazo, entra se o prazo não passou; sem prazo, entra só se publicada depois do marco zero** (`EstadoSync.iniciado_em`, quando o Kairos começou a acompanhar o Classroom); entregues sempre entram, como concluídas. Tentativas descartadas: (1) heurística de idade ("sem prazo e publicada há +14 dias") deixava passar avisos recentes; (2) "ignorar no 1º sync" falhava no 2º: ignorar = não salvar, e no sync seguinte a atividade parecia nova e entrava. A regra final julga cada atividade só pelos dados dela, então dá o mesmo resultado em qualquer sync. Lição: testar sync em sequência (há teste com 3 syncs seguidos), não um só.- **Datas das atividades importadas** (as 27 entregues vieram com "concluída em" = momento da importação: o relatório diria 27 conclusões num dia) → **"criada" = publicação no Classroom; "concluída" (quando foi pela entrega) = última atualização da entrega**; só antecipa datas, nunca empurra → uma conclusão feita pelo dono mantém a data dele.

## Etapa 5.1: Relatórios semanais (2026-10-30)

- **Biblioteca de PDF** → **Microsoft Edge em modo sem janela (`--print-to-pdf`)** em vez de fpdf2/xhtml2pdf/WeasyPrint/Playwright → nada a instalar (o Edge vem no Windows e o pywebview usa o mesmo motor), o PDF reaproveita um template HTML e sai com o visual do Kairos. Custo: depende do Edge (o app já é só Windows) e leva ~1,6 s; perfil temporário próprio para não disputar o Edge aberto; tempo limite de 60 s. Plano B: fpdf2.
- **O que a foto guarda** → texto e números (nomes de solicitante/projeto/disciplina como eram no dia), nunca chaves estrangeiras → renomear ou excluir depois não muda o relatório (há teste).
- **Quais semanas gerar** → na 1ª vez só a semana passada; depois, cada semana encerrada que falta → semanas antigas teriam o "em aberto" de hoje, não daquela época.
- **Quando gerar** → no relógio do sync (a cada minuto) e ao abrir a tela → "toda segunda" sem processo extra, e semanas com o PC desligado são geradas ao abrir.
- **Recortes** → calculados sobre a foto na exportação; o recorte Trabalho inclui as reuniões da agenda da empresa (Invoga).
- **Atrasada no relatório** → prazo antes do que vier primeiro: a próxima segunda (semana encerrada) ou hoje (semana em andamento) → o print pegou tarefas de amanhã marcadas como atrasadas na semana parcial.
- **Formato de data no template** → filtro próprio `add_days` (templatetags) para mostrar "26/10 a 01/11".

## Etapa 6: Kairos como aplicativo (2026-10-30)

- **Janela** → **pywebview** (janela nativa do Windows com o motor do Edge/WebView2) em vez de aba do navegador → ícone próprio, sem barra de endereço; mesmo visual. O app nunca depende do pywebview: é só uma janela em volta do site (requisito da seção 11).
- **Servidor** → **waitress** (`create_server` numa thread) com `DEBUG=False` forçado pelo `iniciar.pyw` → servidor de produção que roda no Windows; fechar a janela chama `servidor.close()`.
- **Estáticos com DEBUG=False** → **whitenoise com `WHITENOISE_USE_FINDERS`** (lê direto de `static/`) → app local: sem `collectstatic` a cada atualização.
- **Instância única** → **mutex com nome do Windows**; se já existe, traz a janela para a frente (busca por título) e sai.
- **Sessão e tema entre aberturas** → `private_mode=False` + pasta própria em `%LOCALAPPDATA%\Kairos\janela` → o padrão do pywebview esquece cookies e localStorage ao fechar (login de 30 dias e tema se perderiam).
- **Ícone da janela** → **API do Windows (`WM_SETICON`)** em vez do objeto WinForms → o evento "janela mostrada" roda em outra thread e o WinForms não aceita ser mexido fora da dele. `SetCurrentProcessExplicitAppUserModelID` agrupa a janela como "Kairos" na barra de tarefas, não como "Python".
- **Ícone (.ico)** → **gerado sem pacote novo**: o Edge desenha o SVG em PNG (fundo transparente) e o script junta os PNGs num .ico (o formato aceita PNG dentro); `ferramentas/gerar_icone.py` regera se o logo mudar.
- **Backup** → **API de backup do SQLite** (cópia consistente com o banco em uso; copiar o arquivo no meio de uma gravação pode corromper), diário + antes de migrations, mantém os últimos 14.
- **Tarefas periódicas** (foto semanal, backup diário) → **no relógio da página, sempre ativo** (antes só existia com o Google conectado) e na abertura do app.
- **.pyw sem terminal** → erros vão para `kairos.log` e erro fatal vira caixa de mensagem → senão sumiriam.
- **Testes de backup no Windows** → `closing()` nas conexões sqlite: `with sqlite3.connect()` não fecha a conexão, e o Windows não deixa apagar arquivo aberto.
- **Script do atalho em PowerShell** → **arquivo .ps1 em UTF-8 com BOM** → o PowerShell 5.1 do Windows lê .ps1 sem BOM no padrão antigo (cp1252); um travessão em UTF-8 virou aspa e quebrou o script. Conferido com o analisador do próprio PowerShell (sem executar).

## Etapa 6.1: Bandeja, iniciar com o Windows e notificações (2026-10-30)

- **Bandeja e notificações** → **`NotifyIcon` do próprio Windows via pythonnet** (já veio com o pywebview) em vez de pystray (sem versão desde 2023, traz o Pillow) ou win11toast/windows-toasts (vários pacotes winrt) → zero pacotes novos; no Windows 11 o aviso aparece como notificação nativa e o clique é informado.
- **Nome e ícone nas notificações** (saía "Kairos.App" e sem ícone; com um ID não registrado o Windows chegou a descartar o aviso) → **AppUserModelID "Kairos" registrado em `HKCU\Software\Classes\AppUserModelId\Kairos`** (DisplayName + IconUri), refeito a cada abertura → sem administrador, só o usuário atual.
- **Fechar a janela** → **esconde na bandeja** (o evento "fechando" devolve False); só "Sair" encerra → sync e avisos continuam com a janela fechada.
- **WinForms só na thread da janela** → bandeja criada e avisos mostrados via `native.BeginInvoke`.
- **Instância única com a janela escondida** → a 2ª abertura **sinaliza** a 1ª por um evento com nome do Windows (antes procurava a janela visível, que não existe quando está na bandeja).
- **Handles de 64 bits no ctypes** → `restype`/`argtypes` declarados; por padrão o ctypes corta retornos para 32 bits.
- **Relógio do app** (thread, a cada minuto) → sync + tarefas periódicas + avisos, mesmo com a janela escondida; chama as mesmas funções do relógio da página.
- **Nunca repetir aviso** → `Notificacao.chave` única que descreve o que foi avisado (`reuniao:42:<início>`): reunião remarcada muda a chave e avisa de novo. 1ª verificação de todas só registra, sem mostrar (não inunda no 1º dia).
- **Gravar chave repetida** → `transaction.atomic()` aninhado (ponto de salvamento) → o erro de chave duplicada "envenenaria" a transação inteira (o teste pegou).
- **Bug da 1ª verificação** → o resumo do dia roda antes e fazia a 1ª verificação achar que já tinha rodado, mostrando tudo de uma vez → o resumo não conta para decidir.
- **Avisos agrupados** → prazos do dia num aviso só; várias atrasadas ou atividades do Classroom num aviso só → menos ruído.
- **Iniciar com o Windows** (especificação: atalho na pasta Inicializar) → **valor no Registro `HKCU\...\Run`** com `pythonw iniciar.pyw --bandeja` → padrão dos apps, sem COM, aparece no Gerenciador de Tarefas → Aplicativos de inicialização; abre direto na bandeja.
- **Clique no aviso** → abre `/?abrir=<id>`: o JS abre o painel daquela tarefa.
- **Teste que enganou** → um Kairos antigo (versão sem bandeja) estava aberto; a instância única desviou o teste para ele. Lição: confirmar qual versão está rodando antes de concluir algo de um teste de integração.
- **Botões do Quadro vazando do card** (o texto "← A fazer / Aguardando →" não cabe numa coluna) → **só a seta**, com o destino no "passar o mouse" e para leitor de tela → arrastar é o caminho principal no computador; os botões ficam compactos.
- **Títulos quebrando no meio da palavra** ("indicador/es") → `overflow-wrap: break-word` em vez de `anywhere` (só corta palavra que não cabe sozinha na linha); no Quadro, bandeira e ⋯ flutuam no canto em vez de ocupar uma coluna ao lado do título.

## Etapa 7: Acabamento (2026-10-30)

- **Verificador de código** → **ruff** (um pacote, regras E/F/W/I/B/UP, linha de 120) configurado no `pyproject.toml` e em `requirements-dev.txt` → mesmas regras nas duas máquinas; o PC de uso não instala ferramentas de desenvolvimento. Formatação automática aplicada uma vez (só forma, sem mudar comportamento; 196 testes passando antes e depois).
- **`.pyw` no verificador** → `extend-include = ["*.pyw"]` → o ruff ignorava o `iniciar.pyw` por padrão.
- **Prints do README** → **gerados por script (`ferramentas/gerar_prints.py`) num banco temporário com dados de demonstração e empresa fictícia** → o repositório é público; nenhum dado real (reuniões, empresa, faculdade) aparece. O script se recusa a rodar fora da pasta temporária.
- **Dados de exemplo no banco de desenvolvimento** → removidos só os registros criados pelo `dados_exemplo` (por nome/título exato), com backup antes → o dono passou a ver só dados reais; o banco do PC de uso nunca teve exemplos.
- **Textos de tempo** → filtro `ha_quanto` ("agora", "há 5 min") em vez do `timesince` do Django ("há 0 minuto"); contador de reuniões diz "em andamento agora" quando a reunião já começou (antes contradizia o topo).
- **DECISOES.md** → resumo, lições aprendidas e índice no topo, histórico intacto → porta de entrada para quem chega pelo GitHub.
