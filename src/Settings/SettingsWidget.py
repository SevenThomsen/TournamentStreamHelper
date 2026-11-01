from qtpy.QtCore import *
from qtpy.QtWidgets import *
from ..TSHColorButton import TSHColorButton
from ..SettingsManager import SettingsManager
import textwrap


class SettingsWidget(QWidget):
    def __init__(self, settingsBase="", settings=[]):
        super().__init__()

        self.settingsBase = settingsBase
        self.settingsCount = 0

        # Create a layout for the widget
        layout = QGridLayout()
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setVerticalSpacing(4)
        layout.setHorizontalSpacing(16)
        layout.setContentsMargins(8, 8, 8, 8)

        # Set the layout for the widget
        self.setLayout(layout)
        layout.setRowStretch(0, 1)

        for setting in settings:
            self.AddSetting(*setting)

    def AddSetting(self, name: str, setting: str, type: str, defaultValue, callback=lambda: None, tooltip=None):
        row = self.settingsCount
        self.settingsCount += 1

        # Background banding frame
        bg = QFrame()
        bg.setObjectName("settingsRowBand")
        bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if row % 2 == 0:
            bg.setStyleSheet("background-color: #1a1a20; border-radius: 6px;")
        else:
            bg.setStyleSheet("background-color: transparent; border-radius: 6px;")
        self.layout().addWidget(bg, row, 0, 1, 3)
        bg.lower()

        lbl = QLabel(name)
        lbl.setStyleSheet("padding-left: 10px; background: transparent;")
        self.layout().addWidget(lbl, row, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        resetButton = QPushButton(
            QApplication.translate("settings", "Default"))
        resetButton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        resetButton.setStyleSheet("margin-right: 8px;")

        if type == "checkbox":
            settingWidget = QCheckBox()
            settingWidget.setChecked(SettingsManager.Get(
                self.settingsBase+"."+setting, defaultValue))
            settingWidget.stateChanged.connect(
                lambda val=None: SettingsManager.Set(self.settingsBase+"."+setting, settingWidget.isChecked()))
            resetButton.clicked.connect(
                lambda bt=None, settingWidget=settingWidget:
                settingWidget.setChecked(defaultValue)
            )
            self.layout().addWidget(settingWidget, row, 1, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        elif type == "spinbox":
            settingWidget = QSpinBox()
            settingWidget.setMinimum(1)
            settingWidget.setMaximum(99999)
            settingWidget.setValue(SettingsManager.Get(
                self.settingsBase+"."+setting, defaultValue))
            settingWidget.valueChanged.connect(
                lambda val=None: SettingsManager.Set(self.settingsBase+"."+setting, settingWidget.value()))
            resetButton.clicked.connect(
                lambda bt=None, settingWidget=settingWidget:
                settingWidget.setValue(defaultValue)
            )
            self.layout().addWidget(settingWidget, row, 1, Qt.AlignmentFlag.AlignVCenter)
        elif type == "hotkey":
            settingWidget = QKeySequenceEdit()
            settingWidget.keySequenceChanged.connect(
                lambda keySequence, settingWidget=settingWidget:
                settingWidget.setKeySequence(keySequence.toString().split(",")[
                    0]) if keySequence.count() > 0 else None
            )
            settingWidget.setKeySequence(SettingsManager.Get(
                self.settingsBase+"."+setting, defaultValue))
            settingWidget.keySequenceChanged.connect(
                lambda sequence=None, setting=setting: [
                    SettingsManager.Set(
                        self.settingsBase+"."+setting, sequence.toString()),
                    self.CheckCallable(callback)
                ]
            )
            resetButton.clicked.connect(
                lambda bt=None, setting=setting, settingWidget=settingWidget: [
                    settingWidget.setKeySequence(defaultValue),
                    self.CheckCallable(callback)
                ]
            )
            self.layout().addWidget(settingWidget, row, 1, Qt.AlignmentFlag.AlignVCenter)
        elif type == "textbox" or type == "password":
            settingWidget = QLineEdit()
            if type == "password":
                settingWidget.setEchoMode(QLineEdit.Password)
            settingWidget.textChanged.connect(
                lambda val=None: SettingsManager.Set(self.settingsBase+"."+setting, settingWidget.text()))
            settingWidget.setText(SettingsManager.Get(
                self.settingsBase+"."+setting, defaultValue))
            resetButton.clicked.connect(
                lambda bt=None, setting=setting, settingWidget=settingWidget: [
                    settingWidget.setText(defaultValue),
                    self.CheckCallable(callback)
                ]
            )
            self.layout().addWidget(settingWidget, row, 1, Qt.AlignmentFlag.AlignVCenter)
        elif type == "color":
            settingWidget = TSHColorButton(color=SettingsManager.Get(self.settingsBase+"."+setting, defaultValue), disable_right_click=True)
            settingWidget.setFixedSize(24, 24)
            settingWidget.colorChanged.connect(
                lambda val=None: SettingsManager.Set(self.settingsBase+"."+setting, settingWidget.color()))
            resetButton.clicked.connect(
                lambda bt=None, setting=setting, settingWidget=settingWidget: [
                    settingWidget.setColor(defaultValue),
                    self.CheckCallable(callback)
                ]
            )
            self.layout().addWidget(settingWidget, row, 1, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        if tooltip:
            settingWidget.setToolTip('\n'.join(textwrap.wrap(tooltip, 40)))

        self.layout().addWidget(resetButton, row, 2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self.layout().setRowMinimumHeight(row, 38)
        self.layout().setRowStretch(row, 0)
        self.layout().setRowStretch(row + 1, 1)

    def CheckCallable(self, callback):
        if callable(callback):
            return callback()
        else:
            return None
