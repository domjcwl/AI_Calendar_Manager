from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from typing import Annotated, Sequence, TypedDict
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import httpx
import os
import pickle
import datetime

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# ── Google Calendar Auth ──────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service():
    """Authenticate and return a Google Calendar service object."""
    creds = None
    # token.pickle stores the user's access/refresh tokens
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    # If no valid credentials, prompt login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build("calendar", "v3", credentials=creds)


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def list_events(days_ahead: int = 7) -> str:
    """
    List upcoming Google Calendar events.
    Args:
        days_ahead: How many days into the future to look (default: 7).
    Returns a formatted list of upcoming events.
    """
    try:
        service = get_calendar_service()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        future = (datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)).isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=future,
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        if not events:
            return f"No upcoming events in the next {days_ahead} days."

        output = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            output.append(f"- [{e['id']}] {e['summary']} | {start}")
        return "\n".join(output)

    except Exception as ex:
        return f"Error listing events: {ex}"


@tool
def create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: str = "",
    location: str = "",
) -> str:
    """
    Create a new event on Google Calendar.
    Args:
        summary: Event title.
        start_datetime: Start time in ISO 8601 format, e.g. '2025-04-20T09:00:00+08:00'.
        end_datetime: End time in ISO 8601 format, e.g. '2025-04-20T10:00:00+08:00'.
        description: Optional event description.
        location: Optional location string.
    Returns a confirmation with the event link.
    """
    try:
        service = get_calendar_service()
        event = {
            "summary": summary,
            "location": location,
            "description": description,
            "start": {"dateTime": start_datetime, "timeZone": "Asia/Singapore"},
            "end": {"dateTime": end_datetime, "timeZone": "Asia/Singapore"},
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return f"✅ Event created: {created['summary']}\nLink: {created.get('htmlLink')}"
    except Exception as ex:
        return f"Error creating event: {ex}"


@tool
def update_event(
    event_id: str,
    summary: str = None,
    start_datetime: str = None,
    end_datetime: str = None,
    description: str = None,
    location: str = None,
) -> str:
    """
    Update an existing Google Calendar event by its ID.
    Use list_events to find event IDs first.
    Args:
        event_id: The event ID (from list_events).
        summary: New title (optional).
        start_datetime: New start time ISO 8601 (optional).
        end_datetime: New end time ISO 8601 (optional).
        description: New description (optional).
        location: New location (optional).
    """
    try:
        service = get_calendar_service()
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        if summary:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location
        if start_datetime:
            event["start"] = {"dateTime": start_datetime, "timeZone": "Asia/Singapore"}
        if end_datetime:
            event["end"] = {"dateTime": end_datetime, "timeZone": "Asia/Singapore"}

        updated = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
        return f"✅ Event updated: {updated['summary']}\nLink: {updated.get('htmlLink')}"
    except Exception as ex:
        return f"Error updating event: {ex}"


@tool
def delete_event(event_id: str) -> str:
    """
    Delete a Google Calendar event by its ID.
    Use list_events to find event IDs first.
    Args:
        event_id: The event ID to delete.
    """
    try:
        service = get_calendar_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return f"✅ Event {event_id} deleted successfully."
    except Exception as ex:
        return f"Error deleting event: {ex}"
    
    
@tool
def confirm_update(start_datetime: str, end_datetime: str) -> str:
    """
    Checks what other events are happening on that day before updating or creating an event. Always call this tool before making changes to show the user the schedule for that day and confirm the event details with the user.
    Args:
        start_datetime: ISO 8601 format (e.g. '2025-04-20T09:00:00+08:00')
        end_datetime: ISO 8601 format
    Returns:
        Event details for the day or confirmation that slot is free.
    """
    try:
        service = get_calendar_service()
        start_date = start_datetime.split("T")[0]
        end_date = end_datetime.split("T")[0]

        events_result = service.events().list(
            calendarId="primary",
            timeMin=start_date + "T00:00:00Z",
            timeMax=end_date + "T23:59:59Z",
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        if not events:
            return "✅ No other events on this day. Time slot is free."

        output = ["⚠️ Conflicting events on this day:"]
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            output.append(f"- [{e['id']}] {e['summary']} | {start}")
        return "\n".join(output)
    except Exception as ex:
        return f"Error checking conflicts: {ex}"
    
    
    
@tool
def search_events(query: str, days_ahead: int = 30) -> str:
    """
    Search for events matching a query string.
    Args:
        query: Keyword to search (e.g. "meeting", "John")
        days_ahead: How far ahead to search (default: 30 days)
    Returns:
        Matching events.
    """
    try:
        service = get_calendar_service()

        now = datetime.datetime.utcnow().isoformat() + "Z"
        future = (datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)).isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=future,
            q=query,
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        ).execute()

        events = events_result.get("items", [])

        if not events:
            return f"No events found matching '{query}'."

        output = [f"🔍 Results for '{query}':"]
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            output.append(f"- [{e['id']}] {e['summary']} | {start}")

        return "\n".join(output)

    except Exception as ex:
        return f"Error searching events: {ex}"


# ── Agent Setup ───────────────────────────────────────────────────────────────

tools = [list_events, create_event, update_event, delete_event, confirm_update, search_events]

model = ChatOpenAI(
    model="gpt-4o",
    http_client=httpx.Client(verify=False),
    api_key=api_key,
).bind_tools(tools)

SYSTEM_PROMPT = """
You are a helpful AI Calendar Manager connected to the user's Google Calendar.

Today's date and time is: {today}
The user's timezone is: Asia/Singapore (UTC+8)

You can:
- list_events: View upcoming events (specify days_ahead)
- create_event: Add a new event (always confirm details before creating)
- update_event: Modify an existing event by ID (use list_events first to find IDs)
- delete_event: Remove an event by ID (always confirm with the user before deleting)
- confirm_update: Check for conflicts on a given day before creating/updating events.
- search_events: Search for events by keyword.

strict guidelines:
- ALWAYS call confirm_update before creating a new event. If conflicts exist, show them and ask the user before proceeding.
- When the user gives a relative time like "tomorrow at 3pm", convert it to the correct ISO 8601 datetime using the current date above.
- If the user wants to END the conversation (e.g. "bye", "exit", "quit", "stop"), respond ONLY with the exact string: TERMINATE
- DO NOT REPLY WITH ANY LINKS THAT MAY INCLUDE SENSITIVE INFORMATION LIKE IDs OR SECRETS
- When updating or deleting, always show the events occuring on that day to confirm the event details with the user before making changes.

Always be concise and confirm actions before making irreversible changes like deletions.
""".format(today=datetime.datetime.now().strftime("%A, %B %d, %Y %H:%M"))


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


def my_agent(state: AgentState) -> AgentState:
    if not state["messages"]:
        greeting = AIMessage(content=(
            "👋 Hello! I'm your AI Calendar Manager.\n\n"
            "I can help you with:\n"
            "  📅 View upcoming events\n"
            "  ➕ Create new events\n"
            "  ✏️  Update existing events\n"
            "  🗑️  Delete events\n\n"
            "Try: 'What do I have this week?' or 'Schedule a meeting tomorrow at 2pm'\n"
            "Type 'exit' or 'bye' to end the session."
        ))
        print(f"\n🤖 AI: {greeting.content}")
        return {"messages": [greeting]}

    system_msg = SystemMessage(content=SYSTEM_PROMPT)

    if isinstance(state["messages"][-1], ToolMessage):
        response = model.invoke([system_msg] + list(state["messages"]))
        if response.content and not (hasattr(response, "tool_calls") and response.tool_calls):
            print(f"\n🤖 AI: {response.content}")
        return {"messages": [response]}

    user_input = input("\n👤 You: ").strip()
    user_message = HumanMessage(content=user_input)

    all_messages = [system_msg] + list(state["messages"]) + [user_message]
    response = model.invoke(all_messages)

    if response.content and not (hasattr(response, "tool_calls") and response.tool_calls):
        print(f"\n🤖 AI: {response.content}")

    return {"messages": [user_message, response]}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]

    if isinstance(last, AIMessage):
        if hasattr(last, "tool_calls") and last.tool_calls:
            names = [tc["name"] for tc in last.tool_calls]
            print(f"\n🔧 Calling tools: {names}")
            return "tools"

        if "TERMINATE" in last.content:
            print("\n👋 Goodbye! Continue to plan your time well.")
            return "TERMINATE"

    return "agent"


# ── Graph ─────────────────────────────────────────────────────────────────────
tool_node = ToolNode(tools)
workflow = StateGraph(AgentState)

workflow.add_node("agent", my_agent)
workflow.add_node("tools", tool_node)

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "agent": "agent",
        "TERMINATE":   END,
    },
)

workflow.add_edge("tools", "agent")

app = workflow.compile()

if __name__ == "__main__":
    print("Starting AI Calendar Manager...")
    app.invoke({"messages": []})