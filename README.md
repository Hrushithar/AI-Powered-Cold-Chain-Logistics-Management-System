# ❄️ AI-Powered Cold Chain Logistics Management System

**FDE Supply Chain Dispatch Console** — an enterprise-grade, AI-powered decision-support platform for cold-chain logistics operations. It lets business stakeholders "chat with their data" to detect cold-chain anomalies, assess route disruptions, and execute SOP-compliant action plans in real time.

---

## 🚀 Live Deployment

The application is deployed on the **Render dashboard** and is live at:

> **https://ai-powered-cold-chain-logistics.onrender.com/**

You can open the link directly to use the **Dispatch Console** and the **Security & Audit Logs** viewer without any local setup.

---

## 📋 Overview

Cold-chain logistics requires constant monitoring of temperature-sensitive cargo, real-time awareness of corridor/weather hazards, and strict adherence to compliance SOPs. This system combines:

*   **Agentic reasoning** (LangGraph) that autonomously decides which data sources to query.
*   **Telemetry SQL queries** against a legacy enterprise fleet database.
*   **Live corridor conditions** from an external weather API (Open-Meteo) via GPS coordinates.
*   **Vector-search retrieval** of cold-chain SOPs from Pinecone (semantic search over policy documents).
*   **LLM fallback resilience** (Gemini primary → Groq fallback on quota/rate-limit errors).
*   **Full audit trail** of every agent execution written to a SQL audit table.

---

## 🎯 Key Features

| Feature | Description |
|---|---|
| **🧊 Dispatch Console** | Chat-based interface to query fleet telemetry, corridor updates, and compliance thresholds. |
| **🤖 Agentic Reasoner** | LangGraph state machine that routes queries through telemetry → corridor → SOP tools automatically. |
| **📊 Structured Incident Reports** | Responses follow a fixed business format: Executive Summary → Telemetry & Environment Analysis → Required Action Plan with SOP citations. |
| **🌐 Live Corridor Telemetry** | Real-time temperature, wind speed, and congestion index fetched from live REST APIs by GPS coordinates. |
| **📚 SOP Knowledge Base** | Semantic search over cold-chain Standard Operating Procedures stored in Pinecone. |
| **🛡️ Security & Audit Logs** | Admin-gated viewer for inspecting the `FDE_VIEWS.AgentAuditLog` table (session, node, tool, payload). |
| **🔁 Session Management** | Isolated conversation threads per user via `thread_id` with one-click session purge. |
| **🔄 LLM Failover** | Automatic Gemini → Groq fallback when the primary LLM hits quota or rate limits. |
| **⚡ Trace Transparency** | Expandable tool-input/output panels so users can inspect exactly what the agent executed. |
| **🗄️ Legacy Data Ingestion** | Scripts to load legacy fleet CSVs into MSSQL and index SOPs into Pinecone with change-detection caching. |

---

## 🛠️ Tech Stack

**Language & Runtime**
*   Python 3.12

**Core Framework**
*   Streamlit — web UI
*   LangGraph — agent orchestration with `MemorySaver` checkpointer
*   LangChain — tools, embeddings, vector-store integrations

**AI / ML**
*   Google Gemini (`gemini-2.5-flash`, `gemini-embedding-001`)
*   Groq (`openai/gpt-oss-20b`) — fallback LLM
*   HuggingFace `BAAI/bge-m3` — local embedding option
*   `sentence-transformers`, `scikit-learn`, `torch`

**Data & Vector Store**
*   Microsoft SQL Server (via `pyodbc` / SQLAlchemy, ODBC Driver 18)
*   Pinecone Serverless — vector index for compliance SOPs (`fde-sop-index-gemini` / `fde-sop-index-local`)
*   Pandas, openpyxl, pypdf

**Configuration & Deployment**
*   `python-dotenv` — environment variable management
*   Render — hosting platform
*   `runtime.txt` — pins Python 3.12 for Render builds

---

## 📁 Project Structure

```
AI-Powered Cold Chain Logistics Management System/
├── README.md
├── requirements.txt          # Python dependencies
├── runtime.txt               # Python version pin (3.12) for Render
├── .env                      # Environment secrets (excluded from git)
├── .gitignore
├── .streamlit/
│   └── config.toml           # Streamlit server config
├── data/
│   ├── raw/
│   │   └── dynamic_supply_chain_logistics_dataset.csv
│   ├── policy/
│   │   └── Cold_Chain_Incident_SOP_v2.md
│   ├── legacy_ingest.db
│   └── cache/                # Ingestion hash cache (change detection)
├── scripts/
│   ├── ingest_legacy_data.py         # Loads CSV into legacy MSSQL schema
│   ├── ingest_sop_pinecone.py        # Indexes SOPs into Pinecone
│   └── setup_security_and_view.sql   # SQL schema/views for audit logging
└── src/
    ├── ui.py                       # Streamlit Dispatch Console + Audit Logs UI
    ├── orchestrator.py             # LangGraph agent graph + fallback reasoner
    ├── agent_tools.py              # SQL telemetry, corridor API, SOP search tools
    └── prompts/
        └── system_prompt.txt       # Structured business output format
```

---

## 🧠 Usability Techniques

The system applies several usability and user-experience techniques to make an autonomous AI agent safe, transparent, and easy for business users to operate:

### 1. Consistent, Structured Output Format
Every agent response follows the same template mandated by the system prompt:
1. **Executive Summary** — situation + immediate risk in 1–2 sentences.
2. **Telemetry & Environment Analysis** — a scannable table (Location, Temp, Cargo Risk, Weather/Congestion) plus brief analysis.
3. **Required Action Plan** — numbered, action-oriented steps with an explicit SOP compliance citation.

This reduces cognitive load: users always know where to find the risk, the evidence, and the next step.

### 2. Conversational Chat Interface
A familiar chat UI (Streamlit `st.chat_input` / `st.chat_message`) with user (👤) and assistant (🤖) avatars makes the system feel like messaging a colleague rather than writing queries or code.

### 3. Real-Time Status Feedback
During execution, a `st.status` component shows progressive stages:
*   "Initializing Core Reasoner Node…"
*   "Agent generated tool parameters…"
*   "Executing Enterprise Subsystem Tools…"
*   "Generating Operational Resolution Report…"
*   "Incident Matrix Evaluation Complete"

Users are never left wondering whether the system is frozen or working.

### 4. Explainability Through Tool Traces
Every tool call and result is surfaced in expandable panels:
*   **Intent Recognized** — which tool the agent chose (e.g., `query_telemetry_db`).
*   **View Generated Input** — the exact parameters passed to the tool.
*   **View Raw Output** — the raw data returned by the tool.

This makes the agent's reasoning auditable and builds user trust.

### 5. Session Isolation & Management
Each browser session gets a unique `thread_id` (shown in the sidebar as a "Session Token"), so multiple users can work concurrently without their conversations mixing. A one-click **"Purge Dispatch Workspace Session"** button resets chat and thread state instantly.

### 6. Dark Enterprise Theme
A high-contrast dark theme (`#0B0E14` background, `#E2E8F0` text, accent `#38BDF8`) reduces eye strain during long monitoring shifts and gives the console a professional, operations-center appearance.

### 7. Admin-Gated Audit Trail
A separate **"Security & Audit Logs"** mode lets authorized administrators inspect the full execution history (SessionID, NodeExecuted, ToolName, Content, Timestamp). Credential gating prevents unauthorized access while preserving accountability.

### 8. Fault-Tolerant LLM Routing
The `_FallbackReasoner` wrapper automatically retries on Groq when Gemini returns quota/rate-limit errors (429, ResourceExhausted). The system stays available even when a single provider is throttled, and the active provider is shown in the sidebar.

### 9. Silent, Non-Blocking Audit Logging
Audit writes to SQL Server are wrapped in try/except and fail silently. If the database is unreachable, the user's chat experience is not interrupted.

### 10. Efficient Data Ingestion
The SOP ingestion script uses MD5 hash-change detection: unchanged documents are skipped, deleted documents are purged from Pinecone, and only modified files are re-indexed. Embedding models are cached with `st.cache_resource` so repeat sessions load faster.

---

## 🛠️ Getting Started (Local Development)

### Prerequisites
*   Python 3.12
*   `pip` / `venv`
*   Access to a Microsoft SQL Server instance (for telemetry + audit logs)
*   Pinecone account and API key
*   Google Gemini API key and/or Groq API key

### 1. Clone the repository
```bash
git clone https://github.com/Hrushithar/AI-Powered-Cold-Chain-Logistics-Management-System.git
cd "AI-Powered Cold Chain Logistics Management System"
```

### 2. Create a virtual environment and install dependencies
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables
Create `.env` in the project root and populate:

```env
SQL_SERVER_HOST=localhost
SQL_SERVER_PORT=1433
SQL_ADMIN_USER=sa
SQL_ADMIN_PASSWORD=your_admin_password

SQL_AGENT_USER=USR_FDE_RO
SQL_AGENT_PASSWORD=your_agent_password

PINECONE_API_KEY=your_pinecone_key
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key

Local_Embedding_Model=BAAI/bge-m3
Embeddings_model=LOCAL          # or GEMINI
Agent_llm=GROQ                  # or GEMINI
```

> ⚠️ The `.env` file is excluded from version control by `.gitignore`. Never commit real credentials.

### 4. (Optional) Ingest data
```bash
# Load legacy fleet CSV into SQL Server
python scripts/ingest_legacy_data.py

# Index compliance SOPs into Pinecone
python scripts/ingest_sop_pinecone.py
```

### 5. Run the application
```bash
streamlit run src/ui.py
```

The app will be available at `http://localhost:8501`.

---

## 🌐 Deployment on Render

1. Push this repository to GitHub.
2. In the **Render dashboard**, create a new **Web Service** and connect the repository.
3. Set the runtime — Render will detect `runtime.txt` (Python 3.12).
4. Use the build command:
   ```bash
   pip install -r requirements.txt
   ```
5. Use the start command:
   ```bash
   streamlit run src/ui.py --server.port $PORT --server.headless true
   ```
6. Add all environment variables from `.env` under the service's **Environment** tab in the Render dashboard.
7. Deploy. The service is live at:
   **https://ai-powered-cold-chain-logistics.onrender.com/**

---

## 🔒 Security Notes

*   The `.env` file contains secrets and is **gitignored** — do not commit it.
*   The Audit Logs tab requires admin credentials matching `SQL_ADMIN_USER` / `SQL_ADMIN_PASSWORD`.
*   The SQL agent user (`SQL_AGENT_USER`) is intended to be read-only for telemetry queries.
*   API calls to Open-Meteo are made with a 6-second timeout to prevent hanging.

---

## 📄 License

This project is developed as part of the AI-Powered Cold Chain Logistics Management System.

---

*Built with Streamlit, LangGraph, Pinecone, and Google Gemini • Deployed on Render*