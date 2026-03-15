"""
Material Consumption Calculator Service
Implements precise material consumption calculations per PrintERP TZ Section 5
"""

from decimal import Decimal
from typing import Dict, Tuple
from django.db.models import Q
from api.models import MaterialNormative, ProductTemplate


class MaterialConsumptionCalculator:
    """
    Calculate material consumption for orders with precision.
    Implements formulas from PrintERP TZ Section 5.
    """
    
    @staticmethod
    def calculate_paper_consumption(
        width_cm: float,
        height_cm: float,
        quantity: int,
        waste_percent: float = 5.0
    ) -> Tuple[Decimal, Dict]:
        """
        Calculate paper consumption in m².
        
        Formula: (width * height * quantity) / 10000 * (1 + waste_percent/100)
        
        Args:
            width_cm: Paper width in centimeters
            height_cm: Paper height in centimeters
            quantity: Number of units
            waste_percent: Waste percentage (default: 5%)
            
        Returns:
            Tuple of (total_m2, breakdown_dict)
        """
        # Convert cm² to m²
        area_per_unit_cm2 = Decimal(str(width_cm)) * Decimal(str(height_cm))
        area_per_unit_m2 = area_per_unit_cm2 / Decimal('10000')
        
        # Calculate base consumption
        base_consumption_m2 = area_per_unit_m2 * Decimal(str(quantity))
        
        # Add waste
        waste_multiplier = Decimal('1') + (Decimal(str(waste_percent)) / Decimal('100'))
        total_consumption_m2 = base_consumption_m2 * waste_multiplier
        
        breakdown = {
            'width_cm': float(width_cm),
            'height_cm': float(height_cm),
            'area_per_unit_m2': float(area_per_unit_m2),
            'quantity': quantity,
            'base_consumption_m2': float(base_consumption_m2),
            'waste_percent': float(waste_percent),
            'waste_amount_m2': float(total_consumption_m2 - base_consumption_m2),
            'total_consumption_m2': float(total_consumption_m2),
        }
        
        return total_consumption_m2, breakdown
    
    @staticmethod
    def calculate_ink_consumption(
        color_count: int,
        quantity: int,
        product_template: ProductTemplate = None,
        default_per_color_g: float = 2.5
    ) -> Tuple[Decimal, Dict]:
        """
        Calculate ink consumption in grams based on color count.
        
        Uses normatives table if available, otherwise uses default rate.
        
        Args:
            color_count: Number of colors (1, 2, 4, 6, etc.)
            quantity: Number of units
            product_template: Product template for normative lookup
            default_per_color_g: Default grams per color per unit
            
        Returns:
            Tuple of (total_grams, breakdown_dict)
        """
        # Try to get normative from database
        consumption_per_unit = None
        waste_percent = Decimal('10.0')  # Default ink waste
        
        if product_template:
            normative = MaterialNormative.objects.filter(
                product_template=product_template,
                material_type='ink',
                color_count=color_count
            ).order_by('-effective_from').first()
            
            if normative:
                consumption_per_unit = normative.consumption_per_unit
                waste_percent = normative.waste_percent
        
        # Use default if no normative found
        if consumption_per_unit is None:
            consumption_per_unit = Decimal(str(default_per_color_g)) * Decimal(str(color_count))
        
        # Calculate base consumption
        base_consumption_g = consumption_per_unit * Decimal(str(quantity))
        
        # Add waste
        waste_multiplier = Decimal('1') + (waste_percent / Decimal('100'))
        total_consumption_g = base_consumption_g * waste_multiplier
        
        breakdown = {
            'color_count': color_count,
            'quantity': quantity,
            'consumption_per_unit_g': float(consumption_per_unit),
            'base_consumption_g': float(base_consumption_g),
            'waste_percent': float(waste_percent),
            'waste_amount_g': float(total_consumption_g - base_consumption_g),
            'total_consumption_g': float(total_consumption_g),
            'source': 'normative' if product_template else 'default'
        }
        
        return total_consumption_g, breakdown
    
    @staticmethod
    def calculate_lacquer_consumption(
        coverage_area_m2: float,
        quantity: int,
        lacquer_type: str = 'standard',
        product_template: ProductTemplate = None,
        default_ml_per_m2: float = 15.0
    ) -> Tuple[Decimal, Dict]:
        """
        Calculate lacquer consumption in milliliters.
        
        Based on coverage area and lacquer type.
        
        Args:
            coverage_area_m2: Area to be lacquered per unit (m²)
            quantity: Number of units
            lacquer_type: Type of lacquer (standard, UV, matte, glossy)
            product_template: Product template for normative lookup
            default_ml_per_m2: Default ml per m²
            
        Returns:
            Tuple of (total_ml, breakdown_dict)
        """
        # Try to get normative from database
        consumption_per_m2 = None
        waste_percent = Decimal('8.0')  # Default lacquer waste
        
        if product_template:
            normative = MaterialNormative.objects.filter(
                product_template=product_template,
                material_type='lacquer'
            ).order_by('-effective_from').first()
            
            if normative:
                consumption_per_m2 = normative.consumption_per_unit
                waste_percent = normative.waste_percent
        
        # Use default if no normative found
        if consumption_per_m2 is None:
            consumption_per_m2 = Decimal(str(default_ml_per_m2))
        
        # Calculate base consumption
        total_area_m2 = Decimal(str(coverage_area_m2)) * Decimal(str(quantity))
        base_consumption_ml = total_area_m2 * consumption_per_m2
        
        # Add waste
        waste_multiplier = Decimal('1') + (waste_percent / Decimal('100'))
        total_consumption_ml = base_consumption_ml * waste_multiplier
        
        breakdown = {
            'coverage_area_per_unit_m2': float(coverage_area_m2),
            'quantity': quantity,
            'total_area_m2': float(total_area_m2),
            'consumption_per_m2_ml': float(consumption_per_m2),
            'base_consumption_ml': float(base_consumption_ml),
            'waste_percent': float(waste_percent),
            'waste_amount_ml': float(total_consumption_ml - base_consumption_ml),
            'total_consumption_ml': float(total_consumption_ml),
            'total_consumption_L': float(total_consumption_ml / 1000),
            'lacquer_type': lacquer_type,
            'source': 'normative' if product_template else 'default'
        }
        
        return total_consumption_ml, breakdown
    
    @staticmethod
    def calculate_adhesive_consumption(
        gluing_length_cm: float,
        quantity: int,
        product_template: ProductTemplate = None,
        default_g_per_cm: float = 0.5
    ) -> Tuple[Decimal, Dict]:
        """
        Calculate adhesive/glue consumption in grams.
        
        Based on gluing length.
        
        Args:
            gluing_length_cm: Length of glue line per unit (cm)
            quantity: Number of units
            product_template: Product template for normative lookup
            default_g_per_cm: Default grams per cm
            
        Returns:
            Tuple of (total_grams, breakdown_dict)
        """
        # Try to get normative from database
        consumption_per_cm = None
        waste_percent = Decimal('10.0')  # Default adhesive waste
        
        if product_template:
            normative = MaterialNormative.objects.filter(
                product_template=product_template,
                material_type='adhesive'
            ).order_by('-effective_from').first()
            
            if normative:
                consumption_per_cm = normative.consumption_per_unit
                waste_percent = normative.waste_percent
        
        # Use default if no normative found
        if consumption_per_cm is None:
            consumption_per_cm = Decimal(str(default_g_per_cm))
        
        # Calculate base consumption
        total_length_cm = Decimal(str(gluing_length_cm)) * Decimal(str(quantity))
        base_consumption_g = total_length_cm * consumption_per_cm
        
        # Add waste
        waste_multiplier = Decimal('1') + (waste_percent / Decimal('100'))
        total_consumption_g = base_consumption_g * waste_multiplier
        
        breakdown = {
            'gluing_length_per_unit_cm': float(gluing_length_cm),
            'quantity': quantity,
            'total_length_cm': float(total_length_cm),
            'consumption_per_cm_g': float(consumption_per_cm),
            'base_consumption_g': float(base_consumption_g),
            'waste_percent': float(waste_percent),
            'waste_amount_g': float(total_consumption_g - base_consumption_g),
            'total_consumption_g': float(total_consumption_g),
            'source': 'normative' if product_template else 'default'
        }
        
        return total_consumption_g, breakdown
    
    @staticmethod
    def calculate_all_materials(
        product_template: ProductTemplate,
        width_cm: float,
        height_cm: float,
        quantity: int,
        color_count: int = 4,
        has_lacquer: bool = False,
        has_gluing: bool = False
    ) -> Dict:
        """
        Calculate all material consumption for an order.
        
        Args:
            product_template: Product template
            width_cm: Width in cm
            height_cm: Height in cm
            quantity: Quantity
            color_count: Number of colors for printing
            has_lacquer: Whether lacquering is needed
            has_gluing: Whether gluing is needed
            
        Returns:
            Dictionary with all material consumption breakdowns
        """
        results = {}
        
        # Paper
        paper_m2, paper_breakdown = MaterialConsumptionCalculator.calculate_paper_consumption(
            width_cm=width_cm,
            height_cm=height_cm,
            quantity=quantity,
            waste_percent=float(product_template.default_waste_percent)
        )
        results['paper'] = paper_breakdown
        
        # Ink
        if color_count > 0:
            ink_g, ink_breakdown = MaterialConsumptionCalculator.calculate_ink_consumption(
                color_count=color_count,
                quantity=quantity,
                product_template=product_template
            )
            results['ink'] = ink_breakdown
        
        # Lacquer
        if has_lacquer:
            # Coverage area is typically the full area
            coverage_area_m2 = (width_cm * height_cm) / 10000
            lacquer_ml, lacquer_breakdown = MaterialConsumptionCalculator.calculate_lacquer_consumption(
                coverage_area_m2=coverage_area_m2,
                quantity=quantity,
                product_template=product_template
            )
            results['lacquer'] = lacquer_breakdown
        
        # Adhesive
        if has_gluing:
            # Estimate gluing length (perimeter for box gluing)
            gluing_length_cm = (width_cm + height_cm) * 2
            adhesive_g, adhesive_breakdown = MaterialConsumptionCalculator.calculate_adhesive_consumption(
                gluing_length_cm=gluing_length_cm,
                quantity=quantity,
                product_template=product_template
            )
            results['adhesive'] = adhesive_breakdown
        
        return results
