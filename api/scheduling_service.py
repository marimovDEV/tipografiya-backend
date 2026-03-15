from django.utils import timezone
from django.db.models import Sum, Q
from .models import ProductionStep
import math
from datetime import timedelta

class SchedulingService:
    WORK_START_HOUR = 9
    WORK_END_HOUR = 18
    WORK_HOURS_PER_DAY = 9 # Including lunch? Let's say 9 hours 9-18. 
    
    @staticmethod
    def calculate_estimated_completion_date(new_order_steps_estimate):
        """
        Calculates when the order will be ready based on current queue.
        new_order_steps_estimate: dict { 'printing': 2.5, 'cutting': 0.5 ... } (hours)
        Returns: datetime
        """
        current_time = timezone.now()
        
        # We need to find the "critical path" or the latest finishing step.
        # Simple Logic: The order is ready when its LAST step is ready.
        # Usually: Printing -> Cutting -> Gluing -> Packaging.
        # We can simulate the pipeline.
        
        defined_sequence = ['printing', 'cutting', 'gluing', 'packaging']
        
        # Track when each machine becomes free
        machine_availability = {}
        
        for step_type in defined_sequence:
            # Get total pending hours for this machine
            pending_hours = ProductionStep.objects.filter(
                step=step_type,
                status__in=['pending', 'in_progress'],
                is_deleted=False
            ).aggregate(total=Sum('estimated_hours'))['total'] or 0
            
            # Machine is free after pending work is done
            # Convert pending hours to "business days" duration? 
            # For simplicity, let's add hours linearly first, then map to calendar.
            
            # Start time for this step for THIS order:
            # It can start only when:
            # 1. Previous step for THIS order is done.
            # 2. Machine is free (after clearing queue).
            
            # But wait, if we put it at the end of queue, it starts when machine is free.
            # So start_time = Now + Pending_Hours_On_Machine.
            
            # But it also waits for previous step of SAME order?
            # Yes. start_time = max(Now + Pending_Machine, Previous_Step_Finish_Time)
            
            # Let's populate machine_availability relative to NOW (in hours)
            machine_availability[step_type] = float(pending_hours)
            
        
        # Calculate flow for the new order
        current_order_time_cursor = 0 # Hours from now
        
        # If order doesn't have a step, skip it.
        # But we need order of steps.
        # Let's assume standard sequence if provided.
        
        final_finish_hours_from_now = 0
        
        active_steps = [s for s in defined_sequence if s in new_order_steps_estimate]
        if not active_steps:
            # Default to provided estimates sum if no sequence match (fallback)
            total_est = sum(new_order_steps_estimate.values())
            # For purely parallel/additive approximation
            final_finish_hours_from_now = total_est 
        else:
            previous_step_finish = 0
            for step in active_steps:
                duration = new_order_steps_estimate.get(step, 0)
                machine_queue = machine_availability.get(step, 0)
                
                # Start time is Max(Previous Step Done, Machine Free)
                # But Machine Free is calculated from Now.
                # So if Previous Step finishes at T=5, and Machine is free at T=2, we start at T=5.
                # If Previous Step finishes at T=1, and Machine free at T=10, we start at T=10.
                
                start_time = max(previous_step_finish, machine_queue)
                finish_time = start_time + duration
                
                # Update "Machine Queue" for subsequent orders? No, just valid for this simulation.
                # But wait, does this machine work on OUR order immediately after queue? Yes.
                
                previous_step_finish = finish_time
            
            final_finish_hours_from_now = previous_step_finish
            
        # Convert business hours to real datetime
        return SchedulingService.add_business_hours(current_time, final_finish_hours_from_now)

    @staticmethod
    def add_business_hours(start_date, hours_to_add):
        """
        Adds business hours to a date, skipping nights and weekends (if needed).
        """
        current = start_date
        remaining_minutes = hours_to_add * 60
        
        while remaining_minutes > 0:
            # Check if current time is within work hours
            # If before 9:00, jump to 9:00
            if current.hour < SchedulingService.WORK_START_HOUR:
                current = current.replace(hour=SchedulingService.WORK_START_HOUR, minute=0, second=0)
            
            # If after 18:00, jump to tomorrow 9:00
            if current.hour >= SchedulingService.WORK_END_HOUR:
                current = current + timedelta(days=1)
                current = current.replace(hour=SchedulingService.WORK_START_HOUR, minute=0, second=0)
                continue # Re-check morning logic
                
            # Time remaining today
            work_end_today = current.replace(hour=SchedulingService.WORK_END_HOUR, minute=0, second=0)
            minutes_available_today = (work_end_today - current).total_seconds() / 60
            
            if remaining_minutes <= minutes_available_today:
                current += timedelta(minutes=remaining_minutes)
                remaining_minutes = 0
            else:
                current += timedelta(minutes=minutes_available_today)
                remaining_minutes -= minutes_available_today
                # Now it's 18:00, loop will push to tomorrow
                
        return current
