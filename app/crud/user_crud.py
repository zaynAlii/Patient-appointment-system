import hashlib
import secrets
from datetime import date as DateType, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.models.modal import Appointment, AppointmentBookingIn, AppointmentBookingResponse, AppointmentStatus, AppointmentStatusUpdate, AvailabilityIntervalIn, DocProfileIn, DoctorAppointmentListResponse, DoctorAppointmentResponse, DoctorAvailability, DoctorProfile, DoctorProfileResponse, DoctorProfileUpdate, DoctorScheduleDay, DoctorScheduleResponse, DoctorScheduleSlot, DoctorWeeklyScheduleIn, DoctorWeeklyScheduleResponse, PatientAppointmentResponse, PatientContact, PatientContactResponse, PublicDoctorProfileResponse, PublicSlotStatus, User, Weekday, WeekdayScheduleIn  #type:ignore
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from sqlmodel import select

class UserCrud():

    async def get_public_doctor_profile(
        self,
        doctor_id: UUID,
        session: AsyncSession,
    ) -> PublicDoctorProfileResponse:
        try:
            profile_row = (await session.execute(
                select(DoctorProfile, User)
                .join(User, User.id == DoctorProfile.user_id)
                .where(DoctorProfile.id == doctor_id)
            )).one_or_none()
            if profile_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor profile not found",
                )

            doctor_profile, user = profile_row
            return PublicDoctorProfileResponse(
                doctor_id=doctor_profile.id,
                first_name=user.first_name,
                last_name=user.last_name,
                specialization=doctor_profile.specialization,
                qualification=doctor_profile.qualification,
                experience_years=doctor_profile.experience_years,
                bio=doctor_profile.bio,
                whatsapp_number=doctor_profile.whatsapp_number,
                clinic_name=doctor_profile.clinic_name,
                clinic_address=doctor_profile.clinic_address,
                consultation_fee=doctor_profile.consultation_fee,
                slot_duration_minutes=doctor_profile.slot_duration_minutes,
                timezone=doctor_profile.timezone,
            )
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while fetching the doctor profile",
            ) from error

    async def update_doctor_profile(
        self,
        profile_update: DoctorProfileUpdate,
        user_id: UUID,
        session: AsyncSession,
    ) -> DoctorProfileResponse:
        try:
            doctor_profile = (await session.execute(
                select(DoctorProfile)
                .where(DoctorProfile.user_id == user_id)
                .with_for_update()
            )).scalar_one_or_none()
            if doctor_profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor profile not found",
                )

            update_data = profile_update.model_dump(exclude_unset=True)
            new_slot_duration = update_data.get(
                "slot_duration_minutes",
                doctor_profile.slot_duration_minutes,
            )
            if new_slot_duration != doctor_profile.slot_duration_minutes:
                clinic_today = datetime.now(ZoneInfo(doctor_profile.timezone)).date()
                future_bookings = (await session.execute(
                    select(Appointment).where(
                        Appointment.doctor_id == doctor_profile.id,
                        Appointment.status == AppointmentStatus.BOOKED,
                        Appointment.date >= clinic_today,
                    )
                )).scalars().all()
                if future_bookings:
                    availability_rows = (await session.execute(
                        select(DoctorAvailability).where(
                            DoctorAvailability.doctor_id == doctor_profile.id
                        )
                    )).scalars().all()
                    availability_by_weekday: dict[
                        Weekday,
                        list[DoctorAvailability],
                    ] = {}
                    for interval in availability_rows:
                        availability_by_weekday.setdefault(
                            interval.weekday,
                            [],
                        ).append(interval)

                    weekdays = (
                        Weekday.MONDAY,
                        Weekday.TUESDAY,
                        Weekday.WEDNESDAY,
                        Weekday.THURSDAY,
                        Weekday.FRIDAY,
                        Weekday.SATURDAY,
                        Weekday.SUNDAY,
                    )
                    duration_seconds = new_slot_duration * 60
                    for appointment in future_bookings:
                        weekday = weekdays[appointment.date.weekday()]
                        appointment_start = (
                            appointment.time_slot.hour * 3600
                            + appointment.time_slot.minute * 60
                            + appointment.time_slot.second
                        )
                        remains_scheduled = any(
                            (interval_start := interval.start_time.hour * 3600
                             + interval.start_time.minute * 60
                             + interval.start_time.second) <= appointment_start
                            and appointment_start + duration_seconds
                            <= interval.end_time.hour * 3600
                            + interval.end_time.minute * 60
                            + interval.end_time.second
                            and (appointment_start - interval_start)
                            % duration_seconds == 0
                            for interval in availability_by_weekday.get(weekday, [])
                        )
                        if not remains_scheduled:
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail="Slot duration change would invalidate a booked appointment",
                            )

            for field_name, value in update_data.items():
                setattr(doctor_profile, field_name, value)

            await session.commit()
            await session.refresh(doctor_profile)
            return DoctorProfileResponse.model_validate(doctor_profile)
        except HTTPException:
            await session.rollback()
            raise
        except IntegrityError as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not update doctor profile",
            ) from error
        except Exception as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while updating the doctor profile",
            ) from error

    async def cancel_patient_appointment(
        self,
        patient_access_token: str,
        session: AsyncSession,
    ) -> PatientAppointmentResponse:
        try:
            token_hash = hashlib.sha256(
                patient_access_token.encode("utf-8")
            ).hexdigest()
            appointment = (await session.execute(
                select(Appointment)
                .where(Appointment.patient_access_token_hash == token_hash)
                .with_for_update()
            )).scalar_one_or_none()
            if appointment is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Appointment not found",
                )
            if appointment.status != AppointmentStatus.BOOKED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only booked appointments can be cancelled",
                )

            doctor_profile = (await session.execute(
                select(DoctorProfile).where(
                    DoctorProfile.id == appointment.doctor_id
                )
            )).scalar_one_or_none()
            if doctor_profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor profile not found",
                )
            if doctor_profile.slot_duration_minutes <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile has an invalid slot duration",
                )

            try:
                clinic_timezone = ZoneInfo(doctor_profile.timezone)
            except ZoneInfoNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile has an invalid timezone",
                ) from error

            appointment_start = datetime.combine(
                appointment.date,
                appointment.time_slot,
            ).replace(tzinfo=clinic_timezone)
            now = datetime.now(timezone.utc)
            minutes_until_appointment = (
                appointment_start.astimezone(timezone.utc) - now
            )
            if minutes_until_appointment < timedelta(minutes=30):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Appointments can only be cancelled at least 30 minutes before start time",
                )

            appointment.status = AppointmentStatus.CANCELLED
            appointment.cancelled_at = now
            await session.commit()
            await session.refresh(appointment)

            return PatientAppointmentResponse(
                appointment_id=appointment.id,
                doctor_id=doctor_profile.id,
                clinic_name=doctor_profile.clinic_name,
                clinic_address=doctor_profile.clinic_address,
                timezone=doctor_profile.timezone,
                date=appointment.date,
                start_time=appointment.time_slot,
                end_time=(
                    datetime.combine(appointment.date, appointment.time_slot)
                    + timedelta(minutes=doctor_profile.slot_duration_minutes)
                ).time(),
                consultation_type=appointment.consultation_type,
                status=appointment.status,
                booked_at=appointment.booked_at,
            )
        except HTTPException:
            await session.rollback()
            raise
        except IntegrityError as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not cancel this appointment",
            ) from error
        except Exception as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while cancelling the appointment",
            ) from error

    async def get_patient_appointment(
        self,
        patient_access_token: str,
        session: AsyncSession,
    ) -> PatientAppointmentResponse:
        try:
            token_hash = hashlib.sha256(
                patient_access_token.encode("utf-8")
            ).hexdigest()
            appointment_result = await session.execute(
                select(Appointment, DoctorProfile)
                .join(
                    DoctorProfile,
                    DoctorProfile.id == Appointment.doctor_id,
                )
                .where(Appointment.patient_access_token_hash == token_hash)
            )
            appointment_row = appointment_result.one_or_none()
            if appointment_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Appointment not found",
                )

            appointment, doctor_profile = appointment_row
            if doctor_profile.slot_duration_minutes <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile has an invalid slot duration",
                )

            appointment_start = datetime.combine(
                appointment.date,
                appointment.time_slot,
            )
            return PatientAppointmentResponse(
                appointment_id=appointment.id,
                doctor_id=doctor_profile.id,
                clinic_name=doctor_profile.clinic_name,
                clinic_address=doctor_profile.clinic_address,
                timezone=doctor_profile.timezone,
                date=appointment.date,
                start_time=appointment.time_slot,
                end_time=(
                    appointment_start
                    + timedelta(minutes=doctor_profile.slot_duration_minutes)
                ).time(),
                consultation_type=appointment.consultation_type,
                status=appointment.status,
                booked_at=appointment.booked_at,
            )
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while fetching the appointment",
            ) from error

    async def update_doctor_appointment_status(
        self,
        user_id: UUID,
        appointment_id: UUID,
        status_update: AppointmentStatusUpdate,
        session: AsyncSession,
    ) -> DoctorAppointmentResponse:
        try:
            doctor_profile = (await session.execute(
                select(DoctorProfile).where(DoctorProfile.user_id == user_id)
            )).scalar_one_or_none()
            if doctor_profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor profile not found",
                )

            appointment = (await session.execute(
                select(Appointment)
                .where(
                    Appointment.id == appointment_id,
                    Appointment.doctor_id == doctor_profile.id,
                )
                .with_for_update()
            )).scalar_one_or_none()
            if appointment is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Appointment not found",
                )

            if appointment.status != status_update.status:
                if appointment.status != AppointmentStatus.BOOKED:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Only booked appointments can be completed or cancelled",
                    )

                now = datetime.now(timezone.utc)
                appointment.status = status_update.status
                if status_update.status == AppointmentStatus.COMPLETED:
                    appointment.completed_at = now
                else:
                    appointment.cancelled_at = now

            patient_contact = (await session.execute(
                select(PatientContact).where(
                    PatientContact.id == appointment.patient_contact_id
                )
            )).scalar_one_or_none()
            if patient_contact is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Appointment contact record is missing",
                )

            if doctor_profile.slot_duration_minutes <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile has an invalid slot duration",
                )

            await session.commit()
            await session.refresh(appointment)
            appointment_start = datetime.combine(
                appointment.date,
                appointment.time_slot,
            )
            return DoctorAppointmentResponse(
                appointment_id=appointment.id,
                date=appointment.date,
                start_time=appointment.time_slot,
                end_time=(
                    appointment_start
                    + timedelta(minutes=doctor_profile.slot_duration_minutes)
                ).time(),
                consultation_type=appointment.consultation_type,
                status=appointment.status,
                booked_at=appointment.booked_at,
                patient=PatientContactResponse.model_validate(patient_contact),
            )
        except HTTPException:
            await session.rollback()
            raise
        except IntegrityError as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not update appointment status",
            ) from error
        except Exception as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while updating the appointment",
            ) from error

    async def get_doctor_appointments(
        self,
        user_id: UUID,
        from_date: DateType | None,
        to_date: DateType | None,
        statuses: list[AppointmentStatus] | None,
        offset: int,
        limit: int,
        session: AsyncSession,
    ) -> DoctorAppointmentListResponse:
        try:
            doctor_profile = (await session.execute(
                select(DoctorProfile).where(DoctorProfile.user_id == user_id)
            )).scalar_one_or_none()
            if doctor_profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor profile not found",
                )

            if from_date is not None and to_date is not None and from_date > to_date:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="from_date must be on or before to_date",
                )
            if doctor_profile.slot_duration_minutes <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile has an invalid slot duration",
                )

            filters = [Appointment.doctor_id == doctor_profile.id]
            if from_date is not None:
                filters.append(Appointment.date >= from_date)
            if to_date is not None:
                filters.append(Appointment.date <= to_date)
            if statuses:
                filters.append(Appointment.status.in_(statuses))

            total_count = (await session.execute(
                select(func.count())
                .select_from(Appointment)
                .where(*filters)
            )).scalar_one()

            appointment_rows = (await session.execute(
                select(Appointment, PatientContact)
                .join(
                    PatientContact,
                    PatientContact.id == Appointment.patient_contact_id,
                )
                .where(*filters)
                .order_by(Appointment.date, Appointment.time_slot)
                .offset(offset)
                .limit(limit)
            )).all()

            slot_duration = timedelta(minutes=doctor_profile.slot_duration_minutes)
            appointments = []
            for appointment, patient_contact in appointment_rows:
                appointment_start = datetime.combine(
                    appointment.date,
                    appointment.time_slot,
                )
                appointments.append(
                    DoctorAppointmentResponse(
                        appointment_id=appointment.id,
                        date=appointment.date,
                        start_time=appointment.time_slot,
                        end_time=(appointment_start + slot_duration).time(),
                        consultation_type=appointment.consultation_type,
                        status=appointment.status,
                        booked_at=appointment.booked_at,
                        patient=PatientContactResponse.model_validate(patient_contact),
                    )
                )

            return DoctorAppointmentListResponse(
                doctor_id=doctor_profile.id,
                timezone=doctor_profile.timezone,
                total_count=total_count,
                offset=offset,
                limit=limit,
                appointments=appointments,
            )
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while fetching appointments",
            ) from error

    async def book_public_appointment(
        self,
        doctor_id: UUID,
        booking: AppointmentBookingIn,
        session: AsyncSession,
    ) -> AppointmentBookingResponse:
        try:
            doctor_profile = (await session.execute(
                select(DoctorProfile)
                .where(DoctorProfile.id == doctor_id)
                .with_for_update()
            )).scalar_one_or_none()
            if doctor_profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor profile not found",
                )

            try:
                clinic_timezone = ZoneInfo(doctor_profile.timezone)
            except ZoneInfoNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile has an invalid timezone",
                ) from error

            clinic_now = datetime.now(clinic_timezone)
            clinic_today = clinic_now.date()
            #  if not clinic_today <= booking.date <= clinic_today + timedelta(days=6):
            #                 raise HTTPException(
            #                     status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            #                     detail="Bookings are limited to the next seven calendar days",
            #                 )
            if booking.date < clinic_today:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Appointments cannot be booked for a past date",
                )
            if booking.time_slot.tzinfo is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="time_slot must be a clinic-local time without a timezone offset",
                )

            slot_duration_minutes = doctor_profile.slot_duration_minutes
            if slot_duration_minutes <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile has an invalid slot duration",
                )
            slot_duration = timedelta(minutes=slot_duration_minutes)
            slot_start = datetime.combine(booking.date, booking.time_slot)
            if booking.date == clinic_today and slot_start <= clinic_now.replace(tzinfo=None):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A past or already-started slot cannot be booked",
                )

            weekday = (
                Weekday.MONDAY,
                Weekday.TUESDAY,
                Weekday.WEDNESDAY,
                Weekday.THURSDAY,
                Weekday.FRIDAY,
                Weekday.SATURDAY,
                Weekday.SUNDAY,
            )[booking.date.weekday()]
            availability_rows = (await session.execute(
                select(DoctorAvailability).where(
                    DoctorAvailability.doctor_id == doctor_profile.id,
                    DoctorAvailability.weekday == weekday,
                )
            )).scalars().all()

            slot_duration_seconds = slot_duration.total_seconds()
            is_scheduled_slot = any(
                (interval_start := datetime.combine(booking.date, interval.start_time))
                <= slot_start
                and slot_start + slot_duration
                <= datetime.combine(booking.date, interval.end_time)
                and (slot_start - interval_start).total_seconds()
                % slot_duration_seconds == 0
                for interval in availability_rows
            )
            if not is_scheduled_slot:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Selected time is not an available slot in the doctor's schedule",
                )

            existing_appointment = (await session.execute(
                select(Appointment).where(
                    Appointment.doctor_id == doctor_profile.id,
                    Appointment.date == booking.date,
                    Appointment.time_slot == booking.time_slot,
                    Appointment.status.in_(
                        (AppointmentStatus.BOOKED, AppointmentStatus.COMPLETED)
                    ),
                )
            )).scalar_one_or_none()
            if existing_appointment is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Selected slot has already been booked",
                )

            patient_access_token = secrets.token_urlsafe(32)
            patient_access_token_hash = hashlib.sha256(
                patient_access_token.encode("utf-8")
            ).hexdigest()
            patient_contact = PatientContact.model_validate(booking.patient)
            session.add(patient_contact)
            await session.flush()

            appointment = Appointment(
                doctor_id=doctor_profile.id,
                patient_contact_id=patient_contact.id,
                date=booking.date,
                time_slot=booking.time_slot,
                consultation_type=booking.consultation_type,
                status=AppointmentStatus.BOOKED,
                patient_access_token_hash=patient_access_token_hash,
            )
            session.add(appointment)
            await session.commit()

            return AppointmentBookingResponse(
                appointment_id=appointment.id,
                doctor_id=doctor_profile.id,
                date=appointment.date,
                start_time=appointment.time_slot,
                end_time=(slot_start + slot_duration).time(),
                status=appointment.status,
                patient_access_token=patient_access_token,
            )
        except HTTPException:
            await session.rollback()
            raise
        except IntegrityError as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Selected slot is no longer available",
            ) from error
        except Exception as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while creating the appointment",
            ) from error

    async def get_public_doctor_schedule(
        self,
        doctor_id: UUID,
        from_date: DateType | None,
        session: AsyncSession,
    ) -> DoctorScheduleResponse:
        try:
            doctor_profile = (await session.execute(
                select(DoctorProfile).where(DoctorProfile.id == doctor_id)
            )).scalar_one_or_none()
            if doctor_profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor profile not found",
                )

            try:
                clinic_timezone = ZoneInfo(doctor_profile.timezone)
            except ZoneInfoNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile has an invalid timezone",
                ) from error
            clinic_today = datetime.now(clinic_timezone).date()
            schedule_start = from_date or clinic_today
            if schedule_start < clinic_today:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Schedule cannot start before today in the doctor's timezone",
                )

            slot_duration_minutes = doctor_profile.slot_duration_minutes
            if slot_duration_minutes <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile has an invalid slot duration",
                )

            schedule_end = schedule_start + timedelta(days=6)
            availability_rows = (await session.execute(
                select(DoctorAvailability).where(
                    DoctorAvailability.doctor_id == doctor_profile.id
                )
            )).scalars().all()
            appointments = (await session.execute(
                select(Appointment).where(
                    Appointment.doctor_id == doctor_profile.id,
                    Appointment.date >= schedule_start,
                    Appointment.date <= schedule_end,
                    Appointment.status.in_(
                        (AppointmentStatus.BOOKED, AppointmentStatus.COMPLETED)
                    ),
                )
            )).scalars().all()

            availability_by_weekday: dict[Weekday, list[DoctorAvailability]] = {}
            for interval in availability_rows:
                availability_by_weekday.setdefault(interval.weekday, []).append(interval)

            appointment_status_by_slot = {
                (appointment.date, appointment.time_slot): PublicSlotStatus(
                    appointment.status.value
                )
                for appointment in appointments
            }

            weekdays = (
                Weekday.MONDAY,
                Weekday.TUESDAY,
                Weekday.WEDNESDAY,
                Weekday.THURSDAY,
                Weekday.FRIDAY,
                Weekday.SATURDAY,
                Weekday.SUNDAY,
            )
            days: list[DoctorScheduleDay] = []
            slot_duration = timedelta(minutes=slot_duration_minutes)
            for day_offset in range(7):
                current_date = schedule_start + timedelta(days=day_offset)
                weekday = weekdays[current_date.weekday()]
                intervals = availability_by_weekday.get(weekday)
                if not intervals:
                    continue

                slots_by_start = {}
                for interval in intervals:
                    slot_start = datetime.combine(current_date, interval.start_time)
                    interval_end = datetime.combine(current_date, interval.end_time)
                    while slot_start + slot_duration <= interval_end:
                        slot_end = slot_start + slot_duration
                        start_time = slot_start.time()
                        slots_by_start[start_time] = DoctorScheduleSlot(
                            start_time=start_time,
                            end_time=slot_end.time(),
                            status=appointment_status_by_slot.get(
                                (current_date, start_time),
                                PublicSlotStatus.AVAILABLE,
                            ),
                        )
                        slot_start = slot_end

                days.append(
                    DoctorScheduleDay(
                        weekday=weekday,
                        date=current_date,
                        slots=sorted(
                            slots_by_start.values(),
                            key=lambda slot: slot.start_time,
                        ),
                    )
                )

            return DoctorScheduleResponse(
                doctor_id=doctor_profile.id,
                timezone=doctor_profile.timezone,
                days=days,
            )
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while building the doctor schedule",
            ) from error

    async def get_doctor_weekly_availability(
        self,
        user_id: UUID,
        session: AsyncSession,
    ) -> DoctorWeeklyScheduleResponse:
        try:
            doctor_profile = (await session.execute(
                select(DoctorProfile).where(DoctorProfile.user_id == user_id)
            )).scalar_one_or_none()
            if doctor_profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor profile not found",
                )

            availability_rows = (await session.execute(
                select(DoctorAvailability)
                .where(DoctorAvailability.doctor_id == doctor_profile.id)
                .order_by(DoctorAvailability.weekday, DoctorAvailability.start_time)
            )).scalars().all()

            intervals_by_weekday: dict[Weekday, list[AvailabilityIntervalIn]] = {}
            for row in availability_rows:
                intervals_by_weekday.setdefault(row.weekday, []).append(
                    AvailabilityIntervalIn(
                        start_time=row.start_time,
                        end_time=row.end_time,
                    )
                )

            days = [
                WeekdayScheduleIn(
                    weekday=weekday,
                    intervals=intervals_by_weekday[weekday],
                )
                for weekday in Weekday
                if weekday in intervals_by_weekday
            ]
            return DoctorWeeklyScheduleResponse(
                doctor_id=doctor_profile.id,
                timezone=doctor_profile.timezone,
                days=days,
            )
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while fetching doctor availability",
            ) from error

    async def replace_doctor_weekly_schedule(
        self,
        schedule: DoctorWeeklyScheduleIn,
        user_id: UUID,
        session: AsyncSession,
    ) -> DoctorWeeklyScheduleIn:
        try:
            doctor_profile = (await session.execute(
                select(DoctorProfile).where(DoctorProfile.user_id == user_id)
            )).scalar_one_or_none()
            if doctor_profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Doctor profile not found. Create a profile first.",
                )

            slot_duration_minutes = doctor_profile.slot_duration_minutes
            if slot_duration_minutes <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile has an invalid slot duration",
                )

            clinic_today = datetime.now(ZoneInfo(doctor_profile.timezone)).date()
            appointments = (await session.execute(
                select(Appointment).where(
                    Appointment.doctor_id == doctor_profile.id,
                    Appointment.status == AppointmentStatus.BOOKED,
                    Appointment.date >= clinic_today,
                )
            )).scalars().all()

            weekdays = (
                Weekday.MONDAY,
                Weekday.TUESDAY,
                Weekday.WEDNESDAY,
                Weekday.THURSDAY,
                Weekday.FRIDAY,
                Weekday.SATURDAY,
                Weekday.SUNDAY,
            )
            slot_duration_seconds = slot_duration_minutes * 60
            for appointment in appointments:
                weekday = weekdays[appointment.date.weekday()]
                weekday_schedule = next(
                    (day for day in schedule.days if day.weekday == weekday),
                    None,
                )
                if weekday_schedule is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Schedule change would remove a day with a booked appointment",
                    )

                appointment_start = (
                    appointment.time_slot.hour * 3600
                    + appointment.time_slot.minute * 60
                    + appointment.time_slot.second
                )
                appointment_is_covered = any(
                    (interval_start := interval.start_time.hour * 3600
                     + interval.start_time.minute * 60
                     + interval.start_time.second) <= appointment_start
                    and appointment_start + slot_duration_seconds
                    <= interval.end_time.hour * 3600
                    + interval.end_time.minute * 60
                    + interval.end_time.second
                    and (appointment_start - interval_start) % slot_duration_seconds == 0
                    for interval in weekday_schedule.intervals
                )
                if not appointment_is_covered:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Schedule change would invalidate a booked appointment",
                    )

            existing_intervals = (await session.execute(
                select(DoctorAvailability).where(
                    DoctorAvailability.doctor_id == doctor_profile.id
                )
            )).scalars().all()
            for interval in existing_intervals:
                await session.delete(interval)

            for day in schedule.days:
                for interval in day.intervals:
                    session.add(
                        DoctorAvailability(
                            doctor_id=doctor_profile.id,
                            weekday=day.weekday,
                            start_time=interval.start_time,
                            end_time=interval.end_time,
                        )
                    )

            await session.commit()
            return schedule
        except HTTPException:
            await session.rollback()
            raise
        except IntegrityError as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not save this doctor availability",
            ) from error
        except Exception as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while saving doctor availability",
            ) from error

    async def create_doctor_profile(
        self,
        profile: DocProfileIn,
        user_id: UUID,
        session: AsyncSession,
    ) -> DoctorProfile:
        try:
            existing_profile = (await session.execute(
                select(DoctorProfile).where(DoctorProfile.user_id == user_id)
            )).scalar_one_or_none()
            if existing_profile:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Doctor profile already exists",
                )

            doctor_profile = DoctorProfile.model_validate(
                profile,
                update={"user_id": user_id},
            )
            session.add(doctor_profile)
            await session.commit()
            await session.refresh(doctor_profile)
            return doctor_profile
        except HTTPException:
            await session.rollback()
            raise
        except IntegrityError as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A doctor profile already exists for this user",
            ) from error
        except Exception as error:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened while creating the doctor profile",
            ) from error
    
   
        
userInstace=UserCrud()        