# Sistema de alerta de alagamentos - Lorena-SP

Demo em Streamlit para estimar risco de alagamento/enchente em bairros de Lorena-SP, com monitor automático opcional via Telegram.

O modelo continua sendo uma prova de conceito treinada com o arquivo sintético-controlado `alagamentos_lorena_mvp_rastreavel.csv`. A aplicação também oferece um modo de entrada com dados meteorológicos reais da Open-Meteo, sem chave de API.

## Aviso importante

Este é um MVP acadêmico. O sistema não deve ser usado como alerta público operacional sem validação adicional, calibração com dados históricos reais e integração oficial com fontes hidrológicas e Defesa Civil.

## Arquivos necessários

- `app.py`
- `monitor.py`
- `alagamentos_lorena_mvp_rastreavel.csv`
- `requirements.txt`
- `.github/workflows/monitor.yml`

## Como rodar localmente

1. Crie e ative um ambiente virtual:

```bash
python -m venv .venv
```

No Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Rode o app:

```bash
streamlit run app.py
```

4. Abra o endereço local indicado pelo Streamlit, normalmente:

```text
http://localhost:8501
```

## Dados meteorológicos reais

No modo `Usar dados meteorológicos reais`, o app consulta a Open-Meteo para Lorena-SP:

- Latitude: `-22.7308`
- Longitude: `-45.1247`
- Precipitação atual ou última hora
- Chuva acumulada recente
- Chuva prevista para as próximas horas
- Probabilidade de chuva quando disponível

O nível do Rio Paraíba do Sul e sua variação ainda são inputs manuais no app. No `monitor.py`, esses valores usam padrões seguros para o MVP:

- `NIVEL_PARAIBA_M=2.5`
- `DELTA_PARAIBA_M_H=0.10`

Se quiser ajustar esses valores no GitHub Actions, crie variáveis ou secrets com esses nomes e adicione ao workflow.

## Como configurar o Telegram

1. No Telegram, converse com `@BotFather`.
2. Crie um bot com `/newbot`.
3. Copie o token do bot.
4. Envie uma mensagem qualquer para o bot criado.
5. Descubra o `chat_id` usando a API do Telegram:

```text
https://api.telegram.org/botSEU_TOKEN/getUpdates
```

Procure o campo `chat.id` na resposta.

Não coloque tokens diretamente no código.

## Secrets necessários

Configure estes secrets no GitHub:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Caminho no GitHub:

```text
Repository > Settings > Secrets and variables > Actions > New repository secret
```

O app Streamlit também aceita esses nomes via variáveis de ambiente ou via `st.secrets`. Se eles não existirem, o app continua funcionando e apenas mostra aviso ao tentar enviar o alerta de teste.

## Monitor automático

O arquivo `monitor.py` executa o fluxo automático:

1. Carrega `alagamentos_lorena_mvp_rastreavel.csv`.
2. Treina o mesmo modelo probabilístico usado no `app.py`.
3. Consulta a Open-Meteo para Lorena-SP.
4. Calcula o risco para todos os bairros monitorados.
5. Identifica bairros com risco maior ou igual a `60%`.
6. Envia um alerta único via Telegram com a lista de bairros em risco.

Se nenhum bairro atingir `60%`, o monitor apenas registra o resultado no log. Se o Telegram não estiver configurado, o monitor também não quebra: ele imprime um aviso e finaliza normalmente.

Para rodar manualmente:

```bash
python monitor.py
```

## GitHub Actions

O workflow `.github/workflows/monitor.yml` roda automaticamente a cada 30 minutos:

```text
*/30 * * * *
```

Ele também pode ser executado manualmente pela aba `Actions` do GitHub usando `Run workflow`.

## Como publicar no Streamlit Community Cloud

1. Crie um repositório no GitHub.
2. Envie para o repositório os arquivos do projeto.
3. Acesse [Streamlit Community Cloud](https://streamlit.io/cloud).
4. Escolha `New app`.
5. Selecione o repositório, a branch e informe:

```text
Main file path: app.py
```

6. Clique em `Deploy`.

Não é necessário configurar secrets para a Open-Meteo, pois a API usada nesta demo não exige chave.

## Limitação da demo

Os dados de treino são sintéticos-controlados e não correspondem a eventos históricos reais datados. A confiança é alta para demonstração metodológica e baixa para validação científica final. Antes de uso operacional, o sistema deve ser calibrado com séries reais de chuva, nível do rio e registros de ocorrência da Defesa Civil.


```text
Main file path: app.py
```

6. Clique em `Deploy`.

Não é necessário configurar secrets para a Open-Meteo, pois a API usada nesta demo não exige chave.

## Limitação da demo

Este app não deve ser usado como sistema operacional de alerta público sem validação adicional. Para uso real, é necessário calibrar o modelo com séries históricas confiáveis de chuva, nível do rio e ocorrências registradas pela Defesa Civil.
