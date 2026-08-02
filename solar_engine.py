import pandas as pd
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain
from hardware import get_panel_details


def calculate_array_ac_power(tmy_data, location, module_specs, inverter_specs, temp_params, tilt, azimuth, panel_count):
    """Calculates total AC generation (in Watts) for a specific panel array setup."""
    system = PVSystem(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        module_parameters=module_specs,
        inverter_parameters=inverter_specs,
        temperature_model_parameters=temp_params,
        modules_per_string=panel_count,
        strings_per_inverter=1
    )
    mc = ModelChain(system, location, aoi_model='physical', spectral_model='no_loss')
    mc.run_model(tmy_data)
    
    return mc.results.ac.fillna(0)


def get_fixed_roof_generation_kwh(tmy_data, location, inverter_specs, temp_params):
    """
    Calculates power generation for existing fixed roof arrays using JA Solar 450W panels.
    """
    roof_module = get_panel_details('roof')
    
    # Roof arrays: (tilt, azimuth, panel_count)
    fixed_arrays = [
        (35, 142, 1),
        (35, 190, 1),
        (3, 120, 1)
    ]
    
    total_roof_ac_watts = pd.Series(0.0, index=tmy_data.index)
    
    for tilt, az, count in fixed_arrays:
        ac_watts = calculate_array_ac_power(
            tmy_data, location, roof_module, inverter_specs, temp_params, tilt, az, count
        )
        total_roof_ac_watts += ac_watts
        
    return total_roof_ac_watts / 1000  # Convert Watts to kWh