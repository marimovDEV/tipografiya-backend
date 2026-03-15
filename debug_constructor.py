
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.constructors import PizzaBoxGenerator, ShoppingBagGenerator
from api.models import ParametricProductProfile

def verify_constructor():
    print("--- Verifying Dieline Generators ---")
    
    # 1. Test Pizza Box (FEFCO 0427)
    L, W, H = 20, 30, 5 # cm
    print(f"\n1. Testing Pizza Box (L={L}, W={W}, H={H} cm)")
    
    generator = PizzaBoxGenerator(L, W, H)
    path_data = generator.generate_svg_path()
    
    # Check output
    if not path_data:
        print("❌ Pizza Box: Failed to generate path")
        return
        
    print(f"✅ Generated SVG Path (First 50 chars): {path_data[:50]}...")
    
    # Simple logic check: path should definitely start with Move command
    if path_data.strip().startswith('M'):
        print("✅ Path format looks correct (Starts with M)")
    else:
        print("❌ Path format incorrect")

    # 2. Test Shopping Bag
    print(f"\n2. Testing Shopping Bag (Gusset=10cm)")
    bag_gen = ShoppingBagGenerator(L, W, H, gusset=10)
    bag_path = bag_gen.generate_svg_path()
    print(f"✅ Generated Bag Path: {bag_path}")

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    verify_constructor()
