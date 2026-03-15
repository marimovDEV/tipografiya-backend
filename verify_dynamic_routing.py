import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import ProductTemplate, ProductTemplateRouting, Order, Client, ProductionStep, User

def verify_dynamic_routing():
    print("🚀 Starting Dynamic Routing Verification...")

    # 1. Create/Get a Client
    client, _ = Client.objects.get_or_create(
        full_name="Test Client", 
        defaults={"phone": "+998901234567"}
    )

    # 2. Create a Professional Template
    template, created = ProductTemplate.objects.get_or_create(
        name="Professional Gift Box",
        category="gift_bag",
        defaults={
            "description": "Premium Gift Box with Lamination",
            "layer_count": 1
        }
    )
    print(f"✅ Template: {template.name}")

    # 3. Define Dynamic Routing (The 'Professional Flow')
    # Prepress -> Print -> Lamination -> Die-cut -> Gluing -> QC -> Packaging -> Dispatch
    routing_flow = [
        ('prepress', 'Dizayn/Pre-press'),
        ('printing', 'Offset Print'),
        ('lamination', 'Matte Lamination'),
        ('die_cutting', 'Die-cut'),
        ('gluing', 'Gluing'),
        ('qc', 'Quality Control'),
        ('packaging', 'Finale Packing'),
        ('dispatch', 'Dispatch/Yuklash'),
    ]

    # Clear existing routings for this template to be clean
    ProductTemplateRouting.objects.filter(template=template).delete()

    print("📝 Creating Routing Steps...")
    for seq, (step_code, description) in enumerate(routing_flow, 1):
        ProductTemplateRouting.objects.create(
            template=template,
            sequence=seq,
            step_name=step_code,
            notes=description
        )
        print(f"   - Step {seq}: {step_code} ({description})")

    # 4. Create an Order using this Template
    order = Order.objects.create(
        client=client,
        product_template=template,
        box_type="Test Dynamic Box",
        quantity=5000,
        status='pending',
        paper_type="Karton",
        paper_density=300,
        print_colors="4+0"
    )
    print(f"📦 Created Order #{order.order_number}")

    # 5. Approve the Order (Triggers generation logic)
    # We simulate what the view does
    print("🔄 Approving Order...")
    
    # Logic extracted from OrderViewSet.approve
    if order.product_template and order.product_template.routing_steps.exists():
        routing = order.product_template.routing_steps.all().order_by('sequence')
        previous_step = None
        for r in routing:
            step = ProductionStep.objects.create(
                order=order,
                step=r.step_name,
                status='pending',
                depends_on_step=previous_step
            )
            # Simulate generic assignment for testing
            if r.step_name == 'printing':
                # Try to assign a printer
                printer = User.objects.filter(role__icontains='print').first()
                if printer: step.assigned_to = printer
            
            step.save()
            previous_step = step
            
    order.status = 'in_production'
    order.save()

    # 6. Verify Created Steps
    steps = ProductionStep.objects.filter(order=order).order_by('created_at') # Should match created order
    print("\n🧐 Verifying Generated Steps:")
    
    matches = True
    if steps.count() != len(routing_flow):
        print(f"❌ Mismatch! Expected {len(routing_flow)} steps, got {steps.count()}")
        matches = False
    
    for i, step in enumerate(steps):
        expected_code = routing_flow[i][0]
        if step.step != expected_code:
            print(f"   ❌ Step {i+1}: Expected '{expected_code}', got '{step.step}'")
            matches = False
        else:
            print(f"   ✅ Step {i+1}: {step.step}")

    if matches:
        print("\n🎉 SUCCESS! Dynamic routing is working correctly.")
    else:
        print("\n⚠️ FAILED! Discrepancies found.")

if __name__ == "__main__":
    verify_dynamic_routing()
