# Especificação

## 1. Objetivo
Um lugar só para controlar demandas do trabalho (com quem pediu), reuniões aceitas no Google Agenda, atividades da faculdade vindas do Google Classroom e projetos pessoais. Uso diário, então precisa ser rápido de usar e agradável de olhar.

## 2. Configuração geral do Django
- Python 3.13 nas duas máquinas (registre a versão no README). Dependências fixadas em `requirements.txt`.
- `LANGUAGE_CODE = "pt-br"`, `TIME_ZONE = "America/Sao_Paulo"`, `USE_TZ = True`.
- Configurações sensíveis via `.env` (sugestão: `django-environ` ou `python-dotenv`).
- Dados FORA da pasta do código: banco, token do Google e backups em `%LOCALAPPDATA%\Kairos\`. Isso evita commit acidental e separa código de dados. Em desenvolvimento pode usar um banco separado (`dev.sqlite3`) para não misturar dados de teste com as tarefas reais.
- Login obrigatório em todas as telas (`LoginRequiredMixin` / middleware). Sem tela de cadastro; usuário criado com `createsuperuser`. Sessão longa (ex.: 30 dias) para não pedir login toda hora.

## 3. Modelo de dados

### Pessoa (quem pede demandas no trabalho; ~10 pessoas)
| campo | tipo | regra |
|---|---|---|
| nome | texto (100) | obrigatório, único |
| ativo | booleano | padrão True. Inativos somem dos seletores, mas o histórico continua |
| cor | texto (7) | opcional, para o avatar/bolinha na interface |

Não pode ser apagada se tiver tarefas (`on_delete=PROTECT`); desativa em vez disso.

### Projeto (agrupa tarefas, principalmente pessoais)
| campo | tipo | regra |
|---|---|---|
| nome | texto (100) | obrigatório |
| categoria | escolha | mesma lista da Tarefa (exceto Reunião) |
| ativo | booleano | padrão True |

### EstadoSync (estado da sincronização de cada fonte do Google)
| campo | tipo | regra |
|---|---|---|
| fonte | texto | único (ex.: `agenda:primary`, `agenda:email@empresa`, `classroom`) |
| sync_token | texto | marca do Google para sync incremental |
| ultimo_completo_em, ultimo_sync_em | data e hora | |
| ultimo_erro, ultimo_erro_em | texto, data e hora | mostrados nas Configurações |

### Disciplina (criada automaticamente pela sincronização do Classroom)
| campo | tipo | regra |
|---|---|---|
| nome | texto (200) | nome da turma no Classroom |
| classroom_id | texto | único |
| ativo | booleano | turma arquivada no Classroom → False |

### Tarefa
| campo | tipo | regra |
|---|---|---|
| titulo | texto (200) | obrigatório |
| observacoes | texto longo | opcional. **Só local, nunca é sobrescrito pela sincronização** |
| categoria | escolha | trabalho / faculdade / pessoal / reuniao |
| status | escolha | a_fazer (padrão) / em_andamento / aguardando / concluida / cancelada |
| prioridade | escolha | baixa / media (padrão) / alta / urgente |
| prazo | data | opcional |
| prazo_hora | hora | opcional (Classroom às vezes tem hora) |
| inicio, fim | data e hora | só para reuniões |
| link_reuniao | URL | opcional (Meet) |
| solicitante | FK Pessoa | **obrigatório se categoria = trabalho; proibido nas outras** |
| projeto | FK Projeto | opcional, `SET_NULL` |
| disciplina | FK Disciplina | opcional, só para faculdade |
| origem | escolha | manual (padrão) / google_agenda / google_classroom |
| id_externo | texto | opcional. Único junto com `origem` (impede duplicatas na sincronização). Na Agenda, usar o `id` do evento (cada ocorrência de evento recorrente tem o seu): evento apagado pode chegar no sync incremental só com `id` e status, sem `iCalUID`. Para um mesmo convite o Google usa o mesmo `id` nas cópias de cada agenda, então não duplica |
| agenda_id | texto | opcional, só `google_agenda`: de qual agenda o evento veio (ID da agenda, que é o e-mail da conta). Usado para a etiqueta e para saber quais eventos o sync pode cancelar |
| link_externo | URL | link para o item no Google |
| descricao_externa | texto longo | o que veio do Google; sobrescrito a cada sync |
| sincronizado_em | data e hora | último sync deste item |
| criado_em, atualizado_em | data e hora | automáticos |
| concluida_em | data e hora | preenchido sozinho quando status vira concluida; limpo se sair de concluida |

Regras (implementar em `clean()` e cobrir com testes):
- Trabalho exige solicitante; outras categorias não podem ter solicitante.
- Reunião exige `inicio`; `fim` não pode ser antes de `inicio`.
- Disciplina só em faculdade.
- "Atrasada" é calculado (prazo < hoje e status não é concluida/cancelada), não um campo salvo.
- Reunião que já terminou não aparece entre as "abertas" (é só exibição; o status não muda) e continua visível com "Todas".
- "Aguardando" serve para demandas paradas esperando outra pessoa; mostrar claramente na interface.

### RelatorioSemanal (foto congelada de uma semana; ver seção 6.1)
| campo | tipo | regra |
|---|---|---|
| semana_inicio | data | segunda-feira da semana; único |
| gerado_em | data e hora | automático |
| dados | JSON | cópia dos dados da semana no momento da geração (nunca recalculado) |

## 4. Telas
1. **Login**: simples, com a identidade visual do app.
2. **Hoje** (tela inicial): atrasadas no topo (destaque), tarefas de hoje, reuniões do dia em linha do tempo, próximos 7 dias. Contadores por categoria.
3. **Tarefas**: lista com filtros combináveis (categoria, status, prioridade, solicitante, projeto, disciplina, busca por texto) e ordenação (prazo, prioridade, criação). Filtros refletidos na URL.
4. **Quadro**: kanban por status (arrastar pode vir depois; começar com botões de mudar status).
5. **Criar/editar tarefa**: painel lateral ou modal (HTMX). O seletor de solicitante só aparece quando a categoria é Trabalho. Itens vindos do Google mostram os campos do Google como somente leitura + link para abrir no Google.
6. **Pessoas e Projetos**: telas próprias simples (o admin do Django fica como reserva, não como interface principal).
7. **Relatórios** (item próprio na barra lateral): lista das semanas salvas + semana atual (parcial); escolher recorte e exportar PDF. Ver seção 6.1.
8. **Configurações**: conectar/desconectar conta Google, horário do último sync, botão "Sincronizar agora", erros recentes de sync.

Interações importantes:
- Criação rápida: campo no topo + atalho de teclado (`N`) para nova tarefa só com título e categoria.
- Concluir com um clique (checkbox), com desfazer.
- Mensagens de sucesso/erro discretas (toast).
- Estados vazios bem desenhados ("Nada atrasado 🎉"), não telas em branco.

## 5. Direção visual ("bem bonito, estilizado")
- **Antes de construir as telas**, gere uma página HTML estática de referência (`docs/prototipo.html`) com paleta, tipografia, um card de tarefa, a tela Hoje e o modo claro/escuro. O dono aprova ou pede ajustes; só depois aplicar nos templates.
- Estilo: moderno, limpo, foco no conteúdo, com espaço em branco generoso, cantos arredondados, sombras sutis, microanimações curtas (hover, concluir tarefa). Evitar visual genérico de "template Bootstrap".
- **Modo escuro como padrão**, com alternância para claro (preferência salva).
- Cor própria por categoria (trabalho, faculdade, pessoal, reunião), usada com consistência em bolinhas, bordas e filtros. Prioridade urgente/alta e atrasada precisam saltar aos olhos sem poluir.
- Tipografia: uma fonte sans moderna (ex.: Inter ou Geist), **arquivos da fonte dentro do projeto** (funciona offline).
- Tailwind CSS via CLI standalone (sem Node; ex.: pacote `django-tailwind-cli`, confirme a versão atual). HTMX para interações sem recarregar a página; Alpine.js só se precisar de estado pequeno na tela.
- Ícone do app (`.ico`) e logo simples coerentes com o nome escolhido.
- Responsivo de verdade (ver seção 11): o alvo principal é desktop, mas tudo precisa funcionar bem no celular.

## 6. Integrações Google (conta pessoal)
- Projeto no Google Cloud com cliente OAuth do tipo **"App para computador" (Desktop)**. Guiar o dono passo a passo na criação.
- Tela de consentimento **publicada como "Em produção"** (em "Teste", o token expira a cada 7 dias). Sem verificação aparece um aviso no login; é aceitável para uso próprio.
- Escopos mínimos, somente leitura: `calendar.events.readonly`, `classroom.courses.readonly`, `classroom.coursework.me.readonly`. Confirme os nomes na documentação atual.
- `credentials.json` e `token.json` ficam em `%LOCALAPPDATA%\Kairos\`, nunca no repositório.
- Bibliotecas: `google-api-python-client`, `google-auth-oauthlib`.
- Sincronização **somente leitura (Google → app)**. O app nunca altera nada no Google.
- Execução: comando `python manage.py sincronizar` + botão "Sincronizar agora" + sync automático enquanto o app está aberto: **Agenda a cada 1 min** (incremental com `syncToken`: o Google devolve só o que mudou) e **ao abrir/voltar para o app**; **Classroom a cada 5 min** (não tem consulta incremental). Registrar data/hora e erros do último sync.
- Tempo real por aviso do Google (push/webhook) **não** é usado: exige endereço público com HTTPS, e o app roda em `127.0.0.1`.
- **Custo zero:** projeto do Google Cloud **sem conta de faturamento** (sem cartão); assim o Google não tem como cobrar. Uso estimado: Agenda ~2.900 req/dia (limite gratuito 1.000.000/dia), Classroom ~3.700 req/dia (limite 4.000.000/dia). Se a cota estourar, a API recusa (429) e o app espera e tenta de novo com intervalo crescente (backoff exponencial).

### Google Agenda
- Agendas sincronizadas (fixas, configuradas no `.env`), janela de 7 dias para trás até 60 dias para frente:
  - **Principal** (conta pessoal): importar como Reunião eventos em que o dono **aceitou** (responseStatus `accepted` do próprio participante) ou é o organizador.
  - **Agendas de empresa** em `GOOGLE_AGENDAS_EXTRAS` (formato `Nome=email, Outra=email2`; o ID da agenda é o e-mail da conta). Hoje: **Invoga**. Importar **todos os eventos, exceto os recusados** pelo e-mail daquela agenda. Exibir com etiqueta do nome (ex.: "Invoga") no card e na linha do tempo.
  - A agenda da empresa precisa estar compartilhada com a conta pessoal como "Ver todos os detalhes do evento" (com "livre/ocupado" o Google não envia título nem link).
- Se depois recusar ou o evento for cancelado → status cancelada (não apagar).
- Agenda removida do `.env` → os eventos já importados ficam como histórico (não são cancelados nem atualizados).
- Mesmo evento em duas agendas → uma tarefa só (mesmo `id`), com a etiqueta da agenda da empresa.
- Eventos de dia inteiro (feriado, férias) **não** viram reunião.
- O sync cancela, mas **nunca reabre** uma reunião cancelada (se o dono cancelou no Kairos, continua cancelada).
- Sync completo (sem token, token vencido = HTTP 410, ou 1º do dia) limitado à janela; incrementais com `syncToken`. O completo diário "anda" a janela (reuniões distantes que entram na janela sem terem mudado). No completo, reuniões que o Kairos tem e o Google não mandou → canceladas (diferença de conjuntos).
- Estado de cada fonte em `EstadoSync` (token, último sync/completo, último erro).
- Título, horário, link do Meet e descrição vêm do Google e são atualizados; `status`, `observacoes`, `prioridade` e `projeto` são do dono e nunca são sobrescritos.

### Google Classroom
- Turmas ativas em que o dono é aluno → Disciplina.
- Atividades (courseWork) → Tarefa categoria faculdade, com prazo/hora e link.
- Se a entrega do aluno estiver como entregue/devolvida → marcar concluída automaticamente (configurável).
- Atividade removida no Classroom → cancelada, não apagada.
- Mesmas regras de campos do Google x campos do dono.

## 6.1 Relatórios semanais (PDF)
- Semana = **segunda a domingo**.
- **Foto congelada:** toda segunda, o app salva um `RelatorioSemanal` da semana anterior com uma cópia dos dados (textos, nomes e status como estavam). Editar ou excluir tarefas depois **não altera** relatórios já salvos. Se o PC estiver desligado, as semanas que faltam são geradas ao abrir o app.
- **Semana atual:** pode ser exportada a qualquer momento como **"parcial"**, montada na hora a partir do banco; só congela na segunda seguinte.
- O que a foto guarda: tarefas concluídas na semana, criadas na semana, abertas ao fim da semana (com destaque para atrasadas e aguardando) e reuniões da semana. Por tarefa: título, categoria, status, prioridade, prazo, datas de criação/conclusão, solicitante, projeto, disciplina, origem e observações.
- **Recortes na exportação** (filtros aplicados sobre a foto, sem fotos extras): Geral; por categoria (Trabalho, Faculdade, Pessoal); por solicitante (Trabalho); por projeto; por disciplina (Faculdade).
- **Observações** só entram no PDF se marcar "incluir observações" na exportação (desmarcado por padrão), para não mandar anotação privada ao gestor sem querer.
- O PDF é gerado na hora a partir da foto (melhorias no visual valem também para semanas antigas). Biblioteca a definir na etapa: preferir solução só em Python que use templates do Django (WeasyPrint exige GTK no Windows).
- Testes: geração da foto, imutabilidade após editar/excluir tarefa, recortes e geração de semanas que faltam.

## 7. Abrir como aplicativo no Windows
- Script `iniciar.pyw` (sem janela de console): sobe o Django com `waitress` (servidor de produção que funciona no Windows; não usar `runserver`) em `127.0.0.1` numa porta fixa, com `DEBUG=False` e estáticos servidos (ex.: `whitenoise`), e abre uma janela `pywebview` com o nome e ícone do app. Ao fechar a janela, encerra o servidor.
- Se o app já estiver aberto, não abrir uma segunda instância.
- Script (PowerShell) que cria o atalho na área de trabalho com o ícone.
- Ao iniciar: rodar migrations pendentes **somente após backup** do banco.
- Backup automático diário do `.sqlite3` em `%LOCALAPPDATA%\Kairos\backups\`, mantendo os últimos 14.
- Empacotar em `.exe` (PyInstaller) é opcional, fica para o fim.

## 7.1 Notificações do Windows
- O app precisa continuar rodando com a janela fechada: ícone na **bandeja do sistema** (ex.: `pystray`) com opções Abrir / Sincronizar / Sair. Fechar a janela minimiza para a bandeja.
- Opção "Iniciar com o Windows" (atalho na pasta Inicializar), ligada/desligada nas Configurações.
- Notificações nativas (toast) do Windows (ex.: `windows-toasts` ou `win11toast`; confirme qual está mantida). Clicar na notificação abre a tarefa.
- Disparos (configuráveis nas Configurações):
  - Reunião: X minutos antes do início (padrão 10).
  - Prazo: no dia, num horário fixo (padrão 9h), e quando ficar atrasada.
  - Nova atividade importada do Classroom.
  - Resumo ao ligar o PC: "3 atrasadas, 5 para hoje, 2 reuniões".
- Guardar o que já foi notificado para não repetir o mesmo aviso.

## 8. Etapas (uma por vez, cada uma termina com commit(s) aprovados)
0. Preparação: venv, Django, estrutura, `.gitignore`, `.env.example`, README inicial, primeiro commit.
1. Modelos + regras + testes + admin + login.
2. Protótipo visual (`docs/prototipo.html`) → aprovação → base de templates, Tailwind, modo escuro.
3. Telas: Hoje, Tarefas (filtros), criar/editar, Pessoas/Projetos, Quadro.
4. Google Agenda (OAuth + sync + testes com respostas simuladas).
5. Google Classroom.
5.1. Relatórios semanais: foto congelada + tela Relatórios + exportação em PDF.
6. Janela pywebview, atalho, backup.
6.1. Bandeja do sistema, iniciar com o Windows e notificações.
7. Acabamento: README completo com prints, `docs/DECISOES.md` revisado, limpeza.

## 9. Testes
- Testes do Django (`python manage.py test`) para as regras de validação e para a sincronização (respostas do Google simuladas; nunca chamar a API real nos testes).
- Rodar os testes antes de propor cada commit.

## 10. Fora do escopo (por enquanto)
Multiusuário, cadastro público, escrever no Google.

## 11. Futuro: acesso pelo celular (NÃO implementar agora, mas não bloquear)
Plano previsto: transformar o app web em **PWA** (instalável na tela inicial do celular) acessado pelo **Tailscale**, com o PC de casa como servidor. Sem app nativo e sem segunda linguagem.
Decisões que já devem ser respeitadas desde o início para isso ser possível depois:
- Todas as telas **responsivas de verdade** (funcionar bem com 380px de largura), não só "mínimo responsivo".
- Nenhuma funcionalidade pode depender do pywebview; ele é só uma janela em volta do site.
- Login e sessão feitos direito (senha forte, proteção contra força bruta como `django-axes`, CSRF), porque no futuro o app ficará acessível pela rede.
- Host/porta configuráveis no `.env` (hoje `127.0.0.1`; no futuro o IP do Tailscale).
Limitações conhecidas desse plano: só funciona com o PC ligado; notificação push no celular exige HTTPS (Tailscale Serve resolve) e, no iPhone, o PWA instalado na tela inicial.
