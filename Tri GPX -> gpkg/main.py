#!/bin/python3 -x

import sys
import os
import gpxpy
import gpxpy.gpx

from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QPushButton, QLabel, QListWidgetItem,
    QFileDialog, QInputDialog, QLineEdit, QComboBox, QUndoStack,
    QUndoCommand, QScrollArea
)
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDrag


# -----------------------------
# WAYPOINT WRAPPER
# -----------------------------
class WP:
    def __init__(self, gpx_wp, source_file):
        self.wp = gpx_wp
        self.name = gpx_wp.name or "Sans nom"
        self.latitude = gpx_wp.latitude
        self.longitude = gpx_wp.longitude
        self.source_file = source_file


# -----------------------------
# UNDO / REDO
# -----------------------------
class MoveOperationCommand(QUndoCommand):
    def __init__(self, source_list, dest_list, waypoints, text="Move"):
        super().__init__(text)
        self.source_list = source_list
        self.dest_list = dest_list
        self.waypoints = waypoints

    def redo(self):
        for wp in self.waypoints:
            if wp in self.source_list.waypoints:
                self.source_list.waypoints.remove(wp)
            if wp not in self.dest_list.waypoints:
                self.dest_list.waypoints.append(wp)

        self.source_list.refresh()
        self.dest_list.refresh()
        self.dest_list.update_label()
        self.source_list.update_label()

    def undo(self):
        for wp in self.waypoints:
            if wp in self.dest_list.waypoints:
                self.dest_list.waypoints.remove(wp)
            if wp not in self.source_list.waypoints:
                self.source_list.waypoints.append(wp)

        self.source_list.refresh()
        self.dest_list.refresh()
        self.dest_list.update_label()
        self.source_list.update_label()


# -----------------------------
# DRAG LIST
# -----------------------------
class DraggableList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.waypoints = []

    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if not items:
            return

        drag = QDrag(self)

        waypoints = [item.data(Qt.UserRole) for item in items]
        drag.waypoints = waypoints

        mime = QMimeData()
        mime.setText("\n".join(w.name for w in waypoints))
        drag.setMimeData(mime)

        drag.setHotSpot(self.viewport().rect().center())
        #drag.setPixmap(self.viewport().grab())

        self.drag = drag

        drag.exec_(Qt.MoveAction)

    def refresh(self):
        self.clear()
        for wp in self.waypoints:
            item = QListWidgetItem(f"{wp.name} [{wp.source_file}]")
            item.setData(Qt.UserRole, wp)
            self.addItem(item)


# -----------------------------
# DROP LIST
# -----------------------------
class DropList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.waypoints = []
        self.parent_window = None
        self.label = None

    def update_label(self):
        if self.label:
            count = len(self.waypoints)
            base_name = self.label.base_name
            self.label.setText(f"{base_name} ({count} points)")

    def dragEnterEvent(self, event):
        event.accept()

    def dragMoveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        source = event.source()

        if source and hasattr(source, "drag"):
            waypoints = source.drag.waypoints

            cmd = MoveOperationCommand(
                source_list=source,
                dest_list=self,
                waypoints=waypoints,
                text=f"Move {len(waypoints)} waypoints"
            )

            self.parent_window.undo_stack.push(cmd)

            event.accept()
        else:
            event.ignore()

    def refresh(self):
        self.clear()
        for wp in self.waypoints:
            self.addItem(f"{wp.name} ({wp.latitude:.5f}, {wp.longitude:.5f})")

        self.update_label()

# -----------------------------
# MAIN WINDOW
# -----------------------------
class GPXDispatcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GPX Dispatcher")

        self.undo_stack = QUndoStack(self)

        layout = QHBoxLayout()

        # -------- LEFT
        left = QVBoxLayout()

        self.import_btn = QPushButton("Importer GPX")
        self.import_btn.clicked.connect(self.import_gpx)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Recherche...")
        self.search.textChanged.connect(self.apply_filter)

        self.file_filter = QComboBox()
        self.file_filter.currentTextChanged.connect(self.apply_filter)

        self.point_list = DraggableList()

        left.addWidget(self.import_btn)
        left.addWidget(self.file_filter)
        left.addWidget(self.search)
        left.addWidget(self.point_list)

        layout.addLayout(left)

        # -------- RIGHT
        right = QVBoxLayout()

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_outputs)

        self.add_out = QPushButton("+ Output")
        self.add_out.clicked.connect(self.add_output)

        self.undo_btn = QPushButton("Undo")
        self.redo_btn = QPushButton("Redo")

        self.undo_btn.clicked.connect(self.undo_stack.undo)
        self.redo_btn.clicked.connect(self.undo_stack.redo)

        # boutons fixes
        right.addWidget(self.add_out)
        right.addWidget(self.undo_btn)
        right.addWidget(self.redo_btn)
        right.addWidget(self.save_btn)

        # -------- SCROLL ZONE
        self.output_container = QWidget()
        self.output_layout = QVBoxLayout()
        self.output_container.setLayout(self.output_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.output_container)

        right.addWidget(self.scroll)

        layout.addLayout(right)

        self.setLayout(layout)

        self.output_lists = []
        self.output_names = []
        self.all_waypoints = []

    # -----------------------------
    def save_outputs(self):
        folder = QFileDialog.getExistingDirectory(self, "Choisir dossier de sortie")

        if not folder:
            return

        for output_list, name in zip(self.output_lists, self.output_names):
            gpx = gpxpy.gpx.GPX()

            for wp in output_list.waypoints:
                gpx.waypoints.append(
                    gpxpy.gpx.GPXWaypoint(
                        latitude=wp.latitude,
                        longitude=wp.longitude,
                        name=wp.name
                    )
                )

            file_path = os.path.join(folder, f"{name}.gpx")

            with open(file_path, "w") as f:
                f.write(gpx.to_xml())

        print("Fichiers enregistrés !")

    # -----------------------------
    def import_gpx(self):
        files, _ = QFileDialog.getOpenFileNames(self, "GPX", "", "GPX (*.gpx)")

        for fpath in files:
            with open(fpath, "r") as f:
                gpx = gpxpy.parse(f)

            fname = os.path.basename(fpath)

            for wp in gpx.waypoints:
                self.all_waypoints.append(WP(wp, fname))

        self.update_file_filter()
        self.apply_filter()

    # -----------------------------
    def update_file_filter(self):
        self.file_filter.blockSignals(True)
        self.file_filter.clear()
        self.file_filter.addItem("Tous fichiers")

        files = sorted(set(w.source_file for w in self.all_waypoints))
        self.file_filter.addItems(files)

        self.file_filter.blockSignals(False)

    # -----------------------------
    def apply_filter(self):
        text = self.search.text().lower()
        file_filter = self.file_filter.currentText()

        self.point_list.waypoints = []

        for wp in self.all_waypoints:
            if file_filter != "Tous fichiers" and wp.source_file != file_filter:
                continue

            if text and text not in wp.name.lower():
                continue

            self.point_list.waypoints.append(wp)

        self.point_list.refresh()

    # -----------------------------
    def add_output(self):
        name, ok = QInputDialog.getText(self, "Output", "Nom fichier:")

        if not ok:
            return

        lbl = QLabel()
        lbl.base_name = name  # 🔥 stock nom original

        lst = DropList()
        lst.parent_window = self
        lst.label = lbl  # 🔥 lien liste → label

        # init texte
        lbl.setText(f"{name} (0 points)")

        self.output_layout.addWidget(lbl)
        self.output_layout.addWidget(lst)

        self.output_lists.append(lst)
        self.output_names.append(name)

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = GPXDispatcher()
    w.resize(900, 500)
    w.show()
    sys.exit(app.exec_())