
import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import ProductTemplate, ParametricProductProfile

def verify_engineering_models():
    print("--- Verifying Engineering Engine Models ---")
    
    # 1. Create a Product Template
    template_name = "Test Parametric Box"
    template, created = ProductTemplate.objects.get_or_create(
        name=template_name,
        defaults={
            'category': 'custom',
            'is_parametric': True,
            'description': 'Test template for Auto-CAD logic'
        }
    )
    print(f"ProductTemplate created: {template.name} (Parametric: {template.is_parametric})")
    
    # 2. Create Parametric Profile
    profile, p_created = ParametricProductProfile.objects.get_or_create(
        template=template,
        defaults={
            'geometry_script': {
                "type": "box",
                "l": "length",
                "w": "width",
                "h": "height",
                "cut_lines": "2*(l+w)"
            },
            'min_width': 10,
            'max_width': 500,
            'ink_density_estimated': 300.00
        }
    )
    print(f"ParametricProfile created for: {profile.template.name}")
    print(f"Geometry Logic: {profile.geometry_script}")
    print(f"Ink Density: {profile.ink_density_estimated}%")
    
    # 3. Verify Relationship
    fetched_template = ProductTemplate.objects.get(name=template_name)
    if hasattr(fetched_template, 'parametric_profile'):
        print("SUCCESS: Relationship established correctly.")
    else:
        print("FAILED: parametric_profile not found on template.")

    # 4. Verify Waste Logic
    print("\n--- Verifying Waste Logic ---")
    from api.waste_logic import WasteManagementService
    
    # Test Case 1: A4 on 70x100 (Efficient)
    a4_w, a4_h = 21.0, 29.7
    result_a4 = WasteManagementService.calculate_layout_efficiency(a4_w, a4_h)
    print(f"Layout A4 ({a4_w}x{a4_h}cm): {result_a4['items_per_sheet']} items, Waste: {result_a4['waste_percent']}%")
    
    # Test Case 2: Awkward Size (High Waste)
    awk_w, awk_h = 45.0, 45.0
    result_awk = WasteManagementService.calculate_layout_efficiency(awk_w, awk_h)
    print(f"Layout Awkward ({awk_w}x{awk_h}cm): {result_awk['items_per_sheet']} items, Waste: {result_awk['waste_percent']}%")
    
    # Test Case 3: Calculation Service Integration
    from api.services import CalculationService
    data = {
        "quantity": 1000,
        "paper_width": 45.0,
        "paper_height": 45.0,
        "paper_density": 300
    }
    usage = CalculationService.calculate_material_usage(data)
    print(f"Service Calculation for 1000x 45x45cm:")
    print(f"  - Sheets needed: {usage['paper_sheets']}")
    if 'waste_percent_used' in usage:
        print(f"  - Dynamic Waste Used: {usage['waste_percent_used']}% (Should match above)")
    else:
        print("  - Dynamic Waste NOT used (check integration)")

    # 5. Verify Currency Logic
    print("\n--- Verifying Currency Logic ---")
    from api.currency import CurrencyService
    from api.models import PricingSettings
    
    # Force update
    print("Fetching CBU rates...")
    result = CurrencyService.update_exchange_rate(force=True)
    print(f"Update Result: {result}")
    
    settings = PricingSettings.load()
    print(f"Current System Rate: {settings.exchange_rate} UZS")

if __name__ == "__main__":
    try:
        verify_engineering_models()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
