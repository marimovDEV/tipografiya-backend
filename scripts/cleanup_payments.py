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
    
    # Identify potential duplicates across client, amount, category and date
    # We remove the order_link requirement to catch more duplicates
    duplicates = Transaction.objects.values(
        'client', 'amount', 'category', 'date'
    ).annotate(
        count=Count('id')
    ).filter(
        count__gt=1
    )
    
    total_deleted = 0
    
    for d in duplicates:
        # Find all records for this specific set of criteria
        qs = Transaction.objects.filter(
            client=d['client'],
            amount=d['amount'],
            category=d['category'],
            date=d['date']
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
