from aqt import mw
from aqt.qt import QAction
from .config import ConfigDialog

def open_shiritori():
    dialog = ConfigDialog(mw)
    dialog.exec()

# Create menu item
action = QAction("Shiritori", mw)
action.triggered.connect(open_shiritori)
mw.form.menuTools.addAction(action)
