"""
FPL-specific calculation utilities
"""

def calculate_fpl_sale_price(current_price: float, purchase_price: float) -> float:
    """
    Calculate FPL sale price using official formula
    
    Args:
        current_price: Current market price of the player
        purchase_price: Price when the player was originally purchased
        
    Returns:
        Sale price following FPL rules
    """
    if current_price > purchase_price:
        # Player gained value: Purchase Price + floor((Current Price - Purchase Price) / 2)
        price_diff = current_price - purchase_price
        sale_price = purchase_price + (price_diff / 2)
        sale_price = (sale_price * 10) // 1 / 10 # Round down to nearest 0.1m (FPL rule)
    else:
        # Player lost value or stayed same: Current Price (full loss)
        sale_price = current_price
    
    return sale_price
