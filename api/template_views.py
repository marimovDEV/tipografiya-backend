"""
API Views for Product Template System (PrintERP TZ Section 3)
Phase 7 Implementation
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Prefetch
from django.utils import timezone

from api.models import (
    ProductTemplate, ProductTemplateLayer, ProductTemplateRouting,
    MaterialNormative, WorkerTimeLog, Material, ProductionStep
)
from api.template_serializers import (
    ProductTemplateSerializer, ProductTemplateListSerializer,
    ProductTemplateLayerSerializer, ProductTemplateRoutingSerializer,
    MaterialNormativeSerializer, WorkerTimeLogSerializer
)
from api.material_consumption import MaterialConsumptionCalculator


class ProductTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Product Templates.
    Provides CRUD operations and custom actions.
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = ProductTemplate.objects.filter(is_deleted=False)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Prefetch related data for detail view
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                'layers__compatible_materials',
                'routing_steps',
                'normatives'
            )
        
        return queryset.order_by('category', 'name')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProductTemplateListSerializer
        return ProductTemplateSerializer
    
    @action(detail=True, methods=['get'])
    def compatible_materials(self, request, pk=None):
        """
        Get all compatible materials for a template.
        Groups by layer.
        """
        template = self.get_object()
        layers = template.layers.all().prefetch_related('compatible_materials')
        
        result = []
        for layer in layers:
            layer_data = {
                'layer_number': layer.layer_number,
                'material_category': layer.material_category,
                'min_density': layer.min_density,
                'max_density': layer.max_density,
                'materials': [
                    {
                        'id': str(mat.id),
                        'name': mat.name,
                        'category': mat.category,
                        'unit': mat.unit,
                        'current_stock': float(mat.current_stock),
                        'in_stock': mat.current_stock > 0
                    }
                    for mat in layer.compatible_materials.all()
                ]
            }
            result.append(layer_data)
        
        return Response(result)
    
    @action(detail=True, methods=['get'])
    def routing(self, request, pk=None):
        """
        Get production routing for a template.
        """
        template = self.get_object()
        routing_steps = template.routing_steps.all().order_by('sequence')
        serializer = ProductTemplateRoutingSerializer(routing_steps, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def calculate_materials(self, request, pk=None):
        """
        Calculate material consumption for given parameters.
        
        POST data:
        {
            "width_cm": 20.0,
            "height_cm": 15.0,
            "quantity": 1000,
            "color_count": 4,
            "has_lacquer": true,
            "has_gluing": true
        }
        """
        template = self.get_object()
        
        # Get parameters
        width_cm = float(request.data.get('width_cm', 0))
        height_cm = float(request.data.get('height_cm', 0))
        quantity = int(request.data.get('quantity', 0))
        color_count = int(request.data.get('color_count', 0))
        has_lacquer = request.data.get('has_lacquer', False)
        has_gluing = request.data.get('has_gluing', False)
        
        # Validate
        if width_cm <= 0 or height_cm <= 0 or quantity <= 0:
            return Response(
                {'error': 'Width, height, and quantity must be positive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate
        try:
            consumption = MaterialConsumptionCalculator.calculate_all_materials(
                product_template=template,
                width_cm=width_cm,
                height_cm=height_cm,
                quantity=quantity,
                color_count=color_count,
                has_lacquer=has_lacquer,
                has_gluing=has_gluing
            )
            
            return Response({
                'template': template.name,
                'parameters': {
                    'width_cm': width_cm,
                    'height_cm': height_cm,
                    'quantity': quantity,
                    'color_count': color_count,
                    'has_lacquer': has_lacquer,
                    'has_gluing': has_gluing
                },
                'consumption': consumption
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductTemplateLayerViewSet(viewsets.ModelViewSet):
    """ViewSet for Product Template Layers"""
    queryset = ProductTemplateLayer.objects.filter(is_deleted=False)
    serializer_class = ProductTemplateLayerSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by template
        template_id = self.request.query_params.get('template')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        
        return queryset.order_by('template', 'layer_number')


class ProductTemplateRoutingViewSet(viewsets.ModelViewSet):
    """ViewSet for Product Template Routing"""
    queryset = ProductTemplateRouting.objects.filter(is_deleted=False)
    serializer_class = ProductTemplateRoutingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by template
        template_id = self.request.query_params.get('template')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        
        return queryset.order_by('template', 'sequence')


class MaterialNormativeViewSet(viewsets.ModelViewSet):
    """ViewSet for Material Normatives"""
    queryset = MaterialNormative.objects.filter(is_deleted=False)
    serializer_class = MaterialNormativeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by template
        template_id = self.request.query_params.get('template')
        if template_id:
            queryset = queryset.filter(product_template_id=template_id)
        
        # Filter by material type
        material_type = self.request.query_params.get('material_type')
        if material_type:
            queryset = queryset.filter(material_type=material_type)
        
        # Only active normatives (effective_to is null or in future)
        active_only = self.request.query_params.get('active_only', 'false')
        if active_only.lower() == 'true':
            queryset = queryset.filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=timezone.now().date())
            )
        
        return queryset.order_by('product_template', 'material_type', 'color_count')


class WorkerTimeLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Worker Time Logs.
    Tracks START, PAUSE, RESUME, FINISH actions.
    """
    queryset = WorkerTimeLog.objects.filter(is_deleted=False)
    serializer_class = WorkerTimeLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by worker
        worker_id = self.request.query_params.get('worker')
        if worker_id:
            queryset = queryset.filter(worker_id=worker_id)
        elif self.request.query_params.get('my_logs', 'false').lower() == 'true':
            # Get logs for current user
            queryset = queryset.filter(worker=self.request.user)
        
        # Filter by production step
        step_id = self.request.query_params.get('production_step')
        if step_id:
            queryset = queryset.filter(production_step_id=step_id)
        
        # Filter by action
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        return queryset.order_by('-timestamp')
    
    @action(detail=False, methods=['post'])
    def log_action(self, request):
        """
        Log a worker action (START, PAUSE, RESUME, FINISH).
        
        POST data:
        {
            "production_step_id": "uuid",
            "action": "start",
            "pause_reason": "break",  // optional, for PAUSE action
            "notes": "...",  // optional
            "location": "Stanok #3"  // optional
        }
        """
        step_id = request.data.get('production_step_id')
        action = request.data.get('action')
        
        if not step_id or not action:
            return Response(
                {'error': 'production_step_id and action are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate production step exists
        try:
            production_step = ProductionStep.objects.get(id=step_id)
        except ProductionStep.DoesNotExist:
            return Response(
                {'error': 'Production step not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create log
        log = WorkerTimeLog.objects.create(
            production_step=production_step,
            worker=request.user,
            action=action,
            pause_reason=request.data.get('pause_reason'),
            notes=request.data.get('notes'),
            location=request.data.get('location')
        )
        
        # Update production step status based on action
        if action == 'start':
            production_step.status = 'in_progress'
            production_step.started_at = timezone.now()
            production_step.save()
        elif action == 'finish':
            production_step.status = 'completed'
            production_step.completed_at = timezone.now()
            production_step.save()
        
        serializer = self.get_serializer(log)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def calculate_duration(self, request):
        """
        Calculate work duration for a production step.
        Excludes pause time.
        
        Query params:
        - production_step_id: UUID of production step
        """
        step_id = request.query_params.get('production_step_id')
        if not step_id:
            return Response(
                {'error': 'production_step_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logs = WorkerTimeLog.objects.filter(
            production_step_id=step_id
        ).order_by('timestamp')
        
        if not logs.exists():
            return Response({
                'production_step_id': step_id,
                'total_duration_minutes': 0,
                'work_duration_minutes': 0,
                'pause_duration_minutes': 0,
                'logs_count': 0
            })
        
        # Calculate durations
        start_time = None
        pause_start = None
        total_work_seconds = 0
        total_pause_seconds = 0
        
        for log in logs:
            if log.action == 'start':
                start_time = log.timestamp
            elif log.action == 'pause' and start_time:
                pause_start = log.timestamp
            elif log.action == 'resume' and pause_start:
                pause_duration = (log.timestamp - pause_start).total_seconds()
                total_pause_seconds += pause_duration
                pause_start = None
            elif log.action == 'finish' and start_time:
                end_time = log.timestamp
                total_duration = (end_time - start_time).total_seconds()
                total_work_seconds = total_duration - total_pause_seconds
        
        return Response({
            'production_step_id': step_id,
            'total_duration_minutes': round(total_work_seconds / 60, 2),
            'work_duration_minutes': round((total_work_seconds - total_pause_seconds) / 60, 2),
            'pause_duration_minutes': round(total_pause_seconds / 60, 2),
            'logs_count': logs.count(),
            'start_time': logs.first().timestamp if logs.exists() else None,
            'end_time': logs.last().timestamp if logs.filter(action='finish').exists() else None
        })
