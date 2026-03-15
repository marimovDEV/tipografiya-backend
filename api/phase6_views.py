"""
Phase 6: Smart Automation API Views
Manual trigger endpoints and automation status.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone
from .automation import AutoAlertSystem, TelegramSmartTriggers, WorkflowAutomation
import asyncio


class RunAutomationChecksView(APIView):
    """Manually trigger all automation checks"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        # Admin only
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        
        # Run async tasks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(AutoAlertSystem.run_all_checks())
        loop.close()
        
        return Response({
            'status': 'completed',
            'results': results
        })


class DeadlineAlertsView(APIView):
    """Check and send deadline alerts"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(AutoAlertSystem.check_approaching_deadlines())
        loop.close()
        
        return Response(result)


class BottleneckAlertsView(APIView):
    """Check and send bottleneck alerts"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(AutoAlertSystem.check_bottlenecks())
        loop.close()
        
        return Response(result)


class TriggerWorkflowView(APIView):
    """Manually trigger workflow for an order"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, order_id):
        from .models import Order
        
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        action = request.data.get('action')
        
        if action == 'reserve_materials':
            result = WorkflowAutomation.auto_reserve_materials(order)
            return Response(result)
        
        elif action == 'create_accounting':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                WorkflowAutomation.auto_create_accounting_entry(order)
            )
            loop.close()
            return Response(result or {'error': 'Failed'})
        
        else:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)
