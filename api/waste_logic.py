import math
from decimal import Decimal

class WasteManagementService:
    """
    Advanced Waste Management Service for Engineering Engine.
    Calculates precise waste based on geometry and nesting, replacing static percentages.
    """
    
    DEFAULT_SHEET_WIDTH = 100.0 # cm (e.g. 70x100)
    DEFAULT_SHEET_HEIGHT = 70.0 # cm
    
    @staticmethod
    def calculate_layout_efficiency(item_width, item_height, sheet_width=None, sheet_height=None, gap=0.2):
        """
        Calculates how many items fit on a sheet and the resulting waste %.
        Tries both orientations (portrait/landscape).
        
        Args:
            item_width (float): Dimensions in cm
            item_height (float): Dimensions in cm
            sheet_width (float): Dimensions in cm
            sheet_height (float): Dimensions in cm
            gap (float): Inter-item gap in cm for cutting
            
        Returns:
            dict: {
                'items_per_sheet': int,
                'waste_percent': float,
                'best_orientation': str ('normal' or 'rotated'),
                'used_area_percent': float
            }
        """
        if not sheet_width: sheet_width = WasteManagementService.DEFAULT_SHEET_WIDTH
        if not sheet_height: sheet_height = WasteManagementService.DEFAULT_SHEET_HEIGHT
        
        # Add gaps to item dimensions
        eff_item_w = item_width + gap
        eff_item_h = item_height + gap
        
        # Option 1: Normal Orientation
        cols_normal = math.floor(sheet_width / eff_item_w)
        rows_normal = math.floor(sheet_height / eff_item_h)
        count_normal = cols_normal * rows_normal
        
        # Option 2: Rotated Orientation
        cols_rotated = math.floor(sheet_width / eff_item_h)
        rows_rotated = math.floor(sheet_height / eff_item_w)
        count_rotated = cols_rotated * rows_rotated
        
        # Determine best fit
        if count_rotated > count_normal:
            best_count = count_rotated
            orientation = 'rotated'
        else:
            best_count = count_normal
            orientation = 'normal'
            
        if best_count == 0:
             return {
                'items_per_sheet': 0,
                'waste_percent': 100.0,
                'best_orientation': 'none',
                'used_area_percent': 0.0
            }
            
        # Calculate areas
        sheet_area = sheet_width * sheet_height
        # Use original item dimensions for used area (without gap) to see true yield
        total_item_area = best_count * (item_width * item_height)
        
        used_area_percent = (total_item_area / sheet_area) * 100
        waste_percent = 100.0 - used_area_percent
        
        return {
            'items_per_sheet': best_count,
            'waste_percent': round(waste_percent, 2),
            'best_orientation': orientation,
            'used_area_percent': round(used_area_percent, 2)
        }

    @staticmethod
    def get_waste_factor(product_profile, material_type, dimensions):
        """
        Get waste factor based on profile logic or fall back to calculation.
        
        Args:
            product_profile (ParametricProductProfile): The engineering profile
            material_type (str): 'paper', 'ink', etc.
            dimensions (dict): {'width': float, 'height': float}
        """
        if material_type == 'paper':
            # Check if profile has specific waste overrides
            if product_profile and product_profile.waste_logic_config:
                config = product_profile.waste_logic_config
                if 'fixed_waste_percent' in config:
                    return float(config['fixed_waste_percent']) / 100.0
            
            # Perform calculation
            width = float(dimensions.get('width', 0))
            height = float(dimensions.get('height', 0))
            
            if width > 0 and height > 0:
                result = WasteManagementService.calculate_layout_efficiency(width, height)
                # Convert percent to factor (e.g. 15% -> 0.15)
                return result['waste_percent'] / 100.0
        
        # Default fallback (should be handled by caller if None)
        return None
