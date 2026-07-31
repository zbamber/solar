import os
import pandas as pd
import pvlib
from datetime import datetime
from dotenv import load_dotenv
import pymysql

from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS


load_dotenv()


LATITUDE = 52.981694
LONGITUDE = -1.496833


def get_tmy_data():
    tmy_data, months_selected, inputs, meta = pvlib.iotools.get_pvgis_tmy(
        lat=LATITUDE, 
        lon=LONGITUDE, 
        map_variables=True
    )

    return tmy_data


def get_location_object():
    location = Location(
    latitude=LATITUDE, 
    longitude=LONGITUDE, 
    tz='Europe/London', 
    name='Garden Shed'
    )

    return location


def get_inverter_and_panel_details():
    # using generic of each for now
    sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
    sapm_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')
    module = sandia_modules['Canadian_Solar_CS5P_220M___2009_']
    inverter = sapm_inverters['ABB__MICRO_0_25_I_OUTD_US_208_208V__CEC_2014_']

    return module, inverter


def fetch_historial_load_data():
    # fetch db credentials
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")

    # check credentials are present
    if not all([host, user, password, database]):
        raise ValueError("Database credentials missing, check .env file")

    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database
    )
    
    query = """
    SELECT DateTimeUTC, consumption AS electric
    FROM electric;
    """
    
    df_elec = pd.read_sql_query(query, connection)
    connection.close()

    return df_elec


def get_tey_data(
        cutoff_date='2024-12-31', # cutoff changes to load (heatpump + ev)
        year=1990 # to align with pvlibs default tmy year
):

    df_elec = fetch_historial_load_data()

    df_elec['DateTimeUTC'] = pd.to_datetime(df_elec['DateTimeUTC'])
    df_elec = df_elec.set_index('DateTimeUTC')

    cutoff_dt = datetime.strptime(cutoff_date, "%Y-%m-%d")
    df_elec = df_elec[df_elec.index < cutoff_dt]

    df_monthly_profile = df_elec.groupby([
        df_elec.index.month, 
        df_elec.index.hour, 
        df_elec.index.minute
    ])['electric'].mean()

    df_monthly_profile.index.names = ['Month', 'Hour', 'Minute']

    full_year_blank_30min = pd.date_range(
        start=f'{year}-01-01 00:00:00',
        end=f'{year}-12-31 23:30:00',
        freq='30min'
    )

    full_year_df = pd.DataFrame(index=full_year_blank_30min)
    full_year_df['Month'] = full_year_df.index.month
    full_year_df['Hour'] = full_year_df.index.hour
    full_year_df['Minute'] = full_year_df.index.minute

    baseline_series = full_year_df.merge(
        df_monthly_profile.reset_index(),
        on=['Month', 'Hour', 'Minute'],
        how='left'
    )['electric']
    
    # Re-apply the datetime index (merging drops it)
    baseline_series.index = full_year_blank_30min

    # resample into hourly - just summing half hourly blocks
    baseline_hourly = baseline_series.resample('1h').sum()
    baseline_hourly.name = 'baseline_kwh'

    baseline_hourly.index = baseline_hourly.index.tz_localize('UTC')
    
    return baseline_hourly


def main():
    tmy_data = get_tmy_data()
    location = get_location_object()
    module, inverter = get_inverter_and_panel_details()
    tey_data = get_tey_data()
    

    # params for the thermal efficiency penalty model (Sandia SAPM model - panel open for airflow)
    temp_params = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

    for i in range(91):
        pass

if __name__ == '__main__':
    main()