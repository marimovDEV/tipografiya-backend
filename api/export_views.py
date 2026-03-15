# backend/api/export_views.py
"""
Excel Export API Views
Provides endpoints for generating and downloading Excel reports
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from datetime import datetime, timedelta

from .report_exporter import ReportExporter


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_daily_production(request):
    """
    Export daily production report to Excel
    POST /api/exports/daily-production/
    Body: {"date": "2026-01-04"}
    """
    date_str = request.data.get('date')
    
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # Validate date format
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)
    
    # Generate Excel
    workbook = ReportExporter.export_daily_production(date_str)
    excel_data = ReportExporter.save_to_bytes(workbook)
    
    # Create response
    response = HttpResponse(
        excel_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="kunlik_ishlab_chiqarish_{date_str}.xlsx"'
    
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_worker_efficiency(request):
    """
    Export worker efficiency report to Excel
    POST /api/exports/worker-efficiency/
    Body: {"start_date": "2026-01-01", "end_date": "2026-01-31"}
    """
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    
    if not start_date or not end_date:
        # Default to current month
        now = datetime.now()
        start_date = now.replace(day=1).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
    
    try:
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)
    
    # Generate Excel
    workbook = ReportExporter.export_worker_efficiency(start_date, end_date)
    excel_data = ReportExporter.save_to_bytes(workbook)
    
    # Create response
    response = HttpResponse(
        excel_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="xodimlar_samaradorligi_{start_date}_to_{end_date}.xlsx"'
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_warehouse_status(request):
    """
    Export warehouse status report to Excel
    GET /api/exports/warehouse-status/
    """
    # Generate Excel
    workbook = ReportExporter.export_warehouse_status()
    excel_data = ReportExporter.save_to_bytes(workbook)
    
    # Create response
    date_str = datetime.now().strftime('%Y-%m-%d')
    response = HttpResponse(
        excel_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="sklad_holati_{date_str}.xlsx"'
    
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_qc_statistics(request):
    """
    Export QC statistics report to Excel
    POST /api/exports/qc-statistics/
    Body: {"start_date": "2026-01-01", "end_date": "2026-01-31"}
    """
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    
    if not start_date or not end_date:
        # Default to last 30 days
        end = datetime.now()
        start = end - timedelta(days=30)
        start_date = start.strftime('%Y-%m-%d')
        end_date = end.strftime('%Y-%m-%d')
    
    try:
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)
    
    # Generate Excel
    workbook = ReportExporter.export_qc_statistics(start_date, end_date)
    excel_data = ReportExporter.save_to_bytes(workbook)
    
    # Create response
    response = HttpResponse(
        excel_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="qc_statistikasi_{start_date}_to_{end_date}.xlsx"'
    
    return response
