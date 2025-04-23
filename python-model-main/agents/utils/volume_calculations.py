import math

def buying_intent(margin, base_volume=100, threshold=0.25, growth_rate=3):
        """
        Calculate buying intent based on a percentage margin using an exponential function.
        
        Parameters:
        margin (float): The margin as a decimal (e.g., 0.2 for 20%).
        base_volume (float): The baseline volume of buying intent (default is 100).
        threshold (float): The margin threshold where buying intent starts increasing significantly (default is 25% or 0.25).
        growth_rate (float): The rate at which the intent grows exponentially beyond the threshold (default is 3).

        Returns:
        float: Calculated buying intent volume.
        """
        return base_volume * math.exp(growth_rate * (margin - threshold))


def buying_intent_increasing_above_1(value, base_volume=1, growth_rate=3):
    """
    Calculate buying intent based on a price using an exponential function
    that asymptotically approaches 1. The intent increases as the margin goes
    above the threshold (1), but is capped at a maximum of 1.
    
    Parameters:
    value (float): The input price.
    base_volume (float): The baseline volume of buying intent (default is 1).
    growth_rate (float): The rate at which the intent grows as value increases (default is 3).

    Returns:
    float: Calculated buying intent volume, capped at a maximum of 1.
    """
    if value <= 1:
        return 0
    else:
        # Scale the exponential to approach 1 as the value increases
        return 1 - math.exp(-growth_rate * (value - 1))
