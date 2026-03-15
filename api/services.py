import math
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from .models import PricingSettings, Material, MaterialBatch, ProductionStep, User
from .nesting_service import NestingService

# Material calculation constants
WASTE_PERCENT = 0.05  # 5% waste allowance for paper
INK_USAGE_PER_M2_PER_COLOR = 1.5  # grams of ink per m2 per color
LACQUER_USAGE_PER_M2 = 4.0  # grams of lacquer per m2
DEFAULT_SHEET_AREA_M2 = 0.125  # Default A3 sheet area if dimensions not provided
DEFAULT_PAPER_DENSITY = 300  # g/m2
DEFAULT_COLORS_COUNT = 4  # CMYK

class CalculationService:
    @staticmethod
    def get_average_material_price(material_name, category=None):
        """Returns 0 since material pricing has been removed from the system."""
        return 0.0

    @staticmethod
    def calculate_material_usage(data):
        """
        Calculates required materials based on order specs using dynamic waste settings.
        """
        quantity = int(data.get('quantity', 0))
        settings = PricingSettings.load()
        
        paper_width = float(data.get('paper_width') or 0)
        paper_height = float(data.get('paper_height') or 0)
        
        sheet_area_m2 = (paper_width * paper_height) / 10000.0 if (paper_width and paper_height) else DEFAULT_SHEET_AREA_M2
        if sheet_area_m2 == 0: 
            sheet_area_m2 = DEFAULT_SHEET_AREA_M2

        material_usage = {
            "paper_sheets": 0,
            "paper_kg": 0,
            "ink_kg": 0,
            "lacquer_kg": 0,
        }
        
        if quantity > 0:
            # Paper: 
            # Phase 1 Engineering Engine: Dynamic Waste Calculation
            waste_paper = float(settings.waste_percentage_paper) / 100.0
            setup_waste = int(settings.setup_waste_sheets)
            
            # Check for Parametric Profile logic
            # For now, we don't have the product instance easily available in this static method
            # In a real scenario, we would fetch Product -> Template -> Profile
            # Here we will try to use dimensions to calculate dynamic waste if provided
            
            if paper_width > 0 and paper_height > 0:
                try:
                    # Phase 2: Advanced Nesting Calculation
                    nesting_result = NestingService.calculate_best_layout(paper_width, paper_height, quantity)
                    
                    if "error" not in nesting_result:
                        best = nesting_result['recommended_format']
                        # Use Big Sheet calculations
                        # best keys: 'sheet_width', 'sheet_height', 'sheets_needed', 'waste_percent', 'items_per_sheet'
                        
                        big_sheet_area_m2 = (best['sheet_width'] * best['sheet_height']) / 10000.0
                        required_sheets = best['sheets_needed'] + setup_waste # Add setup waste to BIG sheets
                        
                        waste_paper = best['waste_percent'] / 100.0
                        
                        material_usage["paper_sheets"] = required_sheets
                        material_usage["waste_percent_used"] = best['waste_percent']
                        material_usage["layout_description"] = f"{best['format']} ishlatildi ({best['layout_columns']}x{best['layout_rows']} = {best['items_per_sheet']} dona)"
                        
                        density = int(data.get('paper_density') or DEFAULT_PAPER_DENSITY)
                        # Correct weight based on purchasing sheets
                        total_weight_kg = (big_sheet_area_m2 * density * required_sheets) / 1000.0
                        material_usage["paper_kg"] = round(total_weight_kg, 2)
                        
                        # Store sheet area for ink calc (approximate, using net area + waste?)
                        # Ink is usually calculated on Net Area or Net + MakeReady?
                        # Let's keep using the 'sheet_area_m2' from inputs (item area) * quantity for INK base, 
                        # because ink is only applied to the item area (plus bleed). 
                        # We don't print on the offcuts.
                        # So we LEAVE sheet_area_m2 as the item area for ink calculations below.
                        
                    else:
                         # Fallback to simple area
                         raise Exception(nesting_result['error'])

                except Exception as e:
                    print(f"Nesting calculation fallback: {e}")
                    # Fallback Logic
                    required_sheets = quantity * (1 + waste_paper) + setup_waste
                    material_usage["paper_sheets"] = math.ceil(required_sheets)
                    material_usage["waste_percent_used"] = round(waste_paper * 100, 2)
                    
                    density = int(data.get('paper_density') or DEFAULT_PAPER_DENSITY)
                    total_weight_kg = (sheet_area_m2 * density * material_usage["paper_sheets"]) / 1000
                    material_usage["paper_kg"] = round(total_weight_kg, 2)

            else:
                 # No dimensions fallback
                 required_sheets = quantity * (1 + waste_paper) + setup_waste
                 material_usage["paper_sheets"] = math.ceil(required_sheets)
                 material_usage["waste_percent_used"] = round(waste_paper * 100, 2)
                 
                 density = int(data.get('paper_density') or DEFAULT_PAPER_DENSITY)
                 total_weight_kg = (sheet_area_m2 * density * material_usage["paper_sheets"]) / 1000
                 material_usage["paper_kg"] = round(total_weight_kg, 2)
            
            # Ink:
            waste_ink = float(settings.waste_percentage_ink) / 100.0
            
            # Phase 6: Precise Ink Coverage Logic
            coverage_percent = data.get('ink_coverage_percent')
            
            if coverage_percent is not None:
                # Use User defined coverage
                # Standard Offset Ink usage: approx 2.5g per m2 for 100% coverage
                INK_USAGE_FULL_COVERAGE_KG = 0.0025 
                
                # If CMYK (4 colors), is coverage total or per separation?
                # User usually gives TOTAL visual coverage.
                # But for CMYK, 100% black is 100%. Rich black might be 200% (C60 M40 Y40 K100).
                # Let's assume input is "Average Coverage Per Sheet Side" relative to full saturation.
                
                c_percent = float(coverage_percent)
                ink_usage_kg = (material_usage["paper_sheets"] * sheet_area_m2 * INK_USAGE_FULL_COVERAGE_KG * (c_percent / 100.0))
            else:
                # Legacy Fallback based on color count
                colors_count = 4
                print_colors = data.get('print_colors', '')
                if '4' in str(print_colors): colors_count = 4
                elif '1' in str(print_colors): colors_count = 1
                elif '0' in str(print_colors): colors_count = 0
                
                # Assume standard 20% coverage per color channel implicitly in constant
                ink_usage_kg = (material_usage["paper_sheets"] * sheet_area_m2 * colors_count * INK_USAGE_PER_M2_PER_COLOR) / 1000 
            
            material_usage["ink_kg"] = round(ink_usage_kg * (1 + waste_ink), 2)
            
            # Lacquer:
            if data.get('lacquer_type') and data.get('lacquer_type') != 'none':
                waste_lacquer = float(settings.waste_percentage_lacquer) / 100.0
                lacquer_usage_kg = (material_usage["paper_sheets"] * sheet_area_m2 * LACQUER_USAGE_PER_M2) / 1000
                material_usage["lacquer_kg"] = round(lacquer_usage_kg * (1 + waste_lacquer), 2)
                
        return material_usage

    @staticmethod
    def calculate_cost(data, material_usage=None, profile=None):
        """
        Calculates estimated cost including machine rates, tax, and profiles.
        """
        if not material_usage:
            material_usage = CalculationService.calculate_material_usage(data)
            
        quantity = int(data.get('quantity', 0))
        if quantity == 0:
            return {"total_price": 0, "price_per_unit": 0, "breakdown": {}}
            
        settings = PricingSettings.load()
        
        cost_paper = 0
        cost_ink = 0
        cost_lacquer = 0
        
        total_material_cost = 0
        
        # Parse additional_processing if it's a JSON string
        extra = {}
        if data.get('additional_processing'):
            try:
                import json
                if isinstance(data['additional_processing'], str):
                    extra = json.loads(data['additional_processing'])
                elif isinstance(data['additional_processing'], dict):
                    extra = data['additional_processing']
            except:
                pass

        # Determine if it's a book for specific formula
        is_book = bool(data.get('book_name'))
        page_count = int(data.get('page_count') or 0)
        
        if is_book and page_count > 0:
            # -------------------------------------------------------------
            # BOOK SPECIFIC CALCULATION (Professional Typography)
            # -------------------------------------------------------------
            # sheet_count = pages / 2 (physcial sheets per book)
            sheets_per_book = math.ceil(page_count / 2)
            
            # 1. Paper Cost (Internal)
            internal_paper = extra.get('internal_paper') or data.get('internal_paper_type')
            
            # 2. Cover Paper Cost
            cover_paper = extra.get('cover_paper') or data.get('cover_paper_type')
            
            # 3. Binding Cost
            binding_type = extra.get('binding') or data.get('binding_type', 'termokley')
            
            # (Rest of book logic stays same...)
            # Re-using variables I already set up
            w = float(data.get('paper_width') or 15)
            h = float(data.get('paper_height') or 21)
            item_area_m2 = (w * h) / 10000.0
            density_internal = 80 # default
            if internal_paper and '80g' in internal_paper: density_internal = 80
            elif internal_paper and '90g' in internal_paper: density_internal = 90
            
            paper_kg_internal = (item_area_m2 * density_internal * sheets_per_book * quantity) / 1000.0
            cost_paper_internal = 0
            
            # Cover Paper
            density_cover = 250
            cover_kg = (item_area_m2 * 2.2 * density_cover * quantity) / 1000.0 # 2.2x area for spread + spine
            cost_cover = 0
            
            # Print Cost
            price_per_print = 100 
            colors = data.get('print_colors', '')
            if '4+4' in colors: price_per_print = 350
            elif '4+0' in colors: price_per_print = 200
            elif '1+1' in colors: price_per_print = 100
            
            cost_printing_internal = sheets_per_book * quantity * price_per_print
            cost_printing_cover = quantity * (500 if '4' in colors else 200) # Cover print cost
            
            # Binding Price
            binding_price = 800 # default termokley
            if binding_type == 'thread': binding_price = 1500
            elif binding_type == 'staple': binding_price = 300
            cost_binding = quantity * binding_price
            
            # Lamination Cost
            cost_lamination = 0
            lamination = extra.get('lamination') or data.get('cover_lamination')
            if lamination and lamination != 'none':
                cost_lamination = quantity * 400
                
            total_material_cost = cost_paper_internal + cost_cover
            total_operational_cost = cost_printing_internal + cost_printing_cover + cost_binding + cost_lamination
            
            gross_cost = total_material_cost + total_operational_cost
            
            # 4. Profit Margin based on Profile
            margin_percent = float(settings.profit_margin_percent)
            profile_name = data.get('pricing_profile')
            if profile_name and profile_name in settings.pricing_profiles:
                margin_percent = float(settings.pricing_profiles[profile_name])
            
            margin = margin_percent / 100.0
            profit = gross_cost * margin
            
            # 5. Tax (QQS)
            total_before_tax = gross_cost + profit
            tax_amount = total_before_tax * (float(settings.tax_percent) / 100.0)
            
            final_price = total_before_tax + tax_amount
            price_per_unit = final_price / quantity
            
            return {
                "total_price": round(final_price, -2), 
                "price_per_unit": round(price_per_unit, 2),
                "breakdown": {
                    "material_cost": round(total_material_cost, 2),
                    "operational_cost": round(total_operational_cost, 2),
                    "paper_internal": round(cost_paper_internal, 2),
                    "paper_cover": round(cost_cover, 2),
                    "printing_cost": round(cost_printing_internal + cost_printing_cover, 2),
                    "binding_cost": round(cost_binding, 2),
                    "lamination_cost": round(cost_lamination, 2),
                    "profit": round(profit, 2),
                    "tax": round(tax_amount, 2)
                }
            }

        # -------------------------------------------------------------
        # STANDARD PACKAGING CALCULATION (Fallback)
        # -------------------------------------------------------------
        # 2. Operational Cost (including machine rate)
        # Phase 2: Granular Machine Costing
        # We try to find specific machines for Printing and Cutting
        from .models import MachineSettings
        
        # Printing Cost
        printer = MachineSettings.objects.filter(machine_type='printer', is_active=True).first()
        printer_rate = float(printer.hourly_rate) if printer else float(settings.machine_hourly_rate)
        printer_setup = float(printer.setup_time_minutes) / 60.0 if printer else 0.5
        
        # Estimate Printing Time: Setup + (Quantity / Speed)
        # Speed assumption: 3000 sheets/hour (Offset)
        # We use 'paper_sheets' from material_usage as the "run quantity"
        run_sheets = material_usage.get("paper_sheets", quantity)
        printing_hours = printer_setup + (run_sheets / 3000.0)
        cost_printing = printing_hours * printer_rate
        
        # Cutting Cost
        cutter = MachineSettings.objects.filter(machine_type='cutter', is_active=True).first()
        cutter_rate = float(cutter.hourly_rate) if cutter else float(settings.machine_hourly_rate)
        cutter_setup = float(cutter.setup_time_minutes) / 60.0 if cutter else 0.5
        
        # Cutting is usually slower? or 1 sheet at a time? 
        # Die cutting: 2000/hour
        cutting_hours = cutter_setup + (run_sheets / 2000.0)
        cost_cutting = cutting_hours * cutter_rate
        
        machine_cost = cost_printing + cost_cutting
        
        # Phase 6: Die-Cut Cost (Engineering Logic)
        die_cut_cost = 0
        knife_length_meters = 0
        
        # Check if profile has a parametric template type
        profile_name = data.get('pricing_profile')
        legacy_profile = settings.pricing_profiles.get(profile_name) if profile_name else None
        
        # Determine Box Style
        box_style = None
        if profile and hasattr(profile, 'box_style'):
            box_style = profile.box_style
        elif legacy_profile and isinstance(legacy_profile, dict):
            box_style = legacy_profile.get('box_style')

        if box_style and box_style != 'custom':
            try:
                from .constructors import PizzaBoxGenerator, ShoppingBagGenerator
                
                # Get dimensions from params or data
                # Assuming data contains 'specs' with width_cm, height_cm, depth_cm
                
                # Fallback L, W, H extraction
                w = float(data.get('width_cm', 0) or 0)
                l = float(data.get('height_cm', 0) or 0) # UI "Height" is usually Length/Depth
                h = float(data.get('depth_cm', 0) or 5)  # Default 5 if missing
                
                # Phase 6: Material Thickness
                thickness_cm = 0
                if material_usage:
                     # Attempt to find thickness from paper/material
                     # material_usage has 'paper_kg', but not the material ID directly typically?
                     # We need to look up the Material object.
                     # 'data' might have 'material_id' or 'paper_type' (name).
                     pass
                
                # Try to get thickness from Settings or Data
                # For now, let's look for a 'thickness_mm' in data or fetch based on 'paper_type'
                # Optimization: In real app, we fetch Material object earlier.
                # Let's mock or quick-fetch
                from .models import Material
                pk = data.get('paper_type') # In Frontend this sends ID or Name? Usually ID if select.
                if isinstance(pk, int) or (isinstance(pk, str) and pk.isdigit()):
                    mat = Material.objects.filter(pk=pk).first()
                    if mat:
                         thickness_cm = mat.thickness_mm / 10.0 # mm to cm
                
                generator = None
                if box_style == 'pizza_box':
                    generator = PizzaBoxGenerator(l, w, h, thickness=thickness_cm)
                elif box_style == 'shopping_bag':
                     generator = ShoppingBagGenerator(l, w, h, thickness=thickness_cm)
                
                if generator:
                    knife_stats = generator.calculate_knife_length()
                    total_knife_len = knife_stats['cut'] + knife_stats['crease']
                    
                    # Formula: Base Die Cost + (Length * Price/m)
                    # Cost is One-Time setup usually, BUT usually amortization is charged per order 
                    # OR full valid die cost if new mold.
                    # For Price Quote, we add full Die Cost usually?
                    # Let's assume full cost for now (User pays for the Mold)
                    
                    die_cut_cost = float(settings.base_die_cost) + (total_knife_len * float(settings.knife_price_per_meter))
                    knife_length_meters = total_knife_len

            except Exception as e:
                print(f"Die Calc Error: {e}")
        
        # 4. Profit Margin
        total_operational_cost = machine_cost + float(settings.setup_cost) + die_cut_cost
        gross_cost = total_material_cost + total_operational_cost
        
        # 4. Profit Margin based on Profile
        margin_percent = float(settings.profit_margin_percent)
        profile_name = data.get('pricing_profile')
        if profile_name and profile_name in settings.pricing_profiles:
            margin_percent = float(settings.pricing_profiles[profile_name])
        
        margin = margin_percent / 100.0
        profit = gross_cost * margin
        
        # 5. Tax (QQS)
        total_before_tax = gross_cost + profit
        tax_amount = total_before_tax * (float(settings.tax_percent) / 100.0)
        
        final_price = total_before_tax + tax_amount
        price_per_unit = final_price / quantity
        
        return {
            "total_price": round(final_price, -2), 
            "price_per_unit": round(price_per_unit, 2),
            "breakdown": {
                "material_cost": round(total_material_cost, 2),
                "operational_cost": round(total_operational_cost, 2),
                "machine_cost": round(machine_cost, 2),
                "die_cut_cost": round(die_cut_cost, 2), # Phase 6
                "knife_length_m": round(knife_length_meters, 2),
                "profit": round(profit, 2),
                "tax": round(tax_amount, 2)
            }
        }

    @staticmethod
    def calculate_deadline(data):
        """
        Estimates completion date based on quantity and complexity.
        """
        quantity = int(data.get('quantity', 0))
        
        # Base: 2 days
        days = 2
        
        # Add 1 day for every 5000 items
        days += (quantity // 5000)
        
        # Add 1 day if additional processing
        if data.get('additional_processing'):
            days += 1
            
        deadline = datetime.now() + timedelta(days=days)
        return deadline.date().isoformat()

class ProductionAssignmentService:
    @staticmethod
    def auto_assign_production_steps(order):
        """
        Automatically generates production steps and assigns employees when an order enters 'in_production'.
        Consolidated logic for Templates, Books, and Boxes.
        """
        if ProductionStep.objects.filter(order=order).exists():
            return # Already assigned
            
        settings = PricingSettings.load()
        from .models import MachineSettings

        # 1. Template-Based Routing (Highest Priority)
        if order.product_template and hasattr(order.product_template, 'routing_steps') and order.product_template.routing_steps.exists():
            routing = order.product_template.routing_steps.all().order_by('sequence')
            previous_step = None
            
            with transaction.atomic():
                for r in routing:
                    step = ProductionStep.objects.create(
                        order=order,
                        step=r.step_name,
                        status='pending',
                        depends_on_step=previous_step
                    )
                    
                    if r.required_machine_type:
                        machine = MachineSettings.objects.filter(
                            machine_type__icontains=r.required_machine_type,
                            is_active=True
                        ).first()
                        if machine:
                            step.machine = machine
                            step.save()
                            
                    previous_step = step
            return # Done with template routing

        # 2. Dynamic/Professional Routing (Fallback)
        flow = []
        if order.book_name:
            # Typography / Book flow
            flow = [
                {'step': 'prepress', 'assign': None},
                {'step': 'printing_internal', 'assign': settings.default_printer_user},
                {'step': 'printing_cover', 'assign': settings.default_printer_user},
                {'step': 'folding', 'assign': settings.default_finisher_user},
                {'step': 'assembly', 'assign': settings.default_finisher_user},
                {'step': 'binding', 'assign': settings.default_finisher_user},
                {'step': 'trimming', 'assign': settings.default_cutter_user},
                {'step': 'packaging', 'assign': settings.default_finisher_user},
                {'step': 'ready', 'assign': settings.default_warehouse_user},
            ]
        else:
            # Box / General packaging flow
            flow = [
                {'step': 'prepress', 'assign': None},
                {'step': 'printing', 'assign': settings.default_printer_user},
            ]
            
            if order.lacquer_type and order.lacquer_type != 'none':
                flow.append({'step': 'lamination', 'assign': None})
            
            cut_step = 'die_cutting' if order.box_type else 'cutting'
            flow.append({'step': cut_step, 'assign': settings.default_cutter_user})
            flow.append({'step': 'gluing', 'assign': settings.default_finisher_user})
            flow.append({'step': 'qc', 'assign': settings.default_qc_user})
            flow.append({'step': 'packaging', 'assign': settings.default_finisher_user})
            flow.append({'step': 'ready', 'assign': settings.default_warehouse_user},)

        # Execute dynamic flow creation
        previous_step = None
        with transaction.atomic():
            for item in flow:
                step = ProductionStep.objects.create(
                    order=order,
                    step=item['step'],
                    status='pending',
                    assigned_to=item['assign'],
                    depends_on_step=previous_step
                )
                previous_step = step
            
        return # Done
