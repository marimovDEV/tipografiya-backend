
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .constructors import get_generator
import traceback

class DielinePreviewView(APIView):
    """
    API Endpoint to generate SVG path for a given packaging style and dimensions.
    Returns structured data with Cut, Crease, and Safety zones.
    """
    def get(self, request):
        try:
            style = request.query_params.get('style', 'mailer_box')
            L = float(request.query_params.get('L', 0))
            W = float(request.query_params.get('W', 0))
            H = float(request.query_params.get('H', 0))
            thickness = float(request.query_params.get('thickness', 3))
            
            generator = get_generator(style, L, W, H, thickness=thickness)
            
            # Generate raw paths
            paths = generator.generate_paths()
            
            # wrapper SVG for simple <img> display
            # Viewbox needs to be dynamic based on dimensions
            # Max width approx: 2*L + 4*H + 2*W (flat layout) -> Multiplied by 10 for mm
            # Let's add some padding
            dim_x = (L + 2*H + W) * 1.5 * 10 
            dim_y = (2*W + 2*H + L) * 1.5 * 10
            
            viewbox_w = int(dim_x)
            viewbox_h = int(dim_y)
            
            svg_content = generator._create_svg_wrapper(paths, viewbox_w, viewbox_h)
            
            return Response({
                'success': True,
                'svg': svg_content, # Ready to render string
                'paths': paths, # Raw paths for Three.js extrusion
                'viewbox': f"0 0 {viewbox_w} {viewbox_h}",
                'style': style,
                'dimensions': {'L': L, 'W': W, 'H': H, 'thickness': thickness}
            })
            
        except ValueError:
            return Response({'error': "Invalid dimensions"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
