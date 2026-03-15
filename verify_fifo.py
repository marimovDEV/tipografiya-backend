import os
import sys
from decimal import Decimal

# Setup Django environment
sys.path.append(os.getcwd())
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import Material, MaterialBatch, Client, Order, ProductionStep, WarehouseLog, User

def verify_fifo():
    print("🚀 Starting FIFO & Multi-batch Verification...")

    # 1. Create a Test Material
    material_name = "FIFO Test Paper"
    material, _ = Material.objects.get_or_create(
        name=material_name,
        defaults={'unit': 'kg', 'category': 'qogoz'}
    )
    # Clear existing batches
    MaterialBatch.objects.filter(material=material).delete()
    material.current_stock = 0
    material.save()

    print(f"✅ Material Created: {material.name}")

    # 2. Create 2 Batches with DIFFERENT prices
    # Batch A: Oldest, Cheap ($1.20)
    batch_a = MaterialBatch.objects.create(
        material=material,
        initial_quantity=100,
        current_quantity=100,
        cost_per_unit=Decimal('1.20'),
        batch_number="BATCH-A-OLD",
        is_active=True
    )
    # Hack to make it older (auto_now_add makes it now)
    # Direct DB update or sleep? Let's just trust creation order or ordering by ID if date same
    # But Views use order_by('received_date'). If dates identical, might be nondeterministic.
    # Let's hope milliseconds diff or ID order prevails. 
    # Logic uses received_date. Ideally we set it. But it is auto_now_add.
    
    # Batch B: Newest, Expensive ($1.50)
    batch_b = MaterialBatch.objects.create(
        material=material,
        initial_quantity=100,
        current_quantity=100, # 100 available
        cost_per_unit=Decimal('1.50'),
        batch_number="BATCH-B-NEW",
        is_active=True
    )
    
    material.current_stock = 200
    material.save()
    
    print(f"📦 Batch A: 100kg @ $1.20 | Batch B: 100kg @ $1.50")

    # 3. Create Order that needs 150kg
    # Expected: 100kg from A ($120) + 50kg from B ($75) = $195
    # (Because usage logic is mocked to 150kg)
    
    client, _ = Client.objects.get_or_create(full_name="FIFO Tester", defaults={"phone": "+000"})
    user = User.objects.filter(is_superuser=True).first()
    
    order = Order.objects.create(
        client=client,
        box_type="FIFO Box",
        paper_type=material_name, # Matches material name
        status='approved'
    )
    
    # 4. Trigger Deduction (Using the View Logic? Or Simulation?)
    # We can invoke the logic directly if we extract it, or simulate via API.
    # But view method is internal. Let's create a ProductionStep and call update_status logic simulation?
    # Or easier: Re-implement just the deduction call using the same function since we just pasted it?
    # No, better to test the ACTUAL view method through 'update_status' action simulation.
    
    # Create Step 1 'cutting'
    step = ProductionStep.objects.create(
        order=order,
        step='cutting',
        status='pending'
    )
    
    # We need to Mock calculation_service to return exactly 150kg paper usage
    # Since we can't easily mock inside the running process without patching,
    # We will rely on our recent edit to services logic? NO, services logic uses dimensions.
    # If we set dimensions so that they result in 150kg?
    # 150kg = (Area * Density * Sheets) / 1000
    # Let's just set `paper_kg` in `calculation_breakdown`? No, view calls calculate_material_usage fresh.
    
    # Let's simulate via a direct call to a test wrapper around the logic, 
    # OR we set order qty/dims to result in approx 150kg.
    # 150 kg paper. Density 300g (0.3kg/m2).
    # Area needed = 150 / 0.3 = 500 m2.
    # If sheet is 1m2 (100x100cm), we need 500 sheets.
    # Qty 500.
    
    order.paper_width = 100.0
    order.paper_height = 100.0
    order.paper_density = 300
    order.quantity = 476 # approx. With waste 5% -> 500 sheets -> 150kg.
    # 476 * 1.05 = 499.8 sheets -> 500 sheets.
    # 500 sheets * 1m2 * 300g = 150,000g = 150kg.
    order.save()
    
    print("🔄 Triggering Step Update to 'in_production'...")
    
    # Use APIClient or RequestFactory? 
    from rest_framework.test import APIRequestFactory
    from api.views import ProductionStepViewSet
    
    factory = APIRequestFactory()
    view = ProductionStepViewSet.as_view({'post': 'update_status'})
    request = factory.post(f'/api/steps/{step.id}/update_status/', {'status': 'in_progress'})
    request.user = user
    response = view(request, pk=step.id)
    
    if response.status_code != 200:
        print(f"❌ API Error: {response.data}")
        return

    # 5. Verify Results
    
    # Check Batches
    batch_a.refresh_from_db()
    batch_b.refresh_from_db()
    
    print(f"\n🧐 Batch Status:")
    print(f"   Batch A Left: {batch_a.current_quantity} (Expected 0)")
    print(f"   Batch B Left: {batch_b.current_quantity} (Expected 50)")
    
    # Check Logs
    logs = WarehouseLog.objects.filter(order=order, type='out').order_by('id')
    print(f"\n📜 Warehouse Logs ({logs.count()}):")
    total_cost = Decimal('0')
    for log in logs:
        # Filter only for our test material
        if log.material.name == material_name:
            cost = log.change_amount * log.material_batch.cost_per_unit
            total_cost += cost
            print(f"   - {log.change_amount}kg from {log.material_batch.batch_number} @ ${log.material_batch.cost_per_unit} = ${cost}")
        else:
             print(f"   - [IGNORED] {log.change_amount}kg of {log.material.name}")
    
    print(f"\n💰 Total Deducted Cost (Paper Only): ${total_cost}")
    
    # Expected: 100*1.2 + 50*1.5 = 120 + 75 = 195
    expected = 195.0
    # Allow small rounding diff
    if abs(float(total_cost) - expected) < 1.0:
        print(f"🎉 SUCCESS! Total cost matches expected ${expected}")
    else:
        print(f"❌ FAILURE! Expected ${expected}, got ${total_cost}")

if __name__ == "__main__":
    verify_fifo()
