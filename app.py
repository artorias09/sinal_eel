import os
import warnings
from datetime import timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler


warnings.filterwarnings("ignore")


st.set_page_config(
    page_title="Alertas de Alagamentos - Lorena",
    layout="centered",
)


st.markdown(
    """
<style>
  .block-container { max-width: 820px; padding-top: 2rem; }
  .metric-card {
      border-radius: 10px;
      padding: 1.2rem 1.5rem;
      margin-bottom: .5rem;
      font-family: sans-serif;
  }
  .card-baixo { background: #d4edda; border-left: 5px solid #28a745; }
  .card-medio { background: #fff3cd; border-left: 5px solid #ffc107; }
  .card-alto { background: #f8d7da; border-left: 5px solid #dc3545; }
  .card-critico { background: #d6dcff; border-left: 5px solid #3a5bd9; }
  .card-title { font-size: 1.05rem; font-weight: 700; margin-bottom: .3rem; }
  .card-prob { font-size: 2.2rem; font-weight: 800; }
  .card-label { font-size: 1rem; }
  .section-title {
      font-size: 1rem;
      font-weight: 600;
      color: #444;
      margin-top: 1.2rem;
  }
  .badge {
      display: inline-block;
      border-radius: 5px;
      padding: .25rem .65rem;
      font-size: .82rem;
      font-weight: 700;
      margin-right: .3rem;
      margin-top: .4rem;
  }
  .badge-fluvial { background: #d0e8ff; color: #0a4a8a; border: 1px solid #0a4a8a; }
  .badge-urbano { background: #fde8c8; color: #7a3a00; border: 1px solid #c06000; }
  .badge-misto { background: #e8d8f8; color: #4a0080; border: 1px solid #7020b0; }
  .badge-nenhum { background: #e8f5e9; color: #1b5e20; border: 1px solid #388e3c; }
  .data-note {
      background: #f5f5f5;
      border-left: 4px solid #888;
      border-radius: 6px;
      padding: .8rem 1rem;
      font-size: .86rem;
      color: #555;
      margin-top: 1rem;
  }
</style>
""",
    unsafe_allow_html=True,
)


CSV_PATH = "alagamentos_lorena_mvp_rastreavel.csv"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
LORENA_LATITUDE = -22.7308
LORENA_LONGITUDE = -45.1247
TIMEZONE = "America/Sao_Paulo"


TIPO_META = {
    "enchente_fluvial": ("Enchente fluvial", "badge-fluvial"),
    "alagamento_urbano": ("Alagamento urbano", "badge-urbano"),
    "misto_indefinido": ("Misto / indefinido", "badge-misto"),
    "enchente_ou_alagamento": ("Enchente ou alagamento", "badge-misto"),
    "nenhum": ("Sem evento esperado", "badge-nenhum"),
}


def find_csv():
    candidates = [
        CSV_PATH,
        os.path.join(os.path.dirname(__file__), CSV_PATH),
        "/mnt/user-data/uploads/alagamentos_lorena_mvp_rastreavel.csv",
        "/mnt/user-data/uploads/alagamentos_lorena_mvp.csv",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


@st.cache_resource(show_spinner="Treinando modelos...")
def load_and_train(path: str):
    df = pd.read_csv(path)

    le_bairro = LabelEncoder()
    df["bairro_enc"] = le_bairro.fit_transform(df["bairro"])

    features = [
        "bairro_enc",
        "chuva_1h_mm",
        "chuva_24h_mm",
        "nivel_paraiba_m",
        "delta_paraiba_m_h",
    ]
    x_train = df[features].values

    y_bin = df["alagou"].values
    model_bin = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    C=1.0,
                    max_iter=500,
                    class_weight="balanced",
                    random_state=42,
                    solver="lbfgs",
                ),
            ),
        ]
    )
    auc = cross_val_score(model_bin, x_train, y_bin, cv=5, scoring="roc_auc").mean()
    model_bin.fit(x_train, y_bin)

    le_tipo = LabelEncoder()
    y_tipo = le_tipo.fit_transform(df["tipo_evento"])
    model_tipo = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    C=1.0,
                    max_iter=500,
                    class_weight="balanced",
                    random_state=42,
                    solver="lbfgs",
                ),
            ),
        ]
    )
    model_tipo.fit(x_train, y_tipo)

    return model_bin, model_tipo, le_bairro, le_tipo, df, auc


@st.cache_data(ttl=900, show_spinner=False)
def buscar_dados_open_meteo():
    params = {
        "latitude": LORENA_LATITUDE,
        "longitude": LORENA_LONGITUDE,
        "current": "precipitation,rain,weather_code",
        "hourly": "precipitation,precipitation_probability,rain",
        "past_days": 1,
        "forecast_days": 2,
        "timezone": TIMEZONE,
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=12)
    response.raise_for_status()
    data = response.json()

    hourly = pd.DataFrame(data.get("hourly", {}))
    if hourly.empty or "time" not in hourly:
        raise ValueError("A resposta da Open-Meteo não trouxe série horária.")

    hourly["time"] = pd.to_datetime(hourly["time"])
    now = pd.Timestamp.now(tz=TIMEZONE).tz_localize(None)

    precipitation = pd.to_numeric(hourly.get("precipitation"), errors="coerce").fillna(0.0)
    probability = pd.to_numeric(hourly.get("precipitation_probability"), errors="coerce")
    hourly["precipitation"] = precipitation
    hourly["precipitation_probability"] = probability

    past = hourly[hourly["time"] <= now]
    recent_24h = hourly[(hourly["time"] > now - timedelta(hours=24)) & (hourly["time"] <= now)]
    next_6h = hourly[(hourly["time"] > now) & (hourly["time"] <= now + timedelta(hours=6))]

    current = data.get("current", {})
    current_precip = current.get("precipitation")
    last_hour_precip = float(past.iloc[-1]["precipitation"]) if not past.empty else 0.0
    chuva_1h = float(current_precip) if current_precip is not None else last_hour_precip
    chuva_24h = float(recent_24h["precipitation"].sum()) if not recent_24h.empty else chuva_1h
    chuva_proximas_6h = float(next_6h["precipitation"].sum()) if not next_6h.empty else 0.0
    prob_chuva_6h = (
        float(next_6h["precipitation_probability"].max())
        if not next_6h.empty and next_6h["precipitation_probability"].notna().any()
        else None
    )

    return {
        "chuva_1h": round(chuva_1h, 2),
        "chuva_24h": round(chuva_24h, 2),
        "chuva_proximas_6h": round(chuva_proximas_6h, 2),
        "prob_chuva_6h": prob_chuva_6h,
        "previsao_chuva": chuva_proximas_6h > 0 or (prob_chuva_6h is not None and prob_chuva_6h >= 40),
        "horario_referencia": current.get("time") or (str(past.iloc[-1]["time"]) if not past.empty else "indisponível"),
        "fonte": "Open-Meteo Forecast API",
    }


def classificar_risco(pct: float):
    if pct < 25:
        return (
            "Baixo",
            "card-baixo",
            "Condições normais. Manter monitoramento de rotina.",
        )
    if pct < 50:
        return (
            "Moderado",
            "card-medio",
            "Atenção recomendada. Acompanhar evolução da chuva e do rio.",
        )
    if pct < 75:
        return (
            "Alto",
            "card-alto",
            "Risco elevado. Evitar áreas historicamente sujeitas a alagamentos.",
        )
    return (
        "Crítico",
        "card-critico",
        "Risco crítico. Acionar protocolo preventivo e acompanhar a Defesa Civil.",
    )


def gerar_alerta_telegram_texto(bairro, pct, tipo_evento):
    tipo_label, _ = TIPO_META.get(tipo_evento, (tipo_evento, "badge-misto"))
    return (
        "ALERTA DE ALAGAMENTO - LORENA-SP\n"
        f"Bairro: {bairro}\n"
        f"Risco estimado: {pct:.1f}%\n"
        f"Tipo provável: {tipo_label}\n\n"
        "Recomendação: evite áreas baixas, acompanhe canais oficiais e mantenha atenção "
        "à evolução da chuva e do nível do Rio Paraíba do Sul.\n\n"
        "Mensagem automática de demonstração. Dados sujeitos a validação operacional."
    )


csv_path = find_csv()

st.title("Sistema de alerta de alagamentos - Lorena-SP")
st.caption(
    "Demonstração probabilística com modelo sintético-controlado e camada opcional de clima real."
)

if csv_path is None:
    st.error(
        f"Arquivo {CSV_PATH} não encontrado. Coloque-o no mesmo diretório que app.py e reinicie o app."
    )
    st.stop()

model_bin, model_tipo, le_bairro, le_tipo, df_train, auc = load_and_train(csv_path)
bairros = sorted(le_bairro.classes_.tolist())

with st.sidebar:
    st.header("Sobre o modelo")
    st.metric("Algoritmo", "Logistic Regression")
    st.metric("AUC-ROC (CV-5)", f"{auc:.3f}")
    st.metric("Amostras de treino", len(df_train))
    st.markdown("---")
    st.markdown(
        """
**Features usadas**
- Bairro codificado
- Chuva na última hora em mm
- Chuva acumulada em 24 h em mm
- Nível do Paraíba em m
- Variação do nível em m/h
"""
    )
    st.markdown("---")
    st.markdown("**Rastreabilidade do dataset**")
    st.markdown(
        """
- Origem: sintético controlado
- Fonte base: mapeamento de risco de Lorena-SP
- Confiança: alta para demonstração metodológica; baixa para evento histórico real
"""
    )

st.markdown('<p class="section-title">Modo de entrada</p>', unsafe_allow_html=True)
modo_entrada = st.radio(
    "Escolha como preencher os dados de chuva",
    ["Entrada manual", "Usar dados meteorológicos reais"],
    horizontal=True,
    label_visibility="collapsed",
)

dados_meteo = None
erro_meteo = None

if modo_entrada == "Usar dados meteorológicos reais":
    try:
        with st.spinner("Buscando dados meteorológicos reais para Lorena-SP..."):
            dados_meteo = buscar_dados_open_meteo()
    except (requests.RequestException, ValueError) as exc:
        erro_meteo = str(exc)

    if dados_meteo:
        st.success("Dados meteorológicos carregados via Open-Meteo para Lorena-SP.")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Chuva atual/última hora", f"{dados_meteo['chuva_1h']:.1f} mm")
        col_m2.metric("Chuva acumulada recente", f"{dados_meteo['chuva_24h']:.1f} mm")
        col_m3.metric("Previsão próximas 6 h", f"{dados_meteo['chuva_proximas_6h']:.1f} mm")

        prob_label = (
            f"{dados_meteo['prob_chuva_6h']:.0f}%"
            if dados_meteo["prob_chuva_6h"] is not None
            else "indisponível"
        )
        st.caption(
            f"Fonte: {dados_meteo['fonte']} | Referência: {dados_meteo['horario_referencia']} | "
            f"Probabilidade máxima de chuva nas próximas 6 h: {prob_label}"
        )
    else:
        st.warning(
            "Não foi possível carregar a Open-Meteo agora. Use a entrada manual ou tente novamente em alguns minutos."
        )
        st.caption(f"Detalhe técnico: {erro_meteo}")

st.markdown('<p class="section-title">Parâmetros de entrada</p>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    bairro = st.selectbox("Bairro", bairros)

    chuva_1h_default = dados_meteo["chuva_1h"] if dados_meteo else 20.0
    chuva_24h_default = dados_meteo["chuva_24h"] if dados_meteo else 60.0

    chuva_1h = st.number_input(
        "Chuva última hora (mm)",
        min_value=0.0,
        max_value=150.0,
        value=float(chuva_1h_default),
        step=0.5,
        disabled=dados_meteo is not None,
        help="Precipitação registrada na última hora. No modo real, vem da Open-Meteo.",
    )

    chuva_24h = st.number_input(
        "Chuva acumulada 24 h (mm)",
        min_value=0.0,
        max_value=300.0,
        value=float(chuva_24h_default),
        step=1.0,
        disabled=dados_meteo is not None,
        help="Precipitação acumulada recente. No modo real, vem da série horária da Open-Meteo.",
    )

with col2:
    nivel_paraiba = st.number_input(
        "Nível do Rio Paraíba do Sul (m)",
        min_value=0.0,
        max_value=10.0,
        value=2.5,
        step=0.05,
        help="Cota fluviométrica atual. Integração futura com ANA/HidroWeb e CEMADEN.",
    )

    delta_paraiba = st.number_input(
        "Variação do nível do rio (m/h)",
        min_value=-2.0,
        max_value=3.0,
        value=0.10,
        step=0.01,
        help="Taxa de subida ou descida do rio. Valor positivo indica subida.",
    )

st.info(
    "O nível do Rio Paraíba do Sul e sua variação ainda são informados manualmente. "
    "Integração futura com ANA/HidroWeb e CEMADEN."
)

run = st.button("Calcular risco", type="primary", width="stretch")

if run:
    bairro_enc = le_bairro.transform([bairro])[0]
    x_input = np.array([[bairro_enc, chuva_1h, chuva_24h, nivel_paraiba, delta_paraiba]])

    prob = model_bin.predict_proba(x_input)[0][1]
    pct = prob * 100

    tipo_enc = model_tipo.predict(x_input)[0]
    tipo_raw = le_tipo.inverse_transform([tipo_enc])[0]
    tipo_label, tipo_badge = TIPO_META.get(tipo_raw, (tipo_raw, "badge-misto"))

    nivel, classe, descricao = classificar_risco(pct)

    st.markdown('<p class="section-title">Resultado da previsão</p>', unsafe_allow_html=True)

    st.markdown(
        f"""
    <div class="metric-card {classe}">
      <div class="card-title">Nível de risco: {nivel}</div>
      <div class="card-prob">{pct:.1f}%</div>
      <div class="card-label">Probabilidade de alagamento ou enchente</div>
      <br>
      <div><b>Tipo de evento previsto:</b>
        <span class="badge {tipo_badge}">{tipo_label}</span>
      </div>
      <div style="margin-top:.5rem; color:#333">{descricao}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.progress(int(min(max(pct, 0), 100)), text=f"Probabilidade: {pct:.1f}%")

    if nivel in {"Alto", "Crítico"}:
        st.markdown('<p class="section-title">Mensagem simulada para Telegram</p>', unsafe_allow_html=True)
        st.code(gerar_alerta_telegram_texto(bairro, pct, tipo_raw), language="text")

    st.markdown(
        """
<div style="margin-top:.6rem; font-size:.86rem; color:#555">
  <b>Tipos de evento monitorados:</b>
  <span class="badge badge-fluvial">Enchente fluvial</span>
  Transbordamento do Rio Paraíba do Sul, associado ao nível e à variação do rio.
  <br>
  <span class="badge badge-urbano">Alagamento urbano</span>
  Acúmulo por drenagem insuficiente, associado a chuva intensa localizada.
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander("Ver parâmetros utilizados"):
        resumo = pd.DataFrame(
            {
                "Parâmetro": [
                    "Modo de entrada",
                    "Bairro",
                    "Chuva 1h (mm)",
                    "Chuva 24h (mm)",
                    "Nível Paraíba (m)",
                    "Variação do nível (m/h)",
                ],
                "Valor": [
                    modo_entrada,
                    bairro,
                    chuva_1h,
                    chuva_24h,
                    nivel_paraiba,
                    delta_paraiba,
                ],
            }
        )
        resumo["Valor"] = resumo["Valor"].astype(str)
        st.dataframe(resumo, width="stretch", hide_index=True)

    st.markdown(
        """
<div class="data-note">
  <b>Dados utilizados.</b><br>
  Este MVP mantém um modelo treinado com dados sintéticos controlados para validação inicial
  da metodologia. Os registros foram construídos com base em perfis de risco por bairro,
  mecanismos físicos de enchente fluvial e alagamento urbano, e faixas plausíveis de chuva
  e variáveis hidrométricas para a região de Lorena-SP.
  <br><br>
  <b>Limitação importante:</b> os dados de treino não correspondem a eventos históricos reais
  datados. A confiança é alta para demonstração metodológica e baixa para validação científica
  final. Antes de uso operacional, o sistema deve ser calibrado com séries reais de chuva,
  nível do rio e registros de ocorrência da Defesa Civil.
</div>
""",
        unsafe_allow_html=True,
    )

    hist = df_train[df_train["bairro"] == bairro]
    if not hist.empty:
        taxa = hist["alagou"].mean() * 100
        total = len(hist)
        with st.expander(f"Histórico sintético - {bairro}"):
            st.markdown(
                f"**{total} registros** no dataset | Taxa sintética de alagamento: **{taxa:.0f}%**"
            )
            st.dataframe(
                hist[
                    [
                        "chuva_1h_mm",
                        "chuva_24h_mm",
                        "nivel_paraiba_m",
                        "delta_paraiba_m_h",
                        "tipo_evento",
                        "alagou",
                    ]
                ].rename(
                    columns={
                        "chuva_1h_mm": "Chuva 1h",
                        "chuva_24h_mm": "Chuva 24h",
                        "nivel_paraiba_m": "Nível (m)",
                        "delta_paraiba_m_h": "Variação (m/h)",
                        "tipo_evento": "Tipo evento",
                        "alagou": "Alagou",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
