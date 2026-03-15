"""
Phase 4: Production Optimization API Views
Bottleneck detection, parallel flow analysis, machine downtime, and smart assignment.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, viewsets
from django.utils import timezone
from .models import ProductionStep, Order, MachineSettings, MachineDowntime, User
from .production_optimizer import (
    BottleneckDetector, ParallelFlowManager, 
    MachineDowntimeTracker, SmartAssignmentEngine
)


class BottleneckAnalysisView(APIView):
    """Detect production bottlenecks"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        bottlenecks = BottleneckDetector.detect_bottlenecks()
        
        return Response({
            'timestamp': timezone.now().isoformat(),
            'bottleneck_count': len(bottlenecks),
            'bottlenecks': bottlenecks,
            'overall_status': 'critical' if any(b['severity'] > 0.8 for b in bottlenecks) else 'warning' if bottlenecks else 'healthy'
        })


class ParallelFlowAnalysisView(APIView):
    """Analyze parallel production flow for an order"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        parallel_plan = ParallelFlowManager.suggest_parallel_steps(order)
        
        # Calculate time savings
        total_sequential_time = sum(wave['estimated_duration'] for wave in parallel_plan['waves'])
        total_parallel_time = sum(wave['estimated_duration'] for wave in parallel_plan['waves'] if not wave['can_run_parallel'])
        time_saved = total_sequential_time - total_parallel_time
        
        return Response({
            'order_number': order.order_number,
            'parallel_plan': parallel_plan,
            'time_savings': {
                'sequential_hours': round(total_sequential_time, 2),
                'parallel_hours': round(total_parallel_time, 2),
                'hours_saved': round(time_saved, 2),
                'efficiency_gain': round((time_saved / total_sequential_time * 100) if total_sequential_time > 0 else 0, 2)
            }
        })


class MachineDowntimeViewSet(viewsets.ModelViewSet):
    """Machine downtime tracking"""
    queryset = MachineDowntime.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        # Simple dict serializer for now
        return None
    
    def list(self, request):
        """List all downtimes with filtering"""
        downtimes = MachineDowntime.objects.select_related('machine', 'reported_by', 'resolved_by')
        
        # Filters
        is_active = request.query_params.get('is_active')
        machine_id = request.query_params.get('machine_id')
        
        if is_active is not None:
            downtimes = downtimes.filter(is_active=is_active.lower() == 'true')
        if machine_id:
            downtimes = downtimes.filter(machine_id=machine_id)
        
        data = []
        for dt in downtimes[:50]:  # Limit to 50
            data.append({
                'id': dt.id,
                'machine': dt.machine.machine_name,
                'machine_id': dt.machine.id,
                'reason': dt.get_reason_display(),
                'description': dt.description,
                'started_at': dt.started_at.isoformat(),
                'ended_at': dt.ended_at.isoformat() if dt.ended_at else None,
                'duration_hours': dt.duration_hours,
                'is_active': dt.is_active,
                'reported_by': dt.reported_by.username if dt.reported_by else None,
                'resolved_by': dt.resolved_by.username if dt.resolved_by else None
            })
        
        return Response({'downtimes': data, 'count': len(data)})
    
    def create(self, request):
        """Record new downtime"""
        machine_id = request.data.get('machine_id')
        reason = request.data.get('reason')
        description = request.data.get('description', '')
        estimated_hours = request.data.get('estimated_duration_hours')
        
        if not machine_id or not reason:
            return Response({'error': 'machine_id and reason required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            machine = MachineSettings.objects.get(id=machine_id)
        except MachineSettings.DoesNotExist:
            return Response({'error': 'Machine not found'}, status=status.HTTP_404_NOT_FOUND)
        
        downtime = MachineDowntime.objects.create(
            machine=machine,
            reason=reason,
            description=description,
            estimated_duration_hours=estimated_hours,
            reported_by=request.user,
            is_active=True
        )
        
        return Response({
            'id': downtime.id,
            'message': f'Downtime recorded for {machine.machine_name}',
            'started_at': downtime.started_at.isoformat()
        }, status=status.HTTP_201_CREATED)
    
    def partial_update(self, request, pk=None):
        """Resolve downtime"""
        try:
            downtime = MachineDowntime.objects.get(id=pk)
        except MachineDowntime.DoesNotExist:
            return Response({'error': 'Downtime not found'}, status=status.HTTP_404_NOT_FOUND)
        
        action = request.data.get('action')
        
        if action == 'resolve':
            downtime.resolve(request.user)
            return Response({
                'status': 'resolved',
                'duration_hours': downtime.duration_hours,
                'ended_at': downtime.ended_at.isoformat()
            })
        
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


class MachineAvailabilityView(APIView):
    """Get machine availability statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, machine_id=None):
        period_days = int(request.query_params.get('days', 7))
        
        if machine_id:
            try:
                machine = MachineSettings.objects.get(id=machine_id)
                machines = [machine]
            except MachineSettings.DoesNotExist:
                return Response({'error': 'Machine not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            machines = MachineSettings.objects.filter(is_active=True)
        
        availability_data = []
        
        for machine in machines:
            # Calculate downtime in period
            start_date = timezone.now() - timezone.timedelta(days=period_days)
            downtimes = MachineDowntime.objects.filter(
                machine=machine,
                started_at__gte=start_date
            )
            
            total_downtime = 0
            for dt in downtimes:
                if dt.ended_at:
                    duration = (dt.ended_at - dt.started_at).total_seconds() / 3600
                else:
                    duration = (timezone.now() - dt.started_at).total_seconds() / 3600
                total_downtime += duration
            
            total_hours = period_days * 24
            availability = ((total_hours - total_downtime) / total_hours) * 100
            
            availability_data.append({
                'machine_id': machine.id,
                'machine_name': machine.machine_name,
                'machine_type': machine.machine_type,
                'period_days': period_days,
                'total_hours': total_hours,
                'downtime_hours': round(total_downtime, 2),
                'productive_hours': round(total_hours - total_downtime, 2),
                'availability_percentage': round(availability, 2),
                'status': 'excellent' if availability > 95 else 'good' if availability > 85 else 'poor'
            })
        
        return Response({'machines': availability_data})


class SmartAssignmentView(APIView):
    """Smart worker assignment for production steps"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, step_id):
        """Auto-assign optimal worker to a step"""
        try:
            step = ProductionStep.objects.get(id=step_id)
        except ProductionStep.DoesNotExist:
            return Response({'error': 'Production step not found'}, status=status.HTTP_404_NOT_FOUND)
        
        optimal_worker = SmartAssignmentEngine.assign_optimal_worker(step)
        
        if optimal_worker:
            step.assigned_to = optimal_worker
            step.save()
            
            return Response({
                'status': 'assigned',
                'worker': {
                    'id': optimal_worker.id,
                    'username': optimal_worker.username,
                    'role': optimal_worker.role
                },
                'step': step.step,
                'order_number': step.order.order_number
            })
        else:
            return Response({
                'error': 'No suitable worker found'
            }, status=status.HTTP_404_NOT_FOUND)


class WorkloadRebalanceView(APIView):
    """Analyze and suggest workload rebalancing"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        rebalance_data = SmartAssignmentEngine.rebalance_workload()
        
        return Response({
            'timestamp': timezone.now().isoformat(),
            'workload_summary': rebalance_data['workload_map'],
            'rebalance_suggestions': rebalance_data['rebalance_suggestions'],
            'requires_action': len(rebalance_data['rebalance_suggestions']) > 0
        })
