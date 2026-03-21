import logging
from decimal import Decimal
from django.db.models import F
from .models import Material, MaterialBatch, WarehouseLog, ActivityLog
from .services import CalculationService
from django.forms.models import model_to_dict

logger = logging.getLogger(__name__)

class InventoryException(Exception):
    pass

class InventoryService:
    @staticmethod
    def validate_and_deduct_order_materials(order, user):
        order_data = model_to_dict(order)
        usage = CalculationService.calculate_material_usage(order_data)
        
        materials_needed = []
        
        # Paper
        paper_kg = Decimal(str(usage.get('paper_kg', 0)))
        if paper_kg > 0:
            paper_name = f"{order.paper_type} {order.paper_density}g/m²"
            material = Material.objects.filter(name__iexact=paper_name).first()
            if not material:
                 material = Material.objects.filter(name__icontains=order.paper_type, category='qogoz').first()
            
            if not material:
                raise InventoryException(f"Qog'oz ({paper_name}) omborda topilmadi.")
                
            if material.current_stock < paper_kg:
                raise InventoryException(f"Qog'oz yetarli emas. Kerak: {paper_kg:.2f} kg, Omborda: {material.current_stock:.2f} kg.")
                
            materials_needed.append({'material': material, 'amount': paper_kg, 'name': 'Qog\'oz'})
            
        # Ink
        ink_kg = Decimal(str(usage.get('ink_kg', 0)))
        if ink_kg > 0:
            ink = Material.objects.filter(name__icontains="Bo'yoq").first()
            if not ink:
                raise InventoryException("Bo'yoq omborda topilmadi.")
            if ink.current_stock < ink_kg:
                raise InventoryException(f"Bo'yoq yetarli emas. Kerak: {ink_kg:.2f} kg, Omborda: {ink.current_stock:.2f} kg.")
            materials_needed.append({'material': ink, 'amount': ink_kg, 'name': "Bo'yoq"})
            
        # Lacquer
        lacquer_kg = Decimal(str(usage.get('lacquer_kg', 0)))
        if lacquer_kg > 0:
            l_type = getattr(order, 'lacquer_type', None)
            if l_type and l_type != 'none':
                lacquer = Material.objects.filter(name__icontains=l_type, category='lak').first()
                if not lacquer:
                    raise InventoryException(f"Lak ({l_type}) omborda topilmadi.")
                if lacquer.current_stock < lacquer_kg:
                    raise InventoryException(f"Lak yetarli emas. Kerak: {lacquer_kg:.2f} kg, Omborda: {lacquer.current_stock:.2f} kg.")
                materials_needed.append({'material': lacquer, 'amount': lacquer_kg, 'name': 'Lak'})
                
        total_actual_cost = Decimal('0')
        all_deduction_details = []
        
        def deduct_material_fifo(material_obj, amount_needed):
            actual_cost = Decimal('0')
            deducted_total = Decimal('0')
            logs = []
            remaining = amount_needed
            
            batches = MaterialBatch.objects.filter(
                material=material_obj, 
                is_active=True, 
                current_quantity__gt=0
            ).order_by('received_date')
            
            from django.db import transaction as db_transaction
            with db_transaction.atomic():
                for batch in batches:
                    if remaining <= 0: break
                    qty_in_batch = Decimal(str(batch.current_quantity))
                    deduct = min(qty_in_batch, remaining)
                    
                    batch.current_quantity = F('current_quantity') - deduct
                    remaining -= deduct
                    
                    batch_cost = deduct * Decimal(str(batch.cost_per_unit))
                    actual_cost += batch_cost
                    deducted_total += deduct
                    
                    batch.save()
                    batch.refresh_from_db()
                    if batch.current_quantity <= 0:
                        batch.is_active = False
                        batch.save(update_fields=['is_active'])
                    
                    WarehouseLog.objects.create(
                        material=material_obj,
                        material_batch=batch,
                        change_amount=deduct,
                        type='out',
                        order=order,
                        user=user,
                        notes=f"Ishlab chiqarish (Buyurtma #{order.order_number})"
                    )
                    logs.append(f"{material_obj.name} (Lot: {batch.batch_number}): -{deduct:.2f}")
                
                material_obj.current_stock = F('current_stock') - deducted_total
                material_obj.save()
            return actual_cost, logs

        from django.db import transaction as db_transaction
        try:
            with db_transaction.atomic():
                for item in materials_needed:
                    cost, logs = deduct_material_fifo(item['material'], item['amount'])
                    total_actual_cost += cost
                    all_deduction_details.extend(logs)
                
                if total_actual_cost > 0:
                    order.total_cost = total_actual_cost
                    order.save(update_fields=['total_cost'])
                    ActivityLog.objects.create(
                        user=user,
                        action=f"Materiallar yechildi (#{order.order_number})",
                        details=", ".join(all_deduction_details) + f" | Tannarx: {total_actual_cost:.2f}"
                    )
                return True
        except Exception as e:
            logger.error(f"Error deducting: {e}")
            ActivityLog.objects.create(user=user, action=f"Material yechish xatosi (#{order.order_number})", details=str(e))
            raise InventoryException(f"Material yechishda xatolik: {e}")
