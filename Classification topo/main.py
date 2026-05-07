#!/bin/python3 -x

import numpy as np
import rasterio
import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter
from matplotlib.colors import ListedColormap

# -----------------------------
# PARAMÈTRES
# -----------------------------
input_mnt = "/home/thibd/Desktop/APT/2A/PAF/SIG/LIDAR/2026-04-20_LidarHD_MNT.tif"
output_tpi = "tpi.tif"
output_classes = "tpi_classes.tif"

window_size = 99  # impair

# -----------------------------
# LECTURE DU MNT
# -----------------------------
with rasterio.open(input_mnt) as src:
    mnt = src.read(1).astype("float32")
    profile = src.profile
    nodata = src.nodata

    if nodata is not None:
        mnt = np.where(mnt == nodata, np.nan, mnt)

mask = np.isnan(mnt)

# -----------------------------
# CALCUL TPI
# -----------------------------
local_mean = uniform_filter(mnt, size=window_size, mode="nearest")
tpi = mnt - local_mean

# remettre nodata
if nodata is not None:
    tpi = np.where(mask, nodata, tpi)

# -----------------------------
# TPI PLAFONÉ [-1, 1]
# (mais on conserve les valeurs originales dans cet intervalle)
# -----------------------------
tpi_clipped = np.clip(tpi, -1, 1)
tpi_clipped[mask] = np.nan

# -----------------------------
# CLASSEMENT CRÊTES / VALLÉES
# -----------------------------
classes = np.zeros_like(tpi, dtype=np.int8)

classes[tpi < -1] = -1   # vallées fortes
classes[tpi > 1] = 1     # crêtes fortes
classes[(tpi >= -1) & (tpi <= 1)] = 0  # normal

classes[mask] = 0

# -----------------------------
# SAUVEGARDE
# -----------------------------
profile.update(dtype=rasterio.float32, nodata=nodata)

with rasterio.open(output_tpi, "w", **profile) as dst:
    dst.write(tpi.astype(rasterio.float32), 1)

profile.update(dtype=rasterio.int8, nodata=0)

with rasterio.open(output_classes, "w", **profile) as dst:
    dst.write(classes.astype(rasterio.int8), 1)

print("TPI enregistré :", output_tpi)
print("Classes enregistrées :", output_classes)

# -----------------------------
# STATS
# -----------------------------
values = tpi[~np.isnan(tpi)]
print(f"{np.nanmin(tpi) = }")
print(f"{np.nanmax(tpi) = }")

# -----------------------------
# HISTOGRAMME
# -----------------------------
plt.figure(figsize=(8, 5))
plt.hist(values, bins=100, color="steelblue", edgecolor="black")
plt.title("Histogramme des valeurs TPI")
plt.xlabel("TPI")
plt.ylabel("Fréquence")
plt.grid(alpha=0.3)

# -----------------------------
# AFFICHAGE TPI PLAFONÉ (IMPORTANT)
# -----------------------------
plt.figure(figsize=(10, 6))
plt.imshow(tpi_clipped, cmap="RdYlBu", vmin=-1, vmax=1)
plt.colorbar(label="TPI (plafonné [-1, 1])")
plt.title("TPI plafonné (valeurs originales conservées dans [-1, 1])")
plt.axis("off")

# -----------------------------
# AFFICHAGE CRÊTES / VALLÉES
# -----------------------------
plt.figure(figsize=(10, 6))

cmap = ListedColormap(["blue", "white", "red"])
plt.imshow(classes, cmap=cmap, vmin=-1, vmax=1)

plt.title("Détection crêtes / vallées (seuil ±1)")
plt.axis("off")

plt.show()
