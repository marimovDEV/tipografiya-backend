"""
Serializers for Product Template System (PrintERP TZ Section 3)
"""

from rest_framework import serializers
from api.models import (
    ProductTemplate, ProductTemplateLayer, ProductTemplateRouting,
    MaterialNormative, WorkerTimeLog, Material
)


class ProductTemplateLayerSerializer(serializers.ModelSerializer):
    """Serializer for product template layers"""
    compatible_materials = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Material.objects.all(),
        required=False
    )
    compatible_materials_detail = serializers.SerializerMethodField()
    effective_waste_percent = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductTemplateLayer
        fields = [
            'id', 'template', 'layer_number', 'material_category',
            'min_density', 'max_density', 'compatible_materials',
            'compatible_materials_detail', 'waste_percent_override',
            'effective_waste_percent', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_compatible_materials_detail(self, obj):
        """Get detailed info about compatible materials"""
        return [
            {
                'id': str(mat.id),
                'name': mat.name,
                'category': mat.category,
                'unit': mat.unit,
                'current_stock': float(mat.current_stock)
            }
            for mat in obj.compatible_materials.all()
        ]


class ProductTemplateRoutingSerializer(serializers.ModelSerializer):
    """Serializer for product template routing"""
    class Meta:
        model = ProductTemplateRouting
        fields = [
            'id', 'template', 'sequence', 'stage_name', 'step_name',
            'department', 'auto_start', 'requires_operator', 'machine',
            'estimated_time_minutes', 'estimated_time_per_unit', 'setup_time_minutes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'template', 'created_at', 'updated_at']


class MaterialNormativeSerializer(serializers.ModelSerializer):
    """Serializer for material normatives"""
    material_type_display = serializers.CharField(source='get_material_type_display', read_only=True)
    consumption_with_waste = serializers.ReadOnlyField()
    
    class Meta:
        model = MaterialNormative
        fields = [
            'id', 'product_template', 'material_type', 'material_type_display',
            'color_count', 'consumption_per_unit', 'unit_of_measure',
            'waste_percent', 'consumption_with_waste', 'effective_from',
            'effective_to', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductTemplateSerializer(serializers.ModelSerializer):
    """Serializer for product templates"""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    layers = ProductTemplateLayerSerializer(many=True, read_only=True)
    # Support both names for transition/compatibility
    stages = ProductTemplateRoutingSerializer(many=True, required=False, source='routing_steps')
    routing_steps = ProductTemplateRoutingSerializer(many=True, read_only=True)
    normatives = MaterialNormativeSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProductTemplate
        fields = [
            'id', 'name', 'category', 'category_display', 'layer_count',
            'default_waste_percent', 'description', 'is_active',
            'default_width', 'default_height', 'default_depth',
            'page_count', 'format', 'binding_type', 'paper_type',
            'paper_weight', 'cover_weight', 'print_type', 'lamination',
            'bleed_mm', 'margin_top_mm', 'margin_bottom_mm', 'margin_inner_mm',
            'margin_outer_mm', 'column_count', 'safe_area_padding_mm',
            'layers', 'routing_steps', 'stages', 'normatives',
            'created_at', 'updated_at', 'is_deleted'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_deleted']

    def create(self, validated_data):
        stages_data = validated_data.pop('routing_steps', [])
        template = ProductTemplate.objects.create(**validated_data)
        
        for stage_data in stages_data:
            ProductTemplateRouting.objects.create(template=template, **stage_data)
            
        return template

    def update(self, instance, validated_data):
        stages_data = validated_data.pop('routing_steps', None)
        
        # Update template fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update stages if provided
        if stages_data is not None:
            # Simple approach: delete and recreate (stable for few stages)
            instance.routing_steps.all().delete()
            for stage_data in stages_data:
                ProductTemplateRouting.objects.create(template=instance, **stage_data)
                
        return instance


class ProductTemplateListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing product templates"""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    layer_count_display = serializers.SerializerMethodField()
    routing_step_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductTemplate
        fields = [
            'id', 'name', 'category', 'category_display', 'layer_count',
            'layer_count_display', 'routing_step_count', 'default_waste_percent',
            'is_active', 'created_at', 'page_count', 'format'
        ]
    
    def get_layer_count_display(self, obj):
        return f"{obj.layer_count} qatlam"
    
    def get_routing_step_count(self, obj):
        return obj.routing_steps.count()


class WorkerTimeLogSerializer(serializers.ModelSerializer):
    """Serializer for worker time logs"""
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    pause_reason_display = serializers.CharField(source='get_pause_reason_display', read_only=True)
    worker_name = serializers.CharField(source='worker.username', read_only=True)
    order_number = serializers.CharField(source='production_step.order.order_number', read_only=True)
    
    class Meta:
        model = WorkerTimeLog
        fields = [
            'id', 'production_step', 'worker', 'worker_name', 'order_number',
            'action', 'action_display', 'timestamp', 'pause_reason',
            'pause_reason_display', 'notes', 'location',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'timestamp', 'created_at', 'updated_at']
