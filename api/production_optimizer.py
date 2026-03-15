
import math
from .models import ProductionStep, User, MachineSettings  # Assumed imports for logic

class LayoutOptimizer:
    """
    Optimizes the layout of product items on a printing sheet/material board.
    Calculates the maximum number of items that can fit and the resulting waste.
    """
    
    def __init__(self, item_width, item_height, sheet_w, sheet_h, gap=0.0):
        """
        :param item_width: Width of single item (cm)
        :param item_height: Height of single item (cm)
        :param sheet_width: Width of parent sheet (cm)
        :param sheet_height: Height of parent sheet (cm)
        :param gap: Required spacing between items (cm)
        """
        self.item_w = float(item_width) + float(gap)
        self.item_h = float(item_height) + float(gap)
        self.sheet_w = float(sheet_w)
        self.sheet_h = float(sheet_h)
        self.gap = float(gap)
        
        # Original dimensions without gap for validation
        self.orig_item_w = float(item_width)
        self.orig_item_h = float(item_height)

    def optimize(self, quantity=0):
        """
        Run optimization strategies.
        Returns dict with best layout metrics.
        """
        if self.item_w > self.sheet_w or self.item_h > self.sheet_h:
            # Check both dimensions against both sheet dimensions to be sure (rotation might fit)
            # Actually, rotation is checked in strategies.
            # But if item is larger than sheet in BOTH dimensions even after rotation...
            pass 

        # Strategy 1: Standard Orientation
        res_std = self._calculate_grid(self.item_w, self.item_h, quantity)
        
        # Strategy 2: Rotated Orientation
        # Swap Item W and H (Rotation 90 deg)
        res_rot = self._calculate_grid(self.item_h, self.item_w, quantity)
        
        # Compare and pick best
        # Criteria: Max Total Items per sheet
        best = res_std if res_std['total_items'] >= res_rot['total_items'] else res_rot
        best['rotated'] = (best == res_rot)
        
        return best

    def _calculate_grid(self, w, h, quantity=0):
        """
        Simple Grid Layout Calculation.
        w, h are effective item dimensions (including gap)
        """
        # Columns
        cols = math.floor(self.sheet_w / w)
        # Rows
        rows = math.floor(self.sheet_h / h)
        
        total = cols * rows
        
        # Calculate Used Area based on ORIGINAL dimensions (without gap) to represent material utility
        product_area_single = self.orig_item_w * self.orig_item_h
        product_area_per_sheet = product_area_single * total
        sheet_area = self.sheet_w * self.sheet_h
        
        # Per Sheet Waste
        waste_sq_cm = sheet_area - product_area_per_sheet
        waste_percent = (waste_sq_cm / sheet_area) * 100 if sheet_area > 0 else 0
        
        result = {
            'total_items': total,
            'cols': cols,
            'rows': rows,
            'waste_percent': round(waste_percent, 2),
            'sheet_w': self.sheet_w,
            'sheet_h': self.sheet_h,
            'item_w': self.orig_item_w,
            'item_h': self.orig_item_h
        }
        
        if quantity > 0 and total > 0:
            sheets_needed = math.ceil(quantity / total)
            total_sheet_area = sheet_area * sheets_needed
            total_product_area = product_area_single * quantity
            real_waste_area = total_sheet_area - total_product_area
            real_waste_percent = (real_waste_area / total_sheet_area) * 100 if total_sheet_area > 0 else 0
            
            result.update({
                'sheets_needed': sheets_needed,
                'real_waste_percent': round(real_waste_percent, 2),
                'total_waste_area_m2': round(real_waste_area / 10000, 4) # cm2 to m2
            })
            
        return result

    def _error_result(self, msg):
        return {
            'total_items': 0, 
            'error': msg, 
            'waste_percent': 100
        }

# --- Phase 4 Restoration ---

class BottleneckDetector:
    @staticmethod
    def detect_bottlenecks():
        # Mock implementation to satisfy import and basic logic
        # In real app, this would query ProductionSteps and analyze delays
        return []

class ParallelFlowManager:
    @staticmethod
    def suggest_parallel_steps(order):
        # Mock implementation returning a simple sequential plan
        return {
            'waves': [{
                'steps': ['Pre-press', 'Print', 'Cut'], 
                'estimated_duration': 5.0, 
                'can_run_parallel': False
            }]
        }

class SmartAssignmentEngine:
    @staticmethod
    def assign_optimal_worker(step):
        # Simple Logic: Assign to first available user with matching role or 'operator'
        # This requires database access, if it fails we return None
        try:
            # Try to find a user with role related to step if possible, or just any 'employee'
            worker = User.objects.filter(role__in=['operator', 'employee']).first()
            return worker
        except:
            return None

    @staticmethod
    def rebalance_workload():
        return {
            'workload_map': {},
            'rebalance_suggestions': []
        }

class MachineDowntimeTracker:
    pass # Empty placeholder
