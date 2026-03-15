from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .pricing_logic import BasePriceCalculator
from .production_optimizer import LayoutOptimizer
from .constructors import get_generator

class PricingCalculationView(APIView):
    """
    API Endpoint for 'Scientific Pricing' Calculation.
    Accepts: Geometry params + Quantity
    Returns: Price Breakdown
    """
    def post(self, request):
        try:
            data = request.data
            
            # Helper for safe float conversion
            def safe_float(val, default=0.0):
                try:
                    if val is None or val == "": return default
                    return float(val)
                except (ValueError, TypeError):
                    return default

            def safe_int(val, default=0):
                try:
                    if val is None or val == "": return default
                    return int(float(val)) # Handle "100.0" as int
                except (ValueError, TypeError):
                    return default
            
            # 1. Extract inputs
            quantity = safe_int(data.get('quantity'), 100)
            if quantity <= 0: return Response({'error': "Quantity must be > 0"}, status=400)
            
            # Geometry Params
            style = data.get('style', 'mailer_box')
            L = safe_float(data.get('L'))
            W = safe_float(data.get('W'))
            H = safe_float(data.get('H'))
            
            if L <= 0 or W <= 0: return Response({'error': "Invalid dimensions (L and W must be > 0)"}, status=400)
            
            # 2. Re-run Optimization (to ensure security/accuracy)
            # (In a real app, we might cache this or pass the optimization result ID)
            generator = get_generator(style, L, W, H)
            flat_dims = generator.get_flat_dimensions()
            item_w = flat_dims['width'] / 10.0
            item_h = flat_dims['height'] / 10.0
            
            optimizer = LayoutOptimizer(
                item_w, item_h, 
                sheet_w=100, sheet_h=70, 
                gap=0.2
            )
            nesting_result = optimizer.optimize(quantity=quantity)
            
            # 3. Machine Time Analysis
            # Re-implement simplified logic here or extract to common service
            # Let's reuse the logic flow (ideally should be a service)
            # For now, we calculate locally to pass to calculator
            knife_stats = generator.calculate_knife_length()
            
            # Machine Settings (Defaults)
            CUT_SPEED = 50.0
            CREASE_SPEED = 80.0
            SETUP_MIN = 15.0
            
            total_cut_m = knife_stats['cut'] * quantity
            total_crease_m = knife_stats['crease'] * quantity
            sheets_needed = nesting_result.get('sheets_needed', 0)
            
            machine_min = SETUP_MIN + \
                          (total_cut_m / CUT_SPEED) + \
                          (total_crease_m / CREASE_SPEED) + \
                          (sheets_needed * 0.2)
                          
            machine_analysis = {
                'total_hours': machine_min / 60.0,
                'total_minutes': machine_min
            }
            
            # 4. Material Cost (Lookup)
            # In real DB, we look up "Cardboard 3mm" price
            MATERIAL_COST_SHEET = 1.50 # $1.50 per sheet default
            
            # 5. Calculate Price
            price_result = BasePriceCalculator.calculate_base_price(
                order_geometry=nesting_result,
                quantity=quantity,
                machine_analysis=machine_analysis,
                material_cost_per_sheet=MATERIAL_COST_SHEET
            )
            
            return Response({
                'success': True,
                'price': price_result,
                'nesting': nesting_result
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)
