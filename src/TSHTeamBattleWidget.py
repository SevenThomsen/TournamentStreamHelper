from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import QIcon, QAction
from qtpy import uic
from typing import List
import math
from loguru import logger
from .SettingsManager import SettingsManager
from .StateManager import StateManager
from .TSHTeamBattleModeEnum import TSHTeamBattleModeEnum
from .Helpers.TSHDirHelper import TSHResolve
from .Helpers.TSHSponsorHelper import TSHSponsorHelper
from .TSHTeamPlayerWidget import TSHTeamPlayerWidget
from .TSHColorButton import TSHColorButton

from .TournamentDataProvider.NexusRoomClient import NexusRoomClient
from .TSHGameAssetManager import TSHGameAssetManager
from .Helpers.TSHLocaleHelper import TSHLocaleHelper
from .Helpers.TSHVersionHelper import add_beta_label
from .Helpers.TSHCharacterHelper import normalize_character_name

class TSHTeamBattleSignals(QObject):
    # GENERAL SIGNALS
    reset_all_stocks       = Signal()
    reset_everything       = Signal()
    dynamicSpinner_changed = Signal()

    # TEAM 1 SIGNALS
    team1_next_active_player    = Signal()
    team1_stock_up              = Signal()
    team1_stock_down            = Signal()
    team1_active_player_changed = Signal(int)

    # TEAM 2 SIGNALS
    team2_next_active_player    = Signal()
    team2_stock_up              = Signal()
    team2_stock_down            = Signal()
    team2_active_player_changed = Signal(int)

# =====================================================
# FUTURE TODOs
# =====================================================
# TODO: Handle player spinner reset when a new active player is selected on opposing team in FIRST_TO
# TODO: Handle triggering "deaths" for the other team when in FIRST_TO and the other team reaches the correct score
# TODO: Add a setting to be able to set the initial value of a stock pool or a first to match up (quicker setup I guess?)
# TODO: Track current active players for both teams via index
# TODO: Add a checkbox to determine if we want to auto track to the next player in line when they "die"
# =====================================================
# FOR REMOTE CONTROL
# =====================================================
# TODO: Add Webserver calls to handle remote control (And add new Elgato Stream Deck plugin to main repo)
# TODO: Link signals above to calls
# TODO: Add a handle to one press jump to the next player in line for active (just check to make sure it's within array bounds and not dead, and if it's at the end of the array, loop back around)
# =====================================================
class TSHTeamBattleWidget(QDockWidget):
    instance: "TSHTeamBattleWidget" = None
    battleMode = TSHTeamBattleModeEnum.STOCK_POOL

    playerWidgets: List[TSHTeamPlayerWidget]      = []
    team1playerWidgets: List[TSHTeamPlayerWidget] = []
    team2playerWidgets: List[TSHTeamPlayerWidget] = []

    currentActiveIndexTeam1: int = 0
    currentActiveIndexTeam2: int = 0

    def __init__(self, *args):
        super().__init__(*args)
        TSHTeamBattleWidget.instance = self
        logger.info("BATTLE START")
        self.signals = TSHTeamBattleSignals()

        StateManager.Unset("team_battle")

        self.setWindowTitle(add_beta_label(QApplication.translate("app", "Crew/Team Battle"), "team_battle"))
        self.setFloating(True)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.widget = QWidget()
        self.setWidget(self.widget)
        self.widget.setLayout(QVBoxLayout())
        self.setWindowFlags(Qt.WindowType.Window)

        self.playerNumber = QSpinBox()
        self.playerNumber.setObjectName("playerNumber")
        self.playerNumber.setFixedWidth(52)
        self.playerNumber.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.playerNumber.setStyleSheet("QSpinBox { padding-right: 14px; padding-left: 2px; }")
        self.playerNumber.valueChanged.connect(
            lambda val: self.SetPlayersPerTeam(val))

        self.characterNumber = QSpinBox()
        self.characterNumber.setFixedWidth(52)
        self.characterNumber.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.characterNumber.setStyleSheet("QSpinBox { padding-right: 14px; padding-left: 2px; }")
        self.characterNumber.valueChanged.connect(self.SetCharacterNumber)

        self.lifeLabel = QLabel(QApplication.translate("app", "Stocks"))
        self.livesNumber = QSpinBox()
        self.livesNumber.setFixedWidth(52)
        self.livesNumber.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.livesNumber.setStyleSheet("QSpinBox { padding-right: 14px; padding-left: 2px; }")
        self.livesNumber.valueChanged.connect(self.SetSpinnerForPlayers)
        self.livesNumber.valueChanged.connect(self.TotalScoreExport)

        self.modeCombo = QComboBox()
        for mode in TSHTeamBattleModeEnum:
            self.modeCombo.addItem(mode.translated())
        self.modeCombo.currentIndexChanged.connect(self.SwitchBattleMode)

        self.phaseCombo = QComboBox()
        self.phaseCombo.setObjectName("phaseCombo")
        self.phaseCombo.setEditable(True)
        self.phaseCombo.currentIndexChanged.connect(self.PhaseExport)
        self.phaseCombo.lineEdit().editingFinished.connect(self.PhaseExport)
        self.phaseCombo.addItem("")
        TSHLocaleHelper.LoadPhaseNamesToWidget(self.phaseCombo)

        self.matchCombo = QComboBox()
        self.matchCombo.setObjectName("matchCombo")
        self.matchCombo.setEditable(True)
        self.matchCombo.currentIndexChanged.connect(self.MatchExport)
        self.matchCombo.lineEdit().editingFinished.connect(self.MatchExport)
        self.matchCombo.addItem("")
        TSHLocaleHelper.LoadMatchNamesToWidget(self.matchCombo)

        self.bestOf = QSpinBox()
        self.bestOf.setObjectName("bestOf")
        self.bestOf.setFixedWidth(52)
        self.bestOf.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bestOf.setStyleSheet("QSpinBox { padding-right: 14px; padding-left: 2px; }")
        self.bestOf.setMinimum(0)
        self.bestOf.setMaximum(99)
        self.bestOf.setValue(3)
        self.bestOf.valueChanged.connect(self.ExportBestOf)

        resetValues = QPushButton(QApplication.translate("app", "Reset Player Mode Values"))
        resetValues.setFixedHeight(24)
        resetValues.clicked.connect(self.ResetAllStocks)

        resetEverything = QPushButton(QApplication.translate("app", "Reset Battle Mode"))
        resetEverything.setFixedHeight(24)
        resetEverything.clicked.connect(self.ResetEverything)

        # Top toolbar row
        row = QWidget()
        rowLayout = QHBoxLayout(row)
        rowLayout.setContentsMargins(4, 2, 4, 2)
        rowLayout.setSpacing(10)
        row.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        self.widget.layout().addWidget(row, 0, Qt.AlignmentFlag.AlignTop)

        # Group 1: Match Rules (Players, Characters, Mode, Stocks)
        rulesCol = QWidget()
        rulesLayout = QGridLayout(rulesCol)
        rulesLayout.setContentsMargins(0, 0, 0, 0)
        rulesLayout.setHorizontalSpacing(6)
        rulesLayout.setVerticalSpacing(3)

        playerLabel = QLabel(QApplication.translate("app", "Players"))
        charLabel = QLabel(QApplication.translate("app", "Characters"))
        modeLabel = QLabel(QApplication.translate("app", "Mode"))

        rulesLayout.addWidget(playerLabel, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        rulesLayout.addWidget(self.playerNumber, 0, 1, Qt.AlignmentFlag.AlignVCenter)
        rulesLayout.addWidget(modeLabel, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        rulesLayout.addWidget(self.modeCombo, 0, 3, Qt.AlignmentFlag.AlignVCenter)

        rulesLayout.addWidget(charLabel, 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        rulesLayout.addWidget(self.characterNumber, 1, 1, Qt.AlignmentFlag.AlignVCenter)
        rulesLayout.addWidget(self.lifeLabel, 1, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        rulesLayout.addWidget(self.livesNumber, 1, 3, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        rowLayout.addWidget(rulesCol)

        # Group 2: Tournament Info (Phase, Best of, Match)
        infoCol = QWidget()
        infoLayout = QGridLayout(infoCol)
        infoLayout.setContentsMargins(0, 0, 0, 0)
        infoLayout.setHorizontalSpacing(6)
        infoLayout.setVerticalSpacing(3)

        phaseLabel = QLabel(QApplication.translate("app", "Phase"))
        matchLabel = QLabel(QApplication.translate("app", "Match"))
        bestOfLabel = QLabel(QApplication.translate("app", "Best of"))

        infoLayout.addWidget(phaseLabel, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        infoLayout.addWidget(self.phaseCombo, 0, 1, Qt.AlignmentFlag.AlignVCenter)
        infoLayout.addWidget(bestOfLabel, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        infoLayout.addWidget(self.bestOf, 0, 3, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        infoLayout.addWidget(matchLabel, 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        infoLayout.addWidget(self.matchCombo, 1, 1, 1, 3, Qt.AlignmentFlag.AlignVCenter)

        rowLayout.addWidget(infoCol)

        # Group 3: Actions & Visibility
        actionsCol = QWidget()
        actionsLayout = QGridLayout(actionsCol)
        actionsLayout.setContentsMargins(0, 0, 0, 0)
        actionsLayout.setHorizontalSpacing(6)
        actionsLayout.setVerticalSpacing(3)

        self.eyeBt = QToolButton()
        self.eyeBt.setIcon(QIcon('assets/icons/eye.svg'))
        self.eyeBt.setFixedSize(26, 26)
        self.eyeBt.setIconSize(QSize(18, 18))
        self.eyeBt.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu()
        self.eyeBt.setMenu(menu)

        menu.addSection(QApplication.translate("app", "Players"))

        self.elements = [
            [QApplication.translate("app", "Sponsors"),   ["team"],                            "show_sponsors"],
            [QApplication.translate("app", "Twitter"),    ["twitter", "twitterLabel"],           "show_social"],
            [QApplication.translate("app", "Location"),   ["locationLabel", "state", "country"], "show_location"],
            [QApplication.translate("app", "Characters"), ["characters"],                        "show_characters"],
            [QApplication.translate("app", "Pronouns"),   ["pronoun"],                           "show_pronouns"],
        ]
        for element in self.elements:
            action: QAction = self.eyeBt.menu().addAction(element[0])
            action.setCheckable(True)
            default_val = False if element[2] == "show_sponsors" else True
            action.setChecked(SettingsManager.Get(f"display_options.{element[2]}", default_val))
            action.toggled.connect(
                lambda toggled, action=action, element=element: [
                    self.ToggleElements(action, element[1]),
                    SettingsManager.Set(f"display_options.{element[2]}", toggled)
                ]
            )

        self.btNexus = QPushButton(QApplication.translate("app", "Load from The Nexus"))
        self.btNexus.setObjectName("btNexusLive")
        self.btNexus.setFixedHeight(24)
        self.btNexus.setIcon(QIcon(TSHResolve("assets/icons/nexus.svg")))
        self.btNexus.setIconSize(QSize(16, 16))
        self.btNexus.clicked.connect(self.PromptNexusLink)

        self.nexusStatusWidget = QFrame()
        self.nexusStatusWidget.setObjectName("nexusStatusWidget")
        self.nexusStatusWidget.setFixedHeight(24)
        statusLayout = QHBoxLayout(self.nexusStatusWidget)
        statusLayout.setContentsMargins(6, 0, 6, 0)
        statusLayout.setSpacing(6)
        statusLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.nexusStatusDot = QLabel()
        self.nexusStatusDot.setObjectName("nexusStatusDot")
        self.nexusStatusDot.setFixedSize(8, 8)
        self.nexusStatusDot.setStyleSheet("background-color: transparent; border-radius: 4px;")

        self.lblNexusStatus = QLabel("")
        self.lblNexusStatus.setObjectName("lblNexusStatus")
        self.lblNexusStatus.setStyleSheet("color: #8e8e93; font-size: 11px; font-weight: 500;")

        statusLayout.addWidget(self.nexusStatusDot)
        statusLayout.addWidget(self.lblNexusStatus)

        actionsLayout.addWidget(resetValues, 0, 0)
        actionsLayout.addWidget(self.btNexus, 0, 1)
        actionsLayout.addWidget(resetEverything, 1, 0)
        actionsLayout.addWidget(self.nexusStatusWidget, 1, 1)

        rowLayout.addWidget(actionsCol)
        rowLayout.addStretch()

        # Visibility (Far Right, matching normal scoreboard)
        self.eyeBt.setFixedSize(24, 24)
        self.eyeBt.setIconSize(QSize(16, 16))
        rowLayout.addWidget(self.eyeBt, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        scrollArea = QScrollArea()
        scrollArea.setFrameShadow(QFrame.Shadow.Plain)
        scrollArea.setFrameShape(QFrame.Shape.Panel)
        scrollArea.setWidgetResizable(True)

        self.widgetArea = QWidget()
        self.widgetArea.setLayout(QHBoxLayout())
        self.widgetArea.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Preferred)
        scrollArea.setWidget(self.widgetArea)

        self.team1column = uic.loadUi(TSHResolve("src/layout/TSHBattleTeam.ui"))
        self.team1column.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Preferred)
        if self.team1column.findChild(QScrollArea):
            sa1 = self.team1column.findChild(QScrollArea)
            sa1.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            if sa1.widget() and sa1.widget().layout():
                sa1.widget().layout().setContentsMargins(0, 0, 8, 0)
        self.team1column.findChild(QLineEdit, "teamName").editingFinished.connect(self.Team1SponsorExport)
        DEFAULT_TEAM1_COLOR = SettingsManager.Get("general.team_1_default_color", "#fe3636")
        self.colorButton1 = TSHColorButton(color=DEFAULT_TEAM1_COLOR, ignore_same_color=False)
        self.team1column.findChild(QHBoxLayout, "team_header").layout().insertWidget(0, self.colorButton1)
        self.colorButton1.colorChanged.connect(
            lambda color: StateManager.Set(f"team_battle.team.{1}.color", color))
        self.colorButton1.setColor(DEFAULT_TEAM1_COLOR)
        self._syncing_stocks = 0

        self.team1score = QSpinBox()
        self.team1score.setObjectName("team1score")
        self.team1score.setFixedWidth(52)
        self.team1score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.team1score.setStyleSheet("QSpinBox { padding-right: 14px; padding-left: 2px; }")
        self.team1score.setRange(0, 99)
        self.team1score.setToolTip(QApplication.translate("app", "Series Score (Sets Won)"))
        self.team1score.valueChanged.connect(self.Team1TotalScoreExport)

        self.team1stocks = QSpinBox()
        self.team1stocks.setObjectName("team1stocks")
        self.team1stocks.setFixedWidth(60)
        self.team1stocks.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.team1stocks.setStyleSheet("QSpinBox { padding-right: 14px; padding-left: 2px; }")
        self.team1stocks.setRange(0, 999)
        self.team1stocks.setValue(12)
        self.team1stocks.setToolTip(QApplication.translate("app", "Team Remaining Stocks"))
        self.team1stocks.valueChanged.connect(self.Team1StocksExport)

        t1_header = self.team1column.findChild(QHBoxLayout, "team_header")
        t1_score_label = QLabel(QApplication.translate("app", "Score:"))
        t1_stocks_label = QLabel(QApplication.translate("app", "Stocks:"))
        t1_header.addWidget(t1_score_label)
        t1_header.addWidget(self.team1score)
        t1_header.addWidget(t1_stocks_label)
        t1_header.addWidget(self.team1stocks)
        self.widgetArea.layout().addWidget(self.team1column)

        self.team2column = uic.loadUi(TSHResolve("src/layout/TSHBattleTeam.ui"))
        self.team2column.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Preferred)
        if self.team2column.findChild(QScrollArea):
            sa2 = self.team2column.findChild(QScrollArea)
            sa2.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            if sa2.widget() and sa2.widget().layout():
                sa2.widget().layout().setContentsMargins(0, 0, 8, 0)
        self.team2column.findChild(QLineEdit, "teamName").editingFinished.connect(self.Team2SponsorExport)
        DEFAULT_TEAM2_COLOR = SettingsManager.Get("general.team_2_default_color", "#2e89ff")
        self.colorButton2 = TSHColorButton(color=DEFAULT_TEAM2_COLOR, ignore_same_color=False)
        self.team2column.findChild(QHBoxLayout, "team_header").layout().insertWidget(0, self.colorButton2)
        self.colorButton2.colorChanged.connect(
            lambda color: StateManager.Set(f"team_battle.team.{2}.color", color))
        self.colorButton2.setColor(DEFAULT_TEAM2_COLOR)

        self.team2score = QSpinBox()
        self.team2score.setObjectName("team2score")
        self.team2score.setFixedWidth(52)
        self.team2score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.team2score.setStyleSheet("QSpinBox { padding-right: 14px; padding-left: 2px; }")
        self.team2score.setRange(0, 99)
        self.team2score.setToolTip(QApplication.translate("app", "Series Score (Sets Won)"))
        self.team2score.valueChanged.connect(self.Team2TotalScoreExport)

        self.team2stocks = QSpinBox()
        self.team2stocks.setObjectName("team2stocks")
        self.team2stocks.setFixedWidth(60)
        self.team2stocks.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.team2stocks.setStyleSheet("QSpinBox { padding-right: 14px; padding-left: 2px; }")
        self.team2stocks.setRange(0, 999)
        self.team2stocks.setValue(12)
        self.team2stocks.setToolTip(QApplication.translate("app", "Team Remaining Stocks"))
        self.team2stocks.valueChanged.connect(self.Team2StocksExport)

        t2_header = self.team2column.findChild(QHBoxLayout, "team_header")
        t2_score_label = QLabel(QApplication.translate("app", "Score:"))
        t2_stocks_label = QLabel(QApplication.translate("app", "Stocks:"))
        t2_header.addWidget(t2_score_label)
        t2_header.addWidget(self.team2score)
        t2_header.addWidget(t2_stocks_label)
        t2_header.addWidget(self.team2stocks)
        self.widgetArea.layout().addWidget(self.team2column)

        self.widget.layout().addWidget(scrollArea, 1)

        self.Team1StocksExport()
        self.Team2StocksExport()


        # Hook into Signals for Control
        self.signals.reset_all_stocks.connect(self.ResetAllStocks)
        self.signals.reset_everything.connect(self.ResetEverything)
        self.signals.dynamicSpinner_changed.connect(self.TotalScoreExport)



        # Nexus Room Client

        self.nexusClient = NexusRoomClient(self)

        self.nexusClient.signals.room_updated.connect(self.ApplyNexusData)

        self.nexusClient.signals.connection_status_changed.connect(self.OnNexusStatusChanged)

        self.nexusClient.signals.error_occurred.connect(self.OnNexusError)

        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.nexusClient.disconnect)

        # Nexus Game Transition Delay State (holds completed game on screen for 15s)
        self._last_game_id = None
        self._last_game_order = None
        self._last_round_number = None
        self._last_effective_active = {}
        self._last_home_score = None
        self._last_away_score = None
        self._pending_snapshot = None
        self._transition_seconds_left = 0
        self._completed_game_label = "Game"
        self._transition_timer = QTimer(self)
        self._transition_timer.setInterval(1000)
        self._transition_timer.timeout.connect(self._OnTransitionTimerTick)

        self.signals.team1_stock_up.connect(self.T1_Stock_Up)
        self.signals.team1_stock_down.connect(self.T1_Stock_Down)
        self.signals.team2_stock_up.connect(self.T2_Stock_Up)
        self.signals.team2_stock_down.connect(self.T2_Stock_Down)

        self.ExportBestOf()
        
        self._syncing_stocks += 1
        try:
            self.playerNumber.setValue(1)
            self.characterNumber.setValue(1)
            self.livesNumber.setValue(3)
            self.team1stocks.setValue(12)
            self.team2stocks.setValue(12)
        finally:
            self._syncing_stocks = 0

    # =====================================================
    # GENERAL CONTROL METHODS
    # =====================================================
    def SwitchBattleMode(self):
        # TODO: Do above with player widgets as well to make sure information displayed is accurate.
        self.battleMode = TSHTeamBattleModeEnum.MatchToMode(self.modeCombo.currentText())
        logger.info(f"Switching Battle Mode to: {self.battleMode.name}")

        if self.battleMode is TSHTeamBattleModeEnum.STOCK_POOL:
            self.lifeLabel.setText(QApplication.translate("app", "Stocks"))
            self.livesNumber.setValue(3)
            for pw in self.playerWidgets:
                pw.SetBattleMode(self.battleMode)
        elif self.battleMode is TSHTeamBattleModeEnum.FIRST_TO:
            self.lifeLabel.setText(QApplication.translate("app", "First To"))
            self.livesNumber.setValue(0)
            for pw in self.playerWidgets:
                pw.SetBattleMode(self.battleMode)
        StateManager.Set("team_battle.battle_mode", self.battleMode.name)
    
    def ResetAllStocks(self):
        self._syncing_stocks += 1
        try:
            for pw in self.playerWidgets:
                pw.ResetDynamicSpinner()
            stk_per_player = self.livesNumber.value() if self.livesNumber.value() > 0 else 3
            self.team1stocks.setValue(len(self.team1playerWidgets) * stk_per_player)
            self.team2stocks.setValue(len(self.team2playerWidgets) * stk_per_player)
        finally:
            self._syncing_stocks = 0
        self.TotalScoreExport()

    def ResetEverything(self):
        self._syncing_stocks += 1
        try:
            for pw in self.playerWidgets:
                pw.ResetDynamicSpinner()
                pw.Clear()
            stk_per_player = self.livesNumber.value() if self.livesNumber.value() > 0 else 3
            self.team1stocks.setValue(len(self.team1playerWidgets) * stk_per_player)
            self.team2stocks.setValue(len(self.team2playerWidgets) * stk_per_player)
        finally:
            self._syncing_stocks = 0
        self.TotalScoreExport()
    
    def SetSpinnerForPlayers(self):
        self._syncing_stocks += 1
        try:
            for pw in self.playerWidgets:
                pw.SetDefaultSpinnerValue(self.livesNumber.value())
        finally:
            self._syncing_stocks = max(0, self._syncing_stocks - 1)
    
    # =====================================================
    # NECESSARY PLAYER METHODS
    # =====================================================
    def SetCharacterNumber(self, value):
        for pw in self.playerWidgets:
            pw.SetCharactersPerPlayer(value)
    
    def SetPlayersPerTeam(self, number):
        while len(self.team1playerWidgets) < number:
            p = TSHTeamPlayerWidget(
                index=len(self.team1playerWidgets)+1,
                teamNumber=1,
                path=f'team_battle.team.{1}.player.{len(self.team1playerWidgets)+1}')
            self.playerWidgets.append(p)

            self.team1column.findChild(QScrollArea).widget().layout().addWidget(p)
            p.SetCharactersPerPlayer(self.characterNumber.value())
            p.SetDefaultSpinnerValue(self.livesNumber.value())
            p.SetDefaultSpinnerValue(self.livesNumber.value())


            self.ApplyVisibility(p)
            
            self.signals.dynamicSpinner_changed.connect(p.instanceSignals.dynamicSpinner_changed)
            p.instanceSignals.dynamicSpinner_changed.connect(self.TotalScoreExport)
            p.instanceSignals.stock_delta.connect(self.OnPlayerStockDelta)

            index = len(self.team1playerWidgets)

            p.btMoveUp.clicked.connect(lambda index, p=p: p.SwapWith(
                self.team1playerWidgets[max(0, self.team1playerWidgets.index(p) - 1)]))
            p.btMoveDown.clicked.connect(lambda index, p=p: p.SwapWith(
                self.team1playerWidgets[min(len(self.team1playerWidgets) - 1, self.team1playerWidgets.index(p) + 1)]))

            self.team1playerWidgets.append(p)

            p = TSHTeamPlayerWidget(
                index=len(self.team2playerWidgets)+1,
                teamNumber=2,
                path=f'team_battle.team.{2}.player.{len(self.team2playerWidgets)+1}')
            self.playerWidgets.append(p)

            self.team2column.findChild(QScrollArea).widget().layout().addWidget(p)
            p.SetCharactersPerPlayer(self.characterNumber.value())


            self.ApplyVisibility(p)
            
            self.signals.dynamicSpinner_changed.connect(p.instanceSignals.dynamicSpinner_changed)
            p.instanceSignals.dynamicSpinner_changed.connect(self.TotalScoreExport)
            p.instanceSignals.stock_delta.connect(self.OnPlayerStockDelta)

            index = len(self.team2playerWidgets)

            p.btMoveUp.clicked.connect(lambda index, p=p: p.SwapWith(
                self.team2playerWidgets[max(0, self.team2playerWidgets.index(p) - 1)]))
            p.btMoveDown.clicked.connect(lambda index, p=p: p.SwapWith(
                self.team2playerWidgets[min(len(self.team2playerWidgets) - 1, self.team2playerWidgets.index(p) + 1)]))

            self.team2playerWidgets.append(p)

        while len(self.team1playerWidgets) > number:
            team1player = self.team1playerWidgets[-1]
            StateManager.Unset(team1player.path)
            team1player.setParent(None)
            self.playerWidgets.remove(team1player)
            self.team1playerWidgets.remove(team1player)
            team1player.deleteLater()

            team2player = self.team2playerWidgets[-1]
            StateManager.Unset(team2player.path)
            team2player.setParent(None)
            self.playerWidgets.remove(team2player)
            self.team2playerWidgets.remove(team2player)
            team2player.deleteLater()

        for team in [1, 2]:
            if StateManager.Get(f'team_battle.team.{team}'):
                for k in list(StateManager.Get(f'team_battle.team.{team}.player').keys()):
                    if int(k) > number:
                        StateManager.Unset(
                            f'team_battle.team.{team}.player.{k}')
        
        self.SwitchBattleMode()
        self.SetSpinnerForPlayers()

    def ApplyVisibility(self, pw):
        if hasattr(self, "elements"):
            for element in self.elements:
                default_val = False if element[2] == "show_sponsors" else True
                visible = SettingsManager.Get(f"display_options.{element[2]}", default_val)
                for el in element[1]:
                    w = pw.findChild(QWidget, el)
                    if w:
                        w.setVisible(visible)

    # =====================================================
    # NEXT ACTIVE PLAYERS
    # =====================================================
    def Team1NextUp(self):
        # TODO: Have this jump to the next player when the current player is "eliminated"
        return
    
    def Team2NextUp(self):
        # TODO: Have this jump to the next player when the current player is "eliminated"
        return

    def ToggleElements(self, action: QAction, elements):
        for pw in self.playerWidgets:
            for element in elements:
                w = pw.findChild(QWidget, element)
                if w:
                    w.setVisible(action.isChecked())

    # =====================================================
    # TEAM 1 STOCK CONTROL
    # =====================================================
    def T1_Stock_Up(self):
        if self.battleMode is TSHTeamBattleModeEnum.STOCK_POOL:
            # TODO: Tick Down Stock for Team 2
            return
        elif self.battleMode is TSHTeamBattleModeEnum.FIRST_TO:
            # TODO: Tick Up Score for Team 1
            return
        
    def T1_Stock_Down(self):
        if self.battleMode is TSHTeamBattleModeEnum.STOCK_POOL:
            # TODO: Tick Up Stock for Team 2
            return
        elif self.battleMode is TSHTeamBattleModeEnum.FIRST_TO:
            # TODO: Tick Down Score for Team 1
            return

    # =====================================================
    # TEAM 2 STOCK CONTROL
    # =====================================================
    def T2_Stock_Up(self):
        if self.battleMode is TSHTeamBattleModeEnum.STOCK_POOL:
            # TODO: Tick Down Stock for Team 1
            return
        elif self.battleMode is TSHTeamBattleModeEnum.FIRST_TO:
            # TODO: Tick Up Score for Team 2
            return
        
    def T2_Stock_Down(self):
        if self.battleMode is TSHTeamBattleModeEnum.STOCK_POOL:
            # TODO: Tick Up Stock for Team 1
            return
        elif self.battleMode is TSHTeamBattleModeEnum.FIRST_TO:
            # TODO: Tick Down Score for Team 2
            return
    
    # =====================================================
    # EXPORTS
    # =====================================================

    def Team1SponsorExport(self):
        path = f"team_battle.team.{1}"
        team = self.team1column.findChild(QLineEdit, "teamName").text()
        StateManager.Set(path + ".sponsor", team)
        TSHSponsorHelper.ExportValidSponsors(team, path)
    
    def Team2SponsorExport(self):
        path = f"team_battle.team.{2}"
        team = self.team2column.findChild(QLineEdit, "teamName").text()
        StateManager.Set(path + ".sponsor", team)
        TSHSponsorHelper.ExportValidSponsors(team, path)
    
    def PhaseExport(self):
        StateManager.Set("team_battle.phase", self.phaseCombo.currentText())
    
    def MatchExport(self):
        StateManager.Set("team_battle.match", self.matchCombo.currentText())

    def ExportBestOf(self, value=None):
        if value is None:
            value = self.bestOf.value()
        with StateManager.SaveBlock():
            StateManager.Set("team_battle.best_of", value)
            StateManager.Set("team_battle.best_of_short_text", f"BO{value}" if value > 0 else "")
            best_of_template = TSHLocaleHelper.matchNames.get("best_of", "Best of {0}")
            best_of_text = best_of_template.format(value) if value > 0 else ""
            StateManager.Set("team_battle.best_of_text", best_of_text)
            first_to = math.ceil(value / 2) if value > 0 else 0
            StateManager.Set("team_battle.first_to", first_to)
            StateManager.Set("team_battle.first_to_short_text", f"FT{first_to}" if first_to > 0 else "")
            first_to_template = TSHLocaleHelper.matchNames.get("first_to", "First to {0}")
            StateManager.Set("team_battle.first_to_text", first_to_template.format(first_to) if first_to > 0 else "")
    
    def OnPlayerStockDelta(self, team_number: int, delta: int):
        if getattr(self, "_syncing_stocks", 0) > 0:
            return
        if team_number == 1:
            self.team1stocks.setValue(max(0, self.team1stocks.value() + delta))
        elif team_number == 2:
            self.team2stocks.setValue(max(0, self.team2stocks.value() + delta))

    def Team1StocksExport(self):
        if not hasattr(self, "team1stocks"):
            return
        val = self.team1stocks.value()
        with StateManager.SaveBlock():
            StateManager.Set("team_battle.team1_stocks", val)
            StateManager.Set("team_battle.team.1.stocks", val)

    def Team2StocksExport(self):
        if not hasattr(self, "team2stocks"):
            return
        val = self.team2stocks.value()
        with StateManager.SaveBlock():
            StateManager.Set("team_battle.team2_stocks", val)
            StateManager.Set("team_battle.team.2.stocks", val)

    def TotalScoreExport(self):
        self.Team1TotalScoreExport()
        self.Team2TotalScoreExport()
        self.Team1StocksExport()
        self.Team2StocksExport()
    
    def Team1TotalScoreExport(self):
        if not hasattr(self, "team1score"):
            return
        scoreCount = 0
        for player in self.team1playerWidgets:
            scoreCount += player.GetSpinnerValue()
        StateManager.Set("team_battle.team1_spinner-total", scoreCount)
        StateManager.Set("team_battle.team1_total-score", self.team1score.value())
        StateManager.Set("team_battle.team.1.score", self.team1score.value())
    
    def Team2TotalScoreExport(self):
        if not hasattr(self, "team2score"):
            return
        scoreCount = 0
        for player in self.team2playerWidgets:
            scoreCount += player.GetSpinnerValue()
        StateManager.Set("team_battle.team2_spinner-total", scoreCount)
        StateManager.Set("team_battle.team2_total-score", self.team2score.value())
        StateManager.Set("team_battle.team.2.score", self.team2score.value())

    # =====================================================
    # THE NEXUS INTEGRATION
    # =====================================================
    def PromptNexusLink(self):
        if self.nexusClient.is_running:
            dlg = QMessageBox(self)
            dlg.setWindowTitle(QApplication.translate("app", "The Nexus Live Room"))
            dlg.setText(f"Connected to room: {self.nexusClient.slug}\nDo you want to disconnect?")
            dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            dlg.setDefaultButton(QMessageBox.No)
            if dlg.exec() == QMessageBox.Yes:
                self.nexusClient.disconnect()
                self._ResetNexusTransitionState()
            return

        text, ok = QInputDialog.getText(
            self,
            QApplication.translate("app", "Load from The Nexus"),
            QApplication.translate("app", "Paste Moderator TSH Link from The Nexus:\n(e.g. https://thenexus.gg/matches/.../live?token=...)"),
            QLineEdit.Normal,
            ""
        )
        if ok and text.strip():
            self._ResetNexusTransitionState()
            success, err_msg = self.nexusClient.connect_url(text.strip())
            if not success:
                QMessageBox.warning(
                    self,
                    QApplication.translate("app", "Invalid Nexus URL"),
                    err_msg or QApplication.translate("app", "The provided URL is not a valid Nexus match room.")
                )

    def SetNexusStatus(self, state: str, message: str):
        """
        Update the Nexus status indicator with a crisp painted dot and sleek dark-theme badge.
        state: 'connected' | 'connecting' | 'transition' | 'error' | 'disconnected'
        """
        if not message:
            self.nexusStatusDot.setStyleSheet("background-color: transparent;")
            self.lblNexusStatus.setText("")
            self.nexusStatusWidget.setStyleSheet("QFrame#nexusStatusWidget { background-color: transparent; border: none; }")
            return

        self.lblNexusStatus.setText(message)

        if state == "connected":
            self.nexusStatusDot.setStyleSheet("background-color: #22c55e; border-radius: 4px;")
            self.lblNexusStatus.setStyleSheet("color: #e4e4e7; font-size: 11px; font-weight: 500;")
            self.nexusStatusWidget.setStyleSheet(
                "QFrame#nexusStatusWidget { background-color: rgba(34, 197, 94, 0.08); border: 1px solid rgba(34, 197, 94, 0.25); border-radius: 4px; }"
            )
        elif state == "transition":
            self.nexusStatusDot.setStyleSheet("background-color: #38bdf8; border-radius: 4px;")
            self.lblNexusStatus.setStyleSheet("color: #e4e4e7; font-size: 11px; font-weight: 500;")
            self.nexusStatusWidget.setStyleSheet(
                "QFrame#nexusStatusWidget { background-color: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 4px; }"
            )
        elif state == "connecting":
            self.nexusStatusDot.setStyleSheet("background-color: #f59e0b; border-radius: 4px;")
            self.lblNexusStatus.setStyleSheet("color: #d4d4d8; font-size: 11px; font-weight: 500;")
            self.nexusStatusWidget.setStyleSheet(
                "QFrame#nexusStatusWidget { background-color: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 4px; }"
            )
        elif state == "error":
            self.nexusStatusDot.setStyleSheet("background-color: #ef4444; border-radius: 4px;")
            self.lblNexusStatus.setStyleSheet("color: #fca5a5; font-size: 11px; font-weight: 500;")
            self.nexusStatusWidget.setStyleSheet(
                "QFrame#nexusStatusWidget { background-color: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 4px; }"
            )
        else:  # disconnected
            self.nexusStatusDot.setStyleSheet("background-color: #71717a; border-radius: 4px;")
            self.lblNexusStatus.setStyleSheet("color: #8e8e93; font-size: 11px; font-weight: 500;")
            self.nexusStatusWidget.setStyleSheet(
                "QFrame#nexusStatusWidget { background-color: #18181b; border: 1px solid #2e2e33; border-radius: 4px; }"
            )

    def OnNexusStatusChanged(self, connected: bool, message: str):
        if connected:
            self.btNexus.setText(QApplication.translate("app", "Nexus (Connected)"))
            self.SetNexusStatus("connected", message)
        elif "Connecting" in message or "Reconnecting" in message:
            self.btNexus.setText(QApplication.translate("app", "Nexus (Connecting...)"))
            self.SetNexusStatus("connecting", message)
        else:
            self._ResetNexusTransitionState()
            self.btNexus.setText(QApplication.translate("app", "Load from The Nexus"))
            self.SetNexusStatus("disconnected", message if message != "Disconnected" else "")

    def OnNexusError(self, error: str):
        logger.error(f"[TSHTeamBattleWidget] Nexus error: {error}")
        msg = f"{error[:25]}..." if len(error) > 25 else error
        self.SetNexusStatus("error", msg)

    def _ResetNexusTransitionState(self):
        if hasattr(self, "_transition_timer") and self._transition_timer.isActive():
            self._transition_timer.stop()
        self._pending_snapshot = None
        self._last_game_id = None
        self._last_game_order = None
        self._last_round_number = None
        self._last_effective_active = {}
        self._last_home_score = None
        self._last_away_score = None
        self._transition_seconds_left = 0

    def ApplyNexusData(self, snapshot: dict):
        if getattr(self, "_transition_timer", None) and self._transition_timer.isActive():
            # While holding the completed game display for 30s, queue the latest snapshot
            self._pending_snapshot = snapshot
            return

        fixture = snapshot.get("fixture") or {}
        active_game = snapshot.get("active_game") or {}
        live_state = snapshot.get("live_state") or {}

        incoming_game_id = active_game.get("id")
        incoming_game_order = active_game.get("game_order")
        incoming_home_score = fixture.get("home_score")
        incoming_away_score = fixture.get("away_score")
        is_match_complete = (
            fixture.get("status") == "completed" or
            live_state.get("phase") == "complete"
        )

        is_game_transition = False
        if self._last_game_order is not None and incoming_game_order is not None:
            if incoming_game_order > self._last_game_order:
                is_game_transition = True
        elif self._last_game_id is not None and incoming_game_id is not None:
            if incoming_game_id != self._last_game_id:
                is_game_transition = True

        if is_game_transition and not is_match_complete:
            # Game completed! Hold the final completed board for 30s before applying the new game.
            # 1. Update series score immediately so OBS diamond displays the new game win
            if incoming_home_score is not None:
                self.team1score.setValue(int(incoming_home_score))
            if incoming_away_score is not None:
                self.team2score.setValue(int(incoming_away_score))

            # 2. Mark the losing team at 0 stocks
            home_won = (
                self._last_home_score is not None and incoming_home_score is not None and
                int(incoming_home_score) > int(self._last_home_score)
            )
            away_won = (
                self._last_away_score is not None and incoming_away_score is not None and
                int(incoming_away_score) > int(self._last_away_score)
            )
            if not home_won and not away_won:
                if incoming_home_score is not None and incoming_away_score is not None:
                    if int(incoming_home_score) > int(self._last_home_score or 0):
                        home_won = True
                    elif int(incoming_away_score) > int(self._last_away_score or 0):
                        away_won = True

            if home_won:
                self.team2stocks.setValue(0)
                for pw in self.team2playerWidgets:
                    if pw.IsActive():
                        pw.dynamicSpinner.setValue(0)
                        pw.SetEliminatedStatus(True)
            elif away_won:
                self.team1stocks.setValue(0)
                for pw in self.team1playerWidgets:
                    if pw.IsActive():
                        pw.dynamicSpinner.setValue(0)
                        pw.SetEliminatedStatus(True)

            self.TotalScoreExport()

            # 3. Queue snapshot and start 30s countdown
            self._pending_snapshot = snapshot
            self._transition_seconds_left = 30
            completed_game_num = self._last_game_order or (incoming_game_order - 1 if incoming_game_order else 1)
            self._completed_game_label = f"Game {completed_game_num}"
            self.SetNexusStatus("transition", f"{self._completed_game_label} complete. Next game in {self._transition_seconds_left}s...")
            self._transition_timer.start(1000)
            return

        self._DoApplyNexusData(snapshot)

    def _OnTransitionTimerTick(self):
        self._transition_seconds_left -= 1
        if self._transition_seconds_left > 0:
            self.SetNexusStatus("transition", f"{self._completed_game_label} complete. Next game in {self._transition_seconds_left}s...")
        else:
            self._transition_timer.stop()
            self._ApplyPendingGameSnapshot()

    def _ApplyPendingGameSnapshot(self):
        snapshot = self._pending_snapshot
        self._pending_snapshot = None
        if snapshot:
            self._DoApplyNexusData(snapshot)
            self.SetNexusStatus("connected", "Connected")

    def _DoApplyNexusData(self, snapshot: dict):
        try:
            StateManager.BlockSaving()
            self._syncing_stocks += 1

            fixture = snapshot.get("fixture") or {}
            home_team = snapshot.get("home_team") or {}
            away_team = snapshot.get("away_team") or {}
            players = snapshot.get("players") or []
            active_game = snapshot.get("active_game") or {}
            live_state = snapshot.get("live_state") or {}
            roster_selections = snapshot.get("roster_selections") or []
            blind_picks = snapshot.get("blind_picks") or []

            # 1. Team Names
            home_name = home_team.get("name") or home_team.get("short_name") or ""
            away_name = away_team.get("name") or away_team.get("short_name") or ""
            if home_name:
                t1 = self.team1column.findChild(QLineEdit, "teamName")
                if t1 and t1.text() != home_name:
                    t1.setText(home_name)
                    self.Team1SponsorExport()
            if away_name:
                t2 = self.team2column.findChild(QLineEdit, "teamName")
                if t2 and t2.text() != away_name:
                    t2.setText(away_name)
                    self.Team2SponsorExport()

            # 2. Match Scores (Series & Remaining Team Stocks)
            if fixture.get("home_score") is not None:
                self.team1score.setValue(int(fixture.get("home_score")))
            if fixture.get("away_score") is not None:
                self.team2score.setValue(int(fixture.get("away_score")))

            round_num = live_state.get("round_number")
            if round_num is not None:
                try:
                    round_num = int(round_num)
                except (ValueError, TypeError):
                    pass
            is_new_round = (self._last_round_number is not None and round_num is not None and round_num != self._last_round_number)

            home_stocks = live_state.get("home_stocks")
            if home_stocks is not None:
                try:
                    h_val = int(home_stocks)
                    # Guard: Do not reset team stocks upward during an active ongoing round!
                    if is_new_round or self._last_round_number is None or self.team1stocks.value() >= h_val:
                        self.team1stocks.setValue(h_val)
                except (ValueError, TypeError):
                    pass
            away_stocks = live_state.get("away_stocks")
            if away_stocks is not None:
                try:
                    a_val = int(away_stocks)
                    # Guard: Do not reset team stocks upward during an active ongoing round!
                    if is_new_round or self._last_round_number is None or self.team2stocks.value() >= a_val:
                        self.team2stocks.setValue(a_val)
                except (ValueError, TypeError):
                    pass

            # 3. Game Rules & Roster Size
            game_type = active_game.get("game", "ultimate")
            stocks_per_player = 4 if game_type == "melee" else 3
            if self.livesNumber.value() != stocks_per_player:
                self.livesNumber.setValue(stocks_per_player)

            home_team_id = fixture.get("home_team_id")
            away_team_id = fixture.get("away_team_id")

            home_players = [p for p in players if p.get("team_id") == home_team_id]
            away_players = [p for p in players if p.get("team_id") == away_team_id]

            roster_size = max(
                len(home_players),
                len(away_players),
                active_game.get("home_roster_size", 0),
                active_game.get("away_roster_size", 0),
                1
            )
            if self.playerNumber.value() != roster_size:
                self.playerNumber.setValue(roster_size)
            self.SetSpinnerForPlayers()

            # 4. Tournament Name, Phase, Best Of & Match Name
            tournament_season = snapshot.get("tournament_season") or {}
            tournament_name = tournament_season.get("tournament_name") or "The Nexus"

            # Set Tournament Name field to "The Nexus" by default
            StateManager.Set("tournamentInfo.tournamentName", tournament_name)
            app = QApplication.instance()
            if app:
                for widget in app.allWidgets():
                    if widget.objectName() == "tournamentName" and isinstance(widget, QLineEdit):
                        if widget.text() != tournament_name:
                            widget.setText(tournament_name)
                            widget.editingFinished.emit()

            season_name = tournament_season.get("name") or "Nexus League"
            if self.phaseCombo.currentText() != season_name:
                self.phaseCombo.setCurrentText(season_name)
                self.PhaseExport()

            # Best of (from fixture or active_game, default 3)
            best_of_val = fixture.get("best_of") or active_game.get("best_of") or 3
            try:
                best_of_val = int(best_of_val)
            except (ValueError, TypeError):
                best_of_val = 3
            if self.bestOf.value() != best_of_val:
                self.bestOf.setValue(best_of_val)
            self.ExportBestOf(best_of_val)

            round_num = live_state.get("round_number")
            match_title = f"Round {round_num}" if round_num else "Crew Battle"
            if self.matchCombo.currentText() != match_title:
                self.matchCombo.setCurrentText(match_title)
                self.MatchExport()

            # 5. Set active game (Nexus currently supports SSBU; future-proofed with snapshot game field)
            game_target = active_game.get("game") or snapshot.get("game") or tournament_season.get("game") or "ssbu"
            if TSHGameAssetManager.instance:
                TSHGameAssetManager.instance.SetGame(game_target)

            # Selections & Characters
            selections_by_player = {s.get("player_id"): s for s in roster_selections if s.get("player_id")}
            blind_by_player = {bp.get("player_id"): bp for bp in blind_picks if bp.get("player_id")}

            active_home_id = live_state.get("home_active_player_id")
            active_away_id = live_state.get("away_active_player_id")

            # Dual-layer protection: During starter selection (round 1), do not show either starter until both are locked in
            if live_state.get("round_number") == 1 and (not active_home_id or not active_away_id):
                active_home_id = None
                active_away_id = None
                roster_selections = [s for s in roster_selections if s.get("slot_order") != 1]
                selections_by_player = {s.get("player_id"): s for s in roster_selections if s.get("player_id")}

            def sort_key(p):
                sel = selections_by_player.get(p.get("id"), {})
                return sel.get("slot_order", 999)

            home_players.sort(key=sort_key)
            away_players.sort(key=sort_key)

            # 5. Populate Team 1 & Team 2 Player Widgets
            home_round_start = live_state.get("home_round_start_stocks")
            away_round_start = live_state.get("away_round_start_stocks")
            stk_default = stocks_per_player

            current_effective_active = {}
            for team_idx, (team_players, player_widgets, active_id, team_info, round_start_stk) in enumerate([
                (home_players, self.team1playerWidgets, active_home_id, home_team, home_round_start),
                (away_players, self.team2playerWidgets, active_away_id, away_team, away_round_start)
            ]):
                sponsor = team_info.get("short_name") or ""

                # Determine active player for this team:
                # 1. If active_id is explicitly set by live_state, use that player
                # 2. If active_id is None but players from this team were already sent in,
                #    keep the most recently sent-in player (highest slot_order) marked active
                #    (with 0 stocks & eliminated status) until the next player is sent in.
                effective_active_id = active_id
                if not effective_active_id:
                    team_selections = [
                        (p, selections_by_player[p["id"]])
                        for p in team_players
                        if p.get("id") in selections_by_player
                    ]
                    if team_selections:
                        team_selections.sort(key=lambda item: item[1].get("slot_order", 0))
                        effective_active_id = team_selections[-1][0].get("id")

                if effective_active_id is not None:
                    effective_active_id = str(effective_active_id)
                current_effective_active[team_idx] = effective_active_id

                for p_idx, player in enumerate(team_players):
                    if p_idx < len(player_widgets):
                        pw = player_widgets[p_idx]
                        p_id = str(player.get("id")) if player.get("id") is not None else None
                        tag = player.get("tag", "")

                        sel_entry = selections_by_player.get(player.get("id")) or selections_by_player.get(p_id) or {}
                        bp_entry = blind_by_player.get(player.get("id")) or blind_by_player.get(p_id) or {}
                        is_starter_hidden = (live_state.get("round_number") == 1 and (not active_home_id or not active_away_id))
                        char_name = sel_entry.get("selected_character") or sel_entry.get("character")
                        if not char_name and not is_starter_hidden:
                            char_name = bp_entry.get("selected_character") or bp_entry.get("character")

                        base_char, moveset = normalize_character_name(char_name)
                        is_active = (p_id == effective_active_id) if (effective_active_id and p_id) else False

                        player_data = {
                            "gamerTag": tag,
                            "prefix": sponsor,
                        }

                        # Preserve live active fighter's costume skin / character if already set from live match
                        cur_char_name = None
                        cur_color_idx = 0
                        if is_active and pw.character_elements:
                            char_elem = pw.character_elements[0][1]
                            color_elem = pw.character_elements[0][2]
                            cdata = char_elem.currentData()
                            if cdata and cdata.get("en_name"):
                                cur_char_name = cdata.get("en_name")
                                cur_color_idx = color_elem.currentIndex()

                        if is_active and cur_char_name:
                            # Keep the live fighter and costume skin
                            player_data["mains"] = {"ssbu": [[cur_char_name, cur_color_idx]]}
                        elif base_char:
                            player_data["mains"] = [base_char]

                        if moveset:
                            player_data["moveset"] = moveset

                        pw.SetData(player_data, dontLoadFromDB=True, clear=False)
                        pw.SetActiveStatus(is_active)

                        # Set player stocks and eliminated status
                        sel = selections_by_player.get(player.get("id")) or selections_by_player.get(p_id)
                        last_active = getattr(self, "_last_effective_active", {}).get(team_idx)
                        if last_active is not None:
                            last_active = str(last_active)
                        is_new_active = (last_active != effective_active_id)

                        if sel is not None:
                            # Player has entered the match / been sent in
                            p_stocks = sel.get("stocks_remaining")
                            # If actively playing and not eliminated, respect round_start_stk if present
                            if is_active and p_stocks is not None and int(p_stocks) > 0 and round_start_stk is not None:
                                cur_stk = int(round_start_stk)
                            elif p_stocks is not None:
                                cur_stk = int(p_stocks)
                            else:
                                cur_stk = stk_default

                            current_val = pw.dynamicSpinner.value()
                            # Guard: Do not reset stocks upward during an active ongoing round!
                            if is_active and not is_new_round and not is_new_active and 0 <= current_val < cur_stk:
                                # Keep the in-game decremented stocks
                                pass
                            else:
                                pw.dynamicSpinner.setValue(cur_stk)
                                pw.SetEliminatedStatus(cur_stk <= 0)
                                pw._previous_stock = cur_stk
                        else:
                            # Bench player: has not been sent in yet
                            pw.dynamicSpinner.setValue(stk_default)
                            pw.SetEliminatedStatus(False)
                            pw._previous_stock = stk_default

            # Record active round and player tracking
            self._last_round_number = round_num
            self._last_effective_active = current_effective_active

            # Save double blind picks to StateManager for dedicated stream overlays / scenes
            StateManager.Set("team_battle.blind_picks", blind_picks)
            home_team_id = home_team.get("id")
            away_team_id = away_team.get("id")
            team1_blind_picks = [
                bp for bp in blind_picks
                if bp.get("team_id") == home_team_id or bp.get("side") == "home" or bp.get("team_side") == "home"
            ]
            team2_blind_picks = [
                bp for bp in blind_picks
                if bp.get("team_id") == away_team_id or bp.get("side") == "away" or bp.get("team_side") == "away"
            ]
            StateManager.Set("team_battle.team.1.blind_picks", team1_blind_picks)
            StateManager.Set("team_battle.team.2.blind_picks", team2_blind_picks)

            # Record last applied state
            self._last_game_id = active_game.get("id")
            self._last_game_order = active_game.get("game_order")
            self._last_home_score = fixture.get("home_score")
            self._last_away_score = fixture.get("away_score")

            is_match_complete = (
                fixture.get("status") == "completed" or
                live_state.get("phase") == "complete"
            )
            if is_match_complete:
                home_score = int(fixture.get("home_score") or 0)
                away_score = int(fixture.get("away_score") or 0)
                if home_score > away_score:
                    self.team2stocks.setValue(0)
                    for pw in self.team2playerWidgets:
                        if pw.IsActive():
                            pw.dynamicSpinner.setValue(0)
                            pw.SetEliminatedStatus(True)
                elif away_score > home_score:
                    self.team1stocks.setValue(0)
                    for pw in self.team1playerWidgets:
                        if pw.IsActive():
                            pw.dynamicSpinner.setValue(0)
                            pw.SetEliminatedStatus(True)
                self.SetNexusStatus("connected", f"Match complete ({home_score} - {away_score})")

            self.TotalScoreExport()
        except Exception as e:
            logger.error(f"[TSHTeamBattleWidget] Error applying Nexus data: {e}")
        finally:
            self._syncing_stocks = 0
            StateManager.ReleaseSaving()