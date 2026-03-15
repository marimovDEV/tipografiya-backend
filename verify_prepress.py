import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import DesignFile, Order, Client, User

def verify_prepress_locking():
    print("🚀 Verifying Prepress Locking & Digital Signature...")
    
    # Setup
    user = User.objects.filter(is_superuser=True).first()
    client, _ = Client.objects.get_or_create(full_name="Prepress Client")
    import random
    suffix = random.randint(1000, 9999)
    order = Order.objects.create(
        client=client, 
        order_number=f"PREPRESS-{suffix}",
        status='pending'
    )
    
    # 1. Create Version 1
    # Mocking a file (just a string for FileField content/name in test if not strict)
    # Actually FileField needs a File object or we just set name manually for DB test.
    
    v1 = DesignFile.objects.create(
        order=order,
        version=1,
        status='pending',
        uploaded_by=user
    )
    print(f"📁 Created v1 (Pending): {v1}")
    
    # 2. Create Version 2 (New update)
    v2 = DesignFile.objects.create(
        order=order,
        version=2,
        status='pending',
        uploaded_by=user
    )
    print(f"📁 Created v2 (Pending): {v2}")
    
    # 3. Approve v2 (Should Archive v1 if it was approved? No, v1 is pending.)
    # Let's say we approved v1 before.
    v1.approve(user)
    print(f"✅ Approved v1. Status: {v1.status}")
    
    # Now verify v1 is approved.
    v1.refresh_from_db()
    if v1.status != 'approved':
        print("❌ Error: v1 should be approved")
        return

    # 4. Now Approve v2 (The latest one) -> Should auto-archive v1
    print("🔄 Approving v2 (Should archive v1)...")
    v2.approve(user)
    
    v1.refresh_from_db()
    v2.refresh_from_db()
    
    print(f"   - v1 Status: {v1.status} (Expected: archived)")
    print(f"   - v2 Status: {v2.status} (Expected: approved)")
    print(f"   - v2 Signed By: {v2.approved_by.username}")
    print(f"   - v2 Signed At: {v2.approved_at}")
    
    if v1.status == 'archived' and v2.status == 'approved':
        print("🎉 SUCCESS: Version locking and archiving works!")
    else:
        print("❌ FAILURE: Archiving logic incorrect.")

if __name__ == "__main__":
    verify_prepress_locking()
