#!/bin/python3 -x

import rasterio
import numpy as np
import matplotlib.pyplot as plt

A  = [-1, 0, 1, 2, 3]
VU = [-1, 4, 5, 6, 7, 8]
VM = [-1, 9, 10, 11, 12, 13, 14, 15, 16]
HV = [-1, 17, 18, 19]
FV = [-1, 20, 21, 22, 23]
P  = [-1, 24, 25, 26, 27, 28, 29, 30, 31, 32]

def make_array(a, ha, vu, vm, hv, fv, p):
    return [-1, FV[fv], A[a], HV[hv], P[p], VM[vm], VU[vu], A[ha]]

def calculate_station(acidite, RUM, topo):
    if -9999 in (acidite, RUM, topo):
        return -9999

    reference = [
        # RU Faible
        [
        make_array(2, 2, 2, 2, 3, 4, 2),
        make_array(2, 2, 2, 2, 3, 3, 2),
        make_array(1, 1, 2, 2, 3, 3, 2)
        ],
        # RU Moyen
        [
        make_array(2, 2, 5, 5, 3, 4, 5),
        make_array(2, 2, 5, 5, 3, 3, 5),
        make_array(1, 1, 3, 4, 1, 2, 4)
        ],
        # RU Fort
        [
        make_array(4, 2, 5, 8, 3, 4, 9),
        make_array(4, 2, 5, 8, 3, 3, 8),
        make_array(3, 1, 4, 7, 2, 2, 7)
        ]
    ]

    return reference[RUM][acidite][topo]

with rasterio.open("Acidite.tif", "r") as src:
    acidite = src.read(1)

    print(f"{acidite.max() = } | {acidite.min() = }")

with rasterio.open("RUM.tif", "r") as src:
    RUM = src.read(1)

    print(f"{RUM.max() = } | {RUM.min() = }")

with rasterio.open("/home/thibd/Desktop/APT/2A/PAF/SIG/STATIONS/2026-05-05_Topographie.tif", "r") as src:
    topo = src.read(1)
    profile = src.profile

    print(f"{topo.max() = } | {topo.min() = }")

profile["nodata"] = -9999

stations = np.full_like(topo, 0)

nbre_pix = topo.shape[0] * topo.shape[1]
compteur = 0

for x, y in np.ndindex(topo.shape):
    stations[x, y] = calculate_station(acidite[x, y], 
            RUM[x, y],
            topo[x, y])
    compteur += 1
    if (compteur % 500000) == 0:
        print(f"\rProcess : {round(compteur / nbre_pix * 100, 2)}%", end="")

with rasterio.open("./output.tif", "w", **profile) as output:
    output.write(stations, 1)
