"""
Accounting Service - Double-Entry Bookkeeping System
Automatically creates journal entries for all financial transactions.
"""

from django.db import transaction, models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal


class AccountingService:
    """
    Double-entry accounting service.
    Every transaction has equal debits and credits.
    """
    
    @staticmethod
    def setup_default_chart_of_accounts():
        """
        Create standard chart of accounts for printing business.
        Should be run once during system setup.
        """
        from api.models import ChartOfAccounts
        
        accounts = [
            # ASSETS (1000-1999)
            {'code': '1000', 'name': 'Naqd pul (Cash)', 'account_type': 'asset', 'parent': None},
            {'code': '1100', 'name': 'Bank hisobi', 'account_type': 'asset', 'parent': None},
            {'code': '1200', 'name': 'Debitorlar (Accounts Receivable)', 'account_type': 'asset', 'parent': None},
            {'code': '1300', 'name': 'Xom ashyo (Raw Materials)', 'account_type': 'asset', 'parent': None},
            {'code': '1400', 'name': 'Tayyor mahsulot (Finished Goods)', 'account_type': 'asset', 'parent': None},
            {'code': '1500', 'name': 'Asosiy vositalar (Fixed Assets)', 'account_type': 'asset', 'parent': None},
            
            # LIABILITIES (2000-2999)
            {'code': '2000', 'name': 'Kreditorlar (Accounts Payable)', 'account_type': 'liability', 'parent': None},
            {'code': '2100', 'name': 'Qarz (Loans)', 'account_type': 'liability', 'parent': None},
            {'code': '2200', 'name': 'Ish haqi to\'lash (Salaries Payable)', 'account_type': 'liability', 'parent': None},
            
            # EQUITY (3000-3999)
            {'code': '3000', 'name': 'Ustav kapitali (Share Capital)', 'account_type': 'equity', 'parent': None},
            {'code': '3100', 'name': 'Taqsimlanmagan foyda (Retained Earnings)', 'account_type': 'equity', 'parent': None},
            
            # REVENUE (4000-4999)
            {'code': '4000', 'name': 'Sotuv daromadi (Sales Revenue)', 'account_type': 'revenue', 'parent': None},
            {'code': '4100', 'name': 'Boshqa daromadlar (Other Income)', 'account_type': 'revenue', 'parent': None},
            
            # EXPENSES (5000-5999)
            {'code': '5000', 'name': 'Xom ashyo xarajati (Material Cost)', 'account_type': 'expense', 'parent': None},
            {'code': '5100', 'name': 'Ish haqi (Salaries)', 'account_type': 'expense', 'parent': None},
            {'code': '5200', 'name': 'Operatsion xarajatlar (Operating Expenses)', 'account_type': 'expense', 'parent': None},
            {'code': '5300', 'name': 'Mashina amortizatsiya (Depreciation)', 'account_type': 'expense', 'parent': None},
        ]
        
        created_accounts = {}
        for acc_data in accounts:
            account, created = ChartOfAccounts.objects.get_or_create(
                code=acc_data['code'],
                defaults=acc_data
            )
            created_accounts[acc_data['code']] = account
        
        return created_accounts
    
    @staticmethod
    def record_sale(order, user):
        """
        Record sale when order completed.
        DR: Accounts Receivable (1200)
        CR: Sales Revenue (4000)
        """
        from api.models import ChartOfAccounts, JournalEntry, JournalEntryLine
        
        # Get accounts
        receivable = ChartOfAccounts.objects.get(code='1200')  # Debitorlar
        revenue = ChartOfAccounts.objects.get(code='4000')  # Sotuv daromadi
        
        # Create journal entry
        entry = JournalEntry.objects.create(
            date=timezone.now().date(),
            entry_type='sale',
            description=f"Sotuv: Buyurtma #{order.order_number} - {order.client.full_name}",
            reference=f"ORD-{order.order_number}",
            order=order,
            created_by=user
        )
        
        amount = order.total_price or 0
        
        # Debit: Accounts Receivable (increase asset)
        JournalEntryLine.objects.create(
            entry=entry,
            account=receivable,
            debit=amount,
            credit=0,
            notes=f"Mijoz qarzi: {order.client.full_name}"
        )
        
        # Credit: Sales Revenue (increase revenue)
        JournalEntryLine.objects.create(
            entry=entry,
            account=revenue,
            debit=0,
            credit=amount,
            notes=f"Sotuv daromadi"
        )
        
        return entry
    
    @staticmethod
    def record_payment(transaction_obj, user):
        """
        Record payment received.
        DR: Cash (1000)
        CR: Accounts Receivable (1200)
        """
        from api.models import ChartOfAccounts, JournalEntry, JournalEntryLine
        
        cash = ChartOfAccounts.objects.get(code='1000')  # Naqd pul
        receivable = ChartOfAccounts.objects.get(code='1200')  # Debitorlar
        
        entry = JournalEntry.objects.create(
            date=transaction_obj.date,
            entry_type='payment',
            description=f"To'lov qabul qilindi: {transaction_obj.client.full_name if transaction_obj.client else 'N/A'}",
            transaction=transaction_obj,
            created_by=user
        )
        
        amount = transaction_obj.amount
        
        # Debit: Cash (increase asset)
        JournalEntryLine.objects.create(
            entry=entry,
            account=cash,
            debit=amount,
            credit=0,
            notes=f"{transaction_obj.payment_method}"
        )
        
        # Credit: Accounts Receivable (decrease asset)
        JournalEntryLine.objects.create(
            entry=entry,
            account=receivable,
            debit=0,
            credit=amount,
            notes="Mijoz qarzi kamaydi"
        )
        
        return entry
    
    @staticmethod
    def record_material_purchase(batch, user):
        """
        Record material purchase.
        DR: Raw Materials (1300)
        CR: Accounts Payable (2000)
        """
        from api.models import ChartOfAccounts, JournalEntry, JournalEntryLine
        
        materials = ChartOfAccounts.objects.get(code='1300')  # Xom ashyo
        payable = ChartOfAccounts.objects.get(code='2000')  # Kreditorlar
        
        entry = JournalEntry.objects.create(
            date=batch.received_date,
            entry_type='purchase',
            description=f"Xom ashyo xaridi: {batch.material.name}",
            reference=f"BATCH-{batch.batch_number}",
            created_by=user
        )
        
        amount = batch.initial_quantity * batch.cost_per_unit
        
        # Debit: Materials (increase asset)
        JournalEntryLine.objects.create(
            entry=entry,
            account=materials,
            debit=amount,
            credit=0,
            notes=f"{batch.initial_quantity} x {batch.cost_per_unit}"
        )
        
        # Credit: Accounts Payable (increase liability)
        JournalEntryLine.objects.create(
            entry=entry,
            account=payable,
            debit=0,
            credit=amount,
            notes=f"Ta'minotchi: {batch.supplier.name}"
        )
        
        return entry
    
    @staticmethod
    def get_trial_balance(as_of_date=None):
        """
        Generate trial balance (all accounts with debits/credits).
        Should balance: Total Debits = Total Credits
        """
        from api.models import ChartOfAccounts, JournalEntryLine
        
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        accounts = ChartOfAccounts.objects.filter(is_active=True).order_by('code')
        
        trial_balance = []
        total_debits = 0
        total_credits = 0
        
        for account in accounts:
            # Get all journal entry lines for this account
            lines = JournalEntryLine.objects.filter(
                account=account,
                entry__date__lte=as_of_date
            ).aggregate(
                total_debit=models.Sum('debit'),
                total_credit=models.Sum('credit')
            )
            
            debit_sum = lines['total_debit'] or 0
            credit_sum = lines['total_credit'] or 0
            
            # Calculate balance based on account type
            if account.account_type in ['asset', 'expense']:
                balance = debit_sum - credit_sum
                balance_type = 'DR' if balance >= 0 else 'CR'
            else:  # liability, equity, revenue
                balance = credit_sum - debit_sum
                balance_type = 'CR' if balance >= 0 else 'DR'
            
            if balance != 0:  # Only show accounts with balance
                trial_balance.append({
                    'code': account.code,
                    'name': account.name,
                    'account_type': account.account_type,
                    'debit': float(debit_sum),
                    'credit': float(credit_sum),
                    'balance': abs(float(balance)),
                    'balance_type': balance_type
                })
                
                total_debits += debit_sum
                total_credits += credit_sum
        
        return {
            'as_of_date': as_of_date.isoformat(),
            'accounts': trial_balance,
            'total_debits': float(total_debits),
            'total_credits': float(total_credits),
            'is_balanced': abs(total_debits - total_credits) < 0.01
        }
    
    @staticmethod
    def get_balance_sheet(as_of_date=None):
        """
        Generate balance sheet: Assets = Liabilities + Equity
        """
        from api.models import ChartOfAccounts
        
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        assets = []
        liabilities = []
        equity = []
        
        accounts = ChartOfAccounts.objects.filter(is_active=True)
        
        for account in accounts:
            balance = account.balance
            
            if balance != 0:
                account_data = {
                    'code': account.code,
                    'name': account.name,
                    'balance': float(abs(balance))
                }
                
                if account.account_type == 'asset':
                    assets.append(account_data)
                elif account.account_type == 'liability':
                    liabilities.append(account_data)
                elif account.account_type == 'equity':
                    equity.append(account_data)
        
        total_assets = sum(a['balance'] for a in assets)
        total_liabilities = sum(l['balance'] for l in liabilities)
        total_equity = sum(e['balance'] for e in equity)
        
        return {
            'as_of_date': as_of_date.isoformat(),
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'total_equity': total_equity,
            'is_balanced': abs(total_assets - (total_liabilities + total_equity)) < 0.01
        }


class KPICalculator:
    """Advanced KPI calculations for business intelligence"""
    
    @staticmethod
    def calculate_gross_margin(start_date=None, end_date=None):
        """
        Gross Margin % = (Revenue - COGS) / Revenue × 100
        """
        from api.models import Order
        
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        orders = Order.objects.filter(
            status__in=['completed', 'delivered'],
            completed_at__gte=start_date,
            completed_at__lte=end_date
        )
        
        cost = 0 # Cost logic removed
        
        gross_profit = revenue - cost
        gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0
        
        return {
            'period': f"{start_date.date()} to {end_date.date()}",
            'total_revenue': revenue,
            'total_cost': cost,
            'gross_profit': gross_profit,
            'gross_margin_percent': round(gross_margin, 2),
            'order_count': orders.count()
        }
    
    @staticmethod
    def calculate_order_profitability(order_id):
        """Detailed profitability analysis for single order"""
        from api.models import Order, ReworkLog
        
        order = Order.objects.get(id=order_id)
        
        revenue = float(order.total_price or 0)
        base_cost = 0  # Cost removed
        
        # Add rework costs
        rework_total = 0  # Cost removed
        total_cost = base_cost + rework_total
        
        profit = revenue - total_cost
        margin = (profit / revenue * 100) if revenue > 0 else 0
        
        return {
            'order_number': order.order_number,
            'client': order.client.full_name,
            'revenue': revenue,
            'base_cost': base_cost,
            'rework_cost': rework_total,
            'total_cost': total_cost,
            'profit': profit,
            'profit_margin_percent': round(margin, 2),
            'profitability_status': 'high' if margin > 25 else 'medium' if margin > 15 else 'low'
        }
    
    @staticmethod
    def calculate_employee_roi(employee_id, period_days=30):
        """
        Employee ROI = Revenue Generated / Labor Cost × 100
        """
        from api.models import User, ProductionStep, EmployeeEfficiency
        
        employee = User.objects.get(id=employee_id)
        start_date = timezone.now() - timedelta(days=period_days)
        
        # Get completed steps
        steps = ProductionStep.objects.filter(
            assigned_to=employee,
            status='completed',
            completed_at__gte=start_date
        ).select_related('order')
        
        # Calculate revenue contribution
        total_revenue = 0
        for step in steps:
            if step.order.total_price:
                # Approximate contribution (revenue / steps count)
                step_count = step.order.production_steps.count()
                contribution = float(step.order.total_price) / step_count if step_count > 0 else 0
                total_revenue += contribution
        
        # Get labor cost
        efficiency = EmployeeEfficiency.objects.filter(
            employee=employee
        ).order_by('-effective_from').first()
        
        hours_worked = 0
        for step in steps:
            if step.started_at and step.completed_at:
                duration = (step.completed_at - step.started_at).total_seconds() / 3600
                hours_worked += duration
        
        labor_cost = 0
        if efficiency:
            labor_cost = hours_worked * float(efficiency.hourly_labor_cost)
        
        roi = ((total_revenue - labor_cost) / labor_cost * 100) if labor_cost > 0 else 0
        
        return {
            'employee': employee.username,
            'period_days': period_days,
            'steps_completed': steps.count(),
            'hours_worked': round(hours_worked, 2),
            'revenue_generated': round(total_revenue, 2),
            'labor_cost': round(labor_cost, 2),
            'profit_contribution': round(total_revenue - labor_cost, 2),
            'roi_percent': round(roi, 2)
        }
    
    @staticmethod
    def calculate_machine_roi(machine_id, period_days=90):
        """
        Machine ROI considering revenue vs costs (depreciation, maintenance, downtime)
        """
        from api.models import MachineSettings, MachineDowntime, Order
        
        machine = MachineSettings.objects.get(id=machine_id)
        start_date = timezone.now() - timedelta(days=period_days)
        
        # Total operational hours (period - downtime)
        total_hours = period_days * 24
        downtimes = MachineDowntime.objects.filter(
            machine=machine,
            started_at__gte=start_date
        )
        
        downtime_hours = sum(dt.duration_hours for dt in downtimes)
        productive_hours = total_hours - downtime_hours
        
        # Revenue generated (approximate based on machine type usage)
        revenue_generated = productive_hours * float(machine.hourly_rate)
        
        # Costs
        operational_cost = productive_hours * float(machine.hourly_rate) * 0.3  # 30% operational
        maintenance_cost = downtimes.filter(reason='maintenance').count() * 100000  # avg maintenance
        
        total_cost = operational_cost + maintenance_cost
        profit = revenue_generated - total_cost
        roi = (profit / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'machine': machine.machine_name,
            'period_days': period_days,
            'total_hours': total_hours,
            'downtime_hours': round(downtime_hours, 2),
            'productive_hours': round(productive_hours, 2),
            'availability_percent': round((productive_hours / total_hours * 100), 2),
            'revenue_generated': round(revenue_generated, 2),
            'operational_cost': round(operational_cost, 2),
            'maintenance_cost': round(maintenance_cost, 2),
            'total_cost': round(total_cost, 2),
            'profit': round(profit, 2),
            'roi_percent': round(roi, 2)
        }
