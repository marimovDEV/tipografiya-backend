"""
Production Scheduling Service (PrintERP TZ Section 7)
Phase 3 Implementation

Provides intelligent production scheduling with:
- Machine-specific queue management
- Dependency checking
- Realistic time calculations
- Queue optimization
"""

from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from django.db.models import Q, Count, Sum, F, Max
from django.utils import timezone

from api.models import (
    ProductionStep, Order, MachineSettings, EmployeeEfficiency,
    User, ProductTemplate, ProductTemplateRouting
)


class ProductionScheduler:
    """
    Intelligent production scheduling system.
    Manages machine queues, dependencies, and time calculations.
    """
    
    @staticmethod
    def calculate_step_times(
        production_step: ProductionStep,
        force_recalculate: bool = False
    ) -> Dict:
        """
        Calculate estimated start and end times for a production step.
        
        Args:
            production_step: The production step to calculate
            force_recalculate: Recalculate even if times already set
            
        Returns:
            Dictionary with estimated_start, estimated_end, duration_minutes
        """
        # Skip if already calculated (unless forced)
        if not force_recalculate and production_step.estimated_start:
            return {
                'estimated_start': production_step.estimated_start,
                'estimated_end': production_step.estimated_end,
                'estimated_duration_minutes': production_step.estimated_duration_minutes
            }
        
        # Calculate duration
        duration_minutes = production_step.calculate_estimated_time()
        if not duration_minutes:
            # Fallback to template routing if available
            if hasattr(production_step.order, 'product_template') and production_step.order.product_template:
                routing = ProductTemplateRouting.objects.filter(
                    template=production_step.order.product_template,
                    step_name=production_step.step
                ).first()
                
                if routing:
                    # Calculate based on template
                    duration_per_unit = float(routing.estimated_time_per_unit)
                    setup_time = routing.setup_time_minutes
                    quantity = production_step.order.quantity
                    duration_minutes = (duration_per_unit * quantity) + setup_time
            else:
                # Default fallback
                duration_minutes = 60  # 1 hour default
        
        # Determine start time
        now = timezone.now()
        
        # Check if depends on another step
        if production_step.depends_on_step:
            # Start after dependency completes
            if production_step.depends_on_step.estimated_end:
                estimated_start = production_step.depends_on_step.estimated_end
            elif production_step.depends_on_step.completed_at:
                estimated_start = production_step.depends_on_step.completed_at
            else:
                # Dependency not yet scheduled, use current time
                estimated_start = now
        else:
            # Check machine availability
            if production_step.machine:
                machine_available_from = ProductionScheduler.get_machine_available_time(
                    production_step.machine
                )
                estimated_start = max(now, machine_available_from)
            else:
                estimated_start = now
        
        # Calculate end time
        estimated_end = estimated_start + timedelta(minutes=duration_minutes)
        
        # Update the step
        production_step.estimated_start = estimated_start
        production_step.estimated_end = estimated_end
        production_step.estimated_duration_minutes = int(duration_minutes)
        production_step.save(update_fields=[
            'estimated_start', 'estimated_end', 'estimated_duration_minutes'
        ])
        
        return {
            'estimated_start': estimated_start,
            'estimated_end': estimated_end,
            'estimated_duration_minutes': int(duration_minutes)
        }
    
    @staticmethod
    def get_machine_available_time(machine: MachineSettings) -> datetime:
        """
        Get the earliest time a machine will be available.
        Looks at all pending and in-progress steps assigned to the machine.
        """
        # Get last estimated end time for this machine
        last_step = ProductionStep.objects.filter(
            machine=machine,
            status__in=['pending', 'in_progress'],
            estimated_end__isnull=False
        ).order_by('-estimated_end').first()
        
        if last_step:
            return last_step.estimated_end
        
        # Check if machine is currently in downtime
        from api.models import MachineDowntime
        active_downtime = MachineDowntime.objects.filter(
            machine=machine,
            is_active=True
        ).first()
        
        if active_downtime:
            # Estimate downtime will end in 2 hours if no end time
            if active_downtime.ended_at:
                return active_downtime.ended_at
            else:
                return timezone.now() + timedelta(hours=2)
        
        # Machine is available now
        return timezone.now()
    
    @staticmethod
    def get_machine_queue(
        machine: MachineSettings,
        include_completed: bool = False
    ) -> List[Dict]:
        """
        Get the production queue for a specific machine.
        
        Returns:
            List of production steps with order info, sorted by queue position/priority
        """
        queryset = ProductionStep.objects.filter(machine=machine)
        
        if not include_completed:
            queryset = queryset.exclude(status='completed')
        
        queryset = queryset.select_related(
            'order', 'order__client', 'assigned_to'
        ).order_by('queue_position', 'priority', 'estimated_start')
        
        queue = []
        for step in queryset:
            queue.append({
                'id': str(step.id),
                'order_number': step.order.order_number,
                'client_name': step.order.client.full_name,
                'step': step.get_step_display(),
                'status': step.get_status_display(),
                'priority': step.priority,
                'queue_position': step.queue_position,
                'assigned_to': step.assigned_to.username if step.assigned_to else None,
                'estimated_start': step.estimated_start,
                'estimated_end': step.estimated_end,
                'estimated_duration_minutes': step.estimated_duration_minutes,
                'is_ready': step.is_ready_to_start,
                'depends_on': str(step.depends_on_step.id) if step.depends_on_step else None
            })
        
        return queue
    
    @staticmethod
    def assign_to_machine(
        production_step: ProductionStep,
        machine: MachineSettings,
        calculate_times: bool = True
    ) -> ProductionStep:
        """
        Assign a production step to a machine.
        Optionally calculates scheduling times automatically.
        """
        production_step.machine = machine
        
        # Set queue position (add to end of queue)
        last_position = ProductionStep.objects.filter(
            machine=machine,
            status__in=['pending', 'in_progress']
        ).aggregate(max_pos=Max('queue_position'))['max_pos'] or 0
        
        production_step.queue_position = last_position + 1
        production_step.save()
        
        # Calculate times if requested
        if calculate_times:
            ProductionScheduler.calculate_step_times(production_step)
        
        return production_step
    
    @staticmethod
    def optimize_machine_queue(machine: MachineSettings) -> List[ProductionStep]:
        """
        Optimize the queue for a machine based on:
        1. Dependencies (can't start if dependency not done)
        2. Priority
        3. Deadline urgency
        
        Returns:
            List of reordered production steps
        """
        steps = ProductionStep.objects.filter(
            machine=machine,
            status='pending'
        ).select_related('order', 'depends_on_step').order_by('priority', 'order__deadline')
        
        # Separate into ready and blocked steps
        ready_steps = []
        blocked_steps = []
        
        for step in steps:
            if step.is_ready_to_start:
                ready_steps.append(step)
            else:
                blocked_steps.append(step)
        
        # Sort ready steps by priority then deadline
        ready_steps.sort(key=lambda s: (
            s.priority,
            s.order.deadline if s.order.deadline else timezone.now() + timedelta(days=365)
        ))
        
        # Reassign queue positions
        position = 1
        reordered = []
        
        for step in ready_steps:
            step.queue_position = position
            step.save(update_fields=['queue_position'])
            position += 1
            reordered.append(step)
        
        # Blocked steps go after ready ones
        for step in blocked_steps:
            step.queue_position = position
            step.save(update_fields=['queue_position'])
            position += 1
            reordered.append(step)
        
        # Recalculate times for all steps
        for step in reordered:
            ProductionScheduler.calculate_step_times(step, force_recalculate=True)
        
        return reordered
    
    @staticmethod
    def get_all_machine_queues() -> Dict:
        """
        Get queues for all active machines.
        
        Returns:
            Dictionary mapping machine_id to queue list
        """
        machines = MachineSettings.objects.filter(is_active=True)
        
        queues = {}
        for machine in machines:
            queues[str(machine.id)] = {
                'machine_name': machine.machine_name,
                'machine_type': machine.machine_type,
                'queue': ProductionScheduler.get_machine_queue(machine),
                'total_pending': ProductionStep.objects.filter(
                    machine=machine,
                    status='pending'
                ).count(),
                'total_in_progress': ProductionStep.objects.filter(
                    machine=machine,
                    status='in_progress'
                ).count()
            }
        
        return queues
    
    @staticmethod
    def schedule_order_production(order: Order) -> List[ProductionStep]:
        """
        Schedule all production steps for an order.
        Creates steps based on product template routing if available.
        
        Returns:
            List of created/updated production steps
        """
        steps = []
        
        # Check if order has product template
        if hasattr(order, 'product_template') and order.product_template:
            # Create steps from template routing
            routing_steps = ProductTemplateRouting.objects.filter(
                template=order.product_template
            ).order_by('sequence')
            
            previous_step = None
            
            for routing in routing_steps:
                # Skip optional steps if not needed
                if routing.is_optional:
                    # TODO: Add logic to determine if optional step is needed
                    pass
                
                # Create or get production step
                step, created = ProductionStep.objects.get_or_create(
                    order=order,
                    step=routing.step_name,
                    defaults={
                        'status': 'pending',
                        'depends_on_step': previous_step,
                        'priority': 5  # Default priority
                    }
                )
                
                # Try to assign to appropriate machine
                if routing.required_machine_type:
                    machine = MachineSettings.objects.filter(
                        machine_type__icontains=routing.required_machine_type,
                        is_active=True
                    ).first()
                    
                    if machine:
                        ProductionScheduler.assign_to_machine(step, machine)
                
                steps.append(step)
                previous_step = step
        else:
            # Create default production steps
            default_steps = ['cutting', 'printing', 'gluing', 'packaging']
            previous_step = None
            
            for step_name in default_steps:
                step, created = ProductionStep.objects.get_or_create(
                    order=order,
                    step=step_name,
                    defaults={
                        'status': 'pending',
                        'depends_on_step': previous_step
                    }
                )
                
                steps.append(step)
                previous_step = step
        
        return steps
    
    @staticmethod
    def get_production_analytics() -> Dict:
        """
        Get overall production analytics.
        """
        total_pending = ProductionStep.objects.filter(status='pending').count()
        total_in_progress = ProductionStep.objects.filter(status='in_progress').count()
        total_completed_today = ProductionStep.objects.filter(
            status='completed',
            completed_at__date=timezone.now().date()
        ).count()
        
        # Late steps (estimated_end in past but not completed)
        late_steps = ProductionStep.objects.filter(
            status__in=['pending', 'in_progress'],
            estimated_end__lt=timezone.now()
        ).count()
        
        # Average completion time
        completed_steps = ProductionStep.objects.filter(
            status='completed',
            actual_duration_minutes__isnull=False
        )
        
        avg_duration = completed_steps.aggregate(
            avg=Sum('actual_duration_minutes')
        )['avg'] or 0
        
        return {
            'total_pending': total_pending,
            'total_in_progress': total_in_progress,
            'total_completed_today': total_completed_today,
            'late_steps_count': late_steps,
            'average_duration_minutes': float(avg_duration) if avg_duration else 0,
            'timestamp': timezone.now()
        }
