import json
import os

import requests


BASE_DIR = os.path.dirname(__file__) or "."
SUBSCRIBERS_PATH = os.path.join(BASE_DIR, "subscribers.json")


def get_bot_token():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Defina TELEGRAM_BOT_TOKEN antes de executar este script.")
    return token


def load_existing_subscribers(path):
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Nao foi possivel ler {path}: {exc}. Recriando lista.")
        return []

    chat_ids = []
    for item in data:
        chat_id = str(item).strip()
        if chat_id and chat_id not in chat_ids:
            chat_ids.append(chat_id)
    return chat_ids


def fetch_updates(token):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    response = requests.get(url, timeout=12)
    response.raise_for_status()

    payload = response.json()
    if not payload.get("ok"):
        description = payload.get("description", "erro desconhecido")
        raise RuntimeError(f"Telegram getUpdates falhou: {description}")

    return payload.get("result", [])


def extract_chat_ids(updates):
    chat_ids = []
    for update in updates:
        message = update.get("message")
        if not message:
            continue

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if chat_id is None:
            continue

        chat_id = str(chat_id).strip()
        if chat_id and chat_id not in chat_ids:
            chat_ids.append(chat_id)

    return chat_ids


def save_subscribers(path, chat_ids):
    ordered_chat_ids = sorted(set(str(chat_id).strip() for chat_id in chat_ids if str(chat_id).strip()))
    with open(path, "w", encoding="utf-8") as file:
        json.dump(ordered_chat_ids, file, indent=2)
        file.write("\n")
    return ordered_chat_ids


def main():
    token = get_bot_token()
    existing_chat_ids = load_existing_subscribers(SUBSCRIBERS_PATH)

    print("Consultando Telegram getUpdates...")
    updates = fetch_updates(token)
    update_chat_ids = extract_chat_ids(updates)

    subscribers = save_subscribers(
        SUBSCRIBERS_PATH,
        existing_chat_ids + update_chat_ids,
    )

    print(f"Chats encontrados nesta consulta: {len(update_chat_ids)}")
    print(f"Total de inscritos salvos em {SUBSCRIBERS_PATH}: {len(subscribers)}")
    for chat_id in subscribers:
        print(f"- {chat_id}")

    if not subscribers:
        print("Nenhum inscrito encontrado. Peça para o usuario enviar /start ao bot e rode novamente.")


if __name__ == "__main__":
    main()
