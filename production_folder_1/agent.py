import datetime
import httpx
import os
from typing import Annotated, Sequence, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from tools import add_birthday, list_birthdays, search_birthday, update_birthday,delete_birthday,add_task,list_task_lists,search_tasks,update_task,delete_task,list_tasks, list_events, create_event, update_event, delete_event, search_events

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

tools = [add_birthday, list_birthdays, search_birthday, update_birthday,delete_birthday,add_task,list_task_lists,search_tasks,update_task,delete_task,list_tasks, list_events, create_event, update_event, delete_event, search_events]

model = ChatOpenAI(
    model="gpt-4o",
    http_client=httpx.Client(verify=False),
    api_key=api_key,
).bind_tools(tools)


def get_system_prompt():
    return """You are a helpful AI Calendar Manager connected to the user's Google Calendar.

Today's date and time is: {today}
The user's timezone is: Asia/Singapore (UTC+8)

You can:
- list_events: View upcoming events
- create_event: Add a new event
- update_event: Modify an existing event by ID
- delete_event: Remove an event by ID
- search_events: Search for events by keyword
- add_birthday: Add a new birthday
- list_birthdays: view upcoming birthdays
- search_birthday: search for a birthday by keyword
- update_birthday: Modify an existing birthday 
- delete_birthday: Remove a birthday
- add_task: Add a task
- list_task_lists: Discover and view all task list names  (e.g. "My Tasks", "Work")
- search_tasks: search for task by keywords
- update_task: Modify an existing task
- delete_task: Remove a task
- list_tasks: view upcoming tasks

Guidelines:
- Convert relative times like "tomorrow at 3pm" to ISO 8601 using today's date.
- DO NOT include links with sensitive IDs or secrets in your replies.
- When updating or deleting a birthday/task/event, always double confirm their intent before executing tool call. 
- Be concise and always confirm irreversible actions like deletions.
""".format(today=datetime.datetime.now().strftime("%A, %B %d, %Y %H:%M"))


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


def agent_node(state: AgentState) -> AgentState:
    system_msg = SystemMessage(content=get_system_prompt())
    response = model.invoke([system_msg] + list(state["messages"]))
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage):
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
    return "end"


tool_node = ToolNode(tools)
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
workflow.add_edge("tools", "agent")

graph = workflow.compile()


async def run_agent(user_message: str, history: list) -> tuple[str, list]:
    """
    Run one turn of the agent.
    
    Args:
        user_message: The latest message from the user.
        history: List of previous BaseMessage objects for this user.
    
    Returns:
        (reply_text, updated_history)
    """
    new_message = HumanMessage(content=user_message)
    input_state = {"messages": history + [new_message]}

    result = await graph.ainvoke(input_state)

    updated_history = list(result["messages"])

    # Get the last AI text response
    reply = ""
    for msg in reversed(updated_history):
        if isinstance(msg, AIMessage) and msg.content:
            reply = msg.content
            break

    return reply, updated_history