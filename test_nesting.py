import os
import sys

# Setup Django environment
sys.path.append(os.getcwd())

from api.nesting_service import NestingService

def test_nesting():
    print("🧩 Testing Nesting Service...")

    # Test Case 1: A4 Flyer (21x29.7)
    item_w = 21.0
    item_h = 29.7
    qty = 5000
    
    print(f"\n📄 Case 1: Flyer A4 ({item_w} x {item_h} cm), Qty: {qty}")
    result = NestingService.calculate_best_layout(item_w, item_h, qty)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        best = result['recommended_format']
        print(f"✅ Recommended: {best['format']}")
        print(f"   Items/Sheet: {best['items_per_sheet']} ({best['orientation']})")
        print(f"   Layout: {best['layout_columns']} x {best['layout_rows']}")
        print(f"   Waste: {best['waste_percent']}%")
        print(f"   Sheets Needed: {best['sheets_needed']}")
        
        print("   Alternatives:")
        for alt in result['alternatives']:
            print(f"   - {alt['format']}: Waste {alt['waste_percent']}%, Count {alt['items_per_sheet']}")


    # Test Case 2: Pizza Box Unfolded (e.g., 45x45 cm)
    item_w = 45.0
    item_h = 45.0
    qty = 1000
    
    print(f"\n🍕 Case 2: Pizza Box ({item_w} x {item_h} cm), Qty: {qty}")
    result = NestingService.calculate_best_layout(item_w, item_h, qty)
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        best = result['recommended_format']
        print(f"✅ Recommended: {best['format']}")
        print(f"   Items/Sheet: {best['items_per_sheet']} ({best['orientation']})")
        print(f"   Waste: {best['waste_percent']}%")

if __name__ == "__main__":
    test_nesting()
