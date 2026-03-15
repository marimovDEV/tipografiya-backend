"""
Warehouse Enhancement and Order Validation Views (PrintERP TZ Sections 4 & 6)
Phase 2 Implementation
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, F
from django.db import models
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


from api.models import MaterialBatch, Material, ProductTemplate, Order
from api.order_validation import OrderValidationService


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def block_batch(request, batch_id):
    """
    Block a material batch from use.
    
    POST /api/warehouse/batches/{batch_id}/block/
    {
        "reason": "Quality issue detected"
    }
    """
    try:
        batch = MaterialBatch.objects.get(id=batch_id)
    except MaterialBatch.DoesNotExist:
        return Response(
            {'error': 'Batch not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    reason = request.data.get('reason', 'No reason provided')
    batch.block(user=request.user, reason=reason)
    
    return Response({
        'message': 'Batch blocked successfully',
        'batch_number': batch.batch_number,
        'material': batch.material.name,
        'quality_status': batch.quality_status,
        'blocked_by': request.user.username,
        'blocked_at': batch.blocked_at,
        'reason': batch.block_reason
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unblock_batch(request, batch_id):
    """
    Unblock a material batch.
    
    POST /api/warehouse/batches/{batch_id}/unblock/
    """
    try:
        batch = MaterialBatch.objects.get(id=batch_id)
    except MaterialBatch.DoesNotExist:
        return Response(
            {'error': 'Batch not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if batch.quality_status != 'blocked':
        return Response(
            {'error': 'Batch is not blocked'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    batch.unblock()
    
    return Response({
        'message': 'Batch unblocked successfully',
        'batch_number': batch.batch_number,
        'material': batch.material.name,
        'quality_status': batch.quality_status
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def expiring_batches(request):
    """
    Get batches expiring soon.
    
    GET /api/warehouse/expiring-batches/?days=30
    """
    days = int(request.query_params.get('days', 30))
    threshold_date = timezone.now().date() + timedelta(days=days)
    
    batches = MaterialBatch.objects.filter(
        expiry_date__isnull=False,
        expiry_date__lte=threshold_date,
        expiry_date__gte=timezone.now().date(),
        is_active=True
    ).select_related('material', 'supplier').order_by('expiry_date')
    
    result = []
    for batch in batches:
        days_until_expiry = (batch.expiry_date - timezone.now().date()).days
        result.append({
            'id': str(batch.id),
            'batch_number': batch.batch_number,
            'material_name': batch.material.name,
            'material_category': batch.material.category,
            'current_quantity': float(batch.current_quantity),
            'unit': batch.material.unit,
            'expiry_date': batch.expiry_date.isoformat(),
            'days_until_expiry': days_until_expiry,
            'supplier': batch.supplier.name if batch.supplier else None,
            'quality_status': batch.quality_status,
            'urgency': 'critical' if days_until_expiry <= 7 else 'warning' if days_until_expiry <= 14 else 'notice'
        })
    
    return Response({
        'count': len(result),
        'threshold_days': days,
        'batches': result
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def low_stock_alerts(request):
    """
    Get materials with stock below minimum.
    
    GET /api/warehouse/low-stock-alerts/
    """
    from django.db.models import F as DjangoF
    
    materials = Material.objects.filter(
        current_stock__lt=DjangoF('min_stock')
    ).order_by('current_stock')
    
    result = []
    for material in materials:
        # Calculate usable stock (only OK batches)
        usable_stock = MaterialBatch.objects.filter(
            material=material,
            quality_status='ok',
            is_active=True
        ).aggregate(total=Sum('current_quantity'))['total'] or 0
        
        result.append({
            'id': str(material.id),
            'name': material.name,
            'category': material.category,
            'current_stock': float(material.current_stock),
            'usable_stock': float(usable_stock),
            'min_stock': float(material.min_stock),
            'shortage': float(material.min_stock - material.current_stock),
            'unit': material.unit,
            'urgency': 'critical' if material.current_stock == 0 else 'high' if material.current_stock < material.min_stock * Decimal('0.5') else 'medium'
        })
    
    return Response({
        'count': len(result),
        'materials': result
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_order_materials(request):
    """
    Validate material availability for an order before creation.
    
    POST /api/orders/validate-materials/
    {
        "product_template_id": "uuid",
        "width_cm": 20.0,
        "height_cm": 15.0,
        "quantity": 1000,
        "color_count": 4,
        "has_lacquer": true,
        "has_gluing": true
    }
    """
    is_valid, validation_result, error_message = OrderValidationService.validate_and_prepare_order(
        request.data
    )
    
    if error_message:
        return Response(
            {
                'is_valid': is_valid,
                'error': error_message,
                'details': validation_result
            },
            status=status.HTTP_400_BAD_REQUEST if not is_valid else status.HTTP_200_OK
        )
    
    return Response({
        'is_valid': is_valid,
        'validation': validation_result,
        'message': 'Order can be created' if is_valid else 'Material validation failed'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_compatible_materials(request):
    """
    Get materials compatible with a product template layer.
    
    GET /api/orders/compatible-materials/?template={uuid}&layer={number}
    """
    template_id = request.query_params.get('template')
    layer_number = request.query_params.get('layer')
    
    if not template_id or not layer_number:
        return Response(
            {'error': 'template and layer parameters are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        template = ProductTemplate.objects.get(id=template_id)
        layer_num = int(layer_number)
    except (ProductTemplate.DoesNotExist, ValueError):
        return Response(
            {'error': 'Invalid template or layer number'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    compatible = OrderValidationService.get_compatible_materials(
        product_template=template,
        layer_number=layer_num
    )
    
    return Response({
        'template': template.name,
        'layer_number': layer_num,
        'compatible_materials': compatible,
        'count': len(compatible)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_material_suggestions(request):
    """
    Get alternative material suggestions.
    
    GET /api/orders/material-suggestions/?material={uuid}&qty={quantity}
    """
    material_id = request.query_params.get('material')
    quantity = request.query_params.get('qty', 0)
    
    if not material_id:
        return Response(
            {'error': 'material parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        material = Material.objects.get(id=material_id)
        qty = float(quantity)
    except (Material.DoesNotExist, ValueError):
        return Response(
            {'error': 'Invalid material or quantity'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    from decimal import Decimal
    suggestions = OrderValidationService._suggest_alternatives(
        material_category=material.category,
        quantity_needed=Decimal(str(qty))
    )
    
    return Response({
        'original_material': {
            'id': str(material.id),
            'name': material.name,
            'category': material.category
        },
        'quantity_needed': qty,
        'suggestions': suggestions,
        'count': len(suggestions)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def warehouse_status_report(request):
    """
    Comprehensive warehouse status report.
    
    GET /api/warehouse/status-report/
    """
    from django.db import models
    from decimal import Decimal

    # Total materials
    total_materials = Material.objects.count()
    
    # Low stock count
    low_stock_count = Material.objects.filter(
        current_stock__lt=models.F('min_stock')
    ).count()
    
    # Expiring batches (next 30 days)
    threshold_date = timezone.now().date() + timedelta(days=30)
    expiring_count = MaterialBatch.objects.filter(
        expiry_date__isnull=False,
        expiry_date__lte=threshold_date,
        expiry_date__gte=timezone.now().date(),
        is_active=True
    ).count()
    
    # Blocked batches
    blocked_count = MaterialBatch.objects.filter(
        quality_status='blocked'
    ).count()
    
    # Quarantine batches
    quarantine_count = MaterialBatch.objects.filter(
        quality_status='quarantine'
    ).count()
    
    # Total batches
    total_batches = MaterialBatch.objects.filter(is_active=True).count()
    
    # Stock value has been removed as Materials don't track prices anymore
    
    return Response({
        'summary': {
            'total_materials': total_materials,
            'total_batches': total_batches,
            'low_stock_count': low_stock_count,
            'expiring_soon_count': expiring_count,
            'blocked_count': blocked_count,
            'quarantine_count': quarantine_count,
            'total_stock_value': 0
        },
        'alerts': {
            'critical': low_stock_count + blocked_count,
            'warning': expiring_count + quarantine_count
        },
        'generated_at': timezone.now().isoformat()
    })
