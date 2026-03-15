"""
Order Validation Service (PrintERP TZ Section 4)
Smart order creation with material validation and suggestions
"""

from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from django.db.models import Q, Sum
from django.utils import timezone

from api.models import (
    Order, ProductTemplate, ProductTemplateLayer, Material, MaterialBatch,
    Reservation
)
from api.material_consumption import MaterialConsumptionCalculator


class OrderValidationService:
    """
    Validates orders before creation/approval.
    Checks material availability and suggests alternatives.
    """
    
    @staticmethod
    def validate_material_availability(
        product_template: ProductTemplate,
        width_cm: float,
        height_cm: float,
        quantity: int,
        color_count: int = 4,
        has_lacquer: bool = False,
        has_gluing: bool = False
    ) -> Dict:
        """
        Validate if materials are available for an order.
        
        Returns:
            {
                'is_valid': bool,
                'missing_materials': [],
                'available_materials': [],
                'suggestions': {},
                'consumption': {}
            }
        """
        # Calculate required materials
        consumption = MaterialConsumptionCalculator.calculate_all_materials(
            product_template=product_template,
            width_cm=width_cm,
            height_cm=height_cm,
            quantity=quantity,
            color_count=color_count,
            has_lacquer=has_lacquer,
            has_gluing=has_gluing
        )
        
        missing_materials = []
        available_materials = []
        suggestions = {}
        
        # Check paper availability
        if 'paper' in consumption:
            paper_needed_m2 = Decimal(str(consumption['paper']['total_consumption_m2']))
            paper_check = OrderValidationService._check_material_stock(
                material_category='qogoz',
                quantity_needed=paper_needed_m2,
                unit='m2'
            )
            
            if paper_check['available']:
                available_materials.append({
                    'type': 'paper',
                    'needed': float(paper_needed_m2),
                    'available': paper_check['total_available'],
                    'unit': 'm²'
                })
            else:
                missing_materials.append({
                    'type': 'paper',
                    'needed': float(paper_needed_m2),
                    'available': paper_check['total_available'],
                    'shortage': float(paper_needed_m2 - Decimal(str(paper_check['total_available']))),
                    'unit': 'm²'
                })
                suggestions['paper'] = OrderValidationService._suggest_alternatives(
                    material_category='qogoz',
                    quantity_needed=paper_needed_m2
                )
        
        # Check ink availability
        if 'ink' in consumption:
            ink_needed_g = Decimal(str(consumption['ink']['total_consumption_g']))
            ink_check = OrderValidationService._check_material_stock(
                material_category='siyoh',
                quantity_needed=ink_needed_g,
                unit='g'
            )
            
            if ink_check['available']:
                available_materials.append({
                    'type': 'ink',
                    'needed': float(ink_needed_g),
                    'available': ink_check['total_available'],
                    'unit': 'g'
                })
            else:
                missing_materials.append({
                    'type': 'ink',
                    'needed': float(ink_needed_g),
                    'available': ink_check['total_available'],
                    'shortage': float(ink_needed_g - Decimal(str(ink_check['total_available']))),
                    'unit': 'g'
                })
                suggestions['ink'] = OrderValidationService._suggest_alternatives(
                    material_category='siyoh',
                    quantity_needed=ink_needed_g
                )
        
        # Check lacquer availability
        if 'lacquer' in consumption:
            lacquer_needed_ml = Decimal(str(consumption['lacquer']['total_consumption_ml']))
            lacquer_check = OrderValidationService._check_material_stock(
                material_category='lak',
                quantity_needed=lacquer_needed_ml,
                unit='ml'
            )
            
            if lacquer_check['available']:
                available_materials.append({
                    'type': 'lacquer',
                    'needed': float(lacquer_needed_ml),
                    'available': lacquer_check['total_available'],
                    'unit': 'ml'
                })
            else:
                missing_materials.append({
                    'type': 'lacquer',
                    'needed': float(lacquer_needed_ml),
                    'available': lacquer_check['total_available'],
                    'shortage': float(lacquer_needed_ml - Decimal(str(lacquer_check['total_available']))),
                    'unit': 'ml'
                })
        
        # Check adhesive availability
        if 'adhesive' in consumption:
            adhesive_needed_g = Decimal(str(consumption['adhesive']['total_consumption_g']))
            adhesive_check = OrderValidationService._check_material_stock(
                material_category='yelim',
                quantity_needed=adhesive_needed_g,
                unit='g'
            )
            
            if adhesive_check['available']:
                available_materials.append({
                    'type': 'adhesive',
                    'needed': float(adhesive_needed_g),
                    'available': adhesive_check['total_available'],
                    'unit': 'g'
                })
            else:
                missing_materials.append({
                    'type': 'adhesive',
                    'needed': float(adhesive_needed_g),
                    'available': adhesive_check['total_available'],
                    'shortage': float(adhesive_needed_g - Decimal(str(adhesive_check['total_available']))),
                    'unit': 'g'
                })
        
        is_valid = len(missing_materials) == 0
        
        return {
            'is_valid': is_valid,
            'missing_materials': missing_materials,
            'available_materials': available_materials,
            'suggestions': suggestions,
            'consumption': consumption,
            'message': 'All materials available' if is_valid else f'{len(missing_materials)} material(s) insufficient'
        }
    
    @staticmethod
    def _check_material_stock(
        material_category: str,
        quantity_needed: Decimal,
        unit: str
    ) -> Dict:
        """
        Check if sufficient stock exists for a material category.
        Only counts usable batches (quality_status='ok', is_active=True).
        """
        # Get all usable batches for this category
        batches = MaterialBatch.objects.filter(
            material__category__icontains=material_category,
            quality_status='ok',
            is_active=True,
            current_quantity__gt=0
        ).select_related('material')
        
        # Calculate total available (excluding reserved)
        total_available = Decimal('0')
        batch_details = []
        
        for batch in batches:
            # Get reserved quantity for this batch
            reserved = Reservation.objects.filter(
                material_batch=batch,
                consumed=False
            ).aggregate(total=Sum('reserved_qty'))['total'] or Decimal('0')
            
            available = batch.current_quantity - reserved
            if available > 0:
                total_available += available
                batch_details.append({
                    'batch_number': batch.batch_number,
                    'material_name': batch.material.name,
                    'available': float(available),
                    'unit': batch.material.unit
                })
        
        return {
            'available': total_available >= quantity_needed,
            'total_available': float(total_available),
            'quantity_needed': float(quantity_needed),
            'batches': batch_details
        }
    
    @staticmethod
    def _suggest_alternatives(
        material_category: str,
        quantity_needed: Decimal
    ) -> List[Dict]:
        """
        Suggest alternative materials from the same category.
        """
        # Find materials with sufficient stock
        alternatives = []
        
        materials = Material.objects.filter(
            category__icontains=material_category
        )
        
        for material in materials:
            # Check total available stock
            total_stock = MaterialBatch.objects.filter(
                material=material,
                quality_status='ok',
                is_active=True,
                current_quantity__gt=0
            ).aggregate(total=Sum('current_quantity'))['total'] or Decimal('0')
            
            if total_stock >= quantity_needed:
                alternatives.append({
                    'id': str(material.id),
                    'name': material.name,
                    'category': material.category,
                    'available_stock': float(total_stock),
                    'unit': material.unit
                })
        
        return alternatives
    
    @staticmethod
    def get_compatible_materials(
        product_template: ProductTemplate,
        layer_number: int
    ) -> List[Dict]:
        """
        Get materials compatible with a specific layer of a template.
        """
        try:
            layer = ProductTemplateLayer.objects.get(
                template=product_template,
                layer_number=layer_number
            )
        except ProductTemplateLayer.DoesNotExist:
            return []
        
        compatible = []
        for material in layer.compatible_materials.all():
            # Check stock availability
            total_stock = MaterialBatch.objects.filter(
                material=material,
                quality_status='ok',
                is_active=True,
                current_quantity__gt=0
            ).aggregate(total=Sum('current_quantity'))['total'] or Decimal('0')
            
            compatible.append({
                'id': str(material.id),
                'name': material.name,
                'category': material.category,
                'unit': material.unit,
                'current_stock': float(total_stock),
                'in_stock': total_stock > 0,
                'is_compatible': True
            })
        
        return compatible
    
    @staticmethod
    def validate_and_prepare_order(order_data: Dict) -> Tuple[bool, Dict, Optional[str]]:
        """
        Comprehensive validation before order creation.
        
        Returns:
            (is_valid, validation_result, error_message)
        """
        # Extract data
        template_id = order_data.get('product_template_id')
        width_cm = order_data.get('width_cm', 0)
        height_cm = order_data.get('height_cm', 0)
        quantity = order_data.get('quantity', 0)
        color_count = order_data.get('color_count', 0)
        has_lacquer = order_data.get('has_lacquer', False)
        has_gluing = order_data.get('has_gluing', False)
        
        # Validate template exists
        try:
            template = ProductTemplate.objects.get(id=template_id, is_active=True)
        except ProductTemplate.DoesNotExist:
            return False, {}, "Product template not found or inactive"
        
        # Validate dimensions
        if width_cm <= 0 or height_cm <= 0:
            return False, {}, "Width and height must be positive"
        
        if quantity <= 0:
            return False, {}, "Quantity must be positive"
        
        # Validate materials
        validation_result = OrderValidationService.validate_material_availability(
            product_template=template,
            width_cm=width_cm,
            height_cm=height_cm,
            quantity=quantity,
            color_count=color_count,
            has_lacquer=has_lacquer,
            has_gluing=has_gluing
        )
        
        if not validation_result['is_valid']:
            return False, validation_result, "Insufficient materials"
        
        return True, validation_result, None
