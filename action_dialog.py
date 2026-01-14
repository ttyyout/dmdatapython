"""
동작 추가/편집 다이얼로
상위/하위 플래그 동작을 명확히 분리
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QGroupBox, QFormLayout, QDialogButtonBox, QLineEdit, QSpinBox, QCheckBox
)
from PySide6.QtCore import Qt
from flag_system import FlagAction

class ActionDialog(QDialog):
    """동작 추가/편집 다이얼로그"""
    
    def __init__(self, obs_controller, is_upper: bool = True, action: FlagAction = None, parent=None):
        super().__init__(parent)
        self.obs_controller = obs_controller
        self.is_upper = is_upper
        self.action = action
        
        self.setWindowTitle("동작 추가/편집" if action else "동작 추가")
        self.resize(600, 500)
        
        # 다크 테마
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                color: white;
            }
            QLabel {
                color: white;
            }
            QComboBox, QLineEdit, QSpinBox {
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
        
        # 동작 타입 선택
        type_group = QGroupBox("동작 타입")
        type_layout = QVBoxLayout()
        
        self.action_type_combo = QComboBox()
        
        if is_upper:
            # 상위 플래그 동작
            self.action_type_combo.addItems([
                "아무 것도 하지 않기",
                "장면 전환",
                "녹화 시작",
                "녹화 중지",
                "버퍼 저장"
            ])
        else:
            # 하위 플래그 동작
            self.action_type_combo.addItems([
                "아무 것도 하지 않기",
                "소스 표시",
                "소스 숨김",
                "필터 활성화",
                "필터 비활성화"
            ])
        
        self.action_type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.action_type_combo)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # 동작 파라미터
        self.params_group = QGroupBox("동작 파라미터")
        self.params_layout = QFormLayout()
        self.params_group.setLayout(self.params_layout)
        layout.addWidget(self.params_group)
        
        # 파라미터 위젯들
        self.param_widgets = {}
        
        layout.addStretch()
        
        # 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        # 기존 동작이 있으면 로드
        if action:
            self._load_action()
        
        # 초기 파라미터 UI 생성
        self._on_type_changed()
    
    def _on_type_changed(self):
        """동작 타입 변경 시 파라미터 UI 업데이트"""
        # 기존 파라미터 위젯 제거
        while self.params_layout.count():
            child = self.params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.param_widgets.clear()
        
        action_type = self.action_type_combo.currentText()
        
        if action_type == "장면 전환":
            # 장면 선택
            scene_combo = QComboBox()
            scene_combo.addItems(["일반", "일본", "해일"])
            if self.obs_controller:
                try:
                    scenes = self.obs_controller.get_scene_list()
                    for scene in scenes:
                        scene_name = scene.get('name', '')
                        if scene_name and scene_name not in ["일반", "일본", "해일"]:
                            scene_combo.addItem(scene_name)
                except:
                    pass
            self.params_layout.addRow("장면:", scene_combo)
            self.param_widgets["scene_name"] = scene_combo
        
        elif action_type in ["소스 표시", "소스 숨김"]:
            # 소스 선택
            scene_combo = QComboBox()
            scene_combo.addItem("(선택 없음)", "")
            scene_combo.addItems(["일반", "일본", "해일"])
            if self.obs_controller:
                try:
                    scenes = self.obs_controller.get_scene_list()
                    for scene in scenes:
                        scene_name = scene.get('name', '')
                        if scene_name:
                            scene_combo.addItem(scene_name, scene_name)
                except:
                    pass
            self.params_layout.addRow("장면:", scene_combo)
            self.param_widgets["scene_name"] = scene_combo
            
            item_id_spin = QSpinBox()
            item_id_spin.setRange(0, 1000)
            item_id_spin.setValue(0)
            self.params_layout.addRow("소스 ID:", item_id_spin)
            self.param_widgets["item_id"] = item_id_spin
            
            # 상태 반전 옵션
            invert_check = QCheckBox("플래그 상태와 반대로 동작")
            self.params_layout.addRow("상태 반전:", invert_check)
            self.param_widgets["invert"] = invert_check
        
        elif action_type in ["필터 활성화", "필터 비활성화"]:
            # 필터 선택
            source_edit = QLineEdit()
            source_edit.setPlaceholderText("소스 이름 입력")
            self.params_layout.addRow("소스 이름:", source_edit)
            self.param_widgets["source_name"] = source_edit
            
            filter_edit = QLineEdit()
            filter_edit.setPlaceholderText("필터 이름 입력")
            self.params_layout.addRow("필터 이름:", filter_edit)
            self.param_widgets["filter_name"] = filter_edit
    
    def _load_action(self):
        """기존 동작 로드"""
        if not self.action:
            return
        
        # 동작 타입 설정
        index = self.action_type_combo.findText(self.action.action_type)
        if index >= 0:
            self.action_type_combo.setCurrentIndex(index)
        
        # 파라미터 설정
        params = self.action.params
        if "scene_name" in self.param_widgets:
            scene_combo = self.param_widgets["scene_name"]
            scene_name = params.get("scene_name", "")
            index = scene_combo.findText(scene_name) if scene_name else 0
            if index >= 0:
                scene_combo.setCurrentIndex(index)
        
        if "item_id" in self.param_widgets:
            self.param_widgets["item_id"].setValue(params.get("item_id", 0))
        
        if "invert" in self.param_widgets:
            self.param_widgets["invert"].setChecked(params.get("invert", False))
        
        if "source_name" in self.param_widgets:
            self.param_widgets["source_name"].setText(params.get("source_name", ""))
        
        if "filter_name" in self.param_widgets:
            self.param_widgets["filter_name"].setText(params.get("filter_name", ""))
    
    def get_action(self) -> FlagAction:
        """동작 반환"""
        action_type = self.action_type_combo.currentText()
        params = {}
        
        if action_type == "아무 것도 하지 않기":
            return FlagAction("아무 것도 하지 않기", {})
        
        # 파라미터 수집
        if "scene_name" in self.param_widgets:
            scene_combo = self.param_widgets["scene_name"]
            scene_name = scene_combo.currentText()
            if scene_name and scene_name != "(선택 없음)":
                params["scene_name"] = scene_name
        
        if "item_id" in self.param_widgets:
            params["item_id"] = self.param_widgets["item_id"].value()
        
        if "invert" in self.param_widgets:
            params["invert"] = self.param_widgets["invert"].isChecked()
        
        if "source_name" in self.param_widgets:
            source_name = self.param_widgets["source_name"].text().strip()
            if source_name:
                params["source_name"] = source_name
        
        if "filter_name" in self.param_widgets:
            filter_name = self.param_widgets["filter_name"].text().strip()
            if filter_name:
                params["filter_name"] = filter_name
        
        return FlagAction(action_type, params)
