
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.services import CalculationService
from api.models import ParametricProductProfile, ProductTemplate, PricingSettings

def verify_calculator_v2():
    print("--- Verifying Super-Calculator (Phase 6) ---")
    
    # 1. Setup Mock Data
    settings = PricingSettings.load()
    settings.knife_price_per_meter = Decimal(60000)
    settings.base_die_cost = Decimal(150000)
    settings.save()
    
    print(f"Settings: Base={settings.base_die_cost}, PerMeter={settings.knife_price_per_meter}")

    # Create/Get a parametric profile
    template, _ = ProductTemplate.objects.get_or_create(
        name="Pizza Box Test", 
        defaults={'category': 'pizza_box', 'is_parametric': True}
    )
    profile, _ = ParametricProductProfile.objects.get_or_create(template=template)
    profile.box_style = 'pizza_box'
    profile.save()
    
    
    # Create a Material with Thickness
    from api.models import Material
    mat, _ = Material.objects.get_or_create(name="E-Flute Carton", defaults={'price_per_unit': 1000})
    mat.thickness_mm = 2.0 # 2mm thickness
    mat.save()
    
    # 2. Input Data (20x30x5 cm)
    # Mapping in service: Width_cm -> W, Height_cm -> L, Depth_cm -> H
    data = {
        'width_cm': 30,  # W
        'height_cm': 20, # L
        'depth_cm': 5,   # H
        'quantity': 1000,
        'material_cost_per_item': 1000,
        'paper_type': mat.id # Pass ID to trigger thickness lookup
    }
    
    print(f"Input: 30x20x5 cm Box. Style: {profile.box_style}. Material: E-Flute (2mm). Ink Coverage: 100%")
    
    # 3. Calculate
    data['ink_coverage_percent'] = 100 # High coverage
    result_high = CalculationService.calculate_cost(data, profile=profile)
    
    data['ink_coverage_percent'] = 10 # Low coverage
    result_low = CalculationService.calculate_cost(data, profile=profile)
    
    # 4. Verify Breakdown
    die_cost = result_high['breakdown'].get('die_cut_cost', 0)
    knife_len = result_high['breakdown'].get('knife_length_m', 0)
    
    # Check ink cost difference
    # Note: result_high['breakdown'] might not explicitly list ink_cost, it's inside material_cost usually.
    # But calculate_cost computes material usage.
    
    print(f"✅ Calculation Result:")
    print(f"   - Die-Cut Cost: {die_cost:,} UZS")
    print(f"   - Knife Length: {knife_len} meters")
    
    # Comparing Total Price or Cost to verify Ink effect
    price_high = result_high['total_price']
    price_low = result_low['total_price']
    
    print(f"   - Price (100% Ink): {price_high:,}")
    print(f"   - Price (10% Ink):  {price_low:,}")
    
    if price_high > price_low:
        print("SUCCESS: High ink coverage costs more.")
    else:
        print("FAILED: Ink coverage didn't affect price (or margin of error too small).")
    
    # Manual Check
    if die_cost > 150000 and knife_len > 0:
        print("SUCCESS: Die-cut cost calculated correctly.")
    else:
        print("FAILED: Die-cut cost missing.")

if __name__ == "__main__":
    verify_calculator_v2()
