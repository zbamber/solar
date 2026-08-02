import numpy as np

def greedy_battery_dispatch(net_load_kwh, capacity_kwh=10.9, max_power_kw=6.0, round_trip_eff=0.95):
    """
    Greedy / Maximum Self-Consumption battery dispatch strategy.
    Charges from excess solar, discharges to meet house load.
    
    Parameters:
    - net_load_kwh: Series/array where (+) is load deficit, (-) is excess solar.
    - capacity_kwh: Usable battery capacity.
    - max_power_kw: Charge/Discharge power limit.
    
    Returns: (grid_import, grid_export, soc_profile)
    """
    net_load = net_load_kwh.to_numpy() if hasattr(net_load_kwh, 'to_numpy') else np.asarray(net_load_kwh)
    n = len(net_load)
    
    grid_import = np.zeros(n)
    grid_export = np.zeros(n)
    soc = np.zeros(n + 1)
    soc[0] = 0.0  # Start empty at beginning of year
    
    for i in range(n):
        current_soc = soc[i]
        load = net_load[i]
        
        if load < 0:  # Excess Solar
            excess = -load
            charge_attempt = min(excess, max_power_kw)
            room_available = capacity_kwh - current_soc
            actual_charge = min(charge_attempt * round_trip_eff, room_available)
            
            soc[i+1] = current_soc + actual_charge
            grid_export[i] = excess - (actual_charge / round_trip_eff)
            grid_import[i] = 0.0
        else:  # Solar Deficit
            deficit = load
            discharge_attempt = min(deficit, max_power_kw)
            actual_discharge = min(discharge_attempt, current_soc)
            
            soc[i+1] = current_soc - actual_discharge
            grid_import[i] = deficit - actual_discharge
            grid_export[i] = 0.0
            
    return grid_import, grid_export, soc[:-1]