import asyncio
import logging
from enum import Enum
from typing import Annotated, Literal, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.chat_service.prompts import ACCOUNT_SYSTEM_PROMPT, DOCS_SYSTEM_PROMPT, ROUTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

SERVICE_UNAVAILABLE_MSG = "Chat is temporarily unavailable. Please try again later."


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    access_token: str
    tenant_id: str
    user_id: str
    response: str
    error: str | None


class QueryType(Enum):
    account_query = "1"
    product_docs_query = "2"
    none = "None"


class ChatStructure(BaseModel):
    clarification_needed: bool = Field(False, description="Whether the agent needs to ask the user for clarification")
    clarification_message: str = Field("", description="The clarification question to ask the user when clarification_needed is True")
    query_type: QueryType = Field(QueryType.none, description=(
        "The type of question being asked. If clarification is needed query_type will be 'none'. "
        "If query is related to the product, its working or howto, query_type will be 'product_docs_query'. "
        "If the question is related to the user's account data like inventory, orders etc, query_type will be 'account_query'"
    ))


def create_agent(account_tools: list[BaseTool], doc_tools: list[BaseTool]):
    """Create the LangGraph agent with separate account and doc tool sets."""
    from src.chat_service.config import config

    llm = init_chat_model(config.llm_model, model_provider=config.llm_provider)

    chat_llm = llm.with_structured_output(ChatStructure)
    account_llm = llm.bind_tools(account_tools)
    docs_llm = llm.bind_tools(doc_tools)

    account_tool_map = {t.name: t for t in account_tools}
    doc_tool_map = {t.name: t for t in doc_tools}

    def chat_llm_call(state: AgentState) -> Command[Literal["account_llm_call", "docs_llm_call", "__end__"]]:
        """Classify the query and route to the appropriate sub-graph."""
        messages = [SystemMessage(content=ROUTER_SYSTEM_PROMPT)] + state["messages"]
        try:
            result: ChatStructure = chat_llm.invoke(messages)
            if result.clarification_needed or result.query_type == QueryType.none:
                clarification = result.clarification_message or "Could you please clarify your question?"
                logger.info("Routing: clarification needed")
                return Command(
                    goto=END,
                    update={
                        "messages": [AIMessage(content=clarification)],
                        "response": clarification,
                        "error": None,
                    },
                )
            elif result.query_type == QueryType.account_query:
                logger.info("Routing: account_query → account_llm_call")
                return Command(goto="account_llm_call", update={"error": None})
            else:
                logger.info("Routing: product_docs_query → docs_llm_call")
                return Command(goto="docs_llm_call", update={"error": None})
        except Exception as e:
            logger.error(f"Chat LLM call failed: {e}")
            error_msg = SERVICE_UNAVAILABLE_MSG
            return Command(goto=END, update={"error": error_msg, "response": error_msg})

    def account_llm_call(state: AgentState) -> Command[Literal["account_mcp_tools", "__end__"]]:
        """Invoke LLM with account tools; route to tool executor or end."""
        messages = [SystemMessage(content=ACCOUNT_SYSTEM_PROMPT)] + state["messages"]
        try:
            response = account_llm.invoke(messages)
            if hasattr(response, "tool_calls") and response.tool_calls:
                return Command(goto="account_mcp_tools", update={"messages": [response]})
            return Command(goto=END, update={"messages": [response], "response": response.content, "error": None})
        except Exception as e:
            logger.error(f"Account LLM call failed: {e}")
            error_msg = SERVICE_UNAVAILABLE_MSG
            return Command(goto=END, update={"error": error_msg, "response": error_msg})

    def docs_llm_call(state: AgentState) -> Command[Literal["docs_mcp_tools", "__end__"]]:
        """Invoke LLM with doc tools; route to tool executor or end."""
        messages = [SystemMessage(content=DOCS_SYSTEM_PROMPT)] + state["messages"]
        try:
            response = docs_llm.invoke(messages)
            if hasattr(response, "tool_calls") and response.tool_calls:
                return Command(goto="docs_mcp_tools", update={"messages": [response]})
            return Command(goto=END, update={"messages": [response], "response": response.content, "error": None})
        except Exception as e:
            logger.error(f"Docs LLM call failed: {e}")
            error_msg = SERVICE_UNAVAILABLE_MSG
            return Command(goto=END, update={"error": error_msg, "response": error_msg})

    def account_mcp_tools(state: AgentState) -> Command[Literal["account_llm_call"]]:
        """Execute account tool calls, injecting access_token from state."""
        last_message = state["messages"][-1]
        access_token = state.get("access_token", "")
        tenant_id = int(state.get("tenant_id", "1"))
        tool_messages = []
        for tool_call in last_message.tool_calls:
            try:
                tool = account_tool_map.get(tool_call["name"])
                if tool:
                    args = {**tool_call["args"], "access_token": access_token, "tenant_id": tenant_id}
                    result = asyncio.run(tool.ainvoke(args))
                    logger.debug(f"Account tool '{tool_call['name']}' succeeded")
                    tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
                else:
                    tool_messages.append(ToolMessage(
                        content=f"Tool '{tool_call['name']}' not available",
                        tool_call_id=tool_call["id"],
                    ))
            except Exception as e:
                logger.error(f"Account tool '{tool_call['name']}' failed: {e}")
                tool_messages.append(ToolMessage(
                    content=SERVICE_UNAVAILABLE_MSG,
                    tool_call_id=tool_call["id"],
                ))
        return Command(goto="account_llm_call", update={"messages": tool_messages})

    def docs_mcp_tools(state: AgentState) -> Command[Literal["docs_llm_call"]]:
        """Execute documentation tool calls."""
        last_message = state["messages"][-1]
        tool_messages = []
        for tool_call in last_message.tool_calls:
            try:
                tool = doc_tool_map.get(tool_call["name"])
                if tool:
                    result = asyncio.run(tool.ainvoke(tool_call["args"]))
                    logger.debug(f"Docs tool '{tool_call['name']}' succeeded")
                    tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
                else:
                    tool_messages.append(ToolMessage(
                        content=f"Tool '{tool_call['name']}' not available",
                        tool_call_id=tool_call["id"],
                    ))
            except Exception as e:
                logger.error(f"Docs tool '{tool_call['name']}' failed: {e}")
                tool_messages.append(ToolMessage(
                    content=SERVICE_UNAVAILABLE_MSG,
                    tool_call_id=tool_call["id"],
                ))
        return Command(goto="docs_llm_call", update={"messages": tool_messages})

    graph = StateGraph(AgentState)
    graph.add_node("chat_llm_call", chat_llm_call)
    graph.add_node("account_llm_call", account_llm_call)
    graph.add_node("docs_llm_call", docs_llm_call)
    graph.add_node("account_mcp_tools", account_mcp_tools)
    graph.add_node("docs_mcp_tools", docs_mcp_tools)
    graph.set_entry_point("chat_llm_call")

    return graph.compile(checkpointer=MemorySaver())


def build_context_messages(query: str) -> list[HumanMessage]:
    """Wrap the current query as a HumanMessage. History is managed by the graph checkpointer."""
    return [HumanMessage(content=query)]
