from decimal import Decimal
import math

class NestingService:
    """
    Advanced Nesting/Imposition Algorithm for Print Production.
    Calculates the optimal layout of items on a sheet to minimize waste.
    """
    
    # Standard Paper Formats (cm)
    STANDARD_FORMATS = [
        {'name': '70x100', 'width': 70.0, 'height': 100.0, 'area': 7000.0},
        {'name': '62x94', 'width': 62.0, 'height': 94.0, 'area': 5828.0},
        {'name': '52x72', 'width': 52.0, 'height': 72.0, 'area': 3744.0},
        {'name': '47x65', 'width': 47.0, 'height': 65.0, 'area': 3055.0},
        {'name': 'Customize', 'width': 0, 'height': 0, 'area': 0} # Placeholder
    ]
    
    # Technical constraints
    GRIPPER_MARGIN = 1.5  # cm (Klapan)
    SIDE_MARGIN = 0.5     # cm
    CUT_GAP = 0.3         # cm (Knife gap between items)

    @staticmethod
    def calculate_best_layout(item_width: float, item_height: float, quantity: int, sheet_format: str = None):
        """
        Finds the best paper format and layout for a given item.
        
        Args:
            item_width (float): Width of the single item (box unfolded width)
            item_height (float): Height of the single item
            quantity (int): Total ordered quantity
            sheet_format (str, optional): Force specific format name (e.g. '70x100')
            
        Returns:
            dict: Best layout details including waste %, total sheets, etc.
        """
        
        candidates = []
        
        # 1. Determine which formats to check
        formats_to_check = NestingService.STANDARD_FORMATS
        if sheet_format:
            formats_to_check = [f for f in NestingService.STANDARD_FORMATS if f['name'] == sheet_format]
            
        # 2. Iterate through formats
        for paper in formats_to_check:
            if paper['name'] == 'Customize': continue
            
            # Use printable area (subtract margins)
            printable_w = paper['width'] - (NestingService.SIDE_MARGIN * 2)
            printable_h = paper['height'] - NestingService.GRIPPER_MARGIN - NestingService.SIDE_MARGIN
            
            # --- Strategy A: Normal Orientation ---
            layout_a = NestingService._calculate_single_layout(
                item_width, item_height, printable_w, printable_h, NestingService.CUT_GAP
            )
            
            # --- Strategy B: Rotated Orientation ---
            layout_b = NestingService._calculate_single_layout(
                item_height, item_width, printable_w, printable_h, NestingService.CUT_GAP
            )
            
            # --- Strategy C: Mixed/Combination (Simplified: Best of A or B for now) ---
            # Advanced bin packing algorithms would go here for complex mixed layouts.
            
            best_for_paper = layout_a if layout_a['count'] >= layout_b['count'] else layout_b
            
            if best_for_paper['count'] == 0:
                continue # Item too big for this paper
                
            # Calculate Waste
            items_on_sheet = best_for_paper['count']
            used_area = items_on_sheet * (item_width * item_height)
            waste_area = paper['area'] - used_area
            waste_percent = (waste_area / paper['area']) * 100
            
            # Calculate Production Requirements
            sheets_needed = math.ceil(quantity / items_on_sheet)
            
            candidates.append({
                'format': paper['name'],
                'sheet_width': paper['width'],
                'sheet_height': paper['height'],
                'items_per_sheet': items_on_sheet,
                'sheets_needed': sheets_needed,
                'waste_percent': round(waste_percent, 2),
                'orientation': 'Rotated' if best_for_paper == layout_b else 'Normal',
                'layout_columns': best_for_paper['cols'],
                'layout_rows': best_for_paper['rows'],
                'used_area_cm2': used_area,
                'total_paper_area_cm2': paper['area'],
                'efficiency_score': items_on_sheet / paper['area'] # Higher is better (items per cm2)
            })
            
        if not candidates:
            return {"error": "Item too large for any standard paper format"}
            
        # 3. Select Best Candidate
        # Strategy: Minimize Waste % (Primary) AND Minimize Total Sheets (Secondary)
        # Actually in printing, minimizing total cost is key. 
        # Usually minimizing waste % on the largest possible sheet is good, but depends on paper price.
        # Let's simple sort by Waste Percent ascending.
        
        candidates.sort(key=lambda x: x['waste_percent'])
        
        best_choice = candidates[0]
        
        return {
            "recommended_format": best_choice,
            "alternatives": candidates[1:4] # Return top 3 alternatives
        }

    @staticmethod
    def _calculate_single_layout(w, h, sheet_w, sheet_h, gap):
        """
        Helper to calculate how many items fit in a grid (cols x rows)
        """
        # Cols
        # item + gap + item + gap ...
        # N*w + (N-1)*gap <= sheet_w
        # N(w+gap) - gap <= sheet_w
        # N(w+gap) <= sheet_w + gap
        # N <= (sheet_w + gap) / (w + gap)
        
        cols = int((sheet_w + gap) / (w + gap))
        rows = int((sheet_h + gap) / (h + gap))
        
        return {
            'count': cols * rows,
            'cols': cols,
            'rows': rows
        }
