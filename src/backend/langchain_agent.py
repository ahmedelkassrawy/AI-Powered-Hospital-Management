import sys
import os

# Ensure the project root (d:\Enviroment\hospital) is on sys.path,
# regardless of where or how this file is executed.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import asyncio
import datetime as dt
from langchain.tools import tool
from langchain.agents import create_agent
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
from sqlalchemy import select, update
from src.database.db import AsyncSessionLocal
from src.database.model import Appointment, Doctor, Patient
from config import get_settings
from langchain_openrouter import ChatOpenRouter
from langsmith import traceable

load_dotenv()
settings = get_settings()

# ─── LLM ────────────────────────────────────────────────────────────────────
# llm = ChatGroq(
#     model_name="llama-3.1-8b-instant",
#     api_key=settings.GROQ_API_KEY,
# )

# os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY

# llm = ChatGoogleGenerativeAI(
#     model = "gemini-2.5-flash",
#     google_api_key = os.getenv("GOOGLE_API_KEY")
# )

llm = ChatOpenRouter(
    model="z-ai/glm-4.5-air:free",
    api_key = settings.OPENROUTER_API_KEY,
    reasoning = {"effort": "none", "summary": "auto"},
)

# ─── Tools ──────────────────────────────────────────────────────────────────
@tool
async def get_doctor_schedule(doctor_id: int = 0) -> str:
    """Retrieve the working hours and availability of a specific doctor.

    Use this when a patient or user asks about a doctor's availability
    or schedule. Always call this before booking to confirm the slot exists.

    Args:
        doctor_id: The integer ID of the doctor to look up (e.g., 1, 2, 3).
    """
    if doctor_id == 0:
        return "Please provide a doctor ID (e.g., 1, 2, 3) first."
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Doctor.working_hours).where(Doctor.id == doctor_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return f"No doctor found with id {doctor_id}."
        return f"Doctor {doctor_id} working hours: {row}"


@tool
async def list_all_departments() -> list[str]:
    """List all departments that currently have doctors registered in the system.

    Use this when a user asks which departments or specializations are available
    at the hospital. This tool has no required parameters.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Doctor.department).distinct())
        departments = [row[0] for row in result.fetchall()]
        return departments if departments else ["No departments found."]


@tool
async def check_patient_appointments(patient_id: int = 0) -> list[dict]:
    """Retrieve all appointments (past and upcoming) for a specific patient.

    Use this when a patient asks to see their appointments or check their
    appointment history. Always call this before cancelling an appointment.

    Args:
        patient_id: The integer ID of the patient (e.g., 1, 2, 3).
    """
    if patient_id == 0:
        return [{"message": "Please provide your patient ID first."}]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Appointment).where(Appointment.patient_id == patient_id)
        )
        appointments = result.scalars().all()
        if not appointments:
            return [{"message": f"No appointments found for patient {patient_id}."}]
        return [
            {
                "id": appt.id,
                "doctor_id": appt.doctor_id,
                "date": str(appt.date),
                "time": str(appt.time),
                "reason": appt.reason,
                "status": appt.status,
            }
            for appt in appointments
        ]

@tool
async def create_patient_record(
    name: str = "",
    age: int = 0,
    gender: str = "",
    phone_number: str = "",
    email: str = "",
    date_of_birth: str = "",
    address: str = "",
    medical_history: str = ""
) -> dict:
    """Create a new patient record in the hospital system.

    Use this when a new patient needs to be registered. You MUST ask the user
    for all personal details in the conversation before calling this tool.
    Do NOT guess or invent any values.

    Args:
        name: Full name of the patient.
        age: Age of the patient in years (integer).
        gender: Gender of the patient (e.g., 'Male', 'Female', 'Other').
        phone_number: Patient's contact phone number.
        email: Patient's email address.
        date_of_birth: Date of birth in YYYY-MM-DD format.
        address: Full residential address of the patient.
        medical_history: Medical History of the patient
    """
    # NO input() - LLM must provide ALL args or ask user first
    if not all([name, age, gender, phone_number, email, date_of_birth, address, medical_history]):
        missing = [k for k, v in locals().items() if not v]
        return {"error": f"Missing patient details: {', '.join(missing)}. Provide all before registering."}

    async with AsyncSessionLocal() as session:
        try:
            dob_date = dt.datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "date_of_birth must be a valid date in YYYY-MM-DD format."}

        new_patient = Patient(
            name=name,
            age=age,
            gender=gender,
            phone_number=phone_number,
            email=email,
            date_of_birth=dob_date,
            address=address,
            medical_history=[medical_history]
        )
        session.add(new_patient)
        await session.commit()
        await session.refresh(new_patient)
        
        return {
            "id": new_patient.id,
            "name": new_patient.name,
            "message": "Patient record created successfully.",
        }


@tool
async def book_appointment(
    patient_id: int,      # REQUIRED - from user or prior check_patient_appointments
    doctor_id: int,       # REQUIRED - from get_doctor_schedule
    date: str,            # REQUIRED YYYY-MM-DD - ask user explicitly
    time: str,            # REQUIRED HH:MM - ask user explicitly  
    reason: str,          # REQUIRED - ask user explicitly
    is_emergency: bool = False,
) -> dict:
    """Book appointment ONLY after confirming ALL details with user.
    
    STRICT PREREQUISITES:
    1. get_doctor_schedule(doctor_id) called first
    2. User provided date/time/reason explicitly
    3. Summarize + confirm before calling
    
    Args (ALL REQUIRED - NO DEFAULTS):
        patient_id: From user or check_patient_appointments result
        doctor_id: From list_doctors/get_doctor_schedule
        date: YYYY-MM-DD (user must say "2026-03-20")
        time: HH:MM 24hr (user must say "09:30") 
        reason: User reason REQUIRED
        is_emergency: True ONLY for life-threatening
    """
    # STRICT VALIDATION - catch hallucinations
    if patient_id <= 0:
        return {"error": "Patient ID required (e.g. 6). Ask user first."}
    if doctor_id <= 0:
        return {"error": "Doctor ID required (e.g. 5). Use list_doctors first."}
    if not all([date.strip(), time.strip(), reason.strip()]):
        return {"error": "Date, time, reason ALL required. Ask user EACH before calling."}
    
    # Parse validation
    try:
        date_obj = dt.date.fromisoformat(date.strip())
        time_obj = dt.time.fromisoformat(time.strip())
    except ValueError:
        return {"error": "Date must be YYYY-MM-DD, time HH:MM. Confirm format with user."}
    
    async with AsyncSessionLocal() as session:
        new_appointment = Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            date=date_obj,
            time=time_obj,
            reason=reason.strip(),
            is_emergency=is_emergency,
            status="Emergency" if is_emergency else "Pending",
        )
        session.add(new_appointment)
        await session.commit()
        await session.refresh(new_appointment)
        
        return {
            "id": new_appointment.id,
            "date": str(new_appointment.date),
            "time": str(new_appointment.time),
            "status": new_appointment.status,
            "message": "Appointment booked successfully!",
        }

@tool
async def list_doctors() -> list[dict]:
    """List ALL doctors with ID, name, specialization.
    
    ALWAYS call when user says "doctors", "list doctors", "available doctors", "doctor list".
    Returns: [{"id":1,"name":"Dr X","specialization":"Y"}]
    """
    print("DEBUG: list_doctors CALLED")  # Confirm invocation
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Doctor))
        doctors = result.scalars().all()
        doctors_list = [
            {
                "id": doc.id, 
                "name": doc.name, 
                "specialization": doc.specialization
            } 
            for doc in doctors
        ]
        print(f"DEBUG: Returning {len(doctors_list)} doctors: {[d['name'] for d in doctors_list]}")
        return doctors_list or [{"message": "No doctors found - contact admin"}]

@tool
async def cancel_appointment(patient_id: int = 0, appointment_id: int = 0) -> str:
    """Cancel an existing appointment for a patient.

    Use this when a patient explicitly requests to cancel a scheduled appointment.
    PREREQUISITE: call check_patient_appointments first to confirm the appointment ID.
    Both patient_id and appointment_id must match for the cancellation to succeed.

    Args:
        patient_id: Integer ID of the patient. Leave as 0 to use the session value.
        appointment_id: Integer ID of the specific appointment to cancel.
    """
    if patient_id == 0:
        return "Patient ID required."
    if appointment_id == 0:
        return "Appointment ID required. Use `check_patient_appointments` first."

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(Appointment)
            .where(
                Appointment.id == appointment_id,
                Appointment.patient_id == patient_id,
            )
            .values(status="Cancelled")
        )
        await session.commit()
        if result.rowcount == 0:
            return (
                f"No appointment with id {appointment_id} found "
                f"for patient {patient_id}. Nothing was cancelled."
            )
        return "Appointment cancelled successfully."


# ─── Agent Setup ─────────────────────────────────────────────────────────────

tools = [
    get_doctor_schedule,
    list_all_departments,
    check_patient_appointments,
    create_patient_record,
    list_doctors,
    book_appointment,
    cancel_appointment,
]

SYSTEM_PROMPT = f"""
# SYSTEM ROLE AND PRIMARY DIRECTIVE
You are an advanced AI Healthcare Receptionist and Hospital Management Assistant. Your primary objective is to streamline hospital operations by managing patient records, coordinating appointments, and providing accurate facility information. 

You must execute all tasks with strict precision, zero assumptions, and a calm, empathetic, and professional demeanor. 

Current Date and Time: {dt.datetime.now().strftime('%A, %Y-%m-%d %H:%M:%S')}

### CRITICAL GUARDRAILS (HARD RULES)
1. **ZERO HALLUCINATION:** NEVER guess, invent, or assume any IDs, names, dates, times, or medical information. 
2. **EXPLICIT CONFIRMATION:** All tool parameters (patient_id, doctor_id, date, time) MUST come directly from the user's explicit input. If a value is missing, you MUST ask the user for it before calling any tool.
3. **EMERGENCY OVERRIDE:** If a user describes a life-threatening emergency (e.g., chest pain, severe bleeding, breathing issues, loss of consciousness), ABORT ALL WORKFLOWS. Immediately direct them to call emergency services or go to the nearest ER. Do not attempt to book an appointment.
4. **TOOL SEPARATION:** NEVER mention the names of your internal tools (e.g., "I will now call the book_appointment tool"). NEVER output raw function calls, JSON, or XML tags (like `<function>`) to the user. Present the results of your actions in natural, conversational language.
5. **SCOPE LIMITATION:** If a user request falls outside your defined workflows or available tools, politely inform them that you cannot assist with that specific task and direct them to human hospital staff.

### STANDARD OPERATING PROCEDURES (SOPs)

You must follow these workflows in the exact, chronological order listed. Do not skip steps.

**SOP 1: New Patient Registration (Mandatory for First-Time Users)**
If a user indicates they are new or do not have a Patient ID, execute this SOP before any other action:
1. Ask the user to provide their: Full Name, Age, Gender, Phone Number, Email, Date of Birth, and Home Address. (Collect this naturally; do not overwhelm them).
2. Once all details are gathered, present a summary to the user for confirmation.
3. ONLY after explicit confirmation, call `create_patient_record`.
4. Provide the user with their new Patient ID and advise them to save it.

**SOP 2: Booking an Appointment**
1. Ask the user for their Patient ID (If they do not have one, immediately switch to SOP 1).
2. Ask the user which department or doctor they need. 
   - *Note:* If they ask for available doctors, call `list_doctors` and return the COMPLETE list without filtering or modifying it. Let the user choose.
   - *Note:* If they ask for departments, call `list_all_departments`.
3. Once the user selects a doctor, call `get_doctor_schedule` using that doctor's integer ID to confirm availability.
4. Ask the user for their preferred date (YYYY-MM-DD), time (HH:MM), and the specific REASON for the visit.
5. Summarize the appointment details (Patient ID, Doctor Name, Date, Time, Reason) and ask for final confirmation.
6. ONLY after explicit confirmation, call `book_appointment` with the confirmed values.

**SOP 3: Canceling an Appointment**
1. Ask the user for their Patient ID.
2. Call `check_patient_appointments` to retrieve their current schedule.
3. Present the list of appointments and ask the user to specify which one they want to cancel.
4. Retrieve the integer appointment ID for the selected appointment.
5. Summarize the cancellation request and ask for final confirmation.
6. ONLY after explicit confirmation, call `cancel_appointment`.

### COMMUNICATION STYLE
* **Empathetic & Professional:** Healthcare inquiries can be stressful. Use a reassuring and polite tone.
* **Concise:** Keep responses strictly focused on the current step of the SOP. Avoid unnecessary filler or conversational fluff.
* **Proactive:** If a requested doctor is unavailable, proactively suggest checking the schedule of another doctor within the same department.
"""

checkpointer = MemorySaver()

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

# ─── Entry Point ─────────────────────────────────────────────────────────────
@traceable
async def run_agent(user_message: str, thread_id: str = "default-session") -> str:
    config = {
        "configurable": {"thread_id": thread_id},
    }
        
    messages = [{"role": "user", "content": user_message}]

    result = await agent.ainvoke(
        {   
            "messages": messages
        },
        config,  # First: config (required for checkpointer)
    )

    print(f"DEBUG: Full result keys: {list(result.keys())}")
    print(f"DEBUG: Messages count: {len(result['messages'])}")
    print(f"DEBUG: Last message: {result['messages'][-1]}")
    
    last_msg = result["messages"][-1]

    if hasattr(last_msg, 'content'):
        print(f"DEBUG: Last content: {last_msg.content[:200]}...")

    return last_msg.content if hasattr(last_msg, 'content') else "No content"

async def chat_loop() -> None:
    """Interactive conversation loop with the hospital agent."""
    thread_id = "interactive-session"
    print("=" * 60)
    print("  [+]  Hospital AI Assistant  -  type 'quit' to exit")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "bye"}:
            print("Agent: Goodbye! Stay healthy! 👋")
            break

        try:
            # Run agent for the current user message.
            response = await run_agent(user_input, thread_id=thread_id)
            print(f"\nAgent: {response}\n")
        except Exception as exc:
            print(f"\n[Error] {exc}\n")


if __name__ == "__main__":
    asyncio.run(chat_loop())