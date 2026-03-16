"""
seed_db.py — populate the hospital database with realistic mock data.

Run from the project root:
    python seed_db.py
"""
import sys
import os
import asyncio
from datetime import date, time, datetime

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.database.db import AsyncSessionLocal, async_engine, Base
from src.database.model import Doctor, Patient, Appointment, Calendar


# ─── Mock Data ────────────────────────────────────────────────────────────────

DOCTORS = [
    Doctor(
        name="Dr. Sarah Mitchell",
        department="Cardiology",
        phone_number="+1-555-0101",
        email="s.mitchell@hospital.com",
        specialization="Interventional Cardiology",
        working_hours="Mon-Fri 08:00-16:00",
        consultation_duration=30,
    ),
    Doctor(
        name="Dr. James Okafor",
        department="Neurology",
        phone_number="+1-555-0102",
        email="j.okafor@hospital.com",
        specialization="Epilepsy & Sleep Disorders",
        working_hours="Mon-Thu 09:00-17:00",
        consultation_duration=45,
    ),
    Doctor(
        name="Dr. Aisha Rahman",
        department="Pediatrics",
        phone_number="+1-555-0103",
        email="a.rahman@hospital.com",
        specialization="Neonatal Care",
        working_hours="Mon-Fri 07:00-15:00",
        consultation_duration=20,
    ),
    Doctor(
        name="Dr. Carlos Mendez",
        department="Orthopedics",
        phone_number="+1-555-0104",
        email="c.mendez@hospital.com",
        specialization="Sports Medicine & Joint Replacement",
        working_hours="Tue-Sat 10:00-18:00",
        consultation_duration=30,
    ),
    Doctor(
        name="Dr. Emily Chen",
        department="Dermatology",
        phone_number="+1-555-0105",
        email="e.chen@hospital.com",
        specialization="Cosmetic & Medical Dermatology",
        working_hours="Mon-Wed-Fri 08:00-14:00",
        consultation_duration=20,
    ),
]

PATIENTS = [
    Patient(
        name="John Harrison",
        age=54,
        gender="Male",
        phone_number="+1-555-1001",
        email="john.harrison@email.com",
        date_of_birth=date(1970, 3, 15),
        address="12 Maple Street, Springfield, IL 62701",
        medical_history=["Hypertension", "Type 2 Diabetes"],
    ),
    Patient(
        name="Maria Gonzalez",
        age=32,
        gender="Female",
        phone_number="+1-555-1002",
        email="m.gonzalez@email.com",
        date_of_birth=date(1992, 7, 22),
        address="85 Oak Avenue, Denver, CO 80203",
        medical_history=["Asthma"],
    ),
    Patient(
        name="Liam O'Brien",
        age=8,
        gender="Male",
        phone_number="+1-555-1003",
        email="obrien.family@email.com",
        date_of_birth=date(2016, 11, 5),
        address="7 Elm Close, Boston, MA 02101",
        medical_history=None,
    ),
    Patient(
        name="Priya Sharma",
        age=41,
        gender="Female",
        phone_number="+1-555-1004",
        email="priya.sharma@email.com",
        date_of_birth=date(1983, 1, 30),
        address="220 Pine Road, Austin, TX 78701",
        medical_history=["Migraine", "Anxiety"],
    ),
    Patient(
        name="David Park",
        age=67,
        gender="Male",
        phone_number="+1-555-1005",
        email="d.park@email.com",
        date_of_birth=date(1957, 9, 12),
        address="3 Cedar Lane, Seattle, WA 98101",
        medical_history=["Osteoarthritis", "Hypertension", "Hyperlipidemia"],
    ),
]


async def seed() -> None:
    # Ensure tables exist (safe no-op if they already do)
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # ── Doctors ──────────────────────────────────────────────────────────
        session.add_all(DOCTORS)
        await session.flush()           # get auto-assigned IDs
        print(f"[OK] Inserted {len(DOCTORS)} doctors.")

        # ── Patients ─────────────────────────────────────────────────────────
        session.add_all(PATIENTS)
        await session.flush()
        print(f"[OK] Inserted {len(PATIENTS)} patients.")

        # ── Appointments ─────────────────────────────────────────────────────
        # IDs are assigned after flush; reference by object attribute.
        appointments = [
            Appointment(
                patient_id=PATIENTS[0].id,          # John Harrison
                doctor_id=DOCTORS[0].id,            # Dr. Mitchell – Cardiology
                date=date(2026, 3, 20),
                time=time(9, 0),
                reason="Annual cardiac check-up",
                is_emergency=False,
                status="Pending",
                created_at=datetime.utcnow(),
            ),
            Appointment(
                patient_id=PATIENTS[3].id,          # Priya Sharma
                doctor_id=DOCTORS[1].id,            # Dr. Okafor – Neurology
                date=date(2026, 3, 21),
                time=time(10, 30),
                reason="Recurrent migraines evaluation",
                is_emergency=False,
                status="Pending",
                created_at=datetime.utcnow(),
            ),
            Appointment(
                patient_id=PATIENTS[2].id,          # Liam O'Brien
                doctor_id=DOCTORS[2].id,            # Dr. Rahman – Pediatrics
                date=date(2026, 3, 18),
                time=time(8, 0),
                reason="Routine well-child visit",
                is_emergency=False,
                status="Completed",
                created_at=datetime.utcnow(),
            ),
            Appointment(
                patient_id=PATIENTS[4].id,          # David Park
                doctor_id=DOCTORS[3].id,            # Dr. Mendez – Orthopedics
                date=date(2026, 3, 22),
                time=time(11, 0),
                reason="Knee pain follow-up",
                is_emergency=False,
                status="Pending",
                created_at=datetime.utcnow(),
            ),
            Appointment(
                patient_id=PATIENTS[1].id,          # Maria Gonzalez
                doctor_id=DOCTORS[4].id,            # Dr. Chen – Dermatology
                date=date(2026, 3, 17),
                time=time(9, 30),
                reason="Skin rash examination",
                is_emergency=False,
                status="Cancelled",
                created_at=datetime.utcnow(),
            ),
            Appointment(
                patient_id=PATIENTS[0].id,          # John Harrison (emergency)
                doctor_id=DOCTORS[0].id,            # Dr. Mitchell
                date=date(2026, 3, 15),
                time=time(14, 0),
                reason="Chest pain – emergency consult",
                is_emergency=True,
                status="Emergency",
                created_at=datetime.utcnow(),
            ),
        ]
        session.add_all(appointments)
        await session.flush()
        print(f"[OK] Inserted {len(appointments)} appointments.")

        # ── Calendar ─────────────────────────────────────────────────────────
        calendar_entries = [
            Calendar(
                doctor_id=appt.doctor_id,
                appointment_id=appt.id,
                date=appt.date,
                time=appt.time,
                status="Booked" if appt.status in ("Pending", "Emergency") else "Available",
                created_at=datetime.utcnow(),
            )
            for appt in appointments
        ]
        session.add_all(calendar_entries)
        await session.flush()
        print(f"[OK] Inserted {len(calendar_entries)} calendar entries.")

        await session.commit()
        print("\nSeed complete -- database is ready to use!")


if __name__ == "__main__":
    asyncio.run(seed())
