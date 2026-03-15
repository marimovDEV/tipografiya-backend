"""
Production Scheduling API Views (PrintERP TZ Section 7)
Phase 3 Implementation
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from api.models import ProductionStep, MachineSettings, Order
from api.production_scheduler import ProductionScheduler


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_machine_queue(request, machine_id=None):
    """
    Get production queue for a specific machine or all machines.
    
    GET /api/scheduling/machines/{machine_id}/queue/
    GET /api/scheduling/machines/queues/  (all machines)
    """
    if machine_id:
        try:
            machine = MachineSettings.objects.get(id=machine_id)
        except MachineSettings.DoesNotExist:
            return Response(
                {'error': 'Machine not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        queue = ProductionScheduler.get_machine_queue(machine)
        
        return Response({
            'machine_id': str(machine.id),
            'machine_name': machine.machine_name,
            'machine_type': machine.machine_type,
            'queue': queue,
            'total_steps': len(queue)
        })
    else:
        # Get all machine queues
        queues = ProductionScheduler.get_all_machine_queues()
        
        return Response({
            'machines': queues,
            'total_machines': len(queues)
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_step_to_machine(request):
    """
    Assign a production step to a machine.
    
    POST /api/scheduling/assign-to-machine/
    {
        "production_step_id": "uuid",
        "machine_id": "uuid",
        "calculate_times": true
    }
    """
    step_id = request.data.get('production_step_id')
    machine_id = request.data.get('machine_id')
    calculate_times = request.data.get('calculate_times', True)
    
    if not step_id or not machine_id:
        return Response(
            {'error': 'production_step_id and machine_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        step = ProductionStep.objects.get(id=step_id)
        machine = MachineSettings.objects.get(id=machine_id)
    except (ProductionStep.DoesNotExist, MachineSettings.DoesNotExist):
        return Response(
            {'error': 'Production step or machine not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Assign to machine
    updated_step = ProductionScheduler.assign_to_machine(
        production_step=step,
        machine=machine,
        calculate_times=calculate_times
    )
    
    return Response({
        'message': 'Step assigned to machine successfully',
        'production_step_id': str(updated_step.id),
        'machine_id': str(machine.id),
        'machine_name': machine.machine_name,
        'queue_position': updated_step.queue_position,
        'estimated_start': updated_step.estimated_start,
        'estimated_end': updated_step.estimated_end,
        'estimated_duration_minutes': updated_step.estimated_duration_minutes
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def optimize_machine_queue(request, machine_id):
    """
    Optimize the production queue for a machine.
    
    POST /api/scheduling/machines/{machine_id}/optimize/
    """
    try:
        machine = MachineSettings.objects.get(id=machine_id)
    except MachineSettings.DoesNotExist:
        return Response(
            {'error': 'Machine not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Optimize queue
    reordered_steps = ProductionScheduler.optimize_machine_queue(machine)
    
    # Build response
    queue = []
    for step in reordered_steps:
        queue.append({
            'id': str(step.id),
            'order_number': step.order.order_number,
            'step': step.get_step_display(),
            'queue_position': step.queue_position,
            'priority': step.priority,
            'estimated_start': step.estimated_start,
            'estimated_end': step.estimated_end
        })
    
    return Response({
        'message': f'Queue optimized for {machine.machine_name}',
        'machine_id': str(machine.id),
        'reordered_steps_count': len(queue),
        'queue': queue
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_step_times(request, step_id):
    """
    Calculate or recalculate estimated times for a production step.
    
    POST /api/scheduling/steps/{step_id}/calculate-times/
    {
        "force_recalculate": true
    }
    """
    try:
        step = ProductionStep.objects.get(id=step_id)
    except ProductionStep.DoesNotExist:
        return Response(
            {'error': 'Production step not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    force_recalculate = request.data.get('force_recalculate', False)
    
    # Calculate times
    result = ProductionScheduler.calculate_step_times(step, force_recalculate)
    
    return Response({
        'production_step_id': str(step.id),
        'order_number': step.order.order_number,
        'step': step.get_step_display(),
        **result
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def schedule_order_production(request, order_id):
    """
    Create and schedule production steps for an order.
    
    POST /api/scheduling/orders/{order_id}/schedule/
    """
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Order not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Schedule production
    steps = ProductionScheduler.schedule_order_production(order)
    
    # Build response
    step_list = []
    for step in steps:
        step_list.append({
            'id': str(step.id),
            'step': step.get_step_display(),
            'status': step.get_status_display(),
            'machine': step.machine.machine_name if step.machine else None,
            'estimated_start': step.estimated_start,
            'estimated_end': step.estimated_end,
            'estimated_duration_minutes': step.estimated_duration_minutes,
            'depends_on': str(step.depends_on_step.id) if step.depends_on_step else None
        })
    
    return Response({
        'message': f'Production scheduled for order {order.order_number}',
        'order_id': str(order.id),
        'order_number': order.order_number,
        'steps_created': len(steps),
        'steps': step_list
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_production_analytics(request):
    """
    Get overall production analytics and statistics.
    
    GET /api/scheduling/analytics/
    """
    analytics = ProductionScheduler.get_production_analytics()
    
    return Response(analytics)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_step_priority(request, step_id):
    """
    Update priority for a production step.
    
    POST /api/scheduling/steps/{step_id}/update-priority/
    {
        "priority": 1
    }
    """
    try:
        step = ProductionStep.objects.get(id=step_id)
    except ProductionStep.DoesNotExist:
        return Response(
            {'error': 'Production step not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    priority = request.data.get('priority')
    if priority is None:
        return Response(
            {'error': 'priority is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        priority = int(priority)
        if priority < 1 or priority > 10:
            raise ValueError
    except ValueError:
        return Response(
            {'error': 'priority must be an integer between 1 and 10'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    step.priority = priority
    step.save(update_fields=['priority'])
    
    # Re-optimize queue if step is assigned to a machine
    if step.machine:
        ProductionScheduler.optimize_machine_queue(step.machine)
    
    return Response({
        'message': 'Priority updated successfully',
        'production_step_id': str(step.id),
        'new_priority': priority,
        'queue_optimized': step.machine is not None
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_machine_availability(request, machine_id):
    """
    Get availability information for a machine.
    
    GET /api/scheduling/machines/{machine_id}/availability/
    """
    try:
        machine = MachineSettings.objects.get(id=machine_id)
    except MachineSettings.DoesNotExist:
        return Response(
            {'error': 'Machine not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    available_from = ProductionScheduler.get_machine_available_time(machine)
    
    # Check if available now
    now = timezone.now()
    is_available_now = available_from <= now
    
    # Calculate busy until
    if not is_available_now:
        busy_duration = (available_from - now).total_seconds() / 60  # minutes
    else:
        busy_duration = 0
    
    return Response({
        'machine_id': str(machine.id),
        'machine_name': machine.machine_name,
        'is_available_now': is_available_now,
        'available_from': available_from,
        'busy_duration_minutes': round(busy_duration, 2),
        'current_time': now
    })
