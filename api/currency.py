import requests
import logging
from decimal import Decimal
from django.conf import settings
from .models import PricingSettings, SettingsLog, User

logger = logging.getLogger(__name__)

class CurrencyService:
    """
    Service for managing dynamic currency exchange rates.
    Integrates with Central Bank of Uzbekistan (CBU) API.
    """
    
    CBU_API_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
    
    @staticmethod
    def fetch_cbu_rates():
        """
        Fetch latest exchange rates from Central Bank.
        Returns dict: {'USD': 12800.00, 'EUR': 13500.00, ...}
        """
        try:
            response = requests.get(CurrencyService.CBU_API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            rates = {}
            for item in data:
                ccy = item.get('Ccy')
                rate = item.get('Rate')
                if ccy and rate:
                    rates[ccy] = float(rate)
            
            return rates
            
        except Exception as e:
            logger.error(f"Failed to fetch CBU rates: {e}")
            return None

    @staticmethod
    def update_exchange_rate(force=False, user=None):
        """
        Update system exchange rate from CBU.
        
        Args:
            force (bool): Update even if auto_update is disabled
            user (User): User initiating update (optional)
        
        Returns:
            dict: {
                'success': bool, 
                'old_rate': Decimal, 
                'new_rate': Decimal, 
                'message': str
            }
        """
        settings_obj = PricingSettings.load()
        
        if not settings_obj.auto_update_currency and not force:
            return {'success': False, 'message': 'Auto-update disabled'}
            
        rates = CurrencyService.fetch_cbu_rates()
        if not rates or 'USD' not in rates:
            return {'success': False, 'message': 'Failed to fetch USD rate'}
            
        new_rate = Decimal(str(rates['USD']))
        old_rate = settings_obj.exchange_rate
        
        # Check if change is significant (e.g. diff > 1 so'm)
        if abs(new_rate - old_rate) < Decimal('1.00'):
             return {'success': True, 'message': 'Rate unchanged', 'old_rate': old_rate, 'new_rate': new_rate}
             
        # Update Settings
        settings_obj.exchange_rate = new_rate
        settings_obj.save()
        
        # Log Logic
        system_user = User.objects.filter(role='admin').first() if not user else user
        
        SettingsLog.objects.create(
            user=system_user,
            setting_type='exchange_rate_auto_update',
            old_value=str(old_rate),
            new_value=str(new_rate)
        )
        
        return {
            'success': True, 
            'old_rate': old_rate, 
            'new_rate': new_rate,
            'message': f"Updated USD rate: {old_rate} -> {new_rate}"
        }
