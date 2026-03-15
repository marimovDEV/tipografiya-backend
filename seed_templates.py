import os
import django
import sys

# Set up Django
sys.path.append('/Users/ogabek/Documents/projects/erp+crm kitob/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import ProductionTemplate, TemplateStage, Order, ProductionStep, User

def seed_templates():
    print("Seeding templates...")
    
    # 1. Standard Vizitka Template
    vizitka, _ = ProductionTemplate.objects.get_or_create(
        name="Vizitka (Standart)",
        description="Oddiy vizitkalar uchun 4 bosqichli standart jarayon"
    )
    
    stages_vizitka = ["prepress", "printing", "cutting", "packaging"]
    for i, stage_name in enumerate(stages_vizitka):
        TemplateStage.objects.get_or_create(
            template=vizitka,
            stage_name=stage_name,
            sequence=i + 1
        )
        
    # 2. Quti (Box) Template
    quti, _ = ProductionTemplate.objects.get_or_create(
        name="Quti (Karton)",
        description="Karton qutilar uchun to'liq tsikl"
    )
    
    stages_quti = ["prepress", "printing", "lamination", "die_cutting", "gluing", "packaging"]
    for i, stage_name in enumerate(stages_quti):
        TemplateStage.objects.get_or_create(
            template=quti,
            stage_name=stage_name,
            sequence=i + 1
        )
        
    # 3. Flayer (Flyer) Template
    flayer, _ = ProductionTemplate.objects.get_or_create(
        name="Flayer (Buklet)",
        description="Flayer va bukletlar uchun jarayon"
    )
    
    stages_flayer = ["prepress", "printing", "drying", "cutting", "packaging"]
    for i, stage_name in enumerate(stages_flayer):
        TemplateStage.objects.get_or_create(
            template=flayer,
            stage_name=stage_name,
            sequence=i + 1
        )

    print("Templates seeded successfully!")

    # Let's apply one of these templates to existing orders that don't have a template yet
    orders = Order.objects.filter(status__in=['pending', 'approved', 'in_production'])
    if orders.exists():
        print(f"Applying templates to {orders.count()} existing orders...")
        for order in orders:
            if not order.template:
                order.template = vizitka
                order.save()
                
            # If the order has no steps, create them based on the template
            if not order.production_steps.exists():
                print(f"Creating steps for order {order.id}...")
                stages = order.template.stages.all()
                for i, stage in enumerate(stages):
                    # Only assign first step's input_qty to the order's quantity
                    # Admin can assign workers later
                    input_qty = order.quantity if i == 0 else 0
                    
                    ProductionStep.objects.create(
                        order=order,
                        step=stage.stage_name,
                        sequence=stage.sequence,
                        input_qty=input_qty,
                        status='pending' if i == 0 else 'pending' # First step could be ready, but let's keep all pending
                    )

if __name__ == '__main__':
    seed_templates()
