"""
Phase 5: Financial Module API Views
Accounting, KPI, profitability, and ROI endpoints.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone
from datetime import timedelta
from .models import (
    Order, User, MachineSettings, ChartOfAccounts, 
    Transaction, ProductionStep, Material, WarehouseLog,
    MonthlyPlan
)
from .accounting import AccountingService, KPICalculator
from django.db import models
from django.db.models import F, Sum, Count, Avg, ExpressionWrapper, DecimalField


class SetupAccountsView(APIView):
    """Setup default chart of accounts (run once)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        # Admin only
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        
        accounts = AccountingService.setup_default_chart_of_accounts()
        
        return Response({
            'status': 'success',
            'message': f'{len(accounts)} accounts created',
            'accounts': [{'code': acc.code, 'name': acc.name} for acc in accounts.values()]
        })


class TrialBalanceView(APIView):
    """Get trial balance report"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        as_of_date_str = request.query_params.get('as_of_date')
        
        if as_of_date_str:
            from datetime import datetime
            as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d').date()
        else:
            as_of_date = None
        
        trial_balance = AccountingService.get_trial_balance(as_of_date)
        
        return Response(trial_balance)


class BalanceSheetView(APIView):
    """Get  balance sheet"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        as_of_date_str = request.query_params.get('as_of_date')
        
        if as_of_date_str:
            from datetime import datetime
            as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d').date()
        else:
            as_of_date = None
        
        balance_sheet = AccountingService.get_balance_sheet(as_of_date)
        
        return Response(balance_sheet)


class GrossMarginKPIView(APIView):
    """Calculate gross margin KPI"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        kpi = KPICalculator.calculate_gross_margin(start_date, end_date)
        
        return Response(kpi)


class OrderProfitabilityView(APIView):
    """Get profitability analysis for an order"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, order_id):
        try:
            analysis = KPICalculator.calculate_order_profitability(order_id)
            return Response(analysis)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)


class EmployeeROIView(APIView):
    """Calculate employee ROI"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, employee_id):
        days = int(request.query_params.get('days', 30))
        
        try:
            roi = KPICalculator.calculate_employee_roi(employee_id, days)
            return Response(roi)
        except User.DoesNotExist:
            return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)


class MachineROIView(APIView):
    """Calculate machine ROI"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, machine_id):
        days = int(request.query_params.get('days', 90))
        
        try:
            roi = KPICalculator.calculate_machine_roi(machine_id, days)
            return Response(roi)
        except MachineSettings.DoesNotExist:
            return Response({'error': 'Machine not found'}, status=status.HTTP_404_NOT_FOUND)


class FinancialDashboardView(APIView):
    """Comprehensive financial dashboard"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Get period
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Gross margin
        gross_margin = KPICalculator.calculate_gross_margin(start_date, end_date)
        
        # Balance sheet
        balance_sheet = AccountingService.get_balance_sheet()
        
        # Cash flow (simplified)
        transactions = Transaction.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        )
        
        income_total = transactions.filter(type='income').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        expense_total = transactions.filter(type='expense').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        net_cash_flow = float(income_total) - float(expense_total)
        
        # Rentability
        rentability = (net_cash_flow / float(income_total) * 100) if income_total > 0 else 0
        
        # Average Check
        order_count = Order.objects.filter(
            status__in=['completed', 'delivered'],
            completed_at__gte=start_date
        ).count()
        average_check = (float(income_total) / order_count) if order_count > 0 else 0
        
        # Daily Financial Dynamics (Last 30 days)
        daily_dynamics = []
        for i in range(days):
            target_date = (end_date - timedelta(days=i)).date()
            daily_inc = Transaction.objects.filter(type='income', date=target_date).aggregate(Sum('amount'))['amount__sum'] or 0
            daily_exp = Transaction.objects.filter(type='expense', date=target_date).aggregate(Sum('amount'))['amount__sum'] or 0
            daily_dynamics.append({
                'date': target_date.isoformat(),
                'income': float(daily_inc),
                'expense': float(daily_exp),
                'profit': float(daily_inc - daily_exp)
            })
        daily_dynamics.reverse()
        
        # Production Bottlenecks (Average time per step type)
        # We look at completed steps in the period
        step_bottlenecks = ProductionStep.objects.filter(
            status='completed',
            completed_at__gte=start_date
        ).values('step').annotate(
            avg_duration_minutes=Avg(
                ExpressionWrapper(
                    F('completed_at') - F('started_at'),
                    output_field=models.DurationField()
                )
            )
        ).order_by('-avg_duration_minutes')
        
        bottleneck_data = []
        for b in step_bottlenecks:
            # Convert duration to minutes
            if b['avg_duration_minutes']:
                total_seconds = b['avg_duration_minutes'].total_seconds()
                minutes = round(total_seconds / 60, 1)
                bottleneck_data.append({
                    'process': b['step'],
                    'avg_time_min': minutes
                })
        
        # Employee Ranking (Quantity produced)
        employee_ranking = ProductionStep.objects.filter(
            status='completed',
            completed_at__gte=start_date,
            assigned_to__isnull=False
        ).values(
            'assigned_to__first_name', 
            'assigned_to__last_name'
        ).annotate(
            total_produced=Sum('quantity_produced')
        ).order_by('-total_produced')[:5]
        
        ranking_data = []
        for r in employee_ranking:
            ranking_data.append({
                'name': f"{r['assigned_to__first_name']} {r['assigned_to__last_name']}",
                'produced': r['total_produced'] or 0
            })
            
        # Material Consumption (Warehouse Summary)
        material_consumption = WarehouseLog.objects.filter(
            type='out',
            created_at__gte=start_date
        ).values('material__name').annotate(
            total_usage=Sum('change_amount')
        ).order_by('-total_usage')[:5]
        
        material_data = []
        for m in material_consumption:
            material_data.append({
                'material': m['material__name'],
                'usage': float(m['total_usage'] or 0)
            })

        return Response({
            'period': f"{start_date.date()} to {end_date.date()}",
            'gross_margin': gross_margin,
            'balance_sheet_summary': {
                'total_assets': balance_sheet['total_assets'],
                'total_liabilities': balance_sheet['total_liabilities'],
                'total_equity': balance_sheet['total_equity']
            },
            'cash_flow': {
                'income': float(income_total),
                'expenses': float(expense_total),
                'net': net_cash_flow,
                'rentability': round(rentability, 1),
                'average_check': round(average_check, 0)
            },
            'daily_dynamics': daily_dynamics,
            'top_profitable_orders': top_orders_data,
            'production_bottlenecks': bottleneck_data,
            'employee_ranking': ranking_data,
            'warehouse_summary': material_data
        })


class RecordSaleView(APIView):
    """Manually record sale as journal entry"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, order_id):
        if request.user.role not in ['admin', 'accountant']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            order = Order.objects.get(id=order_id)
            entry = AccountingService.record_sale(order, request.user)
            
            return Response({
                'status': 'success',
                'journal_entry_id': entry.id,
                'message': f'Sale recorded for Order #{order.order_number}',
                'is_balanced': entry.is_balanced()
            })
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except ChartOfAccounts.DoesNotExist:
            return Response({
                'error': 'Chart of accounts not setup. Run /api/accounting/setup/ first'
            }, status=status.HTTP_400_BAD_REQUEST)

class MonthlyPlanView(APIView):
    """
    Manage Monthly Income Plan for the company.
    Calculates completed income vs planned revenue.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        now = timezone.now()
        month_param = request.query_params.get('month', now.month)
        year_param = request.query_params.get('year', now.year)
        
        try:
            month = int(month_param)
            year = int(year_param)
        except ValueError:
            month, year = now.month, now.year
            
        # Get plan
        plan = MonthlyPlan.objects.filter(month=month, year=year).first()
        plan_amount = plan.plan_amount if plan else 0
        
        # Calculate completed (sum of income transactions in that month)
        completed = Transaction.objects.filter(
            type='income',
            date__year=year,
            date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Calculations
        completed = float(completed)
        plan_amount = float(plan_amount)
        remaining = max(0, plan_amount - completed)
        
        progress = 0
        if plan_amount > 0:
            progress = round((completed / plan_amount) * 100, 1)
            
        return Response({
            'month': month,
            'year': year,
            'plan_amount': plan_amount,
            'completed': completed,
            'remaining': remaining,
            'progress': min(progress, 100) # Keep actual progress
        })
        
    def post(self, request):
        if request.user.role != 'admin':
            return Response({'error': 'Faqat Admin oylik rejani tahrirlashi mumkin'}, status=status.HTTP_403_FORBIDDEN)
            
        now = timezone.now()
        month = request.data.get('month', now.month)
        year = request.data.get('year', now.year)
        amount = request.data.get('plan_amount')
        
        if amount is None:
            return Response({'error': 'plan_amount is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        plan, created = MonthlyPlan.objects.update_or_create(
            month=month, year=year,
            defaults={'plan_amount': amount}
        )
        
        return Response({
            'status': 'success',
            'month': month,
            'year': year,
            'plan_amount': float(plan.plan_amount)
        })
