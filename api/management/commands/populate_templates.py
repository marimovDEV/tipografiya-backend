from django.core.management.base import BaseCommand
from api.models import ProductTemplate

class Command(BaseCommand):
    help = 'Flushes existing templates and populates the database with diverse standard product templates'

    def handle(self, *args, **options):
        # 1. Flush existing templates
        count_deleted, _ = ProductTemplate.objects.all().delete()
        self.stdout.write(self.style.WARNING(f'Deleted {count_deleted} existing templates.'))

        # 2. Define Standard Templates
        templates = [
            {
                'name': 'Standard Pizza Box (30cm)',
                'category': 'pizza_box',
                'layer_count': 3,
                'default_waste_percent': 12.00,
                'description': 'Classic corrugated pizza box, strong and heat retaining.',
                'default_width': 30.0,
                'default_height': 30.0,
                'default_depth': 4.0,
                'is_parametric': True
            },
            {
                'name': 'E-commerce Mailer Box',
                'category': 'box_3layer',
                'layer_count': 3,
                'default_waste_percent': 15.00,
                'description': 'Self-locking mailer box allowed for shipping without tape. Perfect for subscription boxes.',
                'default_width': 25.0,
                'default_height': 20.0,
                'default_depth': 8.0,
                'is_parametric': True
            },
            {
                'name': 'Luxury Gift Bag',
                'category': 'gift_bag',
                'layer_count': 1,
                'default_waste_percent': 8.00,
                'description': 'Premium paper bag with rope handles and reinforced bottom.',
                'default_width': 22.0,
                'default_height': 10.0, # Depth for bag usually
                'default_depth': 30.0, # Height for bag
                'is_parametric': True
            },
            {
                'name': 'Hexagonal Cookie Box',
                'category': 'cookie_box',
                'layer_count': 1,
                'default_waste_percent': 18.00,
                'description': 'Six-sided creative box for cookies and sweets.',
                'default_width': 18.0,
                'default_height': 18.0,
                'default_depth': 6.0,
                'is_parametric': True
            },
            {
                'name': 'Pharma Box (Standard)',
                'category': 'medicine_box_1layer',
                'layer_count': 1,
                'default_waste_percent': 5.00,
                'description': 'Standard tuck-end box for medicine bottles or blisters.',
                'default_width': 5.0,
                'default_height': 5.0,
                'default_depth': 12.0,
                'is_parametric': True
            },
            {
                'name': 'Large Shipping Carton',
                'category': 'box_3layer',
                'layer_count': 3,
                'default_waste_percent': 10.00,
                'description': 'Heavy duty RSC shipping carton for moving or storage.',
                'default_width': 50.0,
                'default_height': 40.0,
                'default_depth': 40.0,
                'is_parametric': True
            },
            {
                'name': 'Takeaway Noodle Box',
                'category': 'food_box',
                'layer_count': 1,
                'default_waste_percent': 14.00,
                'description': 'Leak-proof food container with folding top.',
                'default_width': 12.0,
                'default_height': 10.0,
                'default_depth': 12.0,
                'is_parametric': True
            },
            {
                'name': 'Rigid Gift Box (2-Piece)',
                'category': 'box_2layer',
                'layer_count': 2,
                'default_waste_percent': 20.00,
                'description': 'Luxury rigid box with separate lid and base.',
                'default_width': 20.0,
                'default_height': 20.0,
                'default_depth': 10.0,
                'is_parametric': True
            }
        ]

        # 3. Create new templates
        created_count = 0
        for t_data in templates:
            ProductTemplate.objects.create(**t_data)
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully reset database: {count_deleted} removed, {created_count} new templates created.'))
