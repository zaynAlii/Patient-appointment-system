from datetime import date as DateType, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    Index,
    Integer,
    Numeric,
    String,
    Time,
    Date,
    UniqueConstraint,
    func,
    text,
)
from pydantic import model_validator

from sqlmodel import Field, Relationship, SQLModel


class UserRole(str, Enum):
    DOCTOR = "doctor"
    
    
class ConsultationType(str, Enum):
    ONLINE = "online"
    PHYSICAL = "physical"

class AppointmentStatus(str, Enum):
    BOOKED = "booked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PublicSlotStatus(str, Enum):
    AVAILABLE = "available"
    BOOKED = "booked"
    COMPLETED = "completed"
    

class Weekday(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"    

class User_(SQLModel):
    username:str=Field(min_length=3 , unique=True , nullable=False)
    email: str = Field(
             sa_column=Column(String(320), unique=True, nullable=False)
         )
    first_name: str = Field(sa_column=Column(String(100), nullable=False))
    last_name: str = Field(sa_column=Column(String(100), nullable=False))

class UserIn(User_):
    password:str=Field(
        min_length=8 , max_length=30
    )     
        
class UserPublic(SQLModel): 
  pass

class User(User_, table=True):
    __tablename__ = "users"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )

    # email: str = Field(
    #     sa_column=Column(String(320), unique=True, nullable=False)
    # )

    password_hash: str = Field(
        sa_column=Column(String(255), nullable=False)
    )

    role: UserRole = Field(
        sa_column=Column(
            SAEnum(UserRole, name="user_role"),
            nullable=False,
        )
    )

    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true"))
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )

    doctor_profile: Optional["DoctorProfile"] = Relationship(
        back_populates="user"
    )

class DocProfileIn(SQLModel):
    specialization: str = Field(
            sa_column=Column(String(150), nullable=False)
        )
    
    qualification: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True)
    )

    experience_years: Optional[int] = Field(
        default=Field(default=None,ge=0 ),
        sa_column=Column(Integer, nullable=True ,)
    )

    bio: Optional[str] = Field(
        default=None,
        sa_column=Column(String(2000), nullable=True)
    )

    whatsapp_number: str = Field(
        sa_column=Column(String(30), nullable=False)
    )

    clinic_name: str = Field(
        sa_column=Column(String(200), nullable=False)
    )

    clinic_address: str = Field(
        sa_column=Column(String(500), nullable=False)
    )

    consultation_fee: Decimal = Field(
        sa_column=Column(
            Numeric(10, 2),
            nullable=False,
        )
    )

    slot_duration_minutes: int = Field(
        default=45,
        sa_column=Column(
            Integer,
            nullable=False,
            server_default=text("45"),
        )
    )


class PublicDoctorProfileResponse(DocProfileIn):
    doctor_id: UUID
    first_name: str
    last_name: str
    timezone: str


class DoctorProfileUpdate(SQLModel):
    specialization: Optional[str] = Field(default=None, max_length=150)
    qualification: Optional[str] = Field(default=None, max_length=255)
    experience_years: Optional[int] = Field(default=None, ge=0)
    bio: Optional[str] = Field(default=None, max_length=2000)
    whatsapp_number: Optional[str] = Field(default=None, max_length=30)
    clinic_name: Optional[str] = Field(default=None, max_length=200)
    clinic_address: Optional[str] = Field(default=None, max_length=500)
    consultation_fee: Optional[Decimal] = Field(default=None, gt=0)
    slot_duration_minutes: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_patch_fields(self) -> "DoctorProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one profile field to update")

        required_fields = {
            "specialization",
            "whatsapp_number",
            "clinic_name",
            "clinic_address",
            "consultation_fee",
            "slot_duration_minutes",
        }
        null_required_fields = [
            field_name
            for field_name in required_fields & self.model_fields_set
            if getattr(self, field_name) is None
        ]
        if null_required_fields:
            raise ValueError(
                f"These fields cannot be null: {', '.join(sorted(null_required_fields))}"
            )
        return self


class DoctorProfileResponse(DocProfileIn):
    id: UUID
    timezone: str
    
     

class DoctorProfile(DocProfileIn, table=True):
    __tablename__ = "doctor_profiles"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        unique=True,
        nullable=False,
    )
    
    timezone: str = Field(
        default="Asia/Karachi",
        sa_column=Column(
            String(50),
            nullable=False,
            server_default=text("'Asia/Karachi'"),
        )
    )

    user: User = Relationship(
        back_populates="doctor_profile"
    )

    availability: list["DoctorAvailability"] = Relationship(
        back_populates="doctor"
    )

    appointments: list["Appointment"] = Relationship(
        back_populates="doctor"
    )    
    
class DocAvailabilityIn(SQLModel):
    weekday: Weekday = Field(
            sa_column=Column(
                SAEnum(Weekday, name="weekday"),
                nullable=False,
            )
        )
    
    start_time: time = Field(
        sa_column=Column(Time, nullable=False)
    )

    end_time: time = Field(
        sa_column=Column(Time, nullable=False)
    )


class AvailabilityIntervalIn(SQLModel):
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "AvailabilityIntervalIn":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class WeekdayScheduleIn(SQLModel):
    weekday: Weekday
    intervals: list[AvailabilityIntervalIn] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_intervals(self) -> "WeekdayScheduleIn":
        ordered_intervals = sorted(self.intervals, key=lambda interval: interval.start_time)
        for previous, current in zip(ordered_intervals, ordered_intervals[1:]):
            if current.start_time < previous.end_time:
                raise ValueError("Availability intervals for a weekday cannot overlap")
        return self


class DoctorWeeklyScheduleIn(SQLModel):
    days: list[WeekdayScheduleIn] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def validate_unique_weekdays(self) -> "DoctorWeeklyScheduleIn":
        weekdays = [day.weekday for day in self.days]
        if len(weekdays) != len(set(weekdays)):
            raise ValueError("Each weekday can appear only once")
        return self


class DoctorWeeklyScheduleResponse(SQLModel):
    doctor_id: UUID
    timezone: str
    days: list[WeekdayScheduleIn]


class PatientContactIn(SQLModel):
    full_name: str = Field(max_length=150)
    phone: str = Field(max_length=30)
    address: str = Field(max_length=500)
    date_of_birth: Optional[DateType] = None
    visit_reason: Optional[str] = Field(default=None, max_length=2000)


class AppointmentBookingIn(SQLModel):
    date: DateType
    time_slot: time
    consultation_type: ConsultationType
    patient: PatientContactIn


class AppointmentStatusUpdate(SQLModel):
    status: AppointmentStatus

    @model_validator(mode="after")
    def validate_terminal_status(self) -> "AppointmentStatusUpdate":
        if self.status == AppointmentStatus.BOOKED:
            raise ValueError("Appointment status can only be completed or cancelled")
        return self


class AppointmentBookingResponse(SQLModel):
    appointment_id: UUID
    doctor_id: UUID
    date: DateType
    start_time: time
    end_time: time
    status: AppointmentStatus
    patient_access_token: str


class PatientAppointmentResponse(SQLModel):
    appointment_id: UUID
    doctor_id: UUID
    clinic_name: str
    clinic_address: str
    timezone: str
    date: DateType
    start_time: time
    end_time: time
    consultation_type: ConsultationType
    status: AppointmentStatus
    booked_at: Optional[datetime] = None


class PatientContactResponse(SQLModel):
    full_name: str
    phone: str
    address: str
    date_of_birth: Optional[DateType] = None
    visit_reason: Optional[str] = None


class DoctorAppointmentResponse(SQLModel):
    appointment_id: UUID
    date: DateType
    start_time: time
    end_time: time
    consultation_type: ConsultationType
    status: AppointmentStatus
    booked_at: Optional[datetime] = None
    patient: PatientContactResponse


class DoctorAppointmentListResponse(SQLModel):
    doctor_id: UUID
    timezone: str
    total_count: int
    offset: int
    limit: int
    appointments: list[DoctorAppointmentResponse]


class DoctorScheduleSlot(SQLModel):
    start_time: time
    end_time: time
    status: PublicSlotStatus


class DoctorScheduleDay(SQLModel):
    weekday: Weekday
    date: DateType
    slots: list[DoctorScheduleSlot]


class DoctorScheduleResponse(SQLModel):
    doctor_id: UUID
    timezone: str
    days: list[DoctorScheduleDay]


class DoctorAvailability(DocAvailabilityIn, table=True):
    __tablename__ = "doctor_availability"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )

    doctor_id: UUID = Field(
        foreign_key="doctor_profiles.id",
        nullable=False,
    )

  
    doctor: DoctorProfile = Relationship(
        back_populates="availability"
    )

    __table_args__ = (
        UniqueConstraint(
            "doctor_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_doctor_weekday_interval",
        ),
        CheckConstraint(
            "start_time < end_time",
            name="ck_availability_valid_time",
        ),
    )    
    
class PatientContact(SQLModel, table=True):
    __tablename__ = "patient_contacts"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )

    full_name: str = Field(
        sa_column=Column(String(150), nullable=False)
    )

    phone: str = Field(
        sa_column=Column(String(30), nullable=False)
    )

    address: str = Field(
        sa_column=Column(String(500), nullable=False)
    )

    date_of_birth: Optional[DateType] = Field(
        default=None,
        sa_column=Column(Date, nullable=True),
    )

    visit_reason: Optional[str] = Field(
        default=None,
        sa_column=Column(String(2000), nullable=True),
    )

    appointment: Optional["Appointment"] = Relationship(
        back_populates="patient_contact"
    )
    
    
class Appointment(SQLModel, table=True):
    __tablename__ = "appointments"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )

    doctor_id: UUID = Field(
        foreign_key="doctor_profiles.id",
        nullable=False,
    )

    patient_contact_id: UUID = Field(
        foreign_key="patient_contacts.id",
        unique=True,
        nullable=False,
    )

    patient_access_token_hash: str = Field(
        sa_column=Column(String(64), nullable=False, unique=True)
    )

    date: DateType = Field(
        sa_column=Column(
            Date,
            nullable=False,
        )
    )

    # ends_at: datetime = Field(
    #     sa_column=Column(
    #         DateTime(timezone=True),
    #         nullable=False,
    #     )
    # )
    
    time_slot:time=Field(
        sa_column=Column(
            Time,
            nullable=False,
        ))

    consultation_type: ConsultationType = Field(
        sa_column=Column(
            SAEnum(
                ConsultationType,
                name="consultation_type",
            ),
            nullable=False,
        )
    )

    status: AppointmentStatus = Field(
        default=AppointmentStatus.BOOKED,
        sa_column=Column(
            SAEnum(
                AppointmentStatus,
                name="appointment_status",
                values_callable=lambda statuses: [status.value for status in statuses],
            ),
            nullable=False,
            server_default=text("'booked'"),
        )
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        )
    )

    booked_at: Optional[datetime] = Field(
        default_factory=lambda : datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now()
        ))
    cancelled_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        )
    )

    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        )
    )
    

    doctor: DoctorProfile = Relationship(
        back_populates="appointments"
    )

    patient_contact: PatientContact = Relationship(
        back_populates="appointment"
    )

    feedback: Optional["Feedback"] = Relationship(
        back_populates="appointment"
    )

    __table_args__ = (
        Index(
            "uq_active_appointment_doctor_slot",
            "doctor_id",
            "date",
            "time_slot",
            unique=True,
            postgresql_where=text("status != 'cancelled'"),
        ),
    )
      
    
class Feedback(SQLModel, table=True):
    __tablename__ = "feedback"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )

    appointment_id: UUID = Field(
        foreign_key="appointments.id",
        unique=True,
        nullable=False,
    )

    rating: int = Field(
        sa_column=Column(
            Integer,
            nullable=False,
        )
    )

    comment: Optional[str] = Field(
        default=None,
        sa_column=Column(
            String(2000),
            nullable=True,
        )
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        )
    )

    appointment: Appointment = Relationship(
        back_populates="feedback"
    )

    __table_args__ = (
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_feedback_rating",
        ),
    )    
    
    
    
    
    
    

































# backened receive request with date 27-9-26 
# i will determine the day .

# i will get the doctor availability for that day and
# then i will calculate the slots based on the start time
# and end time and the slot duration.
# i will also check if the slot is already booked or not. 

# for this  i need to get the appointments for that doctor on that day and check if the slot is booked or not.

# soo  algo be like this :
#        first fetch all the apointment to that date .      
#        create slot  based on the start time and end time and the slot duration.
#        and see the appointment records if any of the slot is booked or not.
#        if booked the add in the json  .  u need to create the dict . first . then start adding the slots  with status in the dict.

# finally i will return the available slots to the frontend.


# i need to return the json response
# {
#    monday:{
#        date: 27-9-26
#          slots:[
#               {
#                 start_time: 10:00
#                 end_time: 10:45
#                 status: available
#               },
#               {
#                 start_time: 11:00
#                 end_time: 11:45
#                 status: booked
#               }
#          ]
#    } 
#    tuesday:{
#        date: 28-9-26
#          slots:[
#               {
#                 start_time: 10:00
#                 end_time: 10:45
#                 status: available
#               },
#               {
#                 start_time: 11:00
#                 end_time: 11:45
#                 status: booked
#               }
#          ]
#    }
#    ...
#    ...
    
    
# }












    