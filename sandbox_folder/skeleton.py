# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
# from typing import Annotated, Sequence, TypedDict
# from dotenv import load_dotenv  
# from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
# from langchain_openai import ChatOpenAI
# from langchain_core.tools import tool
# from langgraph.graph.message import add_messages
# from langgraph.graph import StateGraph, END
# from langgraph.prebuilt import ToolNode
# import httpx
# import os


# load_dotenv()
# api_key = os.getenv("OPENAI_API_KEY")

# class AgentState(TypedDict):
#     messages: Annotated[Sequence[BaseMessage], add_messages]
    
# @tool

# @tool

# @tool

# @tool

# tools = []
# tool_node = ToolNode(tools)

# model = ChatOpenAI(model = "gpt-4o",
#                    http_client=httpx.Client(verify=False), # to bypass corporate proxy/firewall issue
#                    api_key=api_key
#                    ).bind_tools(tools)

# SYSTEM_PROMPT = """
# """

# def my_agent(state: AgentState) -> AgentState:
#     # ── Greeting on first entry ───────────────────────────────────────────────
#     if not state["messages"]:
#         greeting = AIMessage(content=(
#             "👋 Hello! I'm your AI Calendar Manager.\n\n"
#             "I can help you with:\n"
#             "  \n"
#             "  \n"
#             "  \n"
#             "  \n"
#             "  \n\n"
#             "Type 'exit' or 'bye' to end the session."
#         ))
#         print(f"\n🤖 AI: {greeting.content}")
#         return {"messages": [greeting]}

#     system_msg = SystemMessage(content=SYSTEM_PROMPT)

#     # ── After tool execution: invoke LLM with full context ────────────────────
#     # The LLM may respond with plain text OR trigger another tool call.
#     # should_continue() handles both cases — no printing here so we don't
#     # print intermediate tool-chaining responses that have no content.
#     if isinstance(state["messages"][-1], ToolMessage):
#         response = model.invoke([system_msg] + list(state["messages"]))
#         # Only print if the model produced a visible reply (not a silent tool call)
#         if response.content and not (hasattr(response, "tool_calls") and response.tool_calls):
#             print(f"\n🤖 AI: {response.content}")
#         return {"messages": [response]}

#     # ── Normal user turn: collect input then invoke ───────────────────────────
#     user_input   = input("\n👤 You: ").strip()
#     user_message = HumanMessage(content=user_input)

#     all_messages = [system_msg] + list(state["messages"]) + [user_message]
#     response     = model.invoke(all_messages)

#     # Only print if this is a direct reply, not a tool-dispatch message
#     if response.content and not (hasattr(response, "tool_calls") and response.tool_calls):
#         print(f"\n🤖 AI: {response.content}")

#     return {"messages": [user_message, response]}


# # ── Routing ──────────────────────────────────────────────────────────────────

# def should_continue(state: AgentState) -> str:
#     last = state["messages"][-1]

#     if isinstance(last, AIMessage):
#         # Tool call present → dispatch to tools regardless of where we came from
#         if hasattr(last, "tool_calls") and last.tool_calls:
#             names = [tc["name"] for tc in last.tool_calls]
#             print(f"\n🔧 Calling tools: {names}")
#             return "tools"

#         # Termination signal
#         if "TERMINATE" in last.content:
#             print("\n👋 Goodbye! Continue to plan your time well.")
#             return "end"

#     # Otherwise wait for next user input
#     return "agent"

# workflow = StateGraph(AgentState)

# workflow.add_node("agent", my_agent)
# workflow.add_node("tools", tool_node)

# workflow.set_entry_point("agent")

# workflow.add_conditional_edges(
#     "agent",
#     should_continue,
#     {
#         "tools": "tools",
#         "agent": "agent",
#         "end":   END,
#     },
# )

# workflow.add_edge("tools", "agent")

# graph = workflow.compile()


# if __name__ == "__main__":
#     print("🚀 Financial Analyst Agent started  (type 'exit' or 'bye' to quit)\n")
#     graph.invoke({"messages": []})