from decimal import Decimal, InvalidOperation

def safe_float(value, default=0.0):
    """
    Safely convert a value to float, handling None, empty strings, and invalid formats.
    """
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def calculate_units(value, unit_type, units_per_pack=1, packs_per_box=1):
    """
    Calculate pieces (dona), packs (pochka), and boxes (yashik) based on input.
    - unit_type: 'dona', 'pochka', or 'yashik'
    - units_per_pack: How many pieces in one pack
    - packs_per_box: How many packs in one box
    """
    dona = 0
    pochka = 0
    yashik = 0

    if unit_type == 'dona':
        dona = safe_float(value)
        if units_per_pack > 0:
            pochka = dona / units_per_pack
            if packs_per_box > 0:
                yashik = pochka / packs_per_box
                
    elif unit_type == 'pochka':
        pochka = safe_float(value)
        dona = pochka * units_per_pack
        if packs_per_box > 0:
            yashik = pochka / packs_per_box
            
    elif unit_type == 'yashik':
        yashik = safe_float(value)
        pochka = yashik * packs_per_box
        dona = pochka * units_per_pack

    return {
        "dona": int(dona),
        "pochka": round(pochka, 2),
        "yashik": round(yashik, 2)
    }
