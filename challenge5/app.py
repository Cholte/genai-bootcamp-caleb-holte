"""
Alaska Department of Snow - Online Agent (Flask website)

Self-contained deployment of the ADS agent. It reuses the same backend the
notebook builds: BigQuery RAG (VECTOR_SEARCH over the embedded ADS documents),
the National Weather Service API for live weather, Model Armor for prompt
filtering + response validation, and Gemini 2.5 Flash for grounded answers.
Every prompt and response is logged to ads_agent.log.

PREREQUISITES
  - The notebook has already built the BigQuery embeddings table and the
    remote embedding model (this app only QUERIES them, it does not ingest).
  - Run in Cloud Shell (authenticated) or any environment with ADC.

RUN (Cloud Shell)
  export PROJECT_ID=$(gcloud config get-value project)
  pip install -r requirements.txt
  python app.py
  # then click Web Preview -> Preview on port 8080
"""

import os
import logging
import requests
from flask import Flask, request, jsonify, render_template

from google import genai
from google.genai import types
from google.cloud import bigquery, modelarmor_v1
from google.api_core.client_options import ClientOptions

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
PROJECT_ID      = os.environ.get("PROJECT_ID", "your-gcp-project-id")
BQ_LOCATION     = "us-central1"
DATASET_ID      = "alaska_snow"
FAQ_EMB_TABLE   = f"{PROJECT_ID}.{DATASET_ID}.ads_docs_embedded"
EMBED_MODEL     = f"{PROJECT_ID}.{DATASET_ID}.embedding_model"

GEMINI_LOCATION = "global"
MODEL_ID        = "gemini-2.5-flash"

MA_LOCATION     = "us-central1"
MA_ENDPOINT     = f"modelarmor.{MA_LOCATION}.rep.googleapis.com"
TEMPLATE_ID     = "ads-agent-security-template"
TEMPLATE_NAME   = f"projects/{PROJECT_ID}/locations/{MA_LOCATION}/templates/{TEMPLATE_ID}"

# Representative Alaska location for live weather (Anchorage).
ANCHORAGE_LAT, ANCHORAGE_LON = 61.2181, -149.9003
NWS_HEADERS = {
    "User-Agent": "AlaskaDeptOfSnowAgent (capstone-demo, contact@example.com)",
    "Accept": "application/geo+json",
}
WEATHER_WORDS = (
    "weather", "forecast", "snow", "temperature", "temp", "storm", "wind",
    "road", "plow", "plowing", "closure", "closed", "alert", "warning",
    "cold", "ice", "icy", "blizzard", "conditions",
)

# --------------------------------------------------------------------------
# Logging - every prompt and response is recorded
# --------------------------------------------------------------------------
logging.basicConfig(
    filename="ads_agent.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("ads_agent")

# --------------------------------------------------------------------------
# Clients
# --------------------------------------------------------------------------
bq = bigquery.Client(project=PROJECT_ID, location=BQ_LOCATION)
genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location=GEMINI_LOCATION)
ma_client = modelarmor_v1.ModelArmorClient(
    transport="rest",
    client_options=ClientOptions(api_endpoint=MA_ENDPOINT),
)

# --------------------------------------------------------------------------
# Model Armor - prompt filtering + response validation
# --------------------------------------------------------------------------
def _blocked(sanitization_result) -> bool:
    return sanitization_result.filter_match_state == modelarmor_v1.FilterMatchState.MATCH_FOUND

def screen_prompt(text: str) -> bool:
    r = ma_client.sanitize_user_prompt(
        request=modelarmor_v1.SanitizeUserPromptRequest(
            name=TEMPLATE_NAME,
            user_prompt_data=modelarmor_v1.DataItem(text=text),
        )
    )
    return _blocked(r.sanitization_result)

def screen_response(text: str) -> bool:
    r = ma_client.sanitize_model_response(
        request=modelarmor_v1.SanitizeModelResponseRequest(
            name=TEMPLATE_NAME,
            model_response_data=modelarmor_v1.DataItem(text=text),
        )
    )
    return _blocked(r.sanitization_result)

# --------------------------------------------------------------------------
# RAG retrieval - VECTOR_SEARCH over the embedded ADS documents
# --------------------------------------------------------------------------
def rag_search(question: str, k: int = 5):
    sql = f"""
    SELECT base.content AS content, base.source AS source, distance
    FROM VECTOR_SEARCH(
      TABLE `{FAQ_EMB_TABLE}`, 'embedding',
      (SELECT embedding FROM AI.GENERATE_EMBEDDING(
          MODEL `{EMBED_MODEL}`, (SELECT @q AS content))),
      top_k => {int(k)}, distance_type => 'COSINE')
    ORDER BY distance
    """
    job = bq.query(sql, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("q", "STRING", question)]))
    return [dict(row) for row in job.result()]

# --------------------------------------------------------------------------
# Backend API tool - National Weather Service (free, no key, needs User-Agent)
# --------------------------------------------------------------------------
def get_weather(lat: float = ANCHORAGE_LAT, lon: float = ANCHORAGE_LON) -> str:
    try:
        pts = requests.get(f"https://api.weather.gov/points/{lat},{lon}",
                           headers=NWS_HEADERS, timeout=15).json()
        fc = requests.get(pts["properties"]["forecast"],
                          headers=NWS_HEADERS, timeout=15).json()
        periods = fc["properties"]["periods"][:4]
        return " ".join(f"{p['name']}: {p['detailedForecast']}" for p in periods)
    except Exception as e:
        return f"(weather unavailable: {e})"

def get_alerts(area: str = "AK") -> str:
    try:
        data = requests.get(f"https://api.weather.gov/alerts/active?area={area}",
                            headers=NWS_HEADERS, timeout=15).json()
        feats = data.get("features", [])
        if not feats:
            return "No active alerts."
        return " | ".join(f["properties"].get("headline", "") for f in feats[:5])
    except Exception as e:
        return f"(alerts unavailable: {e})"

def needs_weather(question: str) -> bool:
    q = question.lower()
    return any(w in q for w in WEATHER_WORDS)

# --------------------------------------------------------------------------
# Agent orchestrator
# --------------------------------------------------------------------------
SYSTEM_INSTRUCTION = (
    "You are the virtual assistant for the Alaska Department of Snow (ADS). "
    "Answer using ONLY the provided context: official ADS documents and, when "
    "present, live weather data. If the answer is not in the context, say you "
    "do not have that information and suggest contacting ADS directly. Be "
    "concise, accurate, and friendly. Never invent facts that are not supported "
    "by the context."
)
REFUSAL = ("I'm sorry, I can't help with that request. I can answer questions about "
           "Alaska Department of Snow services and current weather conditions.")

def answer(question: str) -> str:
    # [1] input filtering
    if screen_prompt(question):
        logger.info(f"BLOCKED_INPUT | prompt={question!r}")
        return REFUSAL

    # [2] retrieve ADS document context
    docs = rag_search(question)
    context = "\n\n".join(f"[Source: {d['source']}] {d['content']}" for d in docs)

    # [3] add live weather only when the question calls for it
    weather = ""
    if needs_weather(question):
        weather = ("LIVE WEATHER (Anchorage): " + get_weather()
                   + "  ACTIVE ALERTS: " + get_alerts())

    # [4] grounded generation
    prompt = (f"ADS document context:\n{context}\n\n{weather}\n\n"
              f"User question: {question}\n\nAnswer:")
    resp = genai_client.models.generate_content(
        model=MODEL_ID, contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2, max_output_tokens=1024))
    out = (resp.text or "").strip()

    # [5] response validation
    if not out or screen_response(out):
        logger.info(f"BLOCKED_OUTPUT | prompt={question!r}")
        return REFUSAL

    logger.info(f"OK | prompt={question!r} | response={out!r}")
    return out

# --------------------------------------------------------------------------
# Flask routes
# --------------------------------------------------------------------------
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    question = (request.get_json(silent=True) or {}).get("message", "").strip()
    if not question:
        return jsonify({"reply": "Please type a question about Alaska Department of Snow services or the weather."})
    return jsonify({"reply": answer(question)})

if __name__ == "__main__":
    # Port 8080 matches the Cloud Shell Web Preview default.
    app.run(host="0.0.0.0", port=8080)
