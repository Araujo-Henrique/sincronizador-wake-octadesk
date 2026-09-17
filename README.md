# wake-octadesk-sync

Job diário que substitui o processo manual de "subir planilha de números no
Octadesk": busca na Wake os clientes cadastrados no dia anterior e dispara,
via API do Octadesk, a mensagem de template de WhatsApp já aprovada para cada
um deles.

## O que o job faz

1. Calcula a data de "ontem".
2. Chama a API da Wake pedindo os clientes cadastrados nessa data (com
   paginação — a Wake nunca devolve mais de 50 registros por chamada).
3. Para cada cliente, chama a API do Octadesk (`POST /chat/send-template`)
   para enviar o template de WhatsApp já aprovado, usando só o telefone do
   cliente (não é necessário e-mail — ver explicação abaixo). O envio é
   configurado para deixar o bot/fluxo do canal engatar a conversa em
   seguida, em vez de atribuir direto a um agente humano.
4. Registra em `logs/sent_log.jsonl` quem já recebeu mensagem em cada data,
   para não duplicar envio caso o job seja executado mais de uma vez no
   mesmo dia (idempotência — ver [GUIA_DO_PROJETO.md](GUIA_DO_PROJETO.md)).
5. Termina com exit code `0` se tudo deu certo, ou `1` se algo falhou — isso é
   o que permite ao cron/Agendador de Tarefas detectar e alertar sobre falhas.

### Por que não precisa de e-mail

O endpoint do Octadesk usado aqui (`/chat/send-template`) identifica o
destinatário pelo campo `code` dentro de `target.contact`, que é o próprio
número de WhatsApp — `email` e `name` são opcionais e só existem para
preencher variáveis do template (`email-contato`, `nome-contato`), não para
identificar o contato. Por isso o fluxo Wake → Octadesk aqui só precisa do
telefone.

## Setup local

Requer Python 3.11+ (usa sintaxe de tipos moderna, tipo `list[str]` sem
precisar importar `typing.List`).

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env
# preencha o .env com as credenciais reais (ver seção "Variáveis de ambiente")
```

## Rodando o job manualmente

```bash
python -m src.main
```

Os logs vão para o console (stdout/stderr). Para persistir em arquivo,
redirecione a saída, por exemplo `python -m src.main >> logs/job.log 2>&1`.

## Rodando os testes

```bash
pytest
```

Os testes não fazem nenhuma chamada de rede real: `requests_mock` intercepta
as chamadas HTTP em `wake_client`/`octadesk_client`, e `main.run()` recebe
"dublês" (mocks) no lugar dos clientes reais em `tests/test_main.py`. Isso
significa que rodar `pytest` nunca envia mensagem de verdade nem depende de
credenciais configuradas.

## Agendando a execução diária

Como este é um script simples (não um serviço rodando continuamente), o
disparo diário fica por conta de um agendador externo já existente na infra
da empresa.

**Linux/cron** (rodando todo dia às 07:00, por exemplo):

```cron
0 7 * * * cd /caminho/do/projeto && /caminho/do/projeto/venv/bin/python -m src.main >> logs/job.log 2>&1
```

**Windows (Agendador de Tarefas):** criar uma tarefa diária que execute
`C:\caminho\do\projeto\venv\Scripts\python.exe -m src.main`, com "Iniciar em"
apontando para a pasta do projeto (para o `.env` e o `logs/` serem
encontrados).

Configure o agendador para alertar (e-mail, etc.) quando o exit code for
diferente de `0`.

## Estrutura do projeto

```
wake_octadesk/
├── src/
│   ├── config.py           # leitura/validação de variáveis de ambiente
│   ├── wake_client.py      # cliente HTTP da Wake (busca clientes, com paginação)
│   ├── octadesk_client.py  # cliente HTTP do Octadesk (envio de template)
│   ├── sent_log.py         # controle de idempotência (evita reenvio no mesmo dia)
│   └── main.py             # orquestração: Wake -> Octadesk -> sent_log
├── tests/                  # testes automatizados (pytest), um arquivo por módulo
├── logs/                   # sent_log.jsonl e logs de execução (gitignored)
├── requirements.txt        # dependências de execução
├── requirements-dev.txt    # + dependências de teste
├── .env.example             # variáveis de ambiente necessárias
├── README.md                # este arquivo — setup e operação
```

## Variáveis de ambiente

Ver [.env.example](.env.example) para a lista completa.
Nenhum segredo deve ser commitado — tudo fica em `.env`, que está no
`.gitignore`.

`WAKE_API_BASE_URL` = Host da API da Wake, ex: `https://api.fbits.net`
`WAKE_AUTH_HEADER_NAME` = Nome do header de autenticação (ex: `Authorization`)
`WAKE_API_TOKEN` = Token gerado no painel Wake, em Extensões e Integrações > Tokens
`WAKE_CUSTOMERS_ENDPOINT` = Path do endpoint de listagem de clientes | não origatório - (padrão `/usuarios`)
`OCTADESK_API_BASE_URL` = Host da API do Octadesk (informado pelo suporte deles)
`OCTADESK_API_KEY` = Chave de API (header `x-api-key`)
`OCTADESK_AGENT_EMAIL` = E-mail do agente (header `octa-agent-email`)
`OCTADESK_WABA_NUMBER` = Número de origem do WhatsApp — com ou sem `+`, o código normaliza
`OCTADESK_TEMPLATE_ID` = Id do template de WhatsApp aprovado a ser enviado
`SENT_LOG_PATH` = Onde fica o arquivo de idempotência | não obrigatório -  (padrão `logs/sent_log.jsonl`)
`REQUEST_TIMEOUT_SECONDS` = Timeout das chamadas HTTP | não obrigatória -  (padrão `15`) | 

## Histórico: bugs reais já encontrados e corrigidos

Vale registrar aqui porque explicam **por que** o código de hoje é feito do
jeito que é — sem esse contexto, algumas escolhas (normalizar o `+`, paginar
manualmente, `automaticAssign: false`) parecem complexidade desnecessária.

1. **Nomes de campo da resposta da Wake estavam errados.** O código original
   esperava `Nome`/`Telefone_Celular` (capitalizado); a API real devolve
   `nome`/`telefoneCelular` (camelCase). Resultado: 100% dos clientes eram
   descartados como "inválidos" silenciosamente. Corrigido em
   `WakeCustomer.from_api` ([src/wake_client.py](src/wake_client.py)).
2. **`OCTADESK_WABA_NUMBER` sem `+` na frente quebrava o envio** com um erro
   confuso (`"Template is not applyable for this origin"`, código
   `NOT_MAPPED`) que parecia ser sobre vínculo de template, mas era só
   formatação. Corrigido normalizando em `_with_plus_prefix`
   ([src/config.py](src/config.py)).
3. **A resposta da Wake é paginada (50 registros por página) e o código não
   paginava.** Isso fazia o job nunca enxergar nenhum cliente cadastrado
   depois de um certo ponto no histórico — o bug ficava mascarado porque,
   até esse ponto, sempre havia menos de 50 registros no total. Corrigido em
   `WakeClient._fetch_all_pages` ([src/wake_client.py](src/wake_client.py)),
   usando o header `X-Total-Count` pra saber quantas páginas buscar.
4. **`dataInicial`/`dataFinal` da Wake têm semântica inclusivo/exclusivo**,
   não confirmada em nenhuma documentação pública — descoberta testando
   contra a API real.
5. **`"automaticAssign": true` no envio do template pulava o bot/fluxo do
   canal e atribuía a conversa direto a um agente humano.** Confirmado
   testando manualmente (respondendo a um envio real de teste) que
   `automaticAssign: false` é o que deixa o bot engatar antes de cair num
   humano. Corrigido em `OctadeskClient.send_template_message`
   ([src/octadesk_client.py](src/octadesk_client.py)).

Todos esses foram encontrados rodando testes manuais **de leitura** contra a
API real (sem nunca disparar mensagem pra cliente de verdade) e envios de
teste controlados para um número seguro — não estático, não só lendo código.
