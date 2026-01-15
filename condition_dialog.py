"""
조건 추가/편집 다이얼로그
모든 조건을 한국어로 표시
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QGroupBox, QDoubleSpinBox, QLineEdit, QCheckBox, QFormLayout, QDialogButtonBox, QListWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from flag_system import FlagSystem, FlagCondition

class ConditionDialog(QDialog):
    """조건 추가/편집 다이얼로그"""
    
    def __init__(self, flag_system: FlagSystem, condition: FlagCondition = None, parent=None):
        super().__init__(parent)
        self.flag_system = flag_system
        self.condition = condition
        
        self.setWindowTitle("조건 추가/편집" if condition else "조건 추가")
        self.resize(700, 600)
        
        # 다크 테마
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                color: white;
            }
            QLabel {
                color: white;
            }
            QComboBox, QLineEdit, QDoubleSpinBox, QListWidget {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #4a4a4a;
                padding: 5px;
            }
            QGroupBox {
                border: 1px solid #4a4a4a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # 조건 타입 선택
        type_group = QGroupBox("조건 타입")
        type_layout = QVBoxLayout()
        
        self.condition_type_combo = QComboBox()
        # 모든 조건을 한국어로
        self.condition_type_combo.addItems([
            "다른 플래그 켜짐",
            "다른 플래그 꺼짐",
            "EEW 신규 발표",
            "EEW 속보 발표",
            "EEW 더 정밀한 정보 소스",
            "EEW 최종보",
            "EEW 취소보",
            "EEW 경보 신규 발표",
            "EEW 경보 속보 발표",
            "EEW 경보 취소",
            "EEW 경보 레벨 도달",
            "EEW 예상 최대 진도 상승",
            "EEW 예상 최대 진도 하강",
            "진원진도정보 수신",
            "진도속보 수신",
            "진원정보 수신",
            "해일정보 발표",
            "해일정보 취소",
            "무감지진"
        ])
        self.condition_type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.condition_type_combo)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # 조건 파라미터
        self.params_group = QGroupBox("조건 파라미터")
        self.params_layout = QFormLayout()
        self.params_group.setLayout(self.params_layout)
        layout.addWidget(self.params_group)
        
        # 파라미터 위젯들
        self.param_widgets = {}
        
        # 지연 시간 (무감지진의 경우 무감지 시간을 의미)
        delay_group = QGroupBox("지연 시간 / 무감지 시간")
        delay_layout = QVBoxLayout()
        delay_desc = QLabel("")
        delay_desc.setWordWrap(True)
        delay_desc.setStyleSheet("color: #aaa; font-size: 9pt; padding: 5px;")
        delay_layout.addWidget(delay_desc)
        
        delay_input_layout = QHBoxLayout()
        delay_input_layout.addWidget(QLabel("시간:"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.0, 3600.0)
        self.delay_spin.setSuffix(" 초")
        self.delay_spin.setValue(0.0)
        delay_input_layout.addWidget(self.delay_spin)
        delay_input_layout.addStretch()
        delay_layout.addLayout(delay_input_layout)
        
        # 조건 타입에 따라 설명 변경
        self.delay_desc_label = delay_desc
        delay_group.setLayout(delay_layout)
        layout.addWidget(delay_group)
        
        layout.addStretch()
        
        # 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        # 기존 조건이 있으면 로드
        if condition:
            self._load_condition()
        
        # 초기 파라미터 UI 생성
        self._on_type_changed()
    
    def _on_type_changed(self):
        """조건 타입 변경 시 파라미터 UI 업데이트"""
        # 기존 파라미터 위젯 제거
        while self.params_layout.count():
            child = self.params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.param_widgets.clear()
        
        condition_type = self.condition_type_combo.currentText()
        
        if condition_type in ["다른 플래그 켜짐", "다른 플래그 꺼짐"]:
            # 플래그 선택
            flag_combo = QComboBox()
            flag_combo.addItem("(선택 없음)", "")
            for flag in self.flag_system.all_flags.values():
                flag_combo.addItem(flag.name, flag.flag_id)
            self.params_layout.addRow("대상 플래그:", flag_combo)
            self.param_widgets["flag_id"] = flag_combo
        
        elif condition_type.startswith("EEW "):
            # EEW 조건 파라미터
            # 발표 유형 선택 (다중 선택 가능)
            announcement_list = QListWidget()
            announcement_list.setMaximumHeight(150)
            announcement_list.setSelectionMode(QListWidget.MultiSelection)
            announcement_items = [
                "신규 발표",
                "속보 발표",
                "더 정밀한 정보 소스",
                "최종보",
                "취소보",
                "경보 신규 발표",
                "경보 속보 발표",
                "경보 취소"
            ]
            for item in announcement_items:
                announcement_list.addItem(item)
            self.params_layout.addRow("발표 유형 (다중 선택):", announcement_list)
            self.param_widgets["announcement_list"] = announcement_list
            
            # 진도 필터
            intensity_combo = QComboBox()
            intensity_combo.addItems([
                "필터 없음",
                "진도 1 이상",
                "진도 2 이상",
                "진도 3 이상",
                "진도 4 이상",
                "진도 5약 이상",
                "진도 5강 이상",
                "진도 6약 이상",
                "진도 6강 이상",
                "진도 7"
            ])
            self.params_layout.addRow("최대 예상 진도 필터:", intensity_combo)
            self.param_widgets["intensity_filter"] = intensity_combo
        
        elif condition_type == "무감지진":
            # 무감지진 조건은 파라미터 없음 (delay 시간만 사용)
            info_label = QLabel(
                "무감지진 조건: 마지막 지진 정보 수신 후 지정된 시간 동안\n"
                "새로운 정보가 수신되지 않으면 조건이 만족됩니다.\n"
                "지연 시간은 '무감지 시간'을 의미합니다."
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color: #aaa; padding: 10px;")
            self.params_layout.addRow("", info_label)
        
        # delay 설명 업데이트
        if condition_type == "무감지진":
            self.delay_desc_label.setText(
                "무감지 시간: 마지막 지진 정보 수신 후 이 시간 동안\n"
                "새로운 정보가 없으면 조건이 만족됩니다."
            )
        else:
            self.delay_desc_label.setText(
                "지연 시간: 조건이 만족된 후 이 시간이 지나면 실행됩니다."
            )
    
    def _load_condition(self):
        """기존 조건 로드"""
        if not self.condition:
            return
        
        # 조건 타입 설정
        index = self.condition_type_combo.findText(self.condition.condition_type)
        if index >= 0:
            self.condition_type_combo.setCurrentIndex(index)
        
        # 지연 시간 설정
        self.delay_spin.setValue(self.condition.delay)
        
        # 파라미터 설정
        params = self.condition.params
        if "flag_id" in self.param_widgets:
            flag_combo = self.param_widgets["flag_id"]
            flag_id = params.get("flag_id", "")
            index = flag_combo.findData(flag_id)
            if index >= 0:
                flag_combo.setCurrentIndex(index)
        
        if "announcement_list" in self.param_widgets:
            announcement_list = self.param_widgets["announcement_list"]
            announcement_types = params.get("announcement_types", [])
            for i in range(announcement_list.count()):
                item = announcement_list.item(i)
                if item.text() in announcement_types:
                    item.setSelected(True)
        
        if "intensity_filter" in self.param_widgets:
            intensity_combo = self.param_widgets["intensity_filter"]
            filter_value = params.get("intensity_filter", "필터 없음")
            index = intensity_combo.findText(filter_value)
            if index >= 0:
                intensity_combo.setCurrentIndex(index)
    
    def get_condition(self) -> FlagCondition:
        """조건 반환"""
        condition_type = self.condition_type_combo.currentText()
        params = {}
        
        # 파라미터 수집
        if "flag_id" in self.param_widgets:
            flag_combo = self.param_widgets["flag_id"]
            flag_id = flag_combo.currentData()
            if flag_id:
                params["flag_id"] = flag_id
        
        if "announcement_list" in self.param_widgets:
            announcement_list = self.param_widgets["announcement_list"]
            selected_types = [item.text() for item in announcement_list.selectedItems()]
            if selected_types:
                params["announcement_types"] = selected_types
        
        if "intensity_filter" in self.param_widgets:
            params["intensity_filter"] = self.param_widgets["intensity_filter"].currentText()
        
        delay = self.delay_spin.value()
        
        return FlagCondition(condition_type, params, delay)
