"""
Phase 3: Business Logic API Views
Price locking, scenario pricing, and capacity management endpoints.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Order, PriceVersion, PricingSettings
from .pricing_logic import PriceLockService, ScenarioPricingService, CapacityAwareCalculator
from .serializers import OrderSerializer
import json


class PriceLockView(APIView):
    """Lock/unlock order prices"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, order_id):
        """Lock an order's price"""
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            result = PriceLockService.lock_order_price(order, request.user)
            if result:
                return Response({
                    'status': 'locked',
                    'message': f'Price locked for Order #{order.order_number}',
                    'version': order.price_lock_version
                })
            else:
                return Response({
                    'status': 'skipped',
                    'message': 'Price locking disabled globally'
                })
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, order_id):
        """Unlock an order's price (admin only)"""
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check admin permission
        if request.user.role not in ['admin', 'accountant']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        reason = request.data.get('reason')
        if not reason:
            return Response({'error': 'Reason required'}, status=status.HTTP_400_BAD_REQUEST)
        
        result = PriceLockService.unlock_order_price(order, request.user, reason)
        if result:
            return Response({'status': 'unlocked', 'message': 'Price unlocked'})
        else:
            return Response({'error': 'Price was not locked'}, status=status.HTTP_400_BAD_REQUEST)


class ManualOverrideView(APIView):
    """Manually override order price with audit trail"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        if request.user.role not in ['admin', 'accountant']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Check if can modify
        can_modify, error_msg = PriceLockService.can_modify_price(order)
        if not can_modify:
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
        
        new_price = request.data.get('new_price')
        reason = request.data.get('reason')
        
        if not new_price or not reason:
            return Response({'error': 'new_price and reason required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            updated_order = PriceLockService.manual_override_price(
                order, float(new_price), request.user, reason
            )
            return Response({
                'status': 'overridden',
                'old_price': float(order.total_price) if order.total_price else 0,
                'new_price': float(updated_order.total_price),
                'reason': reason
            })
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PriceHistoryView(APIView):
    """Get price change history for an order"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        history = PriceLockService.get_price_history(order)
        return Response({'order_number': order.order_number, 'history': history})


class ScenarioListView(APIView):
    """Get available pricing scenarios"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        scenarios = ScenarioPricingService.get_available_scenarios()
        return Response({'scenarios': scenarios})


class CapacityStatusView(APIView):
    """Get current production capacity status"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        capacity = CapacityAwareCalculator.get_capacity_status()
        
        # Add recommendation
        if capacity['status'] == 'high':
            capacity['recommendation'] = 'Consider expedited pricing for new orders'
        elif capacity['status'] == 'medium':
            capacity['recommendation'] = 'Normal capacity, standard delivery available'
        else:
            capacity['recommendation'] = 'Low capacity, offer discounts for extended delivery'
        
        return Response(capacity)


class PriceVersionListView(APIView):
    """Get all price versions"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        versions = PriceVersion.objects.all()[:20]  # Last 20 versions
        data = []
        for v in versions:
            data.append({
                'version_number': v.version_number,
                'effective_date': v.effective_date.isoformat(),
                'is_active': v.is_active,
                'created_by': v.created_by.username if v.created_by else None,
                'created_at': v.created_at.isoformat()
            })
        return Response({'versions': data})
