"""
Calendar utilities for working days calculation and deadline management.
"""

from datetime import datetime, timedelta, date
from .models import Calendar, Shift


def populate_calendar_year(year):
    """
    Populate calendar for a given year with default working days (Mon-Fri).
    Uzbekistan public holidays should be added manually.
    """
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    
    current_date = start_date
    created_count = 0
    
    while current_date <= end_date:
        # Check if weekend (Saturday=5, Sunday=6)
        is_working = current_date.weekday() < 5
        
        Calendar.objects.get_or_create(
            date=current_date,
            defaults={
                'is_working_day': is_working,
                'shift_count': 1 if is_working else 0,
                'notes': 'Weekend' if not is_working else ''
            }
        )
        created_count += 1
        current_date += timedelta(days=1)
    
    return created_count


def add_holiday(date_obj, name):
    """Add a specific holiday to the calendar"""
    calendar_day, created = Calendar.objects.get_or_create(
        date=date_obj,
        defaults={
            'is_working_day': False,
            'shift_count': 0,
            'notes': name
        }
    )
    
    if not created:
        calendar_day.is_working_day = False
        calendar_day.shift_count = 0
        calendar_day.notes = name
        calendar_day.save()
    
    return calendar_day


def add_uzbekistan_holidays(year):
    """Add Uzbekistan public holidays for a given year"""
    holidays = [
        (date(year, 1, 1), "Yangi yil"),
        (date(year, 3, 8), "Xotin-qizlar kuni"),
        (date(year, 3, 21), "Navro'z"),
        (date(year, 5, 9), "Xotira va qadrlash kuni"),
        (date(year, 9, 1), "Mustaqillik kuni"),
        (date(year, 10, 1), "O'qituvchi va murabbiylar kuni"),
        (date(year, 12, 8), "Konstitutsiya kuni"),
        # Note: Ramadan and Eid dates vary by year - should be updated manually
    ]
    
    for holiday_date, holiday_name in holidays:
        add_holiday(holiday_date, holiday_name)
    
    return len(holidays)


def calculate_deadline(start_date, estimated_workdays, include_shifts=False):
    """
    Calculate deadline based on working days.
    
    Args:
        start_date: Starting date
        estimated_workdays: Number of working days needed
        include_shifts: If True, account for shift counts
    
    Returns:
        Deadline date
    """
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    
    if include_shifts:
        # More complex calculation with shift capacity
        return Calendar.add_working_days(start_date, estimated_workdays)
    else:
        # Simple working days addition
        return Calendar.add_working_days(start_date, estimated_workdays)


def get_production_capacity(start_date, end_date):
    """
    Calculate total production capacity between two dates.
    Takes into account working days and shifts.
    
    Returns:
        Total capacity hours
    """
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    # Get working days
    working_days = Calendar.objects.filter(
        date__gte=start_date,
        date__lte=end_date,
        is_working_day=True
    )
    
    # Get active shifts
    active_shifts = Shift.objects.filter(is_active=True)
    
    if not active_shifts.exists():
        # Default: 8 hours per working day
        return working_days.count() * 8
    
    # Calculate total capacity
    total_capacity = 0
    for day in working_days:
        for shift in active_shifts[:day.shift_count]:
            total_capacity += shift.duration_hours * float(shift.capacity_multiplier)
    
    return total_capacity
