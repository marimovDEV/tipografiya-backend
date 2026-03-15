import os
import django
import sys

# Set up Django
sys.path.append('/Users/ogabek/Documents/projects/erp+crm kitob/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import ProductionStep, User
from django.utils import timezone

# Assuming the worker is either admin or the first user
user = User.objects.first()

step = ProductionStep.objects.filter(status='pending', assigned_to__isnull=True).first()
if step:
    step.assigned_to = user
    step.status = 'in_progress'
    step.started_at = timezone.now()
    step.save()
    print(f"Claimed step {step.step} logic for user {user.username}")
else:
    print("No pending steps found")

