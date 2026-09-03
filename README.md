# wake-octadesk-sync

Job diário que substitui o processo manual de "subir planilha de números no
Octadesk": busca na Wake os clientes cadastrados no dia anterior e dispara,
via API do Octadesk, a mensagem de template de WhatsApp já aprovada para cada
um deles.

## O que o job faz

1. Calcula a data de "ontem".
2. Chama a API da Wake pedindo os clientes cadastrados nessa data.
3. Para cada cliente, chama a API do Octadesk (`POST /chat/send-template`)
   para enviar o template de WhatsApp já aprovado, usando só o telefone do
   cliente (não é necessário e-mail — ver explicação abaixo).
4. Registra em `logs/sent_log.jsonl` quem já recebeu mensagem em cada data,
   para não duplicar envio caso o job seja executado mais de uma vez no
   mesmo dia.
5. Termina com exit code `0` se tudo deu certo, ou `1` se algo falhou — isso é
   o que permite ao cron/Agendador de Tarefas detectar e alertar sobre falhas.

### Por que não precisa de e-mail

O endpoint do Octadesk usado aqui (`/chat/send-template`) identifica o
destinatário pelo campo `code` dentro de `target.contact`, que é o próprio
número de WhatsApp — `email` e `name` são opcionais e só existem para
preencher variáveis do template (`email-contato`, `nome-contato`), não para
identificar o contato. Por isso o fluxo Wake → Octadesk aqui só precisa do
telefone.

## Pendências antes de rodar em produção

Este script já está pronto e testado no que depende só do Octadesk (cuja API
está documentada publicamente). A parte da **Wake ainda tem lacunas**, porque
não tínhamos acesso à documentação autenticada da conta da empresa ao montar
isso. Procure no código por `TODO` — todos estão em `wake_client.py` e
`.env.example` — e ajuste:

- o path real do endpoint de listagem de clientes (`WAKE_CUSTOMERS_ENDPOINT`);
- o nome dos parâmetros de filtro por data de cadastro;
- o nome do header de autenticação (`WAKE_AUTH_HEADER_NAME`) — hoje está
  como placeholder `TokenAPI`, precisa ser confirmado;
- os nomes dos campos na resposta (hoje o código espera `Nome`, `Celular`/
  `Telefone`, `Email`);
- se a resposta é paginada (se for, `WakeClient.get_customers_registered_on`
  precisa percorrer todas as páginas, não só a primeira).

O token da Wake é gerado no painel admin, em **Extensões e Integrações >
Tokens**. A documentação completa fica em https://wakecommerce.readme.io/.

Da mesma forma, confirme com o suporte da Octadesk o host real da API
(`OCTADESK_API_BASE_URL`) — a documentação pública não expõe esse valor.

## Setup local

Requer Python 3.11+ (usa `zoneinfo`/sintaxe de tipos moderna).

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env.development
# preencha o .env.development com as credenciais reais
```

## Rodando o job manualmente

```bash
python main.py
```

Os logs vão para o console (stdout/stderr). Para persistir em arquivo,
redirecione a saída, por exemplo `python main.py >> logs/job.log 2>&1`.

## Rodando os testes

```bash
pytest
```

Os testes não fazem nenhuma chamada de rede real: `requests_mock` intercepta
as chamadas HTTP em `wake_client`/`octadesk_client`, e `main.py` recebe
"dublês" (mocks) no lugar dos clientes reais em `tests/test_main.py`. Isso
significa que rodar `pytest` nunca envia mensagem de verdade nem depende de
credenciais configuradas.

## Agendando a execução diária

Como este é um script simples (não um serviço rodando continuamente), o
disparo diário fica por conta de um agendador externo já existente na infra
da empresa.

**Linux/cron** (rodando todo dia às 07:00, por exemplo):

```cron
0 7 * * * cd /caminho/do/projeto && /caminho/do/projeto/.venv/bin/python main.py >> logs/job.log 2>&1
```

**Windows (Agendador de Tarefas):** criar uma tarefa diária que execute
`C:\caminho\do\projeto\.venv\Scripts\python.exe C:\caminho\do\projeto\main.py`,
com "Iniciar em" apontando para a pasta do projeto (para o `.env.development`
e o `logs/` serem encontrados).

Configure o agendador para alertar (e-mail, etc.) quando o exit code for
diferente de `0`.

## Estrutura do projeto

```
wake_octadesk_sync/
├── main.py              # orquestração: Wake -> Octadesk -> sent_log
├── config.py             # leitura/validação de variáveis de ambiente
├── wake_client.py        # cliente HTTP da Wake (tem TODOs pendentes)
├── octadesk_client.py    # cliente HTTP do Octadesk (envio de template)
├── sent_log.py           # controle de idempotência (evita reenvio no mesmo dia)
├── tests/                # testes automatizados (pytest)
├── requirements.txt      # dependências de execução
├── requirements-dev.txt  # + dependências de teste
└── .env.example           # variáveis de ambiente necessárias (sem valores reais)
```

## Variáveis de ambiente

Ver `.env.example` para a lista completa com comentários. Nenhum segredo
deve ser commitado — tudo fica em `.env.development`, que está no
`.gitignore`.
