# Instruções para o Claude Code

Leia também `docs/ESPECIFICACAO.md` antes de qualquer etapa. Ele tem o modelo de dados, as regras de sincronização e a direção visual. Se algo no pedido do dono contradizer a especificação, aponte a contradição e pergunte; não escolha sozinho.

## Contexto
- App pessoal de tarefas, um único usuário (o dono do repositório). Repositório público no GitHub dele, usado como portfólio.
- Nome do app: **Kairos**. Pasta de dados: `%LOCALAPPDATA%\Kairos\`.
- Python + Django + SQLite + templates HTML com Tailwind CSS e HTMX. Roda local no Windows 11 Pro, aberto numa janela pywebview com ícone na área de trabalho.
- Desenvolvimento em duas máquinas (PC de casa = onde o app roda de verdade; notebook = desenvolvimento), sincronizadas via Git.

## Como trabalhar: ensinar enquanto coda
- O dono sabe algoritmos, mas nunca montou um sistema em Python. Explique em português simples, sem jargão desnecessário.
- Antes de cada bloco de código: diga O QUE vai fazer e POR QUÊ. Antes de cada comando de terminal: diga o que ele faz.
- De vez em quando, faça UMA pergunta de lógica (nível algoritmo) antes de mostrar a solução. Não pergunte detalhes avançados de framework; explique-os.
- Fim de cada etapa: resumo curto com o que foi feito, decisões e trade-offs (para ele conseguir explicar o projeto numa entrevista). Registre as decisões importantes em `docs/DECISOES.md` (uma linha de contexto + escolha + motivo).
- Seja direto, sem elogios vazios. Se o dono pedir algo que piora o projeto, diga e explique.
- Trabalhe uma etapa por vez. Não pule para a próxima sem ele aprovar.

## SEMPRE peça confirmação antes de
- `git commit` (mostre a mensagem proposta), `git push`, merge, `reset`, `rebase` ou reescrita de histórico.
- Criar migrations que removam/renomeiem colunas ou tabelas, ou alterem dados existentes; e antes de rodar `migrate` no banco real.
- Apagar arquivos ou dados (`rm`, `del`, `Remove-Item`, `flush`, `DELETE`).
- Instalar pacotes (diga qual, para quê e alternativa).
- Mexer em credenciais do Google, `.env`, `SECRET_KEY` ou configurações de segurança.
- Mudar o modelo de dados em relação à especificação.

## Commits
- Saem com a identidade git do dono. NÃO adicione "Co-Authored-By: Claude" nem "Generated with Claude Code" em commits ou PRs.
- Português, curtos, no imperativo ("Adiciona modelo Pessoa"). Um commit por mudança lógica.
- O README deve ter uma seção honesta dizendo que o projeto foi desenvolvido com auxílio de IA (Claude Code), com o dono revisando e decidindo.

## Segurança
- NUNCA commitar: `.env`, `credentials.json`, `token.json`, `*.sqlite3`, `venv/`, `staticfiles/`, backups.
- `SECRET_KEY` vem do `.env`. Mantenha um `.env.example` sem valores reais.
- Não leia arquivos de credenciais. Se precisar de algo deles, pergunte.
- Antes de qualquer mudança arriscada no banco real, faça backup do arquivo `.sqlite3`.
