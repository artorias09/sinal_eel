import os
import warnings
from datetime import timedelta

import numpy as np
import pandas as pd
import requests
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler


warnings.filterwarnings("ignore")


CSV_PATH = "alagamentos_lorena_mvp_rastreavel.csv"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
LORENA_LATITUDE = -22.7308
LORENA_LONGITUDE = -45.1247
TIMEZONE = "America/Sao_Paulo"
ALERT_THRESHOLD = 0.0


TIPO_META = {
    "enchente_fluvial": "Enchente fluvial",
    "alagamento_urbano": "Alagamento urbano",
    "misto_indefinido": "Misto / indefinido",
    "enchente_ou_alagamento": "Enchente ou alagamento",
    "nenhum": "Sem evento esperado",
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


def load_and_train(path):
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

    return model_bin, model_tipo, le_bairro, le_tipo, df


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
        raise ValueError("A resposta da Open-Meteo nao trouxe serie horaria.")

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
        "horario_referencia": current.get("time") or (str(past.iloc[-1]["time"]) if not past.empty else "indisponivel"),
        "fonte": "Open-Meteo Forecast API",
    }


def read_float_env(name, default):
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return float(raw_value.replace(",", "."))
    except ValueError:
        print(f"Variavel {name} invalida: {raw_value!r}. Usando valor padrao {default}.")
        return default


def send_telegram_alert(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram nao configurado. Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=12)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Falha ao enviar alerta Telegram: {exc}")
        return False

    print("Alerta enviado ao Telegram com sucesso.")
    return True


def prever_riscos(model_bin, model_tipo, le_bairro, le_tipo, dados_meteo):
    nivel_paraiba = read_float_env("NIVEL_PARAIBA_M", 2.5)
    delta_paraiba = read_float_env("DELTA_PARAIBA_M_H", 0.10)

    resultados = []
    for bairro in sorted(le_bairro.classes_.tolist()):
        bairro_enc = le_bairro.transform([bairro])[0]
        x_input = np.array(
            [
                [
                    bairro_enc,
                    dados_meteo["chuva_1h"],
                    dados_meteo["chuva_24h"],
                    nivel_paraiba,
                    delta_paraiba,
                ]
            ]
        )

        pct = float(model_bin.predict_proba(x_input)[0][1] * 100)
        tipo_enc = model_tipo.predict(x_input)[0]
        tipo_raw = le_tipo.inverse_transform([tipo_enc])[0]

        resultados.append(
            {
                "bairro": bairro,
                "risco_pct": pct,
                "tipo_evento": tipo_raw,
                "tipo_label": TIPO_META.get(tipo_raw, tipo_raw),
                "nivel_paraiba": nivel_paraiba,
                "delta_paraiba": delta_paraiba,
            }
        )

    return sorted(resultados, key=lambda item: item["risco_pct"], reverse=True)


def montar_mensagem_alerta(alertas, dados_meteo):
    prob_chuva = dados_meteo["prob_chuva_6h"]
    prob_label = f"{prob_chuva:.0f}%" if prob_chuva is not None else "indisponivel"

    linhas = [
        "ALERTA AUTOMATICO DE ALAGAMENTO - LORENA-SP",
        "",
        f"Bairros com risco >= {ALERT_THRESHOLD:.0f}%:",
    ]

    for item in alertas:
        linhas.append(
            f"- {item['bairro']}: {item['risco_pct']:.1f}% | {item['tipo_label']}"
        )

    linhas.extend(
        [
            "",
            "Dados meteorologicos:",
            f"- Chuva atual/ultima hora: {dados_meteo['chuva_1h']:.1f} mm",
            f"- Chuva acumulada 24 h: {dados_meteo['chuva_24h']:.1f} mm",
            f"- Previsao proximas 6 h: {dados_meteo['chuva_proximas_6h']:.1f} mm",
            f"- Probabilidade maxima de chuva 6 h: {prob_label}",
            f"- Referencia: {dados_meteo['horario_referencia']}",
            "",
            "Recomendacao: evitar areas baixas, acompanhar canais oficiais e manter atencao a evolucao da chuva e do Rio Paraiba do Sul.",
            "",
            "MVP academico. Dados sujeitos a validacao operacional e nao substituem alertas oficiais da Defesa Civil.",
        ]
    )
    return "\n".join(linhas)


def main():
    csv_path = find_csv()
    if csv_path is None:
        raise FileNotFoundError(
            f"Arquivo {CSV_PATH} nao encontrado. Coloque-o no mesmo diretorio que monitor.py."
        )

    print(f"Carregando dataset: {csv_path}")
    model_bin, model_tipo, le_bairro, le_tipo, _ = load_and_train(csv_path)

    print("Consultando Open-Meteo para Lorena-SP...")
    dados_meteo = buscar_dados_open_meteo()

    resultados = prever_riscos(model_bin, model_tipo, le_bairro, le_tipo, dados_meteo)
    alertas = [item for item in resultados if item["risco_pct"] >= ALERT_THRESHOLD]

    print("Maiores riscos calculados:")
    for item in resultados[:5]:
        print(f"- {item['bairro']}: {item['risco_pct']:.1f}% ({item['tipo_label']})")

    if not alertas:
        print(f"Nenhum bairro com risco >= {ALERT_THRESHOLD:.0f}%. Telegram nao acionado.")
        return

    message = montar_mensagem_alerta(alertas, dados_meteo)
    print(message)
    send_telegram_alert(message)


if __name__ == "__main__":
    main()
