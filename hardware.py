def get_panel_details(location):
    """
    Returns hardware dictionary specs for solar panels based on location.
    
    Options:
    - 'roof': JA Solar 450W Bifacial (JAM54D41-450/LB)
    - 'shed': DMEGC 515W Monofacial All Black (DM515G12RT-G54HBB)
    """
    panels = {
        'roof': {
            'name': 'JA Solar 450W Bifacial (JAM54D41-450/LB)',
            'pdc0': 450,
            'gamma_pdc': -0.0030,
            'v_mp': 32.82,
            'i_mp': 13.71,
            'v_oc': 39.30,
            'i_sc': 14.48,
            'alpha_sc': 0.00046,
            'beta_voc': -0.0026,
            'bifaciality': 0.80
        },
        'shed': {
            'name': 'DMEGC 515W All Black (DM515G12RT-G54HBB)',
            'pdc0': 515,
            'gamma_pdc': -0.0029,
            'v_mp': 34.61,
            'i_mp': 14.88,
            'v_oc': 40.75,
            'i_sc': 15.83,
            'alpha_sc': 0.00048,
            'beta_voc': -0.0025,
            'bifaciality': 0.0
        }
    }
        
    if location not in panels:
        raise ValueError(f"Unknown panel location '{location}'. Choose 'roof' or 'shed'.")
        
    return panels[location]


def get_inverter_details():
    """SigenStor EC 6.0 SP Inverter Specs."""
    return {
        'pdc0': 6122,
        'pac0': 6000,
        'eta_inv_nom': 0.98,
        'eta_inv_ref': 0.974
    }