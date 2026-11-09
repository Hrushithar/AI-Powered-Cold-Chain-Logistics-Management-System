
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver


# ==========================================
# 1. SETUP & PATH RESOLUTION
# ==========================================

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")


# Import FDE tools
from src.agent_tools import (
    query_telemetry_db,
    fetch_corridor_conditions,
    search_compliance_sop
)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ==========================================
# 2. AGENT REASONER LLM INITIALIZATION
# ==========================================

AGENT_LLM_SETTING = (
    os.getenv("Agent_llm", "GEMINI").strip().upper()
)


# Resolve API keys (both are required so the agent can fail over when Gemini
# is out of limit / rate-limited).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def _is_quota_error(exc: Exception) -> bool:
    """Return True if the exception signals a quota / rate-limit / out-of-limit error."""
    msg = str(exc).lower()
    quota_keywords = (
        "quota",
        "rate limit",
        "ratelimit",
        "429",
        "resource exhausted",
        "out of limit",
    )
    if any(keyword in msg for keyword in quota_keywords):
        return True
    try:
        from google.api_core.exceptions import ResourceExhausted  # type: ignore

        return isinstance(exc, ResourceExhausted)
    except Exception:
        return False


class _FallbackReasoner:
    """
    Wraps a primary LLM (Gemini) with an automatic Groq fallback.

    If the primary LLM raises a quota / rate-limit (out-of-limit) error, the
    call is retried once using the Groq API key with model
    ``openai/gpt-oss-20b``. After a fallback, Groq stays active for the
    lifetime of this wrapper so the agent stops hammering a limited key.
    """

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback
        self._active = primary
        self._using_fallback = False

    def bind_tools(self, tools):
        return _FallbackReasoner(
            self._primary.bind_tools(tools),
            self._fallback.bind_tools(tools) if self._fallback is not None else None,
        )

    @property
    def active_provider(self) -> str:
        if self._using_fallback:
            return "GROQ (openai/gpt-oss-20b)"
        return "GEMINI (gemini-2.5-flash)"

    def invoke(self, input, config=None, **kwargs):
        # Order: active LLM first (sticky after a fallback), then fallback.
        candidates = [self._active]
        if self._active is self._primary and self._fallback is not None:
            candidates.append(self._fallback)

        last_error = None
        for llm in candidates:
            try:
                return llm.invoke(input, config=config, **kwargs)
            except Exception as exc:
                last_error = exc
                if (
                    llm is self._primary
                    and self._fallback is not None
                    and _is_quota_error(exc)
                ):
                    print(
                        "\n\u26a0\ufe0f  Gemini quota/rate-limit reached. "
                        "Shifting to Groq fallback (openai/gpt-oss-20b)...\n"
                    )
                    self._active = self._fallback
                    self._using_fallback = True
                    continue  # retry with Groq
                raise  # non-quota error, or Groq also failed -> propagate

        raise last_error


# ==========================================
# 2. AGENT REASONER LLM INITIALIZATION
# ==========================================

if AGENT_LLM_SETTING == "GROQ":

    print("⚡ Brain Mode: GroqCloud GPT OSS 20B...")

    if not GROQ_API_KEY:
        raise ValueError("Missing GROQ_API_KEY in .env")

    from langchain_groq import ChatGroq

    llm = _FallbackReasoner(
        primary=ChatGroq(
            model="openai/gpt-oss-20b",
            temperature=0,
            api_key=GROQ_API_KEY,
        ),
        fallback=None,
    )

else:

    # Default: Gemini primary, Groq (openai/gpt-oss-20b) as out-of-limit fallback.
    print("🤖 Brain Mode: Google Gemini 2.5 Flash (Groq fallback if out of limit)...")

    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY in .env")
    if not GROQ_API_KEY:
        raise ValueError(
            "Missing GROQ_API_KEY in .env "
            "(required as fallback when Gemini is out of limit)"
        )

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_groq import ChatGroq

    llm = _FallbackReasoner(
        primary=ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            google_api_key=GEMINI_API_KEY,
        ),
        fallback=ChatGroq(
            model="openai/gpt-oss-20b",
            temperature=0,
            api_key=GROQ_API_KEY,
        ),
    )


# ==========================================
# 3. CORE FDE TOOL BINDING
# ==========================================

fde_tools = [
    query_telemetry_db,
    fetch_corridor_conditions,
    search_compliance_sop
]

print("🔗 Binding FDE tools to the selected LLM...")

llm_with_tools = llm.bind_tools(fde_tools)


# ==========================================
# 4. LANGGRAPH ARCHITECTURE ASSEMBLY
# ==========================================

def reasoning_node(state: AgentState):

    response = llm_with_tools.invoke(
        state["messages"]
    )

    return {
        "messages": [response]
    }


print("⚙️ Compiling LangGraph FDE Orchestrator...")

graph_builder = StateGraph(AgentState)

graph_builder.add_node(
    "reasoner",
    reasoning_node
)

graph_builder.add_node(
    "tools",
    ToolNode(fde_tools)
)

graph_builder.add_edge(
    START,
    "reasoner"
)

graph_builder.add_conditional_edges(
    "reasoner",
    tools_condition
)

graph_builder.add_edge(
    "tools",
    "reasoner"
)


# Compile graph with conversation memory
fde_agent = graph_builder.compile(
    checkpointer=MemorySaver()
)


# ==========================================
# 5. CHAT LOOP TESTING PANEL
# ==========================================

if __name__ == "__main__":

    print("\n" + "=" * 55)

    print(
        "🚀 FDE Supply Chain Orchestrator Online"
    )

    print(
        f"   LLM Provider: {AGENT_LLM_SETTING}"
    )

    print(
        f"   Embeddings: "
        f"{os.getenv('Embeddings_model', 'GEMINI')}"
    )

    print("=" * 55 + "\n")


    # Load external system prompt
    prompt_path = (
        project_root
        / "src"
        / "prompts"
        / "system_prompt.txt"
    )

    try:

        with open(
            prompt_path,
            "r",
            encoding="utf-8"
        ) as f:

            system_instructions = f.read()

    except FileNotFoundError:

        print(
            f"Warning: Could not find system prompt: "
            f"{prompt_path}"
        )

        system_instructions = (
            "You are a helpful AI assistant "
            "specialized in cold-chain logistics."
        )


    system_prompt = SystemMessage(
        content=system_instructions
    )


    # Conversation memory configuration
    thread_config = {
        "configurable": {
            "thread_id": "production_test_1"
        }
    }


    # NOTE: Skipping initial system-prompt-only invoke.
    # Gemini API requires at least one user/assistant message in contents;
    # invoking with only a SystemMessage raises ValueError: contents are required.
    # Conversation state is built by MemorySaver from the first user message onward.


    print("Type 'exit' or 'quit' to stop.\n")


    # Interactive chat loop
    while True:

        user_input = input("\nDispatcher > ")

        if user_input.lower() in ["exit", "quit"]:

            print(
                "Shutting down FDE Orchestrator..."
            )

            break


        events = fde_agent.stream(
            {
                "messages": [
                    ("user", user_input)
                ]
            },
            config=thread_config,
            stream_mode="updates"
        )


        for event in events:

            for node_name, node_state in event.items():

                if node_name == "tools":

                    print(
                        "\n[System] 🔄 Retrieving external "
                        "data through ToolNode..."
                    )

                elif node_name == "reasoner":

                    latest_msg = node_state["messages"][-1]

                    if latest_msg.content:

                        print(
                            f"\n🤖 FDE Agent:\n"
                            f"{latest_msg.content}"
                        )
