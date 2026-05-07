#!/bin/python3

import rasterio
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import maximum_filter, gaussian_filter
from scipy.spatial import cKDTree

window = ((0, 9075),(0, 9008))
surface_raster = window[0][1] * window[1][1]

with rasterio.open("MNH_foret.tif") as src:
    image_foret = src.read(window=window)[0]
    transform = src.transform

with rasterio.open("MNH_rege.tif") as src:
    image_rege = src.read(window=window)[0]

image = image_foret - image_rege

image_smooth = gaussian_filter(image, sigma=1)

window_size = 9
local_max = maximum_filter(image_smooth, size=window_size)
maxima = (image_smooth == local_max)

maxima &= image_smooth > 0
# Arbres de plus de X mètres de haut
maxima &= image > 15

rows, cols = np.where(maxima)

points = np.vstack((rows, cols)).T

if len(points) > 0:
    tree = cKDTree(points)

    # Courone de plus de X pixels de rayon (X/2 m)
    distance_min = 7
    keep = np.ones(len(points), dtype=bool)

    for i in range(len(points)):
        if not keep[i]: continue

        idx = tree.query_ball_point(points[i], r=distance_min)

        for j in idx:
            if j != i:
                keep[j] = False

    points_filtered = points[keep]
else:
    points_filtered = np.empty((0, 2))

# Filtre de contexte : supprimer les maxima entourés majoritairement de zéros
window_context = 9
half = window_context // 2

points_clean = []

for row, col in points_filtered:

    r_min = max(0, row - half)
    r_max = min(image.shape[0], row + half + 1)
    c_min = max(0, col - half)
    c_max = min(image.shape[1], col + half + 1)

    window_local = image[r_min:r_max, c_min:c_max]

    ratio_zeros = np.sum(window_local == 0) / window_local.size

    if ratio_zeros < 0.75:
        points_clean.append((row, col))

points_clean = np.array(points_clean)

# Calcul de variables dendros :
hauteurs_arbres = image[points_clean[:, 0], points_clean[: ,1]]
H_moy = np.mean(hauteurs_arbres)
H_dom = np.mean(np.partition(hauteurs_arbres, -100)[-100:])

N = len(points_clean)

# Surface des parcelles (en ha)
S = ( surface_raster - np.sum(image == 0) ) * 0.5 * 0.5 / 10000

print(f"{H_moy = :.2f}")
print(f"{H_dom = :.2f}")
print(f"{S = :.2f}")
print(f"N total = {N}")
print(f"N/ha = {N / S:.2f}")

x_l93, y_l93 = rasterio.transform.xy(transform, points_clean[:,0], points_clean[:,1])

np.savez("./Pts Lidar/arbres.npz", x=x_l93, y=y_l93)

plt.imshow(image, cmap='gray')
plt.scatter(
        points_clean[:, 1],
        points_clean[:, 0],
        s=5,
        c='red'
)
plt.colorbar()
plt.show()
