# backend/api/qc_views.py
"""
QC (Quality Control) Checkpoint API Views
Implements Pass/Fail workflow with defect tracking and rework triggering
"""

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta

from .models import QCCheckpoint, ProductionStep, Order, User
from .serializers import *  # Will create QCCheckpointSerializer


class QCCheckpointViewSet(viewsets.ModelViewSet):
    """CRUD operations for QC Checkpoints"""
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = QCCheckpoint.objects.filter(is_deleted=False).select_related(
            'production_step__order',
            'inspector'
        )
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by order
        order_id = self.request.query_params.get('order_id')
        if order_id:
            queryset = queryset.filter(production_step__order_id=order_id)
        
        # Filter by inspector
        inspector_id = self.request.query_params.get('inspector_id')
        if inspector_id:
            queryset = queryset.filter(inspector_id=inspector_id)
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def inspect(self, request, pk=None):
        """
        Perform inspection: Pass or Fail
        POST /api/qc/checkpoints/{id}/inspect/
        Body: {
            "result": "pass" | "fail",
            "failure_reason": "..." (if fail),
            "defect_type": "..." (if fail),
            "severity": "critical" | "major" | "minor" (if fail),
            "defect_count": 1 (if fail),
            "notes": "..."
        }
        """
        checkpoint = self.get_object()
        result = request.data.get('result')
        
        if result not in ['pass', 'fail']:
            return Response(
                {"error": "Result must be 'pass' or 'fail'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if result == 'pass':
            checkpoint.pass_inspection(
                inspector=request.user,
                notes=request.data.get('notes')
            )
            message = "Checkpoint passed"
        else:
            # Validate required fields for failure
            if not request.data.get('failure_reason'):
                return Response(
                    {"error": "failure_reason is required for fail result"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            checkpoint.fail_inspection(
                inspector=request.user,
                failure_reason=request.data.get('failure_reason'),
                defect_type=request.data.get('defect_type', 'other'),
                severity=request.data.get('severity', 'major'),
                notes=request.data.get('notes'),
                defect_count=request.data.get('defect_count', 1)
            )
            message = "Checkpoint failed"
            
            # Check if rework was triggered
            if checkpoint.rework_triggered:
                message += " and rework triggered"
        
        serializer = self.get_serializer(checkpoint)
        return Response({
            "message": message,
            "checkpoint": serializer.data,
            "rework_triggered": checkpoint.rework_triggered
        })
    
    @action(detail=True, methods=['post'])
    def trigger_rework(self, request, pk=None):
        """
        Manually trigger rework for a failed checkpoint
        POST /api/qc/checkpoints/{id}/trigger-rework/
        """
        checkpoint = self.get_object()
        
        if checkpoint.status != 'fail':
            return Response(
                {"error": "Can only trigger rework for failed checkpoints"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if checkpoint.rework_triggered:
            return Response(
                {"error": "Rework already triggered"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        checkpoint.trigger_rework()
        
        serializer = self.get_serializer(checkpoint)
        return Response({
            "message": "Rework triggered successfully",
            "checkpoint": serializer.data
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def qc_statistics(request):
    """
    Get QC statistics
    GET /api/qc/statistics/
    Query params:
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    - inspector_id: UUID
    """
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    inspector_id = request.GET.get('inspector_id')
    
    queryset = QCCheckpoint.objects.filter(is_deleted=False)
    
    if start_date:
        queryset = queryset.filter(created_at__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__lte=end_date)
    if inspector_id:
        queryset = queryset.filter(inspector_id=inspector_id)
    
    # Overall stats
    total = queryset.count()
    passed = queryset.filter(status='pass').count()
    failed = queryset.filter(status='fail').count()
    pending = queryset.filter(status='pending').count()
    
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    # By defect type
    defects_by_type = queryset.filter(status='fail').values('defect_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # By severity
    defects_by_severity = queryset.filter(status='fail').values('defect_severity').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # By checkpoint type
    by_checkpoint_type = queryset.values('checkpoint_type').annotate(
        total=Count('id'),
        passed=Count('id', filter=Q(status='pass')),
        failed=Count('id', filter=Q(status='fail'))
    )
    
    # Rework stats
    rework_count = queryset.filter(rework_triggered=True).count()
    
    return Response({
        "summary": {
            "total_checkpoints": total,
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "pass_rate": round(pass_rate, 2),
            "rework_triggered": rework_count
        },
        "defects_by_type": list(defects_by_type),
        "defects_by_severity": list(defects_by_severity),
        "by_checkpoint_type": list(by_checkpoint_type)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def defect_trends(request):
    """
    Get defect trends over time
    GET /api/qc/defect-trends/
    Query params:
    - days: number of days (default 30)
    """
    days = int(request.GET.get('days', 30))
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Daily defect counts
    checkpoints = QCCheckpoint.objects.filter(
        is_deleted=False,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    # Group by date
    daily_stats = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        day_checkpoints = checkpoints.filter(
            created_at__date=date.date()
        )
        
        total = day_checkpoints.count()
        failed = day_checkpoints.filter(status='fail').count()
        
        daily_stats.append({
            "date": date.date().isoformat(),
            "total": total,
            "failed": failed,
            "pass_rate": ((total - failed) / total * 100) if total > 0 else 0
        })
    
    return Response({
        "period": {
            "start": start_date.date().isoformat(),
            "end": end_date.date().isoformat(),
            "days": days
        },
        "daily_stats": daily_stats
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_inspections(request):
    """
    Get checkpoints for current QC inspector
    GET /api/qc/my-inspections/
    Query params:
    - status: pending | pass | fail
    """
    if request.user.role != 'qc':
        return Response(
            {"error": "Only QC inspectors can access this endpoint"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    status_filter = request.GET.get('status', 'pending')
    
    checkpoints = QCCheckpoint.objects.filter(
        is_deleted=False,
        inspector=request.user,
        status=status_filter
    ).select_related('production_step__order').order_by('-created_at')
    
    # Also show pending checkpoints assigned to current inspector
    if status_filter == 'pending':
        # Get checkpoints where step is assigned to this QC user
        pending_steps = ProductionStep.objects.filter(
            assigned_to=request.user,
            status='in_progress'
        )
        pending_checkpoints = QCCheckpoint.objects.filter(
            production_step__in=pending_steps,
            status='pending',
            is_deleted=False
        )
        checkpoints = checkpoints | pending_checkpoints
        checkpoints = checkpoints.distinct()
    
    # Serialize (will create serializer)
    data = []
    for cp in checkpoints[:50]:  # Limit to 50
        data.append({
            "id": str(cp.id),
            "checkpoint_name": cp.checkpoint_name,
            "checkpoint_type": cp.checkpoint_type,
            "order_number": cp.production_step.order.order_number,
            "status": cp.status,
            "created_at": cp.created_at.isoformat(),
            "inspected_at": cp.inspected_at.isoformat() if cp.inspected_at else None,
        })
    
    return Response({
        "count": len(data),
        "results": data
    })

class PreflightCheckView(APIView):
    """
    Auto-Preflight Service (Phase 3)
    Checks uploaded artwork for print-readiness.
    Capabilities (Basic): Size, Extension
    Capabilities (Advanced - Requires PIL): DPI, Color Mode
    """
    
    def post(self, request):
        if 'file' not in request.FILES:
             return Response({'error': "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        
        file_obj = request.FILES['file']
        
        # 1. Basic Checks
        name = file_obj.name.lower()
        size_mb = file_obj.size / (1024 * 1024)
        ext = name.split('.')[-1] if '.' in name else ''
        
        warnings = []
        errors = []
        
        # Extension Check
        ALLOWED_EXTS = ['pdf', 'ai', 'eps', 'tiff', 'tif', 'jpg', 'jpeg', 'png', 'psd']
        if ext not in ALLOWED_EXTS:
            errors.append(f"Untitled format '.{ext}'. Preferred: PDF, AI, TIFF")
            
        # Size Check
        if size_mb > 100:
            warnings.append(f"Large file ({size_mb:.1f}MB). Upload may take time.")
        
        # 2. Advanced Checks (Mock/Placeholder)
        # Without Pillow/Ghostscript, we cannot reliably check DPI or CMYK.
        
        specs = {
            'filename': file_obj.name,
            'size_mb': round(size_mb, 2),
            'extension': ext,
            'color_mode': 'Unknown (Lib Missing)',
            'dpi': 'Unknown (Lib Missing)'
        }
        
        # Simple Header sniff for basic mode guess (optional/risky without lib)
        # e.g. PDF header %PDF-1.x
        
        status_code = status.HTTP_200_OK
        if errors:
            status_code = status.HTTP_400_BAD_REQUEST
            
        return Response({
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'specs': specs
        }, status=status_code)
