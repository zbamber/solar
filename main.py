from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

from hardware import get_panel_details, get_inverter_details
from battery import greedy_battery_dispatch
from data_loader import get_tmy_data, get_location_object, get_tey_load, get_historical_octopus_tariffs
from solar_engine import get_fixed_roof_dc_watts, calculate_array_dc_power, invert_power


def evaluate_shed_angle(tilt, azimuth, tmy_data, location, tey_load, roof_dc_watts, import_prices, export_prices, temp_params, battery_strategy):
    """
    Evaluates the total annual electricity bill for a candidate shed angle.
    """
    shed_module = get_panel_details('shed')  # DMEGC 515W
    inverter = get_inverter_details()
    
    # Calculate shed DC power generation (5 x 515W panels)
    shed_dc_watts = calculate_array_dc_power(
        tmy_data, location, shed_module, inverter, temp_params, tilt, azimuth, panel_count=5
    )

    total_dc_watts = roof_dc_watts + shed_dc_watts
    ac_watts = invert_power(total_dc_watts)

    total_solar_kwh = ac_watts / 1000

    lengths = {
        "solar": len(total_solar_kwh),
        "load": len(tey_load),
        "import_prices": len(import_prices),
        "export_prices": len(export_prices),
    }

    if len(set(lengths.values())) != 1:
        raise ValueError(f"Array lengths do not match: {lengths}")
    
    # Total net house load before battery buffering
    total_net_load = tey_load.to_numpy() - total_solar_kwh.to_numpy()
    
    # Run the modular battery dispatch strategy
    imports, exports, soc = battery_strategy(
        total_net_load, capacity_kwh=10.9, max_power_kw=6.0
    )
    
    # Financial calculation using dynamic Octopus tariffs
    total_cost = (imports * import_prices.to_numpy()) - (exports * export_prices.to_numpy())
    return total_cost.sum()


def main():
    print("Loading weather, location, load, and tariff data...")
    tmy_data = get_tmy_data()
    location = get_location_object()
    tey_load = get_tey_load()
    import_prices, export_prices = get_historical_octopus_tariffs(year=2024)
    
    inverter = get_inverter_details()
    temp_params = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
    
    print("Calculating baseline DC generation for existing roof arrays...")
    roof_dc_watts = get_fixed_roof_dc_watts(tmy_data, location, inverter, temp_params)
    
    min_annual_cost = float('inf')
    
    print("Beginning Shed Panel Angle Optimization...")
    
    # Coarse search grid: Tilt 10° to 60°, Azimuth 135° to 270° in 5° steps
    for tilt in range(10, 65, 5):
        for az in range(135, 275, 5):
            print(f'\rCoarse Search: Testing {tilt}° tilt at {az}° azimuth      ', end='', flush=True)
            annual_cost = evaluate_shed_angle(
                tilt, az, tmy_data, location, tey_load, roof_dc_watts, 
                import_prices, export_prices, temp_params, 
                battery_strategy=greedy_battery_dispatch
            )
            
            if annual_cost < min_annual_cost:
                min_annual_cost = annual_cost
                best_coarse_angle = (tilt, az)
    print()


    best_fine_angle = best_coarse_angle
    for tilt in range(best_coarse_angle[0] - 5, best_coarse_angle[0] + 6, 1):
        for az in range(best_coarse_angle[1] - 5, best_coarse_angle[1] + 6, 1):
            print(f'\rFine Search: Testing {tilt}° tilt at {az}° azimuth        ', end='', flush=True)
            annual_cost = evaluate_shed_angle(
                tilt, az, tmy_data, location, tey_load, roof_dc_watts, 
                import_prices, export_prices, temp_params, 
                battery_strategy=greedy_battery_dispatch
            )

            if annual_cost < min_annual_cost:
                min_annual_cost = annual_cost
                best_fine_angle = (tilt, az)
    print()


    print("\n================ OPTIMIZATION RESULT ================")
    print(f"Optimal Shed Panel Angle : Tilt {best_fine_angle[0]}°, Azimuth {best_fine_angle[1]}°")
    print(f"Net Annual Electricity Cost : £{min_annual_cost:.2f}")
    print("=====================================================")


if __name__ == '__main__':
    main()