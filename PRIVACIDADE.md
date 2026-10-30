# Política de Privacidade do Kairos

*Última atualização: 30 de outubro de 2026*

O Kairos é um aplicativo **pessoal** de organização de tarefas, usado por um único usuário (o autor deste repositório) e executado localmente no computador dele. Não é um serviço oferecido ao público.

## Quais dados o Kairos acessa

Com a autorização do próprio usuário, o Kairos acessa **somente para leitura**:

- **Google Agenda:** eventos das agendas do usuário (título, horário, link de reunião, descrição e a resposta do usuário ao convite).
- **Google Classroom:** turmas em que o usuário é aluno e as atividades dessas turmas, com prazos e situação da entrega.

O Kairos **nunca cria, altera ou apaga** nada no Google.

## Onde os dados ficam

- Os dados lidos do Google são guardados **apenas no computador do usuário**, num banco de dados local (SQLite) fora da pasta do código.
- O token de acesso do Google também fica apenas nesse computador.
- O Kairos **não envia dados a nenhum servidor** do autor nem a terceiros, e não usa os dados para publicidade, análise ou treinamento de modelos.

## Como revogar o acesso

O usuário pode revogar o acesso a qualquer momento em <https://myaccount.google.com/permissions> ou pela opção "Desconectar conta Google" nas Configurações do Kairos. Apagar o banco de dados local remove todos os dados guardados.

## Uso dos dados do Google

O uso das informações recebidas das APIs do Google segue a [Política de Dados do Usuário dos Serviços de API do Google](https://developers.google.com/terms/api-services-user-data-policy), incluindo os requisitos de Uso Limitado.

## Contato

Dúvidas: abra uma *issue* em <https://github.com/IgorManes/gerenciador-tarefas/issues>.
