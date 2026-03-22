import os
import sys
import django
from django.db.models import Count

# Setup Django environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import Transaction

def cleanup_duplicate_payments():
    print("Duduplat to'lovlarni tozalash boshlandi...")
    
    # Identify potential duplicates across order_link, client, amount, and category
    duplicates = Transaction.objects.values(
        'order_link', 'client', 'amount', 'category'
    ).annotate(
        count=Count('id')
    ).filter(
        count__gt=1,
        order_link__isnull=False # Only cleanup if linked to an order
    )
    
    total_deleted = 0
    
    for d in duplicates:
        # Find all records for this specific set of criteria
        qs = Transaction.objects.filter(
            order_link=d['order_link'],
            client=d['client'],
            amount=d['amount'],
            category=d['category']
        ).order_by('created_at')
        
        # Keep the first one, delete the rest
        first_id = qs.first().id
        to_delete = qs.exclude(id=first_id)
        count = to_delete.count()
        
        print(f"Buyurtma {d['order_link']} uchun {count} ta dublikat o'chirilmoqda...")
        to_delete.delete()
        total_deleted += count
        
    print(f"Tugallandi. Jami {total_deleted} ta dublikat o'chirildi.")

if __name__ == "__main__":
    cleanup_duplicate_payments()
