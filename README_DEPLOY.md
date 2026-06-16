# Sistema de alerta de alagamentos - Lorena-SP

Demo em Streamlit para estimar risco de alagamento/enchente em bairros de Lorena-SP.

O modelo continua sendo uma prova de conceito treinada com o arquivo sintético-controlado `alagamentos_lorena_mvp_rastreavel.csv`. A aplicação também oferece um modo de entrada com dados meteorológicos reais da Open-Meteo, sem chave de API.

## Arquivos necessários

- `app.py`
- `alagamentos_lorena_mvp_rastreavel.csv`
- `requirements.txt`

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

O nível do Rio Paraíba do Sul e sua variação ainda são inputs manuais. A integração operacional futura deve buscar dados em fontes como ANA/HidroWeb e CEMADEN.

## Como publicar no Streamlit Community Cloud

1. Crie um repositório no GitHub.
2. Envie para o repositório os arquivos:
   - `app.py`
   - `alagamentos_lorena_mvp_rastreavel.csv`
   - `requirements.txt`
3. Acesse [Streamlit Community Cloud](https://streamlit.io/cloud).
4. Escolha `New app`.
5. Selecione o repositório, a branch e informe:

```text
Main file path: app.py
```

6. Clique em `Deploy`.

Não é necessário configurar secrets para a Open-Meteo, pois a API usada nesta demo não exige chave.

## Limitação da demo

Este app não deve ser usado como sistema operacional de alerta público sem validação adicional. Para uso real, é necessário calibrar o modelo com séries históricas confiáveis de chuva, nível do rio e ocorrências registradas pela Defesa Civil.
