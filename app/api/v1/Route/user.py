from datetime import date as DateType
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app.crud.user_crud import userInstace  #type:ignore
from app.models.modal import AppointmentBookingIn, AppointmentBookingResponse, AppointmentStatus, AppointmentStatusUpdate, DocProfileIn, DoctorAppointmentListResponse, DoctorAppointmentResponse, DoctorProfileResponse, DoctorProfileUpdate, DoctorScheduleResponse, DoctorWeeklyScheduleIn, DoctorWeeklyScheduleResponse, PatientAppointmentResponse, PublicDoctorProfileResponse  #type:ignore
from app.api.dependencies import Session_Dependency, Get_Doctor_id  #type:ignore

router:APIRouter=APIRouter()


@router.get(
    "/patient/appointments/me",
    response_model=PatientAppointmentResponse,
)
async def Get_Patient_Appointment(
    patient_access_token: Annotated[
        str,
        Header(alias="X-Appointment-Token", min_length=40, max_length=128),
    ],
    session: Session_Dependency,
):
    return await userInstace.get_patient_appointment(
        patient_access_token,
        session,
    )


@router.patch(
    "/patient/appointments/me/cancel",
    response_model=PatientAppointmentResponse,
)
async def Cancel_Patient_Appointment(
    patient_access_token: Annotated[
        str,
        Header(alias="X-Appointment-Token", min_length=40, max_length=128),
    ],
    session: Session_Dependency,
):
    return await userInstace.cancel_patient_appointment(
        patient_access_token,
        session,
    )


@router.get(
    "/doctors/{doctor_id}/schedule",
    response_model=DoctorScheduleResponse,
)
async def Get_Public_Doctor_Schedule(
    doctor_id: UUID,
    session: Session_Dependency,
    from_date: DateType | None = None,
):
    return await userInstace.get_public_doctor_schedule(
        doctor_id,
        from_date,
        session,
    )


@router.get(
    "/doctors/{doctor_id}/profile",
    response_model=PublicDoctorProfileResponse,
)
async def Get_Public_Doctor_Profile(
    doctor_id: UUID,
    session: Session_Dependency,
):
    return await userInstace.get_public_doctor_profile(
        doctor_id,
        session,
    )


@router.post(
    "/doctors/{doctor_id}/appointments",
    response_model=AppointmentBookingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def Book_Public_Doctor_Appointment(
    doctor_id: UUID,
    booking_data: AppointmentBookingIn,
    session: Session_Dependency,
):
    return await userInstace.book_public_appointment(
        doctor_id,
        booking_data,
        session,
    )


@router.get(
    "/doctors/me/appointments",
    response_model=DoctorAppointmentListResponse,
)
async def Get_Doctor_Appointments(
    doctor_user_id: Get_Doctor_id,
    session: Session_Dependency,
    from_date: DateType | None = None,
    to_date: DateType | None = None,
    appointment_statuses: Annotated[
        list[AppointmentStatus] | None,
        Query(alias="status"),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await userInstace.get_doctor_appointments(
        doctor_user_id,
        from_date,
        to_date,
        appointment_statuses,
        offset,
        limit,
        session,
    )


@router.patch(
    "/doctors/me/appointments/{appointment_id}",
    response_model=DoctorAppointmentResponse,
)
async def Update_Doctor_Appointment_Status(
    appointment_id: UUID,
    status_update: AppointmentStatusUpdate,
    doctor_user_id: Get_Doctor_id,
    session: Session_Dependency,
):
    return await userInstace.update_doctor_appointment_status(
        doctor_user_id,
        appointment_id,
        status_update,
        session,
    )


@router.post("/doctors/profile/info", status_code=status.HTTP_201_CREATED)
async def Add_Profile_Info(
	profile_data: DocProfileIn,
    doctor_user_id:Get_Doctor_id, 
	session: Session_Dependency,
	
):
	return await userInstace.create_doctor_profile(
		profile_data,
		doctor_user_id,
		session,
	)


@router.patch(
    "/doctors/me/profile",
    response_model=DoctorProfileResponse,
)
async def Update_Doctor_Profile(
    profile_data: DoctorProfileUpdate,
    doctor_user_id: Get_Doctor_id,
    session: Session_Dependency,
):
    return await userInstace.update_doctor_profile(
        profile_data,
        doctor_user_id,
        session,
    )


@router.get(
    "/doctors/me/availability",
    response_model=DoctorWeeklyScheduleResponse,
)
async def Get_Doctor_Weekly_Availability(
    doctor_user_id: Get_Doctor_id,
    session: Session_Dependency,
):
    return await userInstace.get_doctor_weekly_availability(
        doctor_user_id,
        session,
    )


@router.put("/doctors/me/availability", status_code=status.HTTP_200_OK)
async def Replace_Doctor_Weekly_Schedule(
    schedule_data: DoctorWeeklyScheduleIn,
    doctor_user_id: Get_Doctor_id,
    session: Session_Dependency,
):
    return await userInstace.replace_doctor_weekly_schedule(
        schedule_data,
        doctor_user_id,
        session,
    )
