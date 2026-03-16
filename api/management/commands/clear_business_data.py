from django.core.management.base import BaseCommand
from api.models import (
    Order, Client, Material, Product, ProductionStep, 
    Invoice, Transaction, ActivityLog, Supplier, 
    MaterialBatch, WarehouseLog, SettingsLog,
    EmployeeEfficiency, MachineSettings, WasteMaterial, 
    Task, Attendance, ProductionLog, ProductionTemplate, 
    TemplateStage, Reservation
)
from django.db import transaction

class Command(BaseCommand):
    help = 'Clears all business data (orders, inventory, transactions, logs) but preserves user accounts.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force deletion without confirmation',
        )

    def handle(self, *args, **options):
        if not options['force']:
            confirm = input("This will PERMANENTLY delete all orders, inventory, transactions and logs. Continue? (y/N): ")
            if confirm.lower() != 'y':
                self.stdout.write(self.style.WARNING('Aborted.'))
                return

        self.stdout.write('Starting database cleanup...')
        
        models_to_clear = [
            ProductionLog,
            ProductionStep,
            Order,
            Invoice,
            Transaction,
            WarehouseLog,
            Reservation,
            MaterialBatch,
            Material,
            WasteMaterial,
            Supplier,
            Product,
            Client,
            Task,
            Attendance,
            EmployeeEfficiency,
            ActivityLog,
            SettingsLog,
            TemplateStage,
            ProductionTemplate
        ]
        
        try:
            with transaction.atomic():
                for model in models_to_clear:
                    count = model.objects.count()
                    if count > 0:
                        self.stdout.write(f'Deleting {count} records from {model.__name__}...')
                        model.objects.all().delete()
                
            self.stdout.write(self.style.SUCCESS('Database cleanup completed successfully. (Users preserved)'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during cleanup: {str(e)}'))
