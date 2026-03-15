import os
import sys

sys.path.append(os.getcwd())
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.services import CalculationService

def verify():
    print("🚀 Verifying Nesting Integration in CalculationService...")
    
    # Test Data: A4 Flyer (21x29.7)
    # 5000 qty
    data = {
        'quantity': 5000,
        'paper_width': 21.0,
        'paper_height': 29.7,
        'paper_density': 300,
        'paper_type': 'Test Paper'
    }
    
    print(f"📊 Input: A4 ({data['paper_width']}x{data['paper_height']}), Qty: {data['quantity']}")
    
    try:
        usage = CalculationService.calculate_material_usage(data)
        
        print("\n✅ Result:")
        print(f"   - Paper Quantity (Sheets): {usage.get('paper_sheets')}")
        print(f"   - Paper Weight (kg): {usage.get('paper_kg')}")
        print(f"   - Waste % Used: {usage.get('waste_percent_used')}%")
        print(f"   - Layout: {usage.get('layout_description')}")
        
        # Validation
        if 'layout_description' in usage and usage['layout_description']:
            print("🎉 SUCCESS: Nesting logic triggered and layout description found.")
        else:
            print("❌ FAILURE: Layout description missing. Nesting might have failed or not triggered.")
            
    except Exception as e:
        print(f"❌ Error during calculation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify()
