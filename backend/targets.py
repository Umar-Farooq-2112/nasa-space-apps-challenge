"""Demo targets. Positions at epoch 2026.0 (SPHEREx era): SIMBAD J2000 position + proper motion x 26 yr.
Fast movers (Barnard's Star 10"/yr, WISE 0855 8"/yr) have shifted up to 0.075 deg since J2000,
so J2000 coordinates would put them off the edge of a 0.1 deg cutout.
pmra/pmdec: catalog proper motion (mas/yr, SIMBAD via Sesame), shown next to our measurement.
detector: where the object is bright. WISE 0855 is a ~250 K brown dwarf, almost invisible below 3 um,
so it needs D6 (4.4-5.0 um); the others are fine in D3 (1.6-2.4 um)."""
TARGETS = [
    {"id": "wise0855", "name": "WISE 0855", "ra": 133.7598, "dec": -7.2422, "detector": "D6", "pmra": -8123.7, "pmdec": 673.2},
    {"id": "barnards_star", "name": "Barnard's Star", "ra": 269.4463, "dec": 4.7682, "detector": "D3", "pmra": -801.6, "pmdec": 10362.4},
    {"id": "eps_indi_b", "name": "Epsilon Indi B", "ra": 331.0966, "dec": -56.8007, "detector": "D3", "pmra": 3982.0, "pmdec": -2466.8},
    {"id": "rw_aur", "name": "RW Aurigae", "ra": 76.9566, "dec": 30.4013, "detector": "D3", "pmra": 7.2, "pmdec": -20.3},
    {"id": "r_dra", "name": "R Draconis", "ra": 248.1672, "dec": 66.7550, "detector": "D3", "pmra": -20.6, "pmdec": 6.1},
    # extra fast movers beyond the challenge list (positions from CDS Sesame + proper motion, see resolve.py)
    {"id": "kapteyn", "name": "Kapteyn's Star", "ra": 77.9855, "dec": -45.0597, "detector": "D3", "pmra": 6491.2, "pmdec": -5708.6},
    {"id": "groombridge", "name": "Groombridge 1830", "ra": 178.2814, "dec": 37.6767, "detector": "D3", "pmra": 4002.7, "pmdec": -5817.8},
    {"id": "wolf359", "name": "Wolf 359", "ra": 164.0924, "dec": 6.9952, "detector": "D3", "pmra": -3866.3, "pmdec": -2699.1},
    {"id": "luhman16", "name": "Luhman 16", "ra": 162.2954, "dec": -53.3169, "detector": "D3", "pmra": -2767.5, "pmdec": 356.9},
]
