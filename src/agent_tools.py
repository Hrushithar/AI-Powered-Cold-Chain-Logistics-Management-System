import os
import urllib
import requests
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore


# ==========================================
# 1. ENVIRONMENT & DYNAMIC INDEX ATTACHMENT
# ==========================================

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent

load_dotenv(dotenv_path=project_root / ".env")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not PINECONE_API_KEY:
    raise ValueError("Missing PINECONE_API_KEY in .env")

EMBEDDINGS_MODEL_SETTING = (
    os.getenv("Embeddings_model", "GEMINI").strip().upper()
)

db_host = os.getenv("SQL_SERVER_HOST", "localhost")
db_port = os.getenv("SQL_SERVER_PORT", "1435")
db_user = os.getenv("SQL_AGENT_USER", "USR_FDE_RO")
db_password = os.getenv("SQL_AGENT_PASSWORD")

if not db_password:
    raise ValueError("Missing SQL_AGENT_PASSWORD in .env")


# ==========================================
# 2. EMBEDDING MODEL CONFIGURATION
# ==========================================

def get_cached_huggingface_embeddings(model_name: str):
    """
    Cache local HuggingFace model in Streamlit RAM.
    """

    import streamlit as st

    @st.cache_resource(show_spinner=False)
    def _load_model(name: str):

        print(f"Loading local model [{name}]...")

        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=name,
            model_kwargs={"device": "cpu"}
        )

    return _load_model(model_name)


if EMBEDDINGS_MODEL_SETTING == "GEMINI":

    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY in .env")

    print("Connecting to Gemini Embeddings...")
    print("Model: gemini-embedding-001 (3072 dimensions)")

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=GEMINI_API_KEY,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=3072
    )

    INDEX_NAME = "fde-sop-index-gemini"


elif EMBEDDINGS_MODEL_SETTING == "LOCAL":

    local_model_target = os.getenv(
        "Local_Embedding_Model",
        "BAAI/bge-m3"
    ).strip()

    print(f"Connecting to local model: {local_model_target}")

    try:

        import streamlit as st

        if st.runtime.exists():

            embeddings = get_cached_huggingface_embeddings(
                local_model_target
            )

        else:

            from langchain_huggingface import HuggingFaceEmbeddings

            embeddings = HuggingFaceEmbeddings(
                model_name=local_model_target,
                model_kwargs={"device": "cpu"}
            )

    except ImportError:

        from langchain_huggingface import HuggingFaceEmbeddings

        embeddings = HuggingFaceEmbeddings(
            model_name=local_model_target,
            model_kwargs={"device": "cpu"}
        )

    INDEX_NAME = "fde-sop-index-local"


else:

    raise ValueError(
        "Invalid Embeddings_model. Choose GEMINI or LOCAL."
    )


# ==========================================
# 3. PINECONE VECTOR STORE
# ==========================================

print(f"Connecting to Pinecone Index: {INDEX_NAME}")

vector_store = PineconeVectorStore(
    index_name=INDEX_NAME,
    embedding=embeddings
)

retriever = vector_store.as_retriever(
    search_kwargs={"k": 2}
)


# ==========================================
# 4. CORE FDE AGENT TOOLS
# ==========================================

@tool
def query_telemetry_db(sql_query: str) -> str:
    """
    Executes a SQL SELECT query against the
    FDE_VIEWS.VW_ACTIVE_FLEET view.

    Available columns:
    Timestamp, Latitude, Longitude,
    Current_Temperature_C, Cargo_Condition_Code,
    Risk_Classification, Delay_Probability,
    Port_Congestion_Level, Route_Risk_Index.

    Always write standard T-SQL queries.
    """

    connection_string = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={db_host},{db_port};"
        f"DATABASE=master;"
        f"UID={db_user};"
        f"PWD={db_password};"
        f"Encrypt=no;"
        f"TrustServerCertificate=yes;"
    )

    params = urllib.parse.quote_plus(connection_string)

    engine = create_engine(
        f"mssql+pyodbc:///?odbc_connect={params}"
    )

    try:

        if not sql_query.strip().upper().startswith("SELECT"):
            return (
                "SECURITY BLOCK: Only SELECT operations "
                "are authorized on this view."
            )

        with engine.connect() as conn:

            cursor = conn.execute(text(sql_query))

            columns = list(cursor.keys())

            rows = cursor.fetchmany(10)

            if not rows:
                return "No records matched the query criteria."

            formatted_output = (
                f"COLUMNS: {', '.join(columns)}\n"
            )

            for row in rows:
                formatted_output += str(tuple(row)) + "\n"

            return formatted_output

    except Exception as e:

        return f"Database Error: {str(e)}"

    finally:

        engine.dispose()


@tool
def fetch_corridor_conditions(
    latitude: float,
    longitude: float
) -> str:
    """
    Fetches real-time weather and corridor conditions
    from a live REST API using GPS coordinates.

    Provides temperature, wind speed and computed
    corridor congestion index.
    """

    try:

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}"
            f"&longitude={longitude}"
            "&current_weather=true"
        )

        response = requests.get(url, timeout=6)

        response.raise_for_status()

        payload = response.json().get(
            "current_weather", {}
        )

        temp = payload.get("temperature", "N/A")

        wind = payload.get("windspeed", 0.0)

        congestion_index = (
            8.5 if wind > 10.0 else 2.5
        )

        status_note = (
            "High Transit Disruption"
            if wind > 10.0
            else "Corridor Normal"
        )

        return (
            "--- LIVE CORRIDOR TELEMETRY ---\n"
            f"Target GPS: {latitude}, {longitude}\n"
            f"External Temp: {temp}°C | "
            f"Wind Speed: {wind} km/h\n"
            f"Corridor Risk: {status_note} "
            f"(Congestion Index: {congestion_index}/10)\n"
            "-------------------------------"
        )

    except Exception as e:

        return (
            f"Corridor API Communication Failure: {str(e)}"
        )


@tool
def search_compliance_sop(query: str) -> str:
    """
    Searches enterprise SOP documents indexed
    in the Pinecone Vector Database.

    Retrieves regulatory thresholds, cold-chain
    breach mitigations and rerouting rules.
    """

    try:

        matched_docs = retriever.invoke(query)

        if not matched_docs:
            return "No matching compliance clauses found."

        formatted_context = "\n\n".join(
            [
                (
                    f"[Source: {doc.metadata.get('source_file', 'SOP')} "
                    f"| Format: {doc.metadata.get('file_format', 'RAW')}]\n"
                    f"{doc.page_content}"
                )
                for doc in matched_docs
            ]
        )

        return (
            "--- COMPLIANCE SOP CONTEXT ---\n"
            f"{formatted_context}\n"
            "------------------------------"
        )

    except Exception as e:

        return f"Vector Store Retrieval Error: {str(e)}"


# ==========================================
# 5. LOCAL VERIFICATION
# ==========================================

if __name__ == "__main__":

    print("\n--- Testing Tool 1: SQL Telemetry View ---")

    print(
        query_telemetry_db.invoke(
            "SELECT TOP 2 Latitude, Longitude, "
            "Current_Temperature_C "
            "FROM FDE_VIEWS.VW_ACTIVE_FLEET"
        )
    )

    print("\n--- Testing Tool 2: Live Corridor API ---")

    print(
        fetch_corridor_conditions.invoke({
            "latitude": 33.77,
            "longitude": -118.19
        })
    )

    print("\n--- Testing Tool 3: Pinecone Vector Retrieval ---")

    print(
        search_compliance_sop.invoke(
            "What are the temperature rules "
            "for fresh perishables?"
        )
    )

    print("\nAll tool verification tests completed.")
