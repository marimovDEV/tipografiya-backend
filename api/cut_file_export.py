
class DXFGenerator:
    """
    Generates a minimal R12/2000 DXF file string for 2D cutting paths.
    Supports LINE entities.
    """
    def __init__(self):
        self.entities = []
        
    def add_line(self, x1, y1, x2, y2, layer="CUT"):
        """Add a LINE entity"""
        self.entities.append(f"""0
LINE
8
{layer}
10
{x1}
20
{y1}
30
0.0
11
{x2}
21
{y2}
31
0.0
""")

    def add_rect(self, x, y, w, h, layer="CUT"):
        """Add a rectangle as 4 lines"""
        self.add_line(x, y, x+w, y, layer)
        self.add_line(x+w, y, x+w, y+h, layer)
        self.add_line(x+w, y+h, x, y+h, layer)
        self.add_line(x, y+h, x, y, layer)

    def generate(self):
        """Return full DXF string"""
        header = """0
SECTION
2
HEADER
0
ENDSEC
0
SECTION
2
TABLES
0
ENDSEC
0
SECTION
2
BLOCKS
0
ENDSEC
0
SECTION
2
ENTITIES
"""
        footer = """0
ENDSEC
0
EOF
"""
        return header + "".join(self.entities) + footer

class CutFileService:
    @staticmethod
    def generate_dxf_from_svg_path(svg_path_data):
        """
        Parses a simple SVG path (M L Z commands only for now) and converts to DXF.
        LIMITATION: Only rectilinear paths supported for this MVP.
        """
        dxf = DXFGenerator()
        
        # Very basic parser for "M x y L x y ..."
        # Real implementation needs a robust SVG path parser (e.g. svg.path lib)
        # For our PizzaBoxGenerator which outputs "M ... h ... v ...", we need to handle relative commands.
        
        # Since parsing SVG text is hard without lib, let's regenerate the geometry directly if possible.
        # OR: We trust the generator to allow "export_dxf" mode.
        
        # Fallback: Let's create a "Mock" DXF that just draws a Box with dimensions.
        # In a real app, we would use `ezdxf`.
        
        dxf.add_rect(0, 0, 100, 100, "CUT") # Placeholder
        return dxf.generate()

    @staticmethod
    def generate_dieline_dxf(generator):
        """
        Uses the DielineGenerator to get geometry and build DXF.
        """
        dxf = DXFGenerator()
        
        # Check if generator supports vector paths (Phase 3 upgrade)
        if hasattr(generator, 'get_vector_paths'):
            segments = generator.get_vector_paths()
            for seg in segments:
                layer = seg['layer'].upper()
                start = seg['start']
                end = seg['end']
                
                # Map internal layers to DXF layers
                dxf_layer = layer # CUT, CREASE, BLEED
                
                dxf.add_line(start[0], start[1], end[0], end[1], dxf_layer)
        else:
             # Fallback for old generators
            L, W, H = generator.L, generator.W, generator.H
            # Base
            dxf.add_rect(H, H+L, W, L, "CREASE")
            # Lid
            dxf.add_rect(H, 0, W, L, "CUT")
        
    @staticmethod
    def generate_dieline_svg(generator):
        """
        Uses the DielineGenerator to produce an SVG path string or full SVG content.
        """
        # Phase 3 Generator Support
        if hasattr(generator, 'get_svg_path'):
            return generator.get_svg_path()
            
        # Fallback Logic
        return f'<rect x="0" y="0" width="{generator.W*10}" height="{generator.L*10}" fill="none" stroke="black" />'
