from api.models import ProductTemplate

# Create 10 diverse product templates
templates_data = [
    {
        "name": "Standart dori qutisi",
        "category": "medicine_box_1layer",
        "layer_count": 1,
        "default_waste_percent": 5.0,
        "description": "1 qatlamli oddiy dori qutisi, eng ko'p ishlatiladigan standart o'lcham",
        "default_width": 10.0,
        "default_height": 15.0,
        "default_depth": 3.0,
        "is_active": True
    },
    {
        "name": "Katta pizza qutisi",
        "category": "pizza_box",
        "layer_count": 1,
        "default_waste_percent": 8.0,
        "description": "32 sm pizza uchun standart quti",
        "default_width": 32.0,
        "default_height": 32.0,
        "default_depth": 4.0,
        "is_active": True
    },
    {
        "name": "O'rta pizza qutisi",
        "category": "pizza_box",
        "layer_count": 1,
        "default_waste_percent": 7.0,
        "description": "26 sm pizza uchun quti",
        "default_width": 26.0,
        "default_height": 26.0,
        "default_depth": 3.5,
        "is_active": True
    },
    {
        "name": "Premium quti 2 qatlam",
        "category": "box_2layer",
        "layer_count": 2,
        "default_waste_percent": 10.0,
        "description": "Yuqori sifatli 2 qatlamli gofrokarton quti",
        "default_width": 30.0,
        "default_height": 20.0,
        "default_depth": 15.0,
        "is_active": True
    },
    {
        "name": "Mustahkam quti 3 qatlam",
        "category": "box_3layer",
        "layer_count": 3,
        "default_waste_percent": 12.0,
        "description": "Og'ir yuklarni ko'tarish uchun 3 qatlamli quti",
        "default_width": 40.0,
        "default_height": 30.0,
        "default_depth": 25.0,
        "is_active": True
    },
    {
        "name": "Pecheniye qutisi kichik",
        "category": "cookie_box",
        "layer_count": 1,
        "default_waste_percent": 6.0,
        "description": "250g pecheniye uchun quti",
        "default_width": 15.0,
        "default_height": 10.0,
        "default_depth": 5.0,
        "is_active": True
    },
    {
        "name": "Pecheniye qutisi katta",
        "category": "cookie_box",
        "layer_count": 1,
        "default_waste_percent": 7.0,
        "description": "500g pecheniye uchun quti",
        "default_width": 20.0,
        "default_height": 15.0,
        "default_depth": 6.0,
        "is_active": True
    },
    {
        "name": "Sovg'a sumka o'rta",
        "category": "gift_bag",
        "layer_count": 1,
        "default_waste_percent": 9.0,
        "description": "O'rta hajmli sovg'a sumka dastakli",
        "default_width": 25.0,
        "default_height": 30.0,
        "default_depth": 10.0,
        "is_active": True
    },
    {
        "name": "Fast food qutisi",
        "category": "food_box",
        "layer_count": 1,
        "default_waste_percent": 8.0,
        "description": "Burger va kartoshka uchun quti",
        "default_width": 18.0,
        "default_height": 18.0,
        "default_depth": 8.0,
        "is_active": True
    },
    {
        "name": "Maxsus individual quti",
        "category": "custom",
        "layer_count": 2,
        "default_waste_percent": 15.0,
        "description": "Mijoz talabiga ko'ra maxsus ishlab chiqilgan quti",
        "default_width": 25.0,
        "default_height": 25.0,
        "default_depth": 12.0,
        "is_active": True
    }
]

print("Creating 10 product templates...")
created_count = 0

for data in templates_data:
    template, created = ProductTemplate.objects.get_or_create(
        name=data["name"],
        defaults=data
    )
    if created:
        created_count += 1
        print(f"✅ Created: {template.name} ({template.get_category_display()})")
    else:
        print(f"⚠️  Already exists: {template.name}")

print(f"\n✅ Successfully created {created_count} new templates!")
print(f"📊 Total templates in database: {ProductTemplate.objects.filter(is_deleted=False).count()}")
