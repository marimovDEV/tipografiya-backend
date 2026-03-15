"""
Price Locking Service
Handles price locking, versioning, and manual overrides with audit trail.
"""

from django.utils import timezone
from django.db import transaction
from .models import Order, PriceVersion, PricingSettings, SettingsLog
import json


class BasePriceCalculator:
    """
    Calculates the base price of an order using "Scientific Pricing" v4.2.
    Aggregates:
    1. Material Cost (Sheets used * Cost per sheet)
    2. Waste Cost (factored into sheet usage)
    3. Production Cost (Machine time * Hourly rate)
    """
    
    @staticmethod
    def calculate_base_price(order_geometry, quantity, machine_analysis=None, material_cost_per_sheet=0.0):
        """
        :param order_geometry: Layout/Nesting data (sheets_needed)
        :param quantity: Total order quantity
        :param machine_analysis: { 'total_hours': float, ... }
        :param material_cost_per_sheet: Cost of one standard sheet (e.g. 100x70)
        
        Returns: {
            'total_price': float,
            'price_per_unit': float,
            'breakdown': dict
        }
        """
        # 1. Material Cost
        sheets_needed = order_geometry.get('sheets_needed', 0)
        total_material_cost = sheets_needed * material_cost_per_sheet
        
        # 2. Production Cost
        # Default rates (should be in DB Settings)
        MACHINE_HOURLY_RATE = 20.0 # $20/hr
        
        total_machine_hours = 0
        if machine_analysis:
            total_machine_hours = machine_analysis.get('total_hours', 0)
        else:
            # Fallback estimation if no analysis provided
            # Setup (0.25h) + Run (1000/hr)
            setup_h = 0.25
            run_h = quantity / 1000.0
            total_machine_hours = setup_h + run_h
            
        total_production_cost = total_machine_hours * MACHINE_HOURLY_RATE
        
        # 3. Base Total
        base_total = total_material_cost + total_production_cost
        
        # 4. Markup (Profit Margin)
        # Simple tiered markup
        markup_percent = 0.30 # 30% default
        if quantity > 5000: markup_percent = 0.20
        elif quantity < 500: markup_percent = 0.50
        
        final_price = base_total * (1.0 + markup_percent)
        
        return {
            'total_price': round(final_price, 2),
            'price_per_unit': round(final_price / quantity, 4) if quantity > 0 else 0,
            'breakdown': {
                'material_cost': round(total_material_cost, 2),
                'production_cost': round(total_production_cost, 2),
                'margin_percent': markup_percent * 100,
                'sheets_used': sheets_needed,
                'machine_hours': round(total_machine_hours, 2),
                'cost_per_sheet': material_cost_per_sheet,
                'hourly_rate': MACHINE_HOURLY_RATE
            }
        }

class PriceLockService:
    """Service for managing price locking and versioning"""
    
    @staticmethod
    def lock_order_price(order, user):
        """
        Lock the price of an order when approved.
        Creates a price snapshot and version.
        """
        if order.price_locked:
            raise ValueError(f"Order #{order.order_number} price is already locked")
        
        # Get current pricing settings
        settings = PricingSettings.load()
        
        if not settings.price_lock_enabled:
            # Price locking disabled globally
            return False
        
        # Create price version snapshot
        version = PriceVersion.create_snapshot(user)
        
        # Create comprehensive snapshot
        snapshot = {
            'total_price': float(order.total_price) if order.total_price else 0,
            'total_cost': float(order.total_cost) if order.total_cost else 0,
            'price_per_unit': 0,
            'calculation_breakdown': order.calculation_breakdown,
            'pricing_profile_used': order.pricing_profile_used,
            'locked_at': timezone.now().isoformat(),
            'locked_by_user_id': user.id,
            'locked_by_username': user.username,
            'price_version': version.version_number,
        }
        
        # Lock the order
        order.price_locked = True
        order.price_lock_version = version.version_number
        order.price_lock_snapshot = snapshot
        order.save()
        
        return True
    
    @staticmethod
    def unlock_order_price(order, user, reason):
        """
        Unlock price (admin only).
        Creates audit log.
        """
        if not order.price_locked:
            return False
        
        # Log the unlock
        SettingsLog.objects.create(
            user=user,
            setting_type='price_unlock',
            old_value=json.dumps(order.price_lock_snapshot),
            new_value=f"Unlocked: {reason}"
        )
        
        order.price_locked = False
        order.save()
        
        return True
    
    @staticmethod
    def manual_override_price(order, new_price, user, reason):
        """
        Manually override order price with audit trail.
        Requires explanation.
        """
        if not reason or len(reason.strip()) < 10:
            raise ValueError("Override reason must be at least 10 characters")
        
        old_price = order.total_price
        
        # Create audit log
        SettingsLog.objects.create(
            user=user,
            setting_type='price_manual_override',
            old_value=f"Order #{order.order_number}: {old_price}",
            new_value=f"New price: {new_price}. Reason: {reason}"
        )
        
        # Update order
        order.total_price = new_price
        order.manual_override = True
        order.manual_override_reason = reason
        order.manual_override_by = user
        order.save()
        
        return order
    
    @staticmethod
    def can_modify_price(order):
        """Check if order price can be modified"""
        # Cannot modify if locked
        if order.price_locked:
            return False, "Price is locked"
        
        # Cannot modify if in certain statuses
        locked_statuses = ['completed', 'delivered', 'canceled']
        if order.status in locked_statuses:
            return False, f"Cannot modify price in {order.status} status"
        
        return True, None
    
    @staticmethod
    def get_price_history(order):
        """Get price change history for an order"""
        history = []
        
        # Original calculation
        if order.calculation_breakdown:
            history.append({
                'timestamp': order.created_at,
                'action': 'created',
                'price': float(order.total_price) if order.total_price else 0,
                'user': order.created_by.username if order.created_by else 'System'
            })
        
        # Lock event
        if order.price_locked and order.price_lock_snapshot:
            snapshot = order.price_lock_snapshot
            history.append({
                'timestamp': snapshot.get('locked_at'),
                'action': 'locked',
                'price': snapshot.get('total_price'),
                'user': snapshot.get('locked_by_username'),
                'version': snapshot.get('price_version')
            })
        
        # Manual overrides
        if order.manual_override:
            # Get from SettingsLog
            logs = SettingsLog.objects.filter(
                setting_type='price_manual_override',
                old_value__contains=f"Order #{order.order_number}"
            ).order_by('created_at')
            
            for log in logs:
                history.append({
                    'timestamp': log.created_at,
                    'action': 'manual_override',
                    'price': float(order.total_price) if order.total_price else 0,
                    'user': log.user.username if log.user else 'Unknown',
                    'reason': order.manual_override_reason
                })
        
        return sorted(history, key=lambda x: x['timestamp'] or timezone.now())


class ScenarioPricingService:
    """
    Service for applying different pricing scenarios.
    Scenarios: Standard, Express, Night, etc.
    """
    
    @staticmethod
    def get_scenario_multiplier(scenario_name='Standard'):
        """Get price multiplier for a scenario"""
        settings = PricingSettings.load()
        
        if not settings.scenario_pricing:
            # Default scenarios if not configured
            settings.scenario_pricing = {
                'Standard': 1.0,
                'Express': 1.5,
                'Night': 1.3,
                'Economy': 0.9
            }
            settings.save()
        
        return settings.scenario_pricing.get(scenario_name, 1.0)
    
    @staticmethod
    def calculate_with_scenario(base_price, scenario='Standard'):
        """Apply scenario multiplier to base price"""
        multiplier = ScenarioPricingService.get_scenario_multiplier(scenario)
        return base_price * multiplier
    
    @staticmethod
    def get_available_scenarios():
        """Get list of available pricing scenarios"""
        settings = PricingSettings.load()
        
        if not settings.scenario_pricing:
            return {
                'Standard': {'multiplier': 1.0, 'description': 'Normal delivery (5-7 days)'},
                'Express': {'multiplier': 1.5, 'description': 'Fast delivery (2-3 days)'},
                'Night': {'multiplier': 1.3, 'description': 'Night shift production'},
                'Economy': {'multiplier': 0.9, 'description': 'Extended delivery (10+ days)'}
            }
        
        # Convert to detailed format
        scenarios = {}
        for name, multiplier in settings.scenario_pricing.items():
            scenarios[name] = {
                'multiplier': multiplier,
                'description': ScenarioPricingService._get_scenario_description(name)
            }
        
        return scenarios
    
    @staticmethod
    def _get_scenario_description(scenario_name):
        """Get default description for scenario"""
        descriptions = {
            'Standard': 'Normal delivery (5-7 days)',
            'Express': 'Fast delivery (2-3 days)',
            'Night': 'Night shift production',
            'Economy': 'Extended delivery (10+ days)',
            'VIP': 'Premium customer pricing',
            'Wholesale': 'Bulk order discount'
        }
        return descriptions.get(scenario_name, 'Custom pricing scenario')
    
    @staticmethod
    def estimate_delivery_days(scenario='Standard'):
        """Estimate delivery days based on scenario"""
        estimates = {
            'Standard': 5,
            'Express': 2,
            'Night': 3,
            'Economy': 10,
            'VIP': 3,
            'Wholesale': 7
        }
        return estimates.get(scenario, 5)


class CapacityAwareCalculator:
    """
    Advanced deadline calculation considering:
    - Working days (Calendar)
    - Production capacity (Shifts)
    - Current workload
    - Machine availability
    """
    
    @staticmethod
    def calculate_realistic_deadline(order, scenario='Standard'):
        """
        Calculate realistic deadline based on:
        1. Order complexity
        2. Current production queue
        3. Available capacity
        4. Scenario (Express gets priority)
        """
        from .models import Calendar, Shift, Order as OrderModel
        from datetime import timedelta
        
        # Base estimate from scenario
        base_days = ScenarioPricingService.estimate_delivery_days(scenario)
        
        # Complexity factor
        complexity_days = CapacityAwareCalculator._calculate_complexity_days(order)
        
        # Queue factor
        queue_days = CapacityAwareCalculator._calculate_queue_delay()
        
        # Total workdays needed
        if scenario == 'Express':
            # Express bypasses queue
            total_workdays = base_days + complexity_days
        else:
            total_workdays = base_days + complexity_days + queue_days
        
        # Convert to calendar date
        from api.calendar_utils import calculate_deadline
        deadline = calculate_deadline(
            timezone.now().date(),
            total_workdays,
            include_shifts=True
        )
        
        return deadline
    
    @staticmethod
    def _calculate_complexity_days(order):
        """Calculate additional days based on order complexity"""
        complexity = 0
        
        # Quantity factor
        if order.quantity > 1000:
            complexity += 2
        elif order.quantity > 500:
            complexity += 1
        
        # Colors factor
        if order.print_colors:
            if '4+4' in order.print_colors or '5+5' in order.print_colors:
                complexity += 1
        
        # Lacquer factor
        if order.lacquer_type and order.lacquer_type != 'none':
            complexity += 1
        
        # Additional processing
        if order.additional_processing:
            complexity += 1
        
        return complexity
    
    @staticmethod
    def _calculate_queue_delay():
        """Calculate delay based on current production queue"""
        from .models import Order as OrderModel
        
        # Count active orders
        active_count = OrderModel.objects.filter(
            status__in=['approved', 'in_production']
        ).count()
        
        # More orders = more delay
        if active_count > 20:
            return 3
        elif active_count > 10:
            return 2
        elif active_count > 5:
            return 1
        
        return 0
    
    @staticmethod
    def get_capacity_status():
        """Get current production capacity status"""
        from .models import Order as OrderModel, Shift
        
        active_orders = OrderModel.objects.filter(
            status__in=['approved', 'in_production']
        ).count()
        
        # Get total shift capacity
        active_shifts = Shift.objects.filter(is_active=True)
        total_capacity_hours = sum(
            shift.duration_hours * float(shift.capacity_multiplier)
            for shift in active_shifts
        )
        
        # Estimate capacity usage
        # Assume average order takes 4 hours
        estimated_hours_needed = active_orders * 4
        capacity_percentage = (estimated_hours_needed / (total_capacity_hours * 5)) * 100 if total_capacity_hours > 0 else 0
        
        return {
            'active_orders': active_orders,
            'capacity_percentage': min(capacity_percentage, 100),
            'status': 'high' if capacity_percentage > 80 else 'medium' if capacity_percentage > 50 else 'low',
            'estimated_queue_days': CapacityAwareCalculator._calculate_queue_delay()
        }
