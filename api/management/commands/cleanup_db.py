from django.core.management.base import BaseCommand
from api.models import (
    Order, Transaction, Client, Product, WasteMaterial, 
    WarehouseLog, ProductionStep, DesignFile, OrderGeometry,
    User, ProductionTemplate, Material, Supplier
)

class Command(BaseCommand):
    help = 'Cleans up transactional data from the database while keeping templates and employees'

    def handle(self, *args, **options):
        self.stdout.write("Starting database cleanup...")

        # 1. Delete Orders and related transactional data
        # Note: Some deletions might happen automatically via CASCADE, 
        # but we do them explicitly to be safe and report counts.
        
        models_to_delete = [
            (OrderGeometry, "Order Geometry"),
            (DesignFile, "Design Files"),
            (ProductionStep, "Production Steps"),
            (WarehouseLog, "Warehouse Logs"),
            (WasteMaterial, "Waste Material"),
            (Order, "Orders"),
            (Transaction, "Transactions"),
            (Product, "Products"),
            (Client, "Clients"),
        ]

        for model, label in models_to_delete:
            count, _ = model.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} {label}"))

        self.stdout.write(self.style.MIGRATE_HEADING("Retained data summary:"))
        self.stdout.write(f"- Users: {User.objects.count()}")
        self.stdout.write(f"- Production Templates: {ProductionTemplate.objects.count()}")
        self.stdout.write(f"- Materials: {Material.objects.count()}")
        self.stdout.write(f"- Suppliers: {Supplier.objects.count()}")

        self.stdout.write(self.style.SUCCESS("Database cleanup completed successfully!"))
