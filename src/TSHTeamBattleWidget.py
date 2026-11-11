from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import QIcon, QAction
from qtpy import uic
from typing import List
import math
import re
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
from .TSHPlayerDB import TSHPlayerDB

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
        self.playerWidgets = []
        self.team1playerWidgets = []
        self.team2playerWidgets = []
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
        self._last_snapshot = None
        self._last_match_id = None
        self._initial_sync_done = False
        self._awaiting_asset_reapply = False
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

        if TSHGameAssetManager.instance:
            TSHGameAssetManager.instance.signals.onLoad.connect(self._OnGameAssetsLoaded)

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
            # In The Nexus crew battles (strictly 4v4), maximum active combatants is 4 (12 stocks max)
            active_combatants1 = min(4, len(self.team1playerWidgets))
            active_combatants2 = min(4, len(self.team2playerWidgets))
            self.team1stocks.setValue(active_combatants1 * stk_per_player)
            self.team2stocks.setValue(active_combatants2 * stk_per_player)
        finally:
            self._syncing_stocks = max(0, self._syncing_stocks - 1)
        self.TotalScoreExport()

    def ResetEverything(self):
        self._syncing_stocks += 1
        try:
            for pw in self.playerWidgets:
                pw.ResetDynamicSpinner()
                pw.Clear()
            stk_per_player = self.livesNumber.value() if self.livesNumber.value() > 0 else 3
            # In The Nexus crew battles (strictly 4v4), maximum active combatants is 4 (12 stocks max)
            active_combatants1 = min(4, len(self.team1playerWidgets))
            active_combatants2 = min(4, len(self.team2playerWidgets))
            self.team1stocks.setValue(active_combatants1 * stk_per_player)
            self.team2stocks.setValue(active_combatants2 * stk_per_player)
        finally:
            self._syncing_stocks = max(0, self._syncing_stocks - 1)
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
        self._last_snapshot = None
        self._last_match_id = None
        self._initial_sync_done = False
        self._awaiting_asset_reapply = False
        self._last_game_id = None
        self._last_game_order = None
        self._last_round_number = None
        self._last_effective_active = {}
        self._last_home_score = None
        self._last_away_score = None
        self._transition_seconds_left = 0
        for pw in getattr(self, "playerWidgets", []):
            setattr(pw, "_live_char", None)
            setattr(pw, "_live_skin", None)
            setattr(pw, "_last_loaded_player_id", None)
            setattr(pw, "_last_loaded_player_tag", None)
            setattr(pw, "_last_nexus_char", None)
            setattr(pw, "_last_nexus_moveset", None)
            pw.moveset = None

    def ApplyNexusData(self, snapshot: dict):
        # After initial load, periodic snapshots only sync players going in (active)
        # and choosing/changing characters without overwriting stocks or scoreboard info.
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

    def _OnGameAssetsLoaded(self):
        if getattr(self, "_awaiting_asset_reapply", False) and getattr(self, "_last_snapshot", None):
            logger.info("[TSHTeamBattleWidget] Game assets loaded; scheduling re-application of live match data")
            QTimer.singleShot(0, self._ReapplyNexusSnapshot)

    def _ReapplyNexusSnapshot(self):
        self._awaiting_asset_reapply = False
        if getattr(self, "_last_snapshot", None):
            self._DoApplyNexusData(self._last_snapshot, reapply_assets=True)

    def _DoApplyNexusData(self, snapshot: dict, reapply_assets: bool = False):
        self._last_snapshot = snapshot
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

            incoming_match_id = fixture.get("id") or snapshot.get("slug") or fixture.get("slug")
            is_new_match = (
                getattr(self, "_last_match_id", None) is not None
                and incoming_match_id is not None
                and self._last_match_id != incoming_match_id
            )
            if is_new_match:
                logger.info(f"[TSHTeamBattleWidget] Connecting to new match: {incoming_match_id} (was {self._last_match_id})")
                for pw in getattr(self, "playerWidgets", []):
                    pw._live_char = None
                    pw._live_skin = None
                    pw._last_loaded_player_id = None
                    pw._last_loaded_player_tag = None
                    pw._last_nexus_char = None
                    pw._last_nexus_moveset = None
                    pw.moveset = None
                    pw.Clear(no_mains=False)
                self._last_round_number = None
                self._last_effective_active = {}
                self._last_home_score = None
                self._last_away_score = None
                self._initial_sync_done = False

            is_initial_load = (not getattr(self, "_initial_sync_done", False)) or is_new_match
            self._last_match_id = incoming_match_id

            home_team_id = fixture.get("home_team_id")
            away_team_id = fixture.get("away_team_id")
            home_players = [p for p in players if p.get("team_id") == home_team_id]
            away_players = [p for p in players if p.get("team_id") == away_team_id]

            round_num = live_state.get("round_number")
            if round_num is not None:
                try:
                    round_num = int(round_num)
                except (ValueError, TypeError):
                    pass

            game_type = active_game.get("game", "ultimate")
            stocks_per_player = 4 if game_type == "melee" else 3
            tournament_season = snapshot.get("tournament_season") or {}

            is_match_complete = (
                fixture.get("status") == "completed" or
                live_state.get("phase") == "complete"
            )

            def _to_int_or_none(val):
                if val is None:
                    return None
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return None

            inc_h = _to_int_or_none(fixture.get("home_score"))
            inc_a = _to_int_or_none(fixture.get("away_score"))
            prv_h = _to_int_or_none(getattr(self, "_last_home_score", None))
            prv_a = _to_int_or_none(getattr(self, "_last_away_score", None))
            game_count_increased = (
                not is_initial_load
                and not reapply_assets
                and (
                    (prv_h is not None and inc_h is not None and inc_h > prv_h)
                    or (prv_a is not None and inc_a is not None and inc_a > prv_a)
                )
            )
            if game_count_increased:
                logger.info(
                    f"[TSHTeamBattleWidget] Game count increased ({prv_h}-{prv_a} -> {inc_h}-{inc_a}); "
                    "syncing series score, incrementing match, deactivating players, and resetting stocks."
                )
                if inc_h is not None:
                    self.team1score.setValue(inc_h)
                if inc_a is not None:
                    self.team2score.setValue(inc_a)

                cur_match = (self.matchCombo.currentText() or "").strip()
                m_match = re.search(r"^(.*?)(\d+)\s*$", cur_match)
                if m_match:
                    new_match = f"{m_match.group(1)}{int(m_match.group(2)) + 1}"
                else:
                    next_num = (inc_h or 0) + (inc_a or 0) + 1
                    if not cur_match or cur_match.lower() == "crew battle":
                        new_match = f"Match {next_num}"
                    else:
                        new_match = f"{cur_match} {next_num}"
                if self.matchCombo.isEditable():
                    self.matchCombo.setCurrentText(new_match)
                else:
                    idx = self.matchCombo.findText(new_match)
                    if idx >= 0:
                        self.matchCombo.setCurrentIndex(idx)
                    else:
                        self.matchCombo.addItem(new_match)
                        self.matchCombo.setCurrentIndex(self.matchCombo.count() - 1)
                self.MatchExport()

                for pw in getattr(self, "playerWidgets", []):
                    pw.SetActiveStatus(False)
                self.ResetAllStocks()

            # Only populate scoreboard, team info, stocks, rules, and game on the initial load
            if is_initial_load:
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

                # 3. Game Rules & Roster Size
                if self.livesNumber.value() != stocks_per_player:
                    self.livesNumber.setValue(stocks_per_player)

                # In The Nexus crew battles, team stocks are capped at 4 active combatants * stocks_per_player (12 max)
                max_crew_combatants = 4
                max_team_stocks = max_crew_combatants * stocks_per_player

                home_stocks = None
                if live_state:
                    home_stocks = live_state.get("home_stocks") if live_state.get("home_stocks") is not None else live_state.get("homeStocks")
                if home_stocks is not None:
                    try:
                        h_val = min(max_team_stocks, int(home_stocks))
                        self.team1stocks.setValue(h_val)
                    except (ValueError, TypeError):
                        pass
                else:
                    self.team1stocks.setValue(min(max_crew_combatants, max(1, len(home_players))) * stocks_per_player)

                away_stocks = None
                if live_state:
                    away_stocks = live_state.get("away_stocks") if live_state.get("away_stocks") is not None else live_state.get("awayStocks")
                if away_stocks is not None:
                    try:
                        a_val = min(max_team_stocks, int(away_stocks))
                        self.team2stocks.setValue(a_val)
                    except (ValueError, TypeError):
                        pass
                else:
                    self.team2stocks.setValue(min(max_crew_combatants, max(1, len(away_players))) * stocks_per_player)

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
                tournament_name = tournament_season.get("tournament_name") or "The Nexus"
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

                best_of_val = fixture.get("best_of") or active_game.get("best_of") or 3
                try:
                    best_of_val = int(best_of_val)
                except (ValueError, TypeError):
                    best_of_val = 3
                if self.bestOf.value() != best_of_val:
                    self.bestOf.setValue(best_of_val)
                self.ExportBestOf(best_of_val)

                match_title = f"Round {round_num}" if round_num else "Crew Battle"
                if self.matchCombo.currentText() != match_title:
                    self.matchCombo.setCurrentText(match_title)
                    self.MatchExport()

                # 5. Set active game (schedule asset re-apply if game wasn't already loaded)
                game_target = active_game.get("game") or snapshot.get("game") or tournament_season.get("game") or "ssbu"
                if TSHGameAssetManager.instance:
                    current_codename = str(TSHGameAssetManager.instance.selectedGame.get("codename", "")).strip().lower()
                    char_count = TSHGameAssetManager.instance.characterModel.rowCount() if TSHGameAssetManager.instance.characterModel else 0
                    if not current_codename or char_count == 0 or current_codename != str(game_target).strip().lower():
                        self._awaiting_asset_reapply = True
                    TSHGameAssetManager.instance.SetGame(game_target)

            # Selections & Characters
            selections_by_player = {}
            for s in roster_selections:
                pid = s.get("player_id")
                if pid is not None:
                    selections_by_player[pid] = s
                    selections_by_player[str(pid)] = s

            blind_by_player = {}
            for bp in blind_picks:
                pid = bp.get("player_id")
                if pid is not None:
                    blind_by_player[pid] = bp
                    blind_by_player[str(pid)] = bp

            active_home_id = live_state.get("home_active_player_id")
            active_away_id = live_state.get("away_active_player_id")

            # Dual-layer protection: During starter selection (round 1 blind pick / player select),
            # do not show either starter until both are locked in.
            # Once round 1 moves to stage striking or match play (or round > 1), starters have been confirmed
            # and must never be hidden or stripped.
            is_round_one = (live_state.get("round_number") or 1) == 1
            is_starter_selection_phase = live_state.get("phase") in ("blind_pick", "player_select")
            if is_round_one and is_starter_selection_phase and (not active_home_id or not active_away_id):
                active_home_id = None
                active_away_id = None
                roster_selections = [s for s in roster_selections if s.get("slot_order") != 1]
                selections_by_player = {}
                for s in roster_selections:
                    pid = s.get("player_id")
                    if pid is not None:
                        selections_by_player[pid] = s
                        selections_by_player[str(pid)] = s

            def sort_key(p):
                pid = p.get("id")
                sel = selections_by_player.get(pid) or selections_by_player.get(str(pid), {})
                slot = int(sel.get("slot_order") or 999) if sel else 999
                return (slot, str(p.get("tag", "")).lower(), str(pid or ""))

            if is_initial_load:
                home_players.sort(key=sort_key)
                away_players.sort(key=sort_key)

            def _inspect_widget_char(pw):
                cur_char_name = None
                cur_color_idx = 0
                cur_moveset = getattr(pw, "moveset", None)
                if pw.character_elements:
                    char_elem = pw.character_elements[0][1]
                    color_elem = pw.character_elements[0][2]
                    var_elem = pw.character_elements[0][3]
                    cdata = char_elem.currentData()
                    if cdata and isinstance(cdata, dict) and cdata.get("en_name"):
                        cur_char_name = cdata.get("en_name")
                    elif char_elem.currentText():
                        cur_char_name = char_elem.currentText()
                    cur_color_idx = color_elem.currentIndex()
                    if not cur_moveset and var_elem is not None and var_elem.currentText().strip():
                        cur_moveset = var_elem.currentText().strip()
                cur_char_name = cur_char_name.strip() if (cur_char_name and cur_char_name.strip()) else None
                live_char = getattr(pw, "_live_char", None)
                live_skin = getattr(pw, "_live_skin", None)
                if live_char:
                    cur_char_name = live_char
                if live_skin is not None:
                    cur_color_idx = live_skin
                return cur_char_name, max(0, cur_color_idx), cur_moveset

            def _lookup_db_info(tag, sponsor):
                db_meta = {}
                db_main_char = None
                db_skin_idx = 0
                db_moveset = None
                db_player = TSHPlayerDB.GetPlayerFromTag(tag, sponsor)
                if db_player:
                    for field in ("name", "country_code", "state_code", "twitter", "pronoun"):
                        if db_player.get(field):
                            db_meta[field] = db_player.get(field)
                    mains_dict = db_player.get("mains", {})
                    if isinstance(mains_dict, dict):
                        curr_game = TSHGameAssetManager.instance.selectedGame.get("codename", "ssbu") if (TSHGameAssetManager.instance and TSHGameAssetManager.instance.selectedGame) else "ssbu"
                        g_mains = mains_dict.get(curr_game) or mains_dict.get("ssbu") or mains_dict.get("ultimate") or []
                        if g_mains and len(g_mains) > 0 and len(g_mains[0]) > 0:
                            first_m = g_mains[0]
                            raw_c = first_m[0] if isinstance(first_m, (list, tuple)) else str(first_m)
                            db_main_char, extracted_ms = normalize_character_name(raw_c)
                            if len(first_m) > 1 and isinstance(first_m[1], int):
                                db_skin_idx = first_m[1]
                            if len(first_m) > 2 and first_m[2]:
                                db_moveset = str(first_m[2]).strip()
                            elif extracted_ms:
                                db_moveset = extracted_ms
                return db_meta, db_main_char, db_skin_idx, db_moveset

            def _find_existing_widget(p_id, tag, player_widgets, used_widgets):
                if p_id:
                    for pw in player_widgets:
                        if pw not in used_widgets and getattr(pw, "_last_loaded_player_id", None) == p_id:
                            return pw
                if tag:
                    for pw in player_widgets:
                        if pw not in used_widgets and getattr(pw, "_last_loaded_player_tag", None) == tag:
                            return pw
                return None

            # Populate / Sync Team 1 & Team 2 Player Widgets
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
                #    keep the most recently sent-in player (highest slot_order) marked active.
                effective_active_id = active_id
                if not effective_active_id:
                    team_selections = []
                    for p in team_players:
                        pid = p.get("id")
                        sel = selections_by_player.get(pid) or selections_by_player.get(str(pid))
                        if sel:
                            team_selections.append((p, sel))
                    if team_selections:
                        team_selections.sort(key=lambda item: int(item[1].get("slot_order") or 0))
                        effective_active_id = team_selections[-1][0].get("id")

                if game_count_increased:
                    effective_active_id = None

                if effective_active_id is not None:
                    effective_active_id = str(effective_active_id)
                current_effective_active[team_idx] = effective_active_id

                last_active = getattr(self, "_last_effective_active", {}).get(team_idx)
                if last_active is not None:
                    last_active = str(last_active)
                is_active_changed = is_initial_load or (last_active != effective_active_id)

                # Pair each player with its target widget
                assignments = []
                used_widgets = set()
                if is_initial_load:
                    for p_idx, player in enumerate(team_players):
                        if p_idx < len(player_widgets):
                            pw = player_widgets[p_idx]
                            assignments.append((player, pw, True))
                            used_widgets.add(pw)
                else:
                    unmatched_players = []
                    for player in team_players:
                        p_id = str(player.get("id")) if player.get("id") is not None else None
                        tag = player.get("tag", "")
                        pw = _find_existing_widget(p_id, tag, player_widgets, used_widgets)
                        if pw is not None:
                            assignments.append((player, pw, False))
                            used_widgets.add(pw)
                        else:
                            unmatched_players.append(player)
                    # Only assign newly joined subs into truly empty slots
                    empty_widgets = [
                        pw for pw in player_widgets
                        if pw not in used_widgets
                        and not getattr(pw, "_last_loaded_player_id", None)
                        and not getattr(pw, "_last_loaded_player_tag", None)
                    ]
                    for player, pw in zip(unmatched_players, empty_widgets):
                        assignments.append((player, pw, True))
                        used_widgets.add(pw)

                for player, pw, is_first_for_widget in assignments:
                    p_id = str(player.get("id")) if player.get("id") is not None else None
                    tag = player.get("tag", "")

                    is_active = (p_id == effective_active_id) if (effective_active_id and p_id) else False
                    sel_entry = selections_by_player.get(player.get("id")) or selections_by_player.get(p_id) or {}
                    bp_entry = blind_by_player.get(player.get("id")) or blind_by_player.get(p_id) or {}
                    is_starter_hidden = (is_round_one and is_starter_selection_phase and (not active_home_id or not active_away_id))

                    # Determine character from Nexus snapshot:
                    # 1. Roster selections (confirmed sent-in player pick) takes highest priority
                    char_name = sel_entry.get("selected_character") or sel_entry.get("character")
                    if char_name in ("", "Character not selected", "None", None):
                        char_name = None

                    # 2. If roster selection has no character, fallback to blind pick ONLY for round 1 starter
                    if not char_name and not is_starter_hidden:
                        if sel_entry.get("slot_order") == 1 or (is_round_one and is_active):
                            bp_char = bp_entry.get("selected_character") or bp_entry.get("character")
                            if bp_char and bp_char not in ("", "Character not selected", "None"):
                                char_name = bp_char

                    base_char, moveset = normalize_character_name(char_name)

                    if is_first_for_widget:
                        pw._live_char = None
                        pw._live_skin = None
                        pw._last_nexus_char = None
                        pw._last_nexus_moveset = None
                        pw.moveset = None
                        pw._last_loaded_player_id = p_id
                        pw._last_loaded_player_tag = tag

                        db_meta, db_main_char, db_skin_idx, db_moveset = _lookup_db_info(tag, sponsor)
                        player_data = {
                            "gamerTag": tag,
                            "prefix": sponsor,
                            **db_meta,
                        }
                        if base_char:
                            init_skin = db_skin_idx if (db_main_char and db_main_char.lower() == base_char.lower()) else 0
                            player_data["mains"] = {"ssbu": [[base_char, init_skin]]}
                        elif db_main_char:
                            player_data["mains"] = {"ssbu": [[db_main_char, db_skin_idx]]}
                        else:
                            player_data["mains"] = [""]

                        player_data["moveset"] = moveset or db_moveset or ""
                        pw.SetData(player_data, dontLoadFromDB=True, clear=True)
                        pw._last_nexus_char = base_char
                        pw._last_nexus_moveset = moveset
                        pw.SetActiveStatus(is_active)

                        # Set initial player stocks and eliminated status
                        sel = selections_by_player.get(player.get("id")) or selections_by_player.get(p_id)
                        if sel is not None:
                            p_stocks = sel.get("stocks_remaining")
                            if is_active and p_stocks is not None and int(p_stocks) > 0 and round_start_stk is not None:
                                cur_stk = int(round_start_stk)
                            elif p_stocks is not None:
                                cur_stk = int(p_stocks)
                            else:
                                cur_stk = stk_default
                            pw.dynamicSpinner.setValue(cur_stk)
                            pw.SetEliminatedStatus(cur_stk <= 0)
                            pw._previous_stock = cur_stk
                        else:
                            pw.dynamicSpinner.setValue(stk_default)
                            pw.SetEliminatedStatus(False)
                            pw._previous_stock = stk_default
                    else:
                        # Subsequent update (periodic sync or asset-load reapply)
                        cur_char_name, cur_color_idx, cur_moveset = _inspect_widget_char(pw)
                        prev_nexus_char = getattr(pw, "_last_nexus_char", None)
                        prev_nexus_moveset = getattr(pw, "_last_nexus_moveset", None)
                        nexus_char_changed = (base_char, moveset) != (prev_nexus_char, prev_nexus_moveset)

                        if not reapply_assets and is_active_changed:
                            pw.SetActiveStatus(is_active)

                        if reapply_assets:
                            _, db_main_char, db_skin_idx, db_moveset = _lookup_db_info(tag, sponsor)
                            if base_char:
                                target_skin = cur_color_idx if (cur_char_name and cur_char_name.lower() == base_char.lower()) else (
                                    db_skin_idx if (db_main_char and db_main_char.lower() == base_char.lower()) else 0
                                )
                                char_data = {"mains": {"ssbu": [[base_char, target_skin]]}}
                                char_data["moveset"] = moveset or cur_moveset or db_moveset or ""
                                pw.SetData(char_data, dontLoadFromDB=True, clear=False)
                            elif not cur_char_name and db_main_char:
                                char_data = {"mains": {"ssbu": [[db_main_char, db_skin_idx]]}, "moveset": db_moveset or ""}
                                pw.SetData(char_data, dontLoadFromDB=True, clear=False)
                            pw._last_nexus_char = base_char
                            pw._last_nexus_moveset = moveset
                        elif nexus_char_changed:
                            if base_char:
                                _, db_main_char, db_skin_idx, db_moveset = _lookup_db_info(tag, sponsor)
                                same_char = bool(cur_char_name and cur_char_name.lower() == base_char.lower())
                                if same_char:
                                    target_skin = cur_color_idx
                                elif db_main_char and db_main_char.lower() == base_char.lower():
                                    target_skin = db_skin_idx
                                else:
                                    target_skin = 0

                                pw._live_char = None
                                pw._live_skin = None
                                char_data = {"mains": {"ssbu": [[base_char, target_skin]]}}
                                if moveset:
                                    char_data["moveset"] = moveset
                                elif not same_char:
                                    pw.moveset = None
                                    if db_main_char and db_main_char.lower() == base_char.lower() and db_moveset:
                                        char_data["moveset"] = db_moveset
                                pw.SetData(char_data, dontLoadFromDB=True, clear=False)
                            pw._last_nexus_char = base_char
                            pw._last_nexus_moveset = moveset

                if not is_initial_load and not reapply_assets and is_active_changed:
                    for pw in player_widgets:
                        if pw not in used_widgets and pw.IsActive():
                            pw.SetActiveStatus(False)

            # Record active round and player tracking
            self._last_round_number = round_num
            self._last_effective_active = current_effective_active

            # Save double blind picks to StateManager for dedicated stream overlays / scenes
            is_starter_hidden = (is_round_one and (not active_home_id or not active_away_id))
            exported_blind_picks = [] if is_starter_hidden else blind_picks
            StateManager.Set("team_battle.blind_picks", exported_blind_picks)
            team1_blind_picks = [
                bp for bp in exported_blind_picks
                if bp.get("team_id") == home_team.get("id") or bp.get("side") == "home" or bp.get("team_side") == "home"
            ]
            team2_blind_picks = [
                bp for bp in exported_blind_picks
                if bp.get("team_id") == away_team.get("id") or bp.get("side") == "away" or bp.get("team_side") == "away"
            ]
            StateManager.Set("team_battle.team.1.blind_picks", team1_blind_picks)
            StateManager.Set("team_battle.team.2.blind_picks", team2_blind_picks)

            # Record last applied metadata
            self._last_game_id = active_game.get("id")
            self._last_game_order = active_game.get("game_order")
            self._last_home_score = fixture.get("home_score")
            self._last_away_score = fixture.get("away_score")

            if is_match_complete:
                home_score = int(fixture.get("home_score") or 0)
                away_score = int(fixture.get("away_score") or 0)
                if is_initial_load:
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

            if is_initial_load:
                self.TotalScoreExport()
            self._initial_sync_done = True
        except Exception as e:
            logger.error(f"[TSHTeamBattleWidget] Error applying Nexus data: {e}")
        finally:
            self._syncing_stocks = 0
            StateManager.ReleaseSaving()