import os
import httpx

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from conversation import ConversationStore


SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
CONVERSATION_MAX_MESSAGES = int(os.getenv("CONVERSATION_MAX_MESSAGES", "12"))

GEMINI_MODELS = [
    GEMINI_MODEL,
    "gemini-3.7-flash",
    "gemini-3.6-flash",
]

GEMINI_BASE_URL = (
    "https://termux.yousef-azimi.workers.dev/v1beta/models/"
)

app = App(token=SLACK_BOT_TOKEN)
conversation_store = ConversationStore(
    max_messages=CONVERSATION_MAX_MESSAGES,
)


def clean_mention(text: str) -> str:
    return text.strip()


def extract_gemini_text(data: dict) -> str:
    candidates = data.get("candidates", [])

    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {data}")

    texts = []

    for candidate in candidates:
        parts = candidate.get("content", {}).get("parts", [])

        for part in parts:
            text = part.get("text")

            if text:
                texts.append(text)

    result = "\n".join(texts).strip()

    if not result:
        raise RuntimeError(f"Gemini returned no text: {data}")

    return result


def ask_gemini(
    user_text: str,
    history: list[dict[str, str]],
) -> str:
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }

    contents = list(history)
    contents.append(
        {
            "role": "user",
            "parts": [{"text": user_text}],
        }
    )

    payload = {
        "contents": contents,
    }

    last_error = None

    with httpx.Client(timeout=120.0) as client:
        for model in GEMINI_MODELS:
            url = f"{GEMINI_BASE_URL}{model}:generateContent"

            print(f"Gemini request: {model}")

            for attempt in range(2):
                try:
                    response = client.post(
                        url,
                        headers=headers,
                        json=payload,
                    )
                except Exception as exc:
                    last_error = (
                        f"{model} attempt={attempt + 1}: {exc}"
                    )
                    print(last_error)
                    continue

                if response.status_code == 200:
                    data = response.json()
                    print(f"Gemini success: {model}")
                    return extract_gemini_text(data)

                last_error = (
                    f"{model} attempt={attempt + 1} "
                    f"HTTP {response.status_code}: {response.text}"
                )

                print(last_error)

                if response.status_code not in (
                    429,
                    500,
                    502,
                    503,
                    504,
                ):
                    raise RuntimeError(last_error)

    raise RuntimeError(
        "All Gemini models failed.\n"
        f"Last error: {last_error}"
    )


@app.event("app_mention")
def handle_app_mention(event, say):
    user_text = clean_mention(event.get("text", ""))
    channel_id = event.get("channel")
    thread_ts = event.get("thread_ts")

    if not user_text:
        say(
            text="سلام 👋 سوالت رو بفرست.",
            thread_ts=event.get("ts"),
        )
        return

    if not channel_id:
        raise RuntimeError("Slack event did not include a channel id")

    try:
        history = conversation_store.get(channel_id, thread_ts)
        answer = ask_gemini(user_text, history)

        conversation_store.append(
            channel_id,
            thread_ts,
            "user",
            user_text,
        )
        conversation_store.append(
            channel_id,
            thread_ts,
            "model",
            answer,
        )

        print(
            "Conversation updated: "
            f"scope={conversation_store.key(channel_id, thread_ts)} "
            f"messages={conversation_store.size(channel_id, thread_ts)}"
        )

        say(
            text=answer,
            thread_ts=event.get("ts"),
        )

    except Exception as exc:
        print(f"YasinAI error: {exc}")

        say(
            text=f"❌ خطا در اتصال به Gemini:\n`{exc}`",
            thread_ts=event.get("ts"),
        )


if __name__ == "__main__":
    print("YasinAI starting...")
    print(f"Gemini primary model: {GEMINI_MODEL}")
    print(f"Gemini fallback models: {', '.join(GEMINI_MODELS[1:])}")
    print(
        "Conversation memory: "
        f"process-local, max_messages={CONVERSATION_MAX_MESSAGES}"
    )
    print("Slack Socket Mode: starting")

    SocketModeHandler(
        app,
        SLACK_APP_TOKEN,
    ).start()
