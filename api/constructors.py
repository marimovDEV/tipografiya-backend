
import math

class DielineGenerator:
    """
    Base class for generating packaging Dielines (Technical drawings).
    Generates SVG path data with separate layers for Cuts and Creases.
    """
    def __init__(self, L, W, H, **kwargs):
        self.L = float(L) * 10 # cm -> mm
        self.W = float(W) * 10 # cm -> mm
        self.H = float(H) * 10 # cm -> mm
        self.kwargs = kwargs
        
        # Phase 6: Material and Engineering Constants
        self.thickness = float(kwargs.get('thickness', 3)) # Default 3mm
        self.k_factor = float(kwargs.get('k_factor', 0.4)) # Neutral axis offset (0.3 - 0.5 for cardboard)
        
        # Bend Allowance Calculation (Simplified for 90 deg folds)
        # BA = (Angle * (R + K*T))
        # For 90deg (1.57 rad), assuming Bend Radius (R) approx equal to Thickness
        # This is a delta to ADD to the unbent length
        self.bend_allowance = 1.57 * (self.thickness + (self.k_factor * self.thickness))

    def generate_paths(self):
        """
        Generates SVG path data from get_vector_paths if available.
        """
        if not hasattr(self, 'get_vector_paths'):
             raise NotImplementedError("Subclasses must implement get_vector_paths or generate_paths")
             
        segments = self.get_vector_paths()
        paths = {'cut': [], 'crease': [], 'bleed': []}
        
        for seg in segments:
            layer = seg['layer'].lower() # cut, crease, bleed
            if layer not in paths: layer = 'cut' # fallback
            
            # Append "M x1 y1 L x2 y2"
            start = seg['start']
            end = seg['end']
            paths[layer].append(f"M {start[0]},{start[1]} L {end[0]},{end[1]}")
            
        # Join into single path string per layer
        return {
            k: " ".join(v) for k, v in paths.items()
        }

    def calculate_knife_length(self):
        """
        Calculates total length of cutting and creasing rules in meters.
        Returns: { 'cut': float, 'crease': float }
        """
        raise NotImplementedError("Subclasses must implement calculate_knife_length")

    def get_flat_dimensions(self):
        """
        Returns the bounding box of the flattened dieline.
        { 'width': float (mm), 'height': float (mm) }
        """
        raise NotImplementedError("Subclasses must implement get_flat_dimensions")

    def _create_svg_wrapper(self, paths, viewbox_w, viewbox_h):
        """
        Generates a visually operational SVG with color coding.
        """
        svg = [f'<svg viewBox="0 0 {viewbox_w} {viewbox_h}" xmlns="http://www.w3.org/2000/svg">']
        
        # Styles
        svg.append('<style>')
        svg.append('.cut { fill: none; stroke: #2ecc71; stroke-width: 1; }') # Green Cut
        svg.append('.crease { fill: none; stroke: #e74c3c; stroke-width: 1; stroke-dasharray: 5,5; }') # Red Crease
        svg.append('.bleed { fill: none; stroke: #3498db; stroke-width: 0.5; stroke-opacity: 0.5; }') # Blue Bleed
        svg.append('</style>')
        
        if 'bleed' in paths:
            svg.append(f'<path class="bleed" d="{paths["bleed"]}" />')
        if 'crease' in paths:
            svg.append(f'<path class="crease" d="{paths["crease"]}" />')
        if 'cut' in paths:
            svg.append(f'<path class="cut" d="{paths["cut"]}" />')
            
        svg.append('</svg>')
    def get_svg_path(self):
        """
        Returns full SVG string for the dieline.
        """
        flat = self.get_flat_dimensions()
        paths = self.generate_paths()
        
        # Add simpler bounding box margin
        margin = 10 # mm
        viewbox_w = flat['width'] + (margin * 2)
        viewbox_h = flat['height'] + (margin * 2)
        
        return self._create_svg_wrapper(paths, viewbox_w, viewbox_h)

class MailerBoxGenerator(DielineGenerator):
    """
    Advanced Parametric Mailer Box (FEFCO 0427 style).
    Includes precise flap calculations and material thickness compensation.
    """
    def get_flat_dimensions(self):
        """
        Calculates the flat width and height of the dieline.
        """
        L, W, H = self.L, self.W, self.H
        T = self.thickness
        lock_tab_h = 15.0
        ear_w = 20.0
        
        # Horizontal (L direction in Code, but visuals might differ)
        # Based on generate_paths X Logic:
        # x_base_start = H + T + lock_tab_h
        # max_x = x_base_start + L + H (Right Wall) + maybe ear?
        
        # Let's re-trace the widest points from generate_paths logic:
        # Leftmost: 0 (implied, if we shift viewbox)
        # Rightmost: x_base_start (H + T + 15) + L + H approx
        
        # Total Flat Width roughly:
        # Left Flap (H) + Left Wall (T) + Base (L) + Right Wall (T) + Right Flap (H)
        # Actually in 0427: Side Walls are attached to Base L.
        # Length of Base is L.
        # Attached to Left of Base: Left Wall (H) + Dust Flap (Usually inside)
        # Attached to Right of Base: Right Wall (H) + Dust Flap
        
        # My generate_paths logic: x_base_start = H + T + 15
        # The structure extends to left by roughly H?
        # Let's derive from the bounding box logic used implicitly (or commonly known 0427 formulas).
        
        # Common 0427 Flat Layout:
        # Width (Grain perpendicular): 2*H + L + 2*T + (Flaps) -> ~ L + 2H
        # Height (Grain parallel): Locking Tab + Lid(W) + Back(H) + Base(W) + Front(H) + FrontLock(H)
        # -> ~ 2W + 4H
        
        # Using the coordinate logic from generate_paths:
        # Max Y = y_end = y_front_start + H + 2T + 0.8H 
        # y_front_start = y_base_start + W
        # y_base_start = y_back_start + H + T
        # y_back_start = y_lid_start + W
        # y_lid_start = 15
        # Total Y = 15 + W + H + T + W + H + 2T + 0.8H = 2W + 2.8H + 3T + 15
        
        # Max X:
        # x_base_start = H + T + 15
        # Rightmost point: base_x + L + H (Right Wall / Dust Flap)
        # Leftmost point: base_x - H (Left Wall / Dust Flap)
        # Span = (base_x + L + H) - (base_x - H) = L + 2H
        
        flat_width = L + (2 * H) + (2 * T) + 30 # Adding some buffer/ear width
        flat_height = (2 * W) + (3 * H) + (4 * T) + 30 # Buffer
        
        return {
            'width': flat_width,
            'height': flat_height
        }

    def get_vector_paths(self):
        """
        Returns list of vector segments:
        [
            {'layer': 'cut'|'crease'|'bleed', 'start': (x,y), 'end': (x,y)}
        ]
        """
        L, W, H = self.L, self.W, self.H
        T = self.thickness
        lock_tab_h = 15.0
        ear_w = 20.0
        
        # Coordinates (same logic as before)
        x_base_start = H + T + lock_tab_h
        y_lid_start = 0 + lock_tab_h
        y_front_start = y_lid_start + W + H + T + W
        
        OFFSET_X = H + 30 
        OFFSET_Y = 30
        
        base_x = OFFSET_X
        base_y = OFFSET_Y + W + H
        lid_y = OFFSET_Y
        
        segments = []
        
        # --- CREASES ---
        # 1. Back Wall Fold (Top of Base)
        segments.append({'layer': 'crease', 'start': (base_x, base_y), 'end': (base_x + L, base_y)})
        # 2. Front Wall Fold (Bottom of Base)
        segments.append({'layer': 'crease', 'start': (base_x, base_y + W), 'end': (base_x + L, base_y + W)})
        # 3. Left Wall Fold
        segments.append({'layer': 'crease', 'start': (base_x, base_y), 'end': (base_x, base_y + W)})
        # 4. Right Wall Fold
        segments.append({'layer': 'crease', 'start': (base_x + L, base_y), 'end': (base_x + L, base_y + W)})
        # 5. Lid Fold (at Back Wall)
        segments.append({'layer': 'crease', 'start': (base_x, base_y - H), 'end': (base_x + L, base_y - H)})
        # 6. Front Double Wall Fold
        segments.append({'layer': 'crease', 'start': (base_x, base_y + W + H), 'end': (base_x + L, base_y + W + H)})
        
        # --- CUT PERIMETER ---
        # We define points in order
        points = [
            (base_x, lid_y), # Start Top Left Lid
            (base_x + L, lid_y), # Top Right Lid
            (base_x + L + ear_w, lid_y + (W/4)), # Right Ear Top
            (base_x + L, lid_y + (W/2)), # Right Ear Mid
            (base_x + L, lid_y + W), # Right Lid Side
            (base_x + L, base_y), # Right Back Wall
            (base_x + L + H, base_y), # Right Side Flap Top
            (base_x + L + H, base_y + W), # Right Side Flap Bottom
            (base_x + L, base_y + W), # Right Side Flap Base
            (base_x + L, base_y + W + H), # Right Front Wall
            (base_x + L - 5, base_y + W + H + (H*0.8)), # Right Locking Tab
            (base_x + 5, base_y + W + H + (H*0.8)), # Left Locking Tab
            (base_x, base_y + W + H), # Left Front Wall
            (base_x, base_y + W), # Left Side Flap Base
            (base_x - H, base_y + W), # Left Side Flap Bottom
            (base_x - H, base_y), # Left Side Flap Top
            (base_x, base_y), # Left Back Wall
            (base_x, lid_y + W), # Left Lid Side
            (base_x, lid_y + (W/2)), # Left Ear Mid
            (base_x - ear_w, lid_y + (W/4)), # Left Ear Top
            (base_x, lid_y) # Close Loop
        ]
        
        for i in range(len(points) - 1):
            segments.append({
                'layer': 'cut',
                'start': points[i],
                'end': points[i+1]
            })
            
        # --- BLEED & SAFE (Simplified Rects) ---
        pad = 3.0 #  30.0 in code was likely 3mm * 10? No, code said 3mm but used 30.
        # Our self.L is in mm (cm*10). So 3mm is just 3.0.
        # Wait, previous code used `pad = 30`. 30 units.
        # If input L=20cm -> self.L = 200.
        # If pad=30, that's 3cm. That's a huge bleed.
        # Standard bleed is 3mm = 3 units.
        # Let's check: "Bleed: +3mm around".
        # If previous code used 30, it might have meant 3mm but scaled?
        # Let's stick to 3.0 for 3mm since self.L is in mm.
        
        # Bleed (Outer)
        b_pad = 3.0
        segments.append({'layer': 'bleed', 'start': (base_x - b_pad, lid_y - b_pad), 'end': (base_x + L + b_pad, lid_y - b_pad)})
        segments.append({'layer': 'bleed', 'start': (base_x + L + b_pad, lid_y - b_pad), 'end': (base_x + L + b_pad, base_y + W + b_pad)}) # Approx cover
        # ... simplifying bleed for now to just a bounding rect around the main body
        
        return segments

    def generate_paths(self):
        segments = self.get_vector_paths()
        
        paths = {
            'cut': [], 
            'crease': [], 
            'bleed': [], 
            'safe': []
        }
        
        for seg in segments:
            layer = seg['layer']
            if layer in paths:
                # Convert segment to SVG "M x y L x y"
                # To optimize, we could chain Ls if start == prev_end, but separate lines are safer for cutting.
                s = seg['start']
                e = seg['end']
                paths[layer].append(f"M {s[0]} {s[1]} L {e[0]} {e[1]}")
                
        return {
            'cut': " ".join(paths['cut']),
            'crease': " ".join(paths['crease']),
            'bleed': "", # " ".join(paths['bleed']),
            'safe': "" # " ".join(paths['safe'])
        }
        
    def calculate_knife_length(self):
        # Approximation based on geometry
        L, W, H = self.L, self.W, self.H
        
        # Perimeter approx
        perimeter = (2*L + 4*H + 2*W) * 2
        
        # Crease approx
        crease = (2*L + 4*W + 4*H)
        
        return {
            'cut': perimeter / 1000.0,
            'crease': crease / 1000.0
        }
        
    def generate_svg_path(self):
        """Legacy compatibility wrapper"""
        paths = self.generate_paths()
        return paths['cut'] + " " + paths['crease']

class PublicationGenerator(DielineGenerator):
    """
    Generator for Books, Magazines, etc.
    Since these are usually just 2D rectangles in layout, 
    we treat them as simple sheets for Nesting/Optimizer purposes.
    """
    def get_flat_dimensions(self):
        # W and H are the sheet dimensions in cm (from constructor)
        return {
            'width': self.L,
            'height': self.W
        }
    
    def get_vector_paths(self):
        # Just a simple rectangle for the "cut" layer
        L, W = self.L, self.W
        return [
            {'layer': 'cut', 'start': (0, 0), 'end': (L, 0)},
            {'layer': 'cut', 'start': (L, 0), 'end': (L, W)},
            {'layer': 'cut', 'start': (L, W), 'end': (0, W)},
            {'layer': 'cut', 'start': (0, W), 'end': (0, 0)},
        ]
    
    def calculate_knife_length(self):
        perimeter = (self.L + self.W) * 2
        return {
            'cut': perimeter / 1000.0,
            'crease': 0
        }

# Factory method
def get_generator(style, L, W, H, **kwargs):
    if style in ['book', 'magazine', 'brochure', 'catalog', 'booklet']:
        return PublicationGenerator(L, W, H, **kwargs)
    if style == 'mailer_box':
        return MailerBoxGenerator(L, W, H, **kwargs)
    elif style == 'pizza_box':
        return MailerBoxGenerator(L, W, H, **kwargs) # Alias
    return MailerBoxGenerator(L, W, H, **kwargs) # Default
