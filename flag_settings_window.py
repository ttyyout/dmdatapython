"""
플래그 시스템 설정 창
4개 탭: 상위 플래그 조건/동작, 하위 플래그 조건/동작
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel,
    QPushButton, QListWidget, QLineEdit, QComboBox, QGroupBox, QTextEdit,
    QCheckBox, QDoubleSpinBox, QDialogButtonBox, QFrame, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from flag_system import FlagSystem, Flag, FlagCondition, FlagAction
from PySide6.QtWidgets import QDialog as QDialogBase

class FlagSystemSettingsWindow(QDialog):
    """플래그 시스템 설정 창"""
    
    def __init__(self, flag_system: FlagSystem, obs_controller, parent=None):
        super().__init__(parent)
        self.flag_system = flag_system
        self.obs_controller = obs_controller
        self.current_flag = None
        
        self.setWindowTitle("플래그 시스템 설정")
        self.resize(1200, 800)
        
        # 다크 테마
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                color: white;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QListWidget {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #4a4a4a;
            }
            QComboBox, QLineEdit, QTextEdit {
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
        
        main_layout = QVBoxLayout()
        
        # 상단 설명 문구
        info_label = QLabel(
            "플래그 시스템은 방송 상태를 결정하는 상태 머신입니다.\n"
            "플래그는 '켜짐/꺼짐' 상태만 가지며, OBS 제어는 중앙 상태 관리자가 자동으로 수행합니다.\n"
            "상위 플래그는 방송 전체(장면/녹화/버퍼)를, 하위 플래그는 장면 내부 요소(소스/필터)를 제어합니다.\n\n"
            "우선순위 규칙:\n"
            "- 여러 상위 플래그가 동시에 켜져 같은 자원을 제어할 때, 우선순위가 낮은 숫자(1, 2, 3...)가 우선됩니다.\n"
            "- '자동(null)'일 경우, 가장 최근에 켜진 플래그가 선택됩니다.\n"
            "- 동일한 우선순위를 가진 플래그가 여러 개면, 마지막으로 켜진 플래그가 선택됩니다."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("background-color: #2a2a2a; padding: 10px; border-radius: 5px; color: #aaa;")
        main_layout.addWidget(info_label)
        
        # 탭 위젯
        self.tab_widget = QTabWidget()
        
        # 탭 1: 상위 플래그 조건 제어
        self.upper_conditions_tab = self._create_conditions_tab(is_upper=True)
        self.tab_widget.addTab(self.upper_conditions_tab, "상위 플래그 조건")
        
        # 탭 2: 하위 플래그 조건 제어
        self.lower_conditions_tab = self._create_conditions_tab(is_upper=False)
        self.tab_widget.addTab(self.lower_conditions_tab, "하위 플래그 조건")
        
        # 탭 3: 상위 플래그 동작 제어
        self.upper_actions_tab = self._create_actions_tab(is_upper=True)
        self.tab_widget.addTab(self.upper_actions_tab, "상위 플래그 동작")
        
        # 탭 4: 하위 플래그 동작 제어
        self.lower_actions_tab = self._create_actions_tab(is_upper=False)
        self.tab_widget.addTab(self.lower_actions_tab, "하위 플래그 동작")
        
        main_layout.addWidget(self.tab_widget)
        
        # 하단 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_and_close)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)
        
        # 초기 로드
        self._load_flags()
    
    def _create_conditions_tab(self, is_upper: bool) -> QWidget:
        """조건 제어 탭 생성"""
        widget = QWidget()
        layout = QHBoxLayout()
        
        # 왼쪽: 플래그 목록
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("플래그 목록"))
        
        flag_list = QListWidget()
        flag_list.currentItemChanged.connect(lambda: self._on_flag_selected(flag_list, is_upper))
        left_panel.addWidget(flag_list)
        
        flag_buttons = QHBoxLayout()
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(lambda: self._add_flag(is_upper))
        remove_btn = QPushButton("삭제")
        remove_btn.clicked.connect(lambda: self._remove_flag(flag_list, is_upper))
        flag_buttons.addWidget(add_btn)
        flag_buttons.addWidget(remove_btn)
        left_panel.addLayout(flag_buttons)
        
        layout.addLayout(left_panel, 1)
        
        # 오른쪽: 조건 편집
        right_panel = QVBoxLayout()
        
        # 플래그 이름
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("플래그 이름:"))
        flag_name_edit = QLineEdit()
        flag_name_edit.textChanged.connect(lambda text: self._on_flag_name_changed(text, is_upper))
        name_layout.addWidget(flag_name_edit)
        right_panel.addLayout(name_layout)
        
        # 상위 플래그 전용: 우선순위 설정
        if is_upper:
            priority_group = QGroupBox("우선순위 설정")
            priority_layout = QVBoxLayout()
            
            priority_combo_layout = QHBoxLayout()
            priority_combo_layout.addWidget(QLabel("우선순위:"))
            priority_combo = QComboBox()
            priority_combo.addItem("자동 (null)", None)
            for i in range(1, 9):  # 1~8까지
                priority_combo.addItem(f"우선순위 {i} (낮을수록 우선)", i)
            priority_combo.currentIndexChanged.connect(lambda idx: self._on_priority_changed(priority_combo.itemData(idx), is_upper))
            priority_combo_layout.addWidget(priority_combo)
            priority_combo_layout.addStretch()
            priority_layout.addLayout(priority_combo_layout)
            
            # 설명 문구 추가
            priority_desc = QLabel(
                "이 우선순위는 여러 상위 플래그가 동시에 켜져\n"
                "같은 방송 자원(장면, 녹화, 버퍼)을 제어하려 할 때만 사용됩니다.\n"
                "'자동(null)'일 경우, 가장 최근에 켜진 플래그가 선택됩니다.\n"
                "동일한 우선순위를 가진 플래그가 여러 개면, 마지막으로 켜진 플래그가 선택됩니다."
            )
            priority_desc.setWordWrap(True)
            priority_desc.setStyleSheet("color: #888; padding: 5px; font-size: 9pt;")
            priority_layout.addWidget(priority_desc)
            
            priority_group.setLayout(priority_layout)
            right_panel.addWidget(priority_group)
            
            if is_upper:
                self.upper_priority_combo = priority_combo
            else:
                self.lower_priority_combo = priority_combo
        
        # 연결된 상위 플래그 설정 (하위 플래그만)
        if not is_upper:
            target_upper_layout = QHBoxLayout()
            target_upper_layout.addWidget(QLabel("연결된 상위 플래그:"))
            target_upper_combo = QComboBox()
            target_upper_combo.addItem("(없음)", None)
            for flag in self.flag_system.upper_flags.values():
                target_upper_combo.addItem(flag.name, flag.flag_id)
            target_upper_combo.currentIndexChanged.connect(lambda idx: self._on_target_upper_changed(target_upper_combo.itemData(idx), is_upper))
            target_upper_layout.addWidget(target_upper_combo)
            right_panel.addLayout(target_upper_layout)
            self.lower_target_upper_combo = target_upper_combo
            
            # 설명 문구
            target_upper_desc = QLabel(
                "이 하위 플래그가 켜지면 연결된 상위 플래그도 자동으로 켜집니다.\n"
                "여러 하위 플래그가 같은 상위 플래그에 연결되면, 하나라도 켜져 있으면 상위 플래그는 켜집니다."
            )
            target_upper_desc.setWordWrap(True)
            target_upper_desc.setStyleSheet("color: #888; padding: 5px; font-size: 9pt;")
            right_panel.addWidget(target_upper_desc)
        
        # 조건 설정 (하위 플래그만, 상위 플래그는 조건 없음)
        if not is_upper:
            # 켜짐 조건
            on_conditions_group = QGroupBox("켜짐 조건 (OR: 하나라도 만족하면 켜짐)")
            on_conditions_layout = QVBoxLayout()
            on_conditions_list = QListWidget()
            on_conditions_list.setMaximumHeight(150)
            on_conditions_layout.addWidget(on_conditions_list)
            
            on_condition_buttons = QHBoxLayout()
            add_on_btn = QPushButton("조건 추가")
            add_on_btn.clicked.connect(lambda: self._add_condition(is_upper, True))
            remove_on_btn = QPushButton("조건 삭제")
            remove_on_btn.clicked.connect(lambda: self._remove_condition(on_conditions_list, is_upper, True))
            on_condition_buttons.addWidget(add_on_btn)
            on_condition_buttons.addWidget(remove_on_btn)
            on_conditions_layout.addLayout(on_condition_buttons)
            
            on_conditions_group.setLayout(on_conditions_layout)
            right_panel.addWidget(on_conditions_group)
            
            # 꺼짐 조건
            off_conditions_group = QGroupBox("꺼짐 조건 (OR: 하나라도 만족하면 꺼짐)")
            off_conditions_layout = QVBoxLayout()
            off_conditions_list = QListWidget()
            off_conditions_list.setMaximumHeight(150)
            off_conditions_layout.addWidget(off_conditions_list)
            
            off_condition_buttons = QHBoxLayout()
            add_off_btn = QPushButton("조건 추가")
            add_off_btn.clicked.connect(lambda: self._add_condition(is_upper, False))
            remove_off_btn = QPushButton("조건 삭제")
            remove_off_btn.clicked.connect(lambda: self._remove_condition(off_conditions_list, is_upper, False))
            off_condition_buttons.addWidget(add_off_btn)
            off_condition_buttons.addWidget(remove_off_btn)
            off_conditions_layout.addLayout(off_condition_buttons)
            
            off_conditions_group.setLayout(off_conditions_layout)
            right_panel.addWidget(off_conditions_group)
        else:
            # 상위 플래그는 조건 없음 - 안내 메시지
            info_label = QLabel(
                "상위 플래그는 조건을 가지지 않습니다.\n"
                "상위 플래그의 상태는 연결된 하위 플래그들의 상태를 OR 집계하여 자동으로 결정됩니다.\n"
                "하위 플래그 탭에서 하위 플래그를 생성하고 '연결된 상위 플래그'를 설정하세요."
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet("background-color: #2a2a2a; padding: 15px; border-radius: 5px; color: #aaa;")
            right_panel.addWidget(info_label)
            # 상위 플래그는 조건 목록 변수를 None으로 초기화
            on_conditions_list = None
            off_conditions_list = None
        
        layout.addLayout(right_panel, 2)
        
        widget.setLayout(layout)
        
        # 위젯 참조 저장
        if is_upper:
            self.upper_flag_list = flag_list
            self.upper_flag_name_edit = flag_name_edit
            self.upper_on_conditions_list = None
            self.upper_off_conditions_list = None
        else:
            self.lower_flag_list = flag_list
            self.lower_flag_name_edit = flag_name_edit
            self.lower_on_conditions_list = on_conditions_list
            self.lower_off_conditions_list = off_conditions_list
        
        return widget
    
    def _create_actions_tab(self, is_upper: bool) -> QWidget:
        """동작 제어 탭 생성"""
        widget = QWidget()
        layout = QHBoxLayout()
        
        # 왼쪽: 플래그 목록
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("플래그 목록"))
        
        flag_list = QListWidget()
        flag_list.currentItemChanged.connect(lambda: self._on_flag_selected_for_action(flag_list, is_upper))
        left_panel.addWidget(flag_list)
        
        layout.addLayout(left_panel, 1)
        
        # 오른쪽: 동작 편집
        right_panel = QVBoxLayout()
        
        # 켜짐 시 동작
        on_actions_group = QGroupBox("켜짐 시 동작")
        on_actions_layout = QVBoxLayout()
        on_actions_list = QListWidget()
        on_actions_list.setMaximumHeight(200)
        on_actions_layout.addWidget(on_actions_list)
        
        on_action_buttons = QHBoxLayout()
        add_on_btn = QPushButton("동작 추가")
        add_on_btn.clicked.connect(lambda: self._add_action(is_upper, True))
        remove_on_btn = QPushButton("동작 삭제")
        remove_on_btn.clicked.connect(lambda: self._remove_action(on_actions_list, is_upper, True))
        on_action_buttons.addWidget(add_on_btn)
        on_action_buttons.addWidget(remove_on_btn)
        on_actions_layout.addLayout(on_action_buttons)
        
        on_actions_group.setLayout(on_actions_layout)
        right_panel.addWidget(on_actions_group)
        
        # 꺼짐 시 동작
        off_actions_group = QGroupBox("꺼짐 시 동작")
        off_actions_layout = QVBoxLayout()
        off_actions_list = QListWidget()
        off_actions_list.setMaximumHeight(200)
        off_actions_layout.addWidget(off_actions_list)
        
        off_action_buttons = QHBoxLayout()
        add_off_btn = QPushButton("동작 추가")
        add_off_btn.clicked.connect(lambda: self._add_action(is_upper, False))
        remove_off_btn = QPushButton("동작 삭제")
        remove_off_btn.clicked.connect(lambda: self._remove_action(off_actions_list, is_upper, False))
        off_action_buttons.addWidget(add_off_btn)
        off_action_buttons.addWidget(remove_off_btn)
        off_actions_layout.addLayout(off_action_buttons)
        
        off_actions_group.setLayout(off_actions_layout)
        right_panel.addWidget(off_actions_group)
        
        layout.addLayout(right_panel, 2)
        
        widget.setLayout(layout)
        
        # 위젯 참조 저장
        if is_upper:
            self.upper_action_flag_list = flag_list
            self.upper_on_actions_list = on_actions_list
            self.upper_off_actions_list = off_actions_list
        else:
            self.lower_action_flag_list = flag_list
            self.lower_on_actions_list = on_actions_list
            self.lower_off_actions_list = off_actions_list
        
        return widget
    
    def _load_flags(self):
        """플래그 목록 로드"""
        # 상위 플래그
        self.upper_flag_list.clear()
        for flag in self.flag_system.upper_flags.values():
            self.upper_flag_list.addItem(flag.name)
        
        # 하위 플래그
        self.lower_flag_list.clear()
        for flag in self.flag_system.lower_flags.values():
            self.lower_flag_list.addItem(flag.name)
        
        # 동작 탭용 플래그 목록도 동일하게
        self.upper_action_flag_list.clear()
        for flag in self.flag_system.upper_flags.values():
            self.upper_action_flag_list.addItem(flag.name)
        
        self.lower_action_flag_list.clear()
        for flag in self.flag_system.lower_flags.values():
            self.lower_action_flag_list.addItem(flag.name)
    
    def _add_flag(self, is_upper: bool):
        """플래그 추가"""
        import uuid
        flag_id = str(uuid.uuid4())[:8]
        flag_name = f"새 플래그 {len(self.flag_system.upper_flags if is_upper else self.flag_system.lower_flags) + 1}"
        
        flag_type = "upper" if is_upper else "lower"
        flag = Flag(flag_id, flag_name, flag_type)
        self.flag_system.add_flag(flag)
        
        self._load_flags()
    
    def _remove_flag(self, flag_list: QListWidget, is_upper: bool):
        """플래그 삭제"""
        current_item = flag_list.currentItem()
        if not current_item:
            return
        
        flag_name = current_item.text()
        flags_dict = self.flag_system.upper_flags if is_upper else self.flag_system.lower_flags
        
        for flag_id, flag in flags_dict.items():
            if flag.name == flag_name:
                self.flag_system.remove_flag(flag_id)
                break
        
        self._load_flags()
    
    def _on_flag_selected(self, flag_list: QListWidget, is_upper: bool):
        """플래그 선택 시"""
        current_item = flag_list.currentItem()
        if not current_item:
            return
        
        flag_name = current_item.text()
        flags_dict = self.flag_system.upper_flags if is_upper else self.flag_system.lower_flags
        
        for flag in flags_dict.values():
            if flag.name == flag_name:
                self.current_flag = flag
                flag_name_edit = self.upper_flag_name_edit if is_upper else self.lower_flag_name_edit
                flag_name_edit.setText(flag.name)
                
                # 우선순위 설정 (상위 플래그만)
                if is_upper and hasattr(self, 'upper_priority_combo'):
                    priority_combo = self.upper_priority_combo
                    if flag.priority is None:
                        priority_combo.setCurrentIndex(0)  # "자동"
                    else:
                        idx = priority_combo.findData(flag.priority)
                        if idx >= 0:
                            priority_combo.setCurrentIndex(idx)
                
                # 연결된 상위 플래그 설정 (하위 플래그만)
                if not is_upper and hasattr(self, 'lower_target_upper_combo'):
                    target_upper_combo = self.lower_target_upper_combo
                    if flag.target_upper_flag_id:
                        idx = target_upper_combo.findData(flag.target_upper_flag_id)
                        if idx >= 0:
                            target_upper_combo.setCurrentIndex(idx)
                    else:
                        target_upper_combo.setCurrentIndex(0)  # "(없음)"
                
                # 조건 목록 업데이트 (하위 플래그만)
                if not is_upper:
                    on_list = self.lower_on_conditions_list
                    off_list = self.lower_off_conditions_list
                    
                    on_list.clear()
                    for condition in flag.on_conditions:
                        condition_text = self._format_condition_text(condition)
                        on_list.addItem(condition_text)
                    
                    off_list.clear()
                    for condition in flag.off_conditions:
                        condition_text = self._format_condition_text(condition)
                        off_list.addItem(condition_text)
                break
    
    def _on_flag_selected_for_action(self, flag_list: QListWidget, is_upper: bool):
        """동작 탭에서 플래그 선택 시"""
        current_item = flag_list.currentItem()
        if not current_item:
            return
        
        flag_name = current_item.text()
        flags_dict = self.flag_system.upper_flags if is_upper else self.flag_system.lower_flags
        
        for flag in flags_dict.values():
            if flag.name == flag_name:
                self.current_flag = flag
                
                # 동작 목록 업데이트
                on_list = self.upper_on_actions_list if is_upper else self.lower_on_actions_list
                off_list = self.upper_off_actions_list if is_upper else self.lower_off_actions_list
                
                on_list.clear()
                for action in flag.on_actions:
                    on_list.addItem(f"{action.action_type}: {action.params}")
                
                off_list.clear()
                for action in flag.off_actions:
                    off_list.addItem(f"{action.action_type}: {action.params}")
                break
    
    def _on_flag_name_changed(self, text: str, is_upper: bool):
        """플래그 이름 변경"""
        if self.current_flag:
            self.current_flag.name = text
            self._load_flags()
    
    def _on_priority_changed(self, priority, is_upper: bool):
        """우선순위 변경 (상위 플래그만)"""
        if self.current_flag and is_upper:
            self.current_flag.priority = priority
    
    def _on_target_upper_changed(self, target_upper_flag_id, is_upper: bool):
        """연결된 상위 플래그 변경 (하위 플래그만)"""
        if self.current_flag and not is_upper:
            self.current_flag.target_upper_flag_id = target_upper_flag_id
    
    def _add_condition(self, is_upper: bool, is_on: bool):
        """조건 추가 (하위 플래그만)"""
        if not self.current_flag or is_upper:
            # 상위 플래그는 조건을 가지지 않음
            return
        
        from condition_dialog import ConditionDialog
        dialog = ConditionDialog(self.flag_system, parent=self)
        if dialog.exec() == QDialogBase.Accepted:
            condition = dialog.get_condition()
            if condition:
                if is_on:
                    self.current_flag.on_conditions.append(condition)
                else:
                    self.current_flag.off_conditions.append(condition)
                
                self._on_flag_selected(
                    self.lower_flag_list,
                    is_upper
                )
    
    def _remove_condition(self, condition_list: QListWidget, is_upper: bool, is_on: bool):
        """조건 삭제 (하위 플래그만)"""
        if is_upper:
            # 상위 플래그는 조건을 가지지 않음
            return
        
        current_row = condition_list.currentRow()
        if current_row < 0 or not self.current_flag:
            return
        
        if is_on:
            if current_row < len(self.current_flag.on_conditions):
                del self.current_flag.on_conditions[current_row]
        else:
            if current_row < len(self.current_flag.off_conditions):
                del self.current_flag.off_conditions[current_row]
        
        self._on_flag_selected(
            self.lower_flag_list,
            is_upper
        )
    
    def _add_action(self, is_upper: bool, is_on: bool):
        """동작 추가"""
        if not self.current_flag:
            return
        
        from action_dialog import ActionDialog
        dialog = ActionDialog(self.obs_controller, is_upper=is_upper, parent=self)
        if dialog.exec() == QDialogBase.Accepted:
            action = dialog.get_action()
            if action:
                if is_on:
                    self.current_flag.on_actions.append(action)
                else:
                    self.current_flag.off_actions.append(action)
                
                self._on_flag_selected_for_action(
                    self.upper_action_flag_list if is_upper else self.lower_action_flag_list,
                    is_upper
                )
    
    def _remove_action(self, action_list: QListWidget, is_upper: bool, is_on: bool):
        """동작 삭제"""
        current_row = action_list.currentRow()
        if current_row < 0 or not self.current_flag:
            return
        
        if is_on:
            if current_row < len(self.current_flag.on_actions):
                del self.current_flag.on_actions[current_row]
        else:
            if current_row < len(self.current_flag.off_actions):
                del self.current_flag.off_actions[current_row]
        
        self._on_flag_selected_for_action(
            self.upper_action_flag_list if is_upper else self.lower_action_flag_list,
            is_upper
        )
    
    def _format_condition_text(self, condition: FlagCondition) -> str:
        """조건 텍스트 포맷팅 (파라미터 포함)"""
        condition_type = condition.condition_type
        params = condition.params or {}
        delay_text = f" (지연: {condition.delay}초)" if condition.delay > 0 else ""
        
        # 다른 플래그 켜짐/꺼짐 조건의 경우 플래그 이름 표시
        if condition_type in ["다른 플래그 켜짐", "다른 플래그 꺼짐"]:
            flag_id = params.get("flag_id")
            if flag_id:
                # 플래그 이름 찾기
                target_flag = self.flag_system.get_flag(flag_id)
                if target_flag:
                    flag_name = target_flag.name
                    return f"{condition_type}: {flag_name}{delay_text}"
                else:
                    return f"{condition_type}: (알 수 없는 플래그: {flag_id}){delay_text}"
            else:
                return f"{condition_type}: (플래그 미지정){delay_text}"
        
        # EEW 조건의 경우 파라미터 표시
        elif condition_type.startswith("EEW "):
            param_parts = []
            if "max_intensity" in params:
                param_parts.append(f"최대진도≥{params['max_intensity']}")
            if "source" in params:
                param_parts.append(f"출처={params['source']}")
            if param_parts:
                return f"{condition_type} ({', '.join(param_parts)}){delay_text}"
            return f"{condition_type}{delay_text}"
        
        # 기타 조건은 기본 형식
        return f"{condition_type}{delay_text}"
    
    def save_and_close(self):
        """저장하고 닫기"""
        self.flag_system.save_config()
        self.accept()

