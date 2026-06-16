# GenAI Bootcamp - Skills Assessment (Caleb Holte)

This repository contains my solutions to the five-challenge Google Cloud generative AI
skills assessment. Each challenge was implemented in Python (Jupyter notebooks run in Agent
Platform Colab Enterprise) on Google Cloud, using Gemini, BigQuery, Model Armor, the Gen AI
Evaluation Service, and related services.

## Challenges

| # | Challenge | What it does | Artifact |
| --- | --- | --- | --- |
| 1 | Gemini prompt security | A coding/IT support chatbot with system instructions and restrictions, Model Armor input/output filtering, and Gemini safety settings; validates that only safe, in-scope responses are returned. | [`challengelab01-calebholte.ipynb`](challengelab01-calebholte.ipynb) |
| 2 | BigQuery RAG | An Aurora Bay FAQ assistant: loads documents into BigQuery, embeds them with `text-embedding-005`, retrieves with `VECTOR_SEARCH`, and answers grounded in the retrieved context. | [`challengelab02-calebholte.ipynb`](challengelab02-calebholte.ipynb) |
| 3 | Testing and evaluation | Two Gemini-powered functions (question classifier + social-media-post generator), pytest unit tests, and prompt comparisons using the Gen AI Evaluation Service. | [`challengelab03-calebholte.ipynb`](challengelab03-calebholte.ipynb) |
| 4 | Conversational Agent (bonus) | An "Aurora Bay Agent" built in AI Applications / Conversational Agents with a playbook and a data store connected to a Cloud Storage bucket, answering resident FAQs without hallucinating. | [`exported_agent_Aurora Bay Agent.zip`](exported_agent_Aurora%20Bay%20Agent.zip), [`aurora_bay_agent.png`](aurora_bay_agent.png), [`aurora_bay_agent_data_store.png`](aurora_bay_agent_data_store.png) |
| 5 | Capstone - Alaska Department of Snow Online Agent | A secure, production-quality agent: BigQuery RAG over ADS documents, live National Weather Service data, Model Armor filtering, logging, unit tests, evaluation, and a deployed Flask chat website. | [`challenge5/`](challenge5/) |

The capstone (Challenge 5) has its own detailed README, architecture diagram, and deployment
instructions in the [`challenge5/`](challenge5/) folder.

## Tech used

Gemini 2.5 (Flash / Pro), BigQuery (ML remote models, `AI.GENERATE_EMBEDDING`,
`VECTOR_SEARCH`), Model Armor, Sensitive Data Protection, the Vertex AI Gen AI Evaluation
Service, the National Weather Service API, Flask, and pytest - all orchestrated from Python
notebooks in Agent Platform Colab Enterprise.
