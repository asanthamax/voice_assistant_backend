import logging
from typing import Annotated, List, TypedDict
import os
from datetime import datetime, timedelta, timezone
import pytz
from langchain.prompts import MessagesPlaceholder
from langchain.schema import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, add_messages, END
from langgraph.prebuilt import ToolNode, tool_node, tools_condition
from langchain_core.tools import tool
from googleapiclient.discovery import build, HttpError
from langchain_core.prompts import ChatPromptTemplate

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(name)s :: %(message)s'
)
logger = logging.getLogger(__name__)

CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

memory = InMemorySaver()

llm = init_chat_model('google_genai:gemini-2.5-flash', temperature=0.8)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

class Event(TypedDict):
    title: str
    start_time: str
    end_time: str

@tool
def get_current_year() -> int:
    """
        Returns the current year in integer format. for example 2025

        Args:
            None
        Returns:
            int: The current year
    """
    return datetime.now(timezone.utc).year

@tool
def check_calendar_availability(date_and_time: str, duration_minutes: int = 30) -> bool:
    """
    Checks if the given date and time conflicts with any existing events in the user's Google Calendar.

    This tool connects to the client's Google Calendar API and verifies whether the specified 
    date and time slot is available or already booked with another event.

    Args:
        date_and_time (str): The date and time to check in ISO format (e.g. '2025-10-11T15:30:00')
        duration_minutes (int): The duration of the appointment in minutes. Default is 30 minutes.
    Returns:
        bool: False if there is a conflict (time slot is already booked)
              True if the time slot is available
    Raises:
        HttpError: If there is an error connecting to the Google Calendar API or date_and_time is invalid.

    Example:
        check_calendar_availability("2025-10-11T15:30:00")
        # Returns: True (if time slot is available)
    """
    try:
        logger.info(f"Checking calendar availability for {date_and_time}")
        service = build("calendar", "v3", cache_discovery=False)
        start_time_dt = datetime.fromisoformat(date_and_time)
        end_time_dt = start_time_dt + timedelta(minutes=duration_minutes)

        calendar = service.calendars().get(calendarId=CALENDAR_ID).execute()
        tz_str = calendar['timeZone']
        tz = pytz.timezone(tz_str)

        event_result = (
            service.events()
            .list(
                calendarId=CALENDAR_ID,
                timeMin=tz.localize(start_time_dt).isoformat(),
                timeMax=tz.localize(end_time_dt).isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = event_result.get("items", [])

        logger.info(f"Events found: {events} for {date_and_time}")
        if len(events) > 0:
            return False  # Conflict exists
        else:
            return True  # No conflict
    except HttpError as error:
        print(f"An error occurred: {error}")
        raise error
    
@tool
def get_events_for_date(date: str) -> List[Event]:
    """
    Fetches all events from the user's Google Calendar for the specified date.

    This tool connects to the client's Google Calendar API and retrieves a list of events 
    scheduled for the given date.

    Args:
        date (str): The date to fetch events for in 'YYYY-MM-DD' format (e.g. '2025-10-11') 
    Returns:
        List[Event]: A list of event summaries scheduled for the specified date.
    Raises:
        HttpError: If there is an error connecting to the Google Calendar API or date is invalid.
    Example:
        get_events_for_date("2025-10-11")
        # Returns: [
            {"title": "Surgery", "start_time": "09:00", "end_time": "10:30"},
            {"title": "Patient Check-up", "start_time": "11:00", "end_time": "11:30"}
        ]
    """
    try:
        logger.info(f"Fetching events for date: {date}")
        service = build("calendar", "v3", cache_discovery=False)
        calendar = service.calendars().get(calendarId=CALENDAR_ID).execute()
        tz_str = calendar['timeZone']
        tz = pytz.timezone(tz_str)

        time_min_dt = tz.localize(datetime.strptime(f"{date}T00:00:00", "%Y-%m-%dT%H:%M:%S"))
        time_max_dt = tz.localize(datetime.strptime(f"{date}T23:59:59", "%Y-%m-%dT%H:%M:%S"))

        event_result = (
            service.events()
            .list(
                calendarId=CALENDAR_ID,
                timeMin=time_min_dt.isoformat(),
                timeMax=time_max_dt.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = event_result.get("items", [])
        event_summaries = []

        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            event_summaries.append({
                "title": event["summary"],
                "start_time": start,
                "end_time": end
            })
        logger.info(f"Events on {date}: {event_summaries}")
        return event_summaries
    except HttpError as error:
        logger.error(f"An error occurred: {error}")
        raise error

@tool
def create_event_for_datetime(date_and_time: str, title: str, description: str, duration_minutes: int = 30) -> str:
    """
    Creates a new event in the user's Google Calendar at the specified date and time.

    This tool connects to the client's Google Calendar API and adds a new event with the 
    provided title and description at the given date and time.

    Args:
        date_and_time (str): The date and time for the event in ISO format (e.g. '2025-10-11T15:30:00')
        title (str): The title of the event.
        description (str): A brief description of the event.
        duration_minutes (int): The duration of the event in minutes. Default is 30 minutes.

    Returns:
        str: A message indicating the success or failure of the event creation.
    Raises:
        HttpError: If there is an error connecting to the Google Calendar API or input parameters are invalid.
    Example:
        create_event_for_datetime("2025-10-11T15:30:00", "Doctor Appointment", "Annual check-up")
        # Returns: "Event created successfully"
    """
    try:
        logger.info(f"Creating event '{title}' at {date_and_time}")
        service = build("calendar", "v3", cache_discovery=False)
        start_time_dt = datetime.fromisoformat(date_and_time)
        end_time_dt = start_time_dt + timedelta(minutes=duration_minutes)
        calendar = service.calendars().get(calendarId=CALENDAR_ID).execute()
        time_zone = calendar['timeZone']
        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_time_dt.isoformat(), "timeZone": time_zone},
            "end": {
                "dateTime": end_time_dt.isoformat(),
                "timeZone": time_zone,
            },
        }
        created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        logger.info(f"Event created: {created_event.get('htmlLink')}")
        return "Event created successfully"
    except HttpError as error:
        logger.error(f"An error occurred: {error}")
        raise error
    
tools = [check_calendar_availability, get_events_for_date, create_event_for_datetime, get_current_year]
    
llm_with_tools = llm.bind_tools(tools=tools)

def initiate_chat(state):
    try:
        with open("/Users/asantha/Desktop/voice_assistant/app/system_prompt.md", "r") as f:
            system_prompt = f.read()
        prompt = ChatPromptTemplate.from_messages(
            messages = [
                SystemMessage(content=system_prompt),
                MessagesPlaceholder(variable_name="messages")
            ]
        )
        chain = prompt | llm_with_tools
        response = chain.invoke({"messages": state['messages']})
        logger.info(f"Agent response: {response}")
        return {
            "messages": state['messages'] + [response]
        }
    except Exception as e:
        logger.error(f"Error in initiate_chat: {e}")
        raise e

graph_builder = StateGraph(AgentState)
graph_builder.add_node('agent_node', initiate_chat)

tool_node = ToolNode(tools=tools)
graph_builder.add_node('tools', tool_node)
graph_builder.add_conditional_edges(
    'agent_node',
    tools_condition
)
graph_builder.add_edge('tools', 'agent_node')
graph_builder.set_entry_point('agent_node')
graph_builder.add_edge('agent_node', END)
graph = graph_builder.compile(checkpointer=memory)
