#!/bin/python3 -x

import laspy
import numpy as np
import rasterio
import open3d as o3d
import matplotlib.pyplot as plt

from sklearn.cluster import DBSCAN
from matplotlib.patches import Circle

S_ha = 100

def affichage3D(x, y, z):
    print("Affichage")
    points = np.vstack((x, y, z)).T

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    z_normed = (z - z.min()) / (z.max() - z.min())

    colors = np.vstack((z_normed, z_normed, z_normed)).T
    pcd.colors = o3d.utility.Vector3dVector(colors)
    o3d.visualization.draw_plotly([pcd])

def affichage2D(x, y, z):
    plt.scatter(x, y, s=1)
    plt.colorbar(label="Hauteur")

print("Lecture Lidar")
las = laspy.read("Lidar.laz")

veg = las.points[las.classification == 5]

x, y, z = veg.x, veg.y, veg.z

print("Normalisation des hauteurs")
with rasterio.open("../../../SIG/LIDAR/2026-04-20_LidarHD_MNT.tif") as src:
    mnt = src.read()[0]
    transform = src.transform

rows, cols = rasterio.transform.rowcol(transform, x, y)
z_norm = z - mnt[rows, cols]

header = laspy.LasHeader(point_format=3, version="1.2")
out = laspy.LasData(header)
out.x = x
out.y = y
out.z = z_norm
out.write("VegeLidar.laz")

print("Echantillonage de la vege a 1.3m")
ech = (z_norm >= 5) & (z_norm <= 5.5)

x = x[ech]
y = y[ech]
z = z_norm[ech]

g = []
trees = []

print("Placement des arbres")
pts_arbres = np.load("arbres.npz")
# No comment sur le x/y inversé...
x_a, y_a = pts_arbres["x"], pts_arbres["y"]

G = np.sum(g) / S_ha
print(f"g = {np.sum(g)}")
print(f"{G = :.2f}")
print(f"N = {len(trees)}")

affichage2D(x, y, z)

for cx, cy, r in trees:
    circle = plt.Circle((cx, cy), r, fill=False, color='red')
    plt.gca().add_patch(circle)

plt.scatter(x_a, y_a, s=1, color="red")
plt.gca().set_aspect('equal')
plt.show()
