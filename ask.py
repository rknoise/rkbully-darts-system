"""Igen/Nem megerősítő kérdés magyar gombokkal (a Qt alap „Yes/No” gombjai angolok lennének)."""
from PySide6.QtWidgets import QMessageBox


def confirm(parent, title, text, yes="Igen", no="Nem"):
    """True, ha a felhasználó az Igen gombot nyomta. Az alapértelmezett (Enter) és az Esc is a Nem."""
    box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.NoButton, parent)
    yes_btn = box.addButton(yes, QMessageBox.YesRole)
    no_btn = box.addButton(no, QMessageBox.NoRole)
    box.setDefaultButton(no_btn)
    box.setEscapeButton(no_btn)
    box.exec()
    answer = box.clickedButton() is yes_btn
    box.deleteLater()
    return answer
