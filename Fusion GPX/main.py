#!/bin/python3 -x

import sys
from PyQt5 import QtWidgets, QtCore, QtGui
import geopandas as gpd
from shapely.geometry import Point
import fiona
import math

print(gpd.options.io_engine)

# ---------------- RULES ----------------
def compute_station(name):
    return 1 if "S" in str(name) else 0

# ---------------- GPX LOADER ----------------
class GPXLoader:
    @staticmethod
    def load_points(file_path):
        points = []
        try:
            layers = fiona.listlayers(file_path)
            layer = "waypoints" if "waypoints" in layers else layers[0]
            gdf = gpd.read_file(file_path, layer=layer)

            for idx, row in gdf.iterrows():
                name = row.get("name", f"pt_{idx}")
                geom = row.geometry

                if isinstance(geom, Point):
                    points.append({
                        "name": name,
                        "geometry": geom,
                        "source": file_path
                    })

        except Exception as e:
            print(f"Erreur chargement {file_path}: {e}")

        return points


# ---------------- HELPERS ----------------
def compute_flags(fid):
    try:
        fid = int(fid)
    except:
        fid = -1

    return {
        "PEUPLEMENT": 1 if 0 <= fid <= 99 else 0,
        "REGE": 1 if 100 <= fid <= 199 else 0,
        "EAU": 1 if 200 <= fid <= 299 else 0,
        "INTERSECTION": 1 if 300 <= fid <= 399 else 0
    }


def distance_m(p1, p2):
    lon1, lat1 = p1.x, p1.y
    lon2, lat2 = p2.x, p2.y
    R = 6371000

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


# ---------------- TABLE MODEL ----------------
class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data, columns):
        super().__init__()
        self._data = data
        self.columns = columns

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self.columns)

    def data(self, index, role):
        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            row = self._data[index.row()]
            col = self.columns[index.column()]
            return row.get(col, "")

    def setData(self, index, value, role):
        if role == QtCore.Qt.EditRole:
            col = self.columns[index.column()]
            row_idx = index.row()
            row = self._data[row_idx]

            if col == "fid":
                try:
                    value = int(value)
                except:
                    return False

                for i, r in enumerate(self._data):
                    if i != row_idx and r.get("fid") == value:
                        same_geom = r.get("geometry").equals(row.get("geometry"))
                        msg = f"FID déjà existant (ligne {i})"
                        msg += " - mêmes coordonnées" if same_geom else " - coordonnées différentes"
                        QtWidgets.QMessageBox.warning(None, "Conflit FID", msg)
                        return False

                row["fid"] = value
                row.update(compute_flags(value))

            elif col == "name":
                row["name"] = str(value)[:32]
                row["STATION"] = compute_station(row["name"])

            self.dataChanged.emit(index, index)
            self.layoutChanged.emit()
            return True

        return False

    def flags(self, index):
        col = self.columns[index.column()]
        if col == "id":
            return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.columns[section]

    def add_row(self, row):
        self.beginResetModel()
        self._data.append(row)
        self.endResetModel()

    def remove_rows(self, rows):
        self.beginResetModel()
        for r in sorted(rows, reverse=True):
            if 0 <= r < len(self._data):
                self._data.pop(r)
        self.endResetModel()

    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()


# ---------------- MAIN WINDOW ----------------
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GPX / GPKG Editor")
        self.resize(1100, 500)

        self.points = []
        self.table_data = []
        self.current_gpkg = None
        self.next_id = 1

        self.columns = [
            "id", "name", "fid", "PEUPLEMENT", "STATION",
            "REGE", "EAU", "INTERSECTION"
        ]

        layout = QtWidgets.QHBoxLayout(self)

        self.list_widget = QtWidgets.QListWidget()
        layout.addWidget(self.list_widget)

        self.table_model = TableModel(self.table_data, self.columns)
        self.table = QtWidgets.QTableView()
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        layout.addWidget(self.table)

        btn_layout = QtWidgets.QVBoxLayout()

        self.load_gpx_btn = QtWidgets.QPushButton("Charger GPX")
        self.open_gpkg_btn = QtWidgets.QPushButton("Ouvrir GPKG")
        self.remove_btn = QtWidgets.QPushButton("Supprimer ligne(s)")
        self.save_btn = QtWidgets.QPushButton("Enregistrer GPKG")

        btn_layout.addWidget(self.load_gpx_btn)
        btn_layout.addWidget(self.open_gpkg_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

        self.load_gpx_btn.clicked.connect(self.load_gpx)
        self.open_gpkg_btn.clicked.connect(self.open_gpkg)
        self.remove_btn.clicked.connect(self.remove_selected_rows)
        self.save_btn.clicked.connect(self.save_gpkg)
        self.list_widget.itemDoubleClicked.connect(self.add_point_to_table)

    def load_gpx(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "GPX", "", "GPX (*.gpx)")
        for file in files:
            pts = GPXLoader.load_points(file)
            for pt in pts:
                self.points.append(pt)
                item = QtWidgets.QListWidgetItem(f"{pt['name']} ({file.split('/')[-1]})")
                item.setData(QtCore.Qt.UserRole, pt)
                self.list_widget.addItem(item)

    def open_gpkg(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Ouvrir GPKG", "", "GeoPackage (*.gpkg)")
        if not path:
            return

        self.current_gpkg = path

        gdf = gpd.read_file(path, engine="fiona").to_crs(epsg=4326)

        data = []
        max_id = 0

        for _, row in gdf.iterrows():
            rid = row.get("id", None)

            if rid is None:
                max_id += 1
                rid = max_id
            else:
                max_id = max(max_id, rid)

            name = row.get("name", "")

            data.append({
                "id": rid,
                "name": name,
                "fid": row.get("fid", None),
                "PEUPLEMENT": row.get("PEUPLEMENT", 0),
                "STATION": compute_station(name),
                "REGE": row.get("REGE", 0),
                "EAU": row.get("EAU", 0),
                "INTERSECTION": row.get("INTERSECTION", 0),
                "geometry": row.geometry
            })

        self.next_id = max_id + 1
        self.table_model.set_data(data)

    def add_point_to_table(self, item):
        pt = item.data(QtCore.Qt.UserRole)

        fid, ok = QtWidgets.QInputDialog.getInt(self, "FID", "fid:")
        if not ok:
            return

        for i, r in enumerate(self.table_data):
            if r.get("fid") == fid:
                same_geom = r.get("geometry").equals(pt["geometry"])

                if same_geom:
                    self.list_widget.takeItem(self.list_widget.row(item))
                    return
                else:
                    dist = distance_m(r.get("geometry"), pt["geometry"])
                    item.setForeground(QtGui.QColor("gray"))
                    item.setText(f"{pt['name']} ⚠ | {int(dist)} m")
                    return

        row = {
            "id": self.next_id,
            "name": pt["name"][:32],
            "fid": fid,
            "STATION": compute_station(pt["name"]),
            **compute_flags(fid),
            "geometry": pt["geometry"]
        }

        self.next_id += 1
        self.table_model.add_row(row)
        self.list_widget.takeItem(self.list_widget.row(item))

    def remove_selected_rows(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        rows = [i.row() for i in indexes]
        self.table_model.remove_rows(rows)

    def save_gpkg(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "GPKG", "", "GeoPackage (*.gpkg)")
        if not path:
            return

        gdf = gpd.GeoDataFrame(self.table_model._data)
        gdf.set_geometry("geometry", inplace=True)
        gdf.set_crs(epsg=4326, inplace=True)

        gdf.to_file(
            path,
            driver="GPKG",
            engine="pyogrio",
            layer_options={"FID": "id"}
        )
        self.current_gpkg = path


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())