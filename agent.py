import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from tools import tools_list


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT = (ROOT_DIR / "system_prompt.txt").read_text(encoding="utf-8")

# 2. Khai báo State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def _resolve_llm_config() -> dict[str, object]:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        return {
            "api_key": openai_api_key,
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "base_url": os.getenv("OPENAI_BASE_URL") or None,
            "default_headers": None,
        }

    github_token = (
        os.getenv("GITHUB_TOKEN")
        or os.getenv("GITHUB_ACCESS_TOKEN")
        or os.getenv("GH_TOKEN")
    )
    if github_token:
        return {
            "api_key": github_token,
            "model": os.getenv("GITHUB_MODEL") or os.getenv("OPENAI_MODEL") or "openai/gpt-4o-mini",
            "base_url": os.getenv("GITHUB_MODELS_BASE_URL") or "https://models.github.ai/inference",
            "default_headers": {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        }

    raise EnvironmentError(
        "Thiếu OPENAI_API_KEY hoặc GITHUB_TOKEN/GITHUB_ACCESS_TOKEN trong .env."
    )


def has_llm_credentials() -> bool:
    return bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GITHUB_TOKEN")
        or os.getenv("GITHUB_ACCESS_TOKEN")
        or os.getenv("GH_TOKEN")
    )


# 3. Agent Node
def agent_node(state: AgentState):
    llm_with_tools = _get_llm_with_tools()
    messages = state["messages"]
    if not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = llm_with_tools.invoke(messages)
    
    # === LOGGING ===
    if response.tool_calls:
        for tc in response.tool_calls:
            print(f"  → Gọi tool: {tc['name']}({tc['args']})")
    else:
        print("  → Trả lời trực tiếp")
        
    return {"messages": [response]}

@lru_cache(maxsize=1)
def _get_llm_with_tools():
    config = _resolve_llm_config()
    llm_kwargs = {
        "model": str(config["model"]),
        "api_key": str(config["api_key"]),
    }
    if config["base_url"]:
        llm_kwargs["base_url"] = config["base_url"]
    if config["default_headers"]:
        llm_kwargs["default_headers"] = config["default_headers"]

    llm = ChatOpenAI(**llm_kwargs)
    return llm.bind_tools(tools_list)


@lru_cache(maxsize=1)
def get_graph():
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)

    tool_node = ToolNode(tools_list)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile()


graph = get_graph() if has_llm_credentials() else None

# 6. Chat loop
if __name__ == "__main__":
    if graph is None:
        raise EnvironmentError("Thiếu OPENAI_API_KEY hoặc GITHUB_TOKEN/GITHUB_ACCESS_TOKEN trong .env.")

    print("=" * 60)
    print("Trợ lý ảo tư vấn bác sĩ - Vinmec")
    print(" Gõ 'quit' để thoát")
    print("=" * 60)
    conversation_messages = []
    
    while True:
        user_input = input("\nBạn: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
            
        print("\nVinmecAI đang suy nghĩ...")
        result = graph.invoke(
            {"messages": conversation_messages + [("human", user_input)]}
        )
        conversation_messages = result["messages"]
        final = result["messages"][-1]
        print(f"\nVinmecAI: {final.content}")
