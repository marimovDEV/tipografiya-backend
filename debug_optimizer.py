
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.production_optimizer import LayoutOptimizer

def verify_optimizer():
    print("--- Verifying Layout Optimizer (Phase 7) ---")
    
    # Case 1: 20x30 on 70x100
    # Option A (Std): 70/20=3, 100/30=3 -> 9 items
    # Option B (Rot): 70/30=2, 100/20=5 -> 10 items
    
    opt = LayoutOptimizer(20, 30, 70, 100, gap=0)
    res = opt.optimize()
    
    print(f"Case 1 (20x30 on 70x100):")
    print(f"   - Items: {res['total_items']}")
    print(f"   - Rotated: {res['rotated']}")
    print(f"   - Waste: {res['waste_percent']}%")
    
    if res['total_items'] == 10 and res['rotated'] == True:
        print("SUCCESS: Rotation strategy found better layout (10 vs 9).")
    else:
        print(f"FAILED: Expected 10 items (Rotated), got {res['total_items']}.")

    # Case 2: 21x29.7 (A4) on 70x100
    # A4 is approx 21x30. 
    # 70/21 = 3, 100/29.7=3.3 -> 9
    # 70/29.7=2.3, 100/21=4.7 -> 2x4=8.
    # Std wins (9).
    
    opt2 = LayoutOptimizer(21, 29.7, 70, 100, gap=0)
    res2 = opt2.optimize()
    print(f"\nCase 2 (A4 on 70x100):")
    print(f"   - Items: {res2['total_items']}")
    print(f"   - Rotated: {res2['rotated']}")
    
    if res2['total_items'] == 9 and res2['rotated'] == False:
         print("SUCCESS: Standard strategy standard is better.")
    else:
         print(f"FAILED: Expected 9 items (Std), got {res2['total_items']}.")

if __name__ == "__main__":
    verify_optimizer()
