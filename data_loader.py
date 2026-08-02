import os
import requests
import pymysql
import pandas as pd
import pvlib
from datetime import datetime
from dotenv import load_dotenv
from pvlib.location import Location

load_dotenv()

LATITUDE = 52.981694
LONGITUDE = -1.496833


def get_location_object():
    return Location(
        latitude=LATITUDE, 
        longitude=LONGITUDE, 
        tz='Europe/London', 
        name='Garden Shed'
    )


def get_tmy_data():
    cache_file = 'typical_meteorological_year.csv'

    if os.path.exists(cache_file):
        print(f'Loading {cache_file}')
        df = pd.read_csv(cache_file, index_col=0)

        df.index = pd.to_datetime(df.index, utc=True)
        return df

    print(f'Fetching Typical Meteorological Year...')
    tmy_data, _ = pvlib.iotools.get_pvgis_tmy(
        latitude=LATITUDE, 
        longitude=LONGITUDE, 
        map_variables=True
    )
    # Shift by 30 minutes to center the solar position calculation
    tmy_data.index = tmy_data.index + pd.Timedelta(minutes=30)

    if tmy_data.index.tz is None:
        tmy_data.index = tmy_data.index.tz_localize('UTC')

    tmy_data.to_csv(cache_file)

    return tmy_data


def fetch_historial_load_data():
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")

    if not all([host, user, password, database]):
        raise ValueError("Database credentials missing, check .env file")

    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database
    )
    
    query = "SELECT DateTimeUTC, consumption AS electric FROM electric;"
    df_elec = pd.read_sql_query(query, connection)
    connection.close()

    return df_elec


def get_tey_load(cutoff_date='2024-12-31', year=1990):
    """
    Computes a 8760-hour Typical Electricity Year (TEY) baseline.
    """
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
    
    baseline_series.index = full_year_blank_30min

    missing_slots = baseline_series.isna().sum()
    if missing_slots > 0:
        print(f'Interpolating {missing_slots} missing half hour slots in electrical history')
        baseline_series = baseline_series.interpolate(method='time')


    baseline_hourly = baseline_series.resample('1h').sum()
    baseline_hourly.name = 'baseline_kwh'
    baseline_hourly.index = baseline_hourly.index.tz_localize('UTC')
    
    return baseline_hourly


def _fetch_paginated_rates(base_url, start_time, end_time):
    rates = []
    url = f"{base_url}?period_from={start_time}&period_to={end_time}&page_size=1500"
    while url:
        resp = requests.get(url).json()
        rates.extend(resp.get('results', []))
        url = resp.get('next')

    df = pd.DataFrame(rates)
    df['valid_from'] = pd.to_datetime(df['valid_from'])
    df = df.set_index('valid_from')[['value_inc_vat']].sort_index()
    return df['value_inc_vat'] / 100  # p/kWh -> £/kWh


def _to_tmy_year(series, tmy_year=1990):
    mask = ~((series.index.month == 2) & (series.index.day == 29))
    series = series[mask]
    series.index = series.index.map(lambda d: d.replace(year=tmy_year))
    return series


def get_historical_octopus_tariffs(year=2024, region='B'):
    """
    Fetches full year of half-hourly pricing from Octopus Energy 
    and resamples to hourly to align with pvlib TMY data.
    """
    cache_file = f"octopus_tariffs_{year}_{region}.csv"

    if os.path.exists(cache_file):
        print(f'Loading {cache_file}')
        df = pd.read_csv(cache_file, index_col=0)

        df.index = pd.to_datetime(df.index, utc=True)
        return df['import_prices'], df['export_prices']

    print(f"Fetching historical Octopus rates for {year}...")
    start_time = f"{year}-01-01T00:00:00Z"
    end_time = f"{year}-12-31T23:59:00Z"

    import_url = (
        f"https://api.octopus.energy/v1/products/AGILE-23-12-06/electricity-tariffs/"
        f"E-1R-AGILE-23-12-06-{region}/standard-unit-rates/"
    )
    export_url = (
        f"https://api.octopus.energy/v1/products/AGILE-OUTGOING-19-05-13/electricity-tariffs/"
        f"E-1R-AGILE-OUTGOING-19-05-13-{region}/standard-unit-rates/"
    )

    import_prices = _fetch_paginated_rates(import_url, start_time, end_time)
    export_prices = _fetch_paginated_rates(export_url, start_time, end_time)

    import_hourly = import_prices.resample('1h').mean().ffill()
    export_hourly = export_prices.resample('1h').mean().fillna(0)

    import_hourly = _to_tmy_year(import_hourly)
    export_hourly = _to_tmy_year(export_hourly)

    print(f'Saving file: {cache_file}')

    df_cache = pd.DataFrame({
        'import_prices': import_hourly,
        'export_prices': export_hourly
    })

    df_cache.to_csv(cache_file)

    return import_hourly, export_hourly