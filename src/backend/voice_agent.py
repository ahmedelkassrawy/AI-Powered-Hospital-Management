import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.services.google.llm import GoogleLLMService
from pipecat.runner.run import main
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
import os
from pipecat.services.openrouter.llm import OpenRouterLLMService
from pipecat.services.groq import GroqLLMService
import datetime as dt
from src.backend.langchain_agent import (
    get_doctor_schedule as _get_doctor_schedule,
    list_all_departments as _list_all_departments,
    check_patient_appointments as _check_patient_appointments,
    create_patient_record as _create_patient_record,
    list_doctors as _list_doctors,
    book_appointment as _book_appointment,
    cancel_appointment as _cancel_appointment,
)

load_dotenv(override=True)
settings = get_settings()

print("Starting Pipecat bot...")

llm = GroqLLMService(
    api_key=settings.GROQ_API_KEY,
    model="llama-3.3-70b-versatile",
)

async def _handle_get_doctor_schedule(function_name, tool_call_id, args, llm, context, result_callback):
    args["doctor_id"] = int(args["doctor_id"])
    result = await _get_doctor_schedule.ainvoke(args)
    await result_callback(str(result))

async def _handle_list_all_departments(function_name, tool_call_id, args, llm, context, result_callback):
    result = await _list_all_departments.ainvoke(args)
    await result_callback(str(result))

async def _handle_check_patient_appointments(function_name, tool_call_id, args, llm, context, result_callback):
    args["patient_id"] = int(args["patient_id"])
    result = await _check_patient_appointments.ainvoke(args)
    await result_callback(str(result))

async def _handle_create_patient_record(function_name, tool_call_id, args, llm, context, result_callback):
    if "age" in args:
        args["age"] = int(args["age"])
    result = await _create_patient_record.ainvoke(args)
    await result_callback(str(result))

async def _handle_list_doctors(function_name, tool_call_id, args, llm, context, result_callback):
    result = await _list_doctors.ainvoke(args)
    await result_callback(str(result))

async def _handle_book_appointment(function_name, tool_call_id, args, llm, context, result_callback):
    args["patient_id"] = int(args["patient_id"])
    args["doctor_id"] = int(args["doctor_id"])
    if "is_emergency" in args:
        v = args["is_emergency"]
        args["is_emergency"] = v if isinstance(v, bool) else str(v).lower() == "true"
    result = await _book_appointment.ainvoke(args)
    await result_callback(str(result))

async def _handle_cancel_appointment(function_name, tool_call_id, args, llm, context, result_callback):
    args["patient_id"] = int(args["patient_id"])
    args["appointment_id"] = int(args["appointment_id"])
    result = await _cancel_appointment.ainvoke(args)
    await result_callback(str(result))

llm.register_function("get_doctor_schedule", _handle_get_doctor_schedule)
llm.register_function("list_all_departments", _handle_list_all_departments)
llm.register_function("check_patient_appointments", _handle_check_patient_appointments)
llm.register_function("create_patient_record", _handle_create_patient_record)
llm.register_function("list_doctors", _handle_list_doctors)
llm.register_function("book_appointment", _handle_book_appointment)
llm.register_function("cancel_appointment", _handle_cancel_appointment)

async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info(f"Starting bot")

    stt = DeepgramSTTService(api_key = settings.DEEPGRAM_API_KEY)
    tts = CartesiaTTSService(api_key = settings.CARTESIA_API_KEY,
                             voice_id = "71a7ad14-091c-4e8e-a314-022ece01c121")
    messages = [
        {
            "role":"system",
            "content": "You are friendly AI Asisstant. Respond naturally and keep your answers conversational."
        }
    ]

    get_doctor_schedule = FunctionSchema(
        name="get_doctor_schedule",
        description="Get the schedule for a specific doctor",
        properties={
            "doctor_id": {
                "type": "string",
                "description": "The ID of the doctor",
            },
        },
        required=["doctor_id"]
    )

    list_all_departments = FunctionSchema(
        name="list_all_departments",
        description="List all available departments",
        properties={},
        required=[]
    )

    check_patient_appointments = FunctionSchema(
        name="check_patient_appointments",
        description="Check upcoming appointments for a patient",
        properties={
            "patient_id": {
                "type": "string",
                "description": "The ID of the patient",
            },
        },
        required=["patient_id"]
    )

    create_patient_record = FunctionSchema(
        name="create_patient_record",
        description="Create a new patient record in the system",
        properties={
            "name": {
                "type": "string",
                "description": "The full name of the patient",
            },
            "age": {
                "type": "string",
                "description": "The age of the patient",
            },
            "gender": {
                "type": "string",
                "description": "The gender of the patient",
            },
            "phone_number": {
                "type": "string",
                "description": "The phone number of the patient",
            },
            "email": {
                "type": "string",
                "description": "The email address of the patient",
            },
            "date_of_birth": {
                "type": "string",
                "description": "The date of birth of the patient",
            },
            "address": {
                "type": "string",
                "description": "The address of the patient",
            },
            "medical_history": {
                "type": "string",
                "description": "The medical history of the patient",
            }
        },
        required=["name", "age", "gender", "phone_number", "email", "date_of_birth", "address", "medical_history"]
    )

    book_appointment = FunctionSchema(
        name="book_appointment",
        description="Book an appointment with a doctor",
        properties={
            "patient_id": {
                "type": "string",
                "description": "The ID of the patient",
            },
            "doctor_id": {
                "type": "string",
                "description": "The ID of the doctor",
            },
            "date": {
                "type": "string",
                "description": "The date of the appointment (YYYY-MM-DD)",
            },
            "time": {
                "type": "string",
                "description": "The time of the appointment (HH:MM)",
            },
            "reason": {
                "type": "string",
                "description": "The reason for the appointment",
            },
            "is_emergency": {
                "type": "string",
                "description": "Whether the appointment is emergency (true or false)",
            }
        },
        required=["patient_id", "doctor_id", "date", "time", "reason"]
    )

    list_doctors = FunctionSchema(
        name="list_doctors",
        description="List all doctors in the hospital",
        properties={},
        required=[]
    )

    cancel_appointment = FunctionSchema(
        name="cancel_appointment",
        description="Cancel an existing appointment",
        properties={
            "appointment_id": {
                "type": "string",
                "description": "The ID of the appointment to cancel",
            },
            "patient_id": {
                "type": "string",
                "description": "The ID of the patient requesting the cancellation",
            }
        },
        required=["appointment_id", "patient_id"]
    )

    tools = ToolsSchema(standard_tools=[get_doctor_schedule,
        list_all_departments,
        check_patient_appointments,
        create_patient_record,
        list_doctors,
        book_appointment,
        cancel_appointment,]
    )

    context = LLMContext(messages)
    context.set_tools(tools)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params = LLMUserAggregatorParams(vad_analyzer = SileroVADAnalyzer()),
    )
 
    pipeline = Pipeline(
        [
            transport.input(),  # Transport user input
            stt,
            user_aggregator,  # User responses
            llm,  # LLM
            tts,  # TTS
            transport.output(),  # Transport bot output
            assistant_aggregator,  # Assistant spoken responses
        ]
    )

    task = PipelineTask(
        pipeline,
        params = PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    SYSTEM_PROMPT = f"""
# SYSTEM ROLE AND PRIMARY DIRECTIVE
You are an advanced AI Healthcare Receptionist and Hospital Management Assistant. Your primary objective is to streamline hospital operations by managing patient records, coordinating appointments, and providing accurate facility information. 

You must execute all tasks with strict precision, zero assumptions, and a calm, empathetic, and professional demeanor. 

Current Date and Time: {dt.datetime.now().strftime('%A, %Y-%m-%d %H:%M:%S')}
FOR DATES AND TIMES, ALWAYS USE THE CURRENT DATE AND TIME AS A REFERENCE POINT. NEVER ASSUME OR INVENT FUTURE OR PAST DATES/TIMES WITHOUT EXPLICIT USER INPUT.

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
    
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connected")
        messages.append(
            {
                "role": "system", 
                "content": "Say hello and briefly introduce yourself." + SYSTEM_PROMPT
            }
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint = runner_args.handle_sigint)
    await runner.run(task)

async def bot(runner_args: RunnerArguments):
    """Main bot entry point"""
    transport_params = {
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    }

    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)

if __name__ == "__main__":
    main()