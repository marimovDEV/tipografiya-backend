from api.models import Material

materials = [
    # Paper
    {"name": "Karton 350g/m²", "category": "karton", "unit": "kg", "price_per_unit": 12000, "current_stock": 5000, "min_stock": 500},
    {"name": "Karton 300g/m²", "category": "karton", "unit": "kg", "price_per_unit": 11000, "current_stock": 2000, "min_stock": 300},
    {"name": "Karton 250g/m²", "category": "karton", "unit": "kg", "price_per_unit": 10000, "current_stock": 3000, "min_stock": 500},
    {"name": "Melovannaya 150g/m²", "category": "qogoz", "unit": "kg", "price_per_unit": 15000, "current_stock": 1000, "min_stock": 200},
    {"name": "Ofset Qog'oz 80g/m²", "category": "qogoz", "unit": "kg", "price_per_unit": 9000, "current_stock": 5000, "min_stock": 1000},
    
    # Ink
    {"name": "Bo'yoq - CMYK", "category": "siyoh", "unit": "kg", "price_per_unit": 85000, "current_stock": 200, "min_stock": 20},
    {"name": "Bo'yoq - Pantone Gold", "category": "siyoh", "unit": "kg", "price_per_unit": 120000, "current_stock": 50, "min_stock": 5},
    
    # Lacquer
    {"name": "UV Lak", "category": "lak", "unit": "kg", "price_per_unit": 55000, "current_stock": 150, "min_stock": 20},
    {"name": "VD Lak (Suvli)", "category": "lak", "unit": "kg", "price_per_unit": 40000, "current_stock": 200, "min_stock": 30},
    
    # Glue & Chemicals
    {"name": "Yelim (Kley)", "category": "kimyoviy", "unit": "kg", "price_per_unit": 25000, "current_stock": 500, "min_stock": 50},
    {"name": "Yuvish vositasi (Smyvka)", "category": "kimyoviy", "unit": "litr", "price_per_unit": 30000, "current_stock": 100, "min_stock": 10},
    
    # Plate
    {"name": "Ofset Qolipi (Plastina)", "category": "rang_qoliplari", "unit": "dona", "price_per_unit": 45000, "current_stock": 500, "min_stock": 50},
]

for m in materials:
    Material.objects.get_or_create(name=m["name"], defaults=m)

print("Materials seeded successfully!")
