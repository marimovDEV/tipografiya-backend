import os
import django
import sys

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import PricingSettings, MachineSettings
from api.services import CalculationService

def verify_costing():
    print("--- Verifying Smart Costing ---")
    
    # 1. Setup Data
    settings = PricingSettings.load()
    settings.setup_waste_sheets = 50
    settings.waste_percentage_paper = 5 # 5%
    settings.save()
    print(f"Settings: Setup Waste = {settings.setup_waste_sheets}, Waste % = {settings.waste_percentage_paper}")
    
    # Create/Update Machines
    MachineSettings.objects.filter(machine_type='printer').delete()
    MachineSettings.objects.filter(machine_type='cutter').delete()
    
    MachineSettings.objects.create(
        machine_name="Test Offset",
        machine_type="printer",
        hourly_rate=100000, # 100k/hr
        setup_time_minutes=60 # 1 hr
    )
    MachineSettings.objects.create(
        machine_name="Test Cutter",
        machine_type="cutter",
        hourly_rate=50000, # 50k/hr
        setup_time_minutes=30 # 0.5 hr
    )
    
    # 2. Calculate
    data = {
        'quantity': 1000,
        'paper_width': 50, # cm
        'paper_height': 70, # cm
        'paper_density': 300,
        'paper_type': 'Test Paper'
    }
    
    # Paper Usage Calc
    # 1000 qty. 50x70 is big. Let's assume 1 per sheet for simplicity if not nesting.
    # Logic: 1000 * 1.05 = 1050 + 50 setup = 1100 sheets.
    
    # But wait, services.py attempts Nesting.
    # 50x70 fits on what? Let's assume it picks a format or falls back.
    # If fallback: quantity * (1+waste) + setup.
    
    cost_data = CalculationService.calculate_cost(data)
    breakdown = cost_data['breakdown']
    
    # 3. Validation
    print(f"Total Price: {cost_data['total_price']}")
    print(f"Machine Cost: {breakdown.get('machine_cost')}")
    
    # Manual Cost Check
    # Printing: Setup 1h. Run: 1100 / 3000 = 0.366h. Total Printing: 1.366h * 100k = 136,666
    # Cutting: Setup 0.5h. Run: 1100 / 2000 = 0.55h. Total Cutting: 1.05h * 50k = 52,500
    # Expected Machine Cost approx: 189,166
    
    print(f"Breakdown: {breakdown}")
    
    if breakdown.get('machine_cost') > 0:
        print("SUCCESS: Machine Cost calculated.")
    else:
        print("FAILURE: Machine Cost is 0.")

if __name__ == '__main__':
    verify_costing()
