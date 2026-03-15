
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .production_optimizer import LayoutOptimizer

class OptimizationView(APIView):
    """
    API Endpoint to calculate optimal layout nesting.
    Query Params:
    - item_w, item_h: Item dimensions (cm)
    - sheet_w, sheet_h: Sheet dimensions (cm). Default 100x70.
    - gap: Spacing (cm). Default 0.2
    """
    def get(self, request):
        try:
            # Check if we have explicit item dimensions or Box Parameters
            item_w = float(request.query_params.get('item_w', 0))
            item_h = float(request.query_params.get('item_h', 0))
            
            # Box Params
            style = request.query_params.get('style', None)
            L = float(request.query_params.get('L', 0))
            W = float(request.query_params.get('W', 0))
            H = float(request.query_params.get('H', 0))
            
            calculated_dims = None

            if style and L > 0 and W > 0:
                # Calculate Flat Dimensions from Generator
                from .constructors import get_generator
                generator = get_generator(style, L, W, H)
                flat_dims = generator.get_flat_dimensions()
                
                # Convert mm to cm for Optimizer
                item_w = flat_dims['width'] / 10.0
                item_h = flat_dims['height'] / 10.0
                calculated_dims = {
                    'flat_w_mm': flat_dims['width'],
                    'flat_h_mm': flat_dims['height'],
                    'flat_w_cm': item_w,
                    'flat_h_cm': item_h
                }
                
                # Get Knife Stats for Machine Time
                if hasattr(generator, 'calculate_knife_length'):
                    knife_stats = generator.calculate_knife_length()
                    calculated_dims['knife_stats'] = knife_stats
            
            sheet_w = float(request.query_params.get('sheet_w', 100)) # Default 100cm
            sheet_h = float(request.query_params.get('sheet_h', 70))  # Default 70cm
            gap = float(request.query_params.get('gap', 0.2)) # 2mm gap
            quantity = int(request.query_params.get('quantity', 0))
            
            if item_w <= 0 or item_h <= 0:
                 return Response({'error': "Item dimensions must be > 0"}, status=status.HTTP_400_BAD_REQUEST)
            
            optimizer = LayoutOptimizer(item_w, item_h, sheet_w, sheet_h, gap)
            result = optimizer.optimize(quantity=quantity)
            
            # Add calculated info & Machine Time
            if calculated_dims:
                result['calculated_dimensions'] = calculated_dims
                
                # Machine Time Calculation
                # Constants (move to MachineSettings model later)
                CUT_SPEED_M_MIN = 50.0 
                CREASE_SPEED_M_MIN = 80.0
                SHEET_LOAD_TIME_MIN = 0.2
                SETUP_TIME_MIN = 15.0
                
                knife = calculated_dims.get('knife_stats', {'cut': 0, 'crease': 0})
                
                total_cut_m = knife['cut'] * quantity
                total_crease_m = knife['crease'] * quantity
                sheets_needed = result.get('sheets_needed', 0)
                
                cutting_time_min = total_cut_m / CUT_SPEED_M_MIN
                creasing_time_min = total_crease_m / CREASE_SPEED_M_MIN
                loading_time_min = sheets_needed * SHEET_LOAD_TIME_MIN
                
                total_time_min = SETUP_TIME_MIN + cutting_time_min + creasing_time_min + loading_time_min
                
                result['machine_analysis'] = {
                    'setup_min': SETUP_TIME_MIN,
                    'cutting_min': round(cutting_time_min, 1),
                    'creasing_min': round(creasing_time_min, 1),
                    'loading_min': round(loading_time_min, 1),
                    'total_time_min': round(total_time_min, 1),
                    'total_hours': round(total_time_min / 60, 2)
                }

                # Phase 8: Smart Deadline Prediction
                from .scheduling_service import SchedulingService
                
                # Estimate hours for each step type
                # Simple heuristic:
                # Printing: 2000 sheets/hr approx
                PRINT_SPEED = 2000
                GLUE_SPEED = 3000
                
                printing_hours = quantity / PRINT_SPEED
                cutting_hours = total_time_min / 60
                gluing_hours = quantity / GLUE_SPEED
                
                steps_estimate = {
                    'printing': printing_hours,
                    'cutting': cutting_hours,
                    'gluing': gluing_hours,
                    'packaging': 0.5 # flat 30 mins
                }
                
                predicted_date = SchedulingService.calculate_estimated_completion_date(steps_estimate)
                result['predicted_deadline'] = predicted_date.isoformat()
            
            # Phase 8: Inventory Check (Ombor Nazorati)
            material_type_code = request.query_params.get('material_type')
            if material_type_code:
                # Map frontend code to backend Material name/search
                # Should ideally use SKU or specific ID, but robust string matching works for MVP
                search_term = ""
                if material_type_code == 'craft':
                    search_term = "Kraft"
                elif material_type_code == 'white':
                    search_term = "Oq"
                elif material_type_code == 'glossy':
                    search_term = "Yaltiroq"
                
                if search_term:
                    from .models import MaterialBatch
                    from django.db.models import Sum
                    
                    total_stock = MaterialBatch.objects.filter(
                        material__name__icontains=search_term,
                        quality_status='ok',
                        is_active=True
                    ).aggregate(total=Sum('current_quantity'))['total'] or 0
                    
                    required_sheets = result.get('sheets_needed', 0)
                    
                    # Assume stock is in "sheets" for simplicity, or "kg"
                    # If unit mismatch, we need conversion. For this prompt, assume sheet count matching.
                    # Or assume stock is infinite if 0 to prevent blocking? No, user wants warnings.
                    
                    is_low_stock = float(total_stock) < float(required_sheets)
                    
                    result['inventory_analysis'] = {
                        'material_name': search_term,
                        'available_quantity': float(total_stock),
                        'required_quantity': required_sheets,
                        'is_low_stock': is_low_stock,
                        'message': "Omborda yetarli emas!" if is_low_stock else "Omborda mavjud"
                    }

            return Response({
                'success': True,
                'result': result,
            })
            
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DownloadDXFView(APIView):
    """
    Download DXF file for a given product config.
    """
    def get(self, request):
        try:
            from .constructors import PizzaBoxGenerator, ShoppingBagGenerator
            from .cut_file_export import CutFileService
            from django.http import HttpResponse

            style = request.query_params.get('style', 'pizza_box')
            L = float(request.query_params.get('L', 20))
            W = float(request.query_params.get('W', 20))
            H = float(request.query_params.get('H', 5))
            
            generator = None
            if style == 'pizza_box':
                generator = PizzaBoxGenerator(L, W, H)
            else:
                generator = ShoppingBagGenerator(L, W, H)
            
            # Generate DXF content
            dxf_content = CutFileService.generate_dieline_dxf(generator)
            
            response = HttpResponse(dxf_content, content_type='application/dxf')
            response['Content-Disposition'] = f'attachment; filename="{style}_{W}x{L}x{H}.dxf"'
            return response
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DielinePreviewView(APIView):
    """
    Returns visual SVG preview of the dieline.
    """
    def get(self, request):
        try:
            from .constructors import get_generator
            from .cut_file_export import CutFileService
            
            style = request.query_params.get('style', 'mailer_box')
            L = float(request.query_params.get('L', 20))
            W = float(request.query_params.get('W', 20))
            H = float(request.query_params.get('H', 5))
            
            generator = get_generator(style, L, W, H)
            
            # Generate SVG
            svg_content = CutFileService.generate_dieline_svg(generator)
            
            flat = generator.get_flat_dimensions()
            # Dimensions in pixels or units for viewBox? 
            # The SVG content from generator already has viewBox.
            # We just return the path content or full SVG.
            # Frontend expects { svg_path: ..., viewbox: ... }
            # Our generator returns full <svg ...> string.
            # We should probably strip the outer <svg> tag if we want to embed, or return full.
            # Frontend VisualCanvas uses dangerouslySetInnerHTML={{ __html: svgPath }}
            # So returning full SVG string is fine.
            
            # Extract viewBox for scaling if needed
            margin = 10
            viewBox = f"0 0 {flat['width'] + margin*2} {flat['height'] + margin*2}"
            
            return Response({
                'svg_path': svg_content,
                'viewbox': viewBox 
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
