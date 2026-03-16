from datetime import date, time, datetime
from pydantic import BaseModel
from typing import Optional, Literal, List
import datetime as dt

class PatientBase(BaseModel):
    name: str
    age: int
    gender: Literal["Male", "Female", "Other"]
    phone_number: str
    email: str
    date_of_birth: dt.date
    address: str
    medical_history: Optional[List[str]] = None

class PatientCreate(PatientBase):
    pass

class Patient(PatientBase):
    id: int

    class Config:
        from_attributes = True

class DoctorBase(BaseModel):
    name: str
    department: str
    phone_number: str
    email: str
    specialization: str
    working_hours: str
    consultation_duration: int

class DoctorCreate(DoctorBase):
    pass

class Doctor(DoctorBase):
    id: int

    class Config:
        from_attributes = True

class AppointmentBase(BaseModel):
    patient_id: int
    doctor_id: int
    date: dt.date
    time: dt.time
    reason: str
    is_emergency: bool
    status: Literal["Pending", "Completed", "Cancelled","Emergency"]

class AppointmentCreate(AppointmentBase):
    pass

class Appointment(AppointmentBase):
    id: int
    created_at: dt.datetime

    class Config:
        from_attributes = True

class CalendarBase(BaseModel):
    doctor_id: int
    appointment_id: int
    date: dt.date
    time: dt.time
    status: Literal["Available", "Booked", "Blocked"]


class CalendarCreate(CalendarBase):
    pass

class Calendar(CalendarBase):
    id: int
    created_at: dt.datetime

    class Config:
        from_attributes = True