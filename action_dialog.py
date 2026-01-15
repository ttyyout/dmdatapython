"""
동작 추가/편집 다이얼로
상위/하위 플래그 동작을 명확히 분리
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QGroupBox, QFormLayout, QDialogButtonBox, QLineEdit, QSpinBox, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
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
        
        # 동작 타입 선택 (트리 구조)
        type_group = QGroupBox("동작 타입")
        type_layout = QVBoxLayout()
        
        # 트리 위젯 생성
        self.action_type_tree = QTreeWidget()
        self.action_type_tree.setHeaderLabel("동작 선택")
        self.action_type_tree.setMaximumHeight(200)
        self.action_type_tree.setRootIsDecorated(True)
        self.action_type_tree.setAlternatingRowColors(False)
        self.action_type_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #4a4a4a;
                font-size: 11pt;
            }
            QTreeWidget::item {
                padding: 6px;
                height: 24px;
            }
            QTreeWidget::item:selected {
                background-color: #4a4a4a;
                color: white;
            }
            QTreeWidget::item:hover {
                background-color: #3a3a3a;
            }
            QTreeWidget::branch {
                background-color: #2a2a2a;
            }
        """)
        self.action_type_tree.itemDoubleClicked.connect(self._on_tree_action_selected)
        self.action_type_tree.itemSelectionChanged.connect(self._on_tree_action_selection_changed)
        
        # 트리 구조로 동작 목록 구성
        self._build_action_tree(is_upper)
        
        type_layout.addWidget(self.action_type_tree)
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
        current_item = self.action_type_tree.currentItem()
        if current_item:
            action_type = current_item.data(0, Qt.UserRole)
            if action_type:
                self._on_type_changed(action_type)
        else:
            # 기본으로 "아무 것도 하지 않기" 선택
            def find_none_action():
                for i in range(self.action_type_tree.topLevelItemCount()):
                    root_item = self.action_type_tree.topLevelItem(i)
                    for j in range(root_item.childCount()):
                        child = root_item.child(j)
                        if child.data(0, Qt.UserRole) == "아무 것도 하지 않기":
                            self.action_type_tree.setCurrentItem(child)
                            self._on_type_changed("아무 것도 하지 않기")
                            return
            find_none_action()
    
    def _build_action_tree(self, is_upper: bool):
        """동작 트리 구조 구성 - 동작 타입만 표시 (실제 대상은 파라미터에서 선택)"""
        self.action_type_tree.clear()
        
        # 동작 그룹 정의 (동작 타입만)
        if is_upper:
            # 상위 플래그 동작
            action_groups = {
                "None": ["아무 것도 하지 않기"],
                "Scene": ["장면 전환"],
                "Recording": ["녹화 시작", "녹화 중지"],
                "Buffer": ["버퍼 저장"]
            }
        else:
            # 하위 플래그 동작
            action_groups = {
                "None": ["아무 것도 하지 않기"],
                "Source": ["소스 표시", "소스 숨김"],
                "Filter": ["필터 활성화", "필터 비활성화"]
            }
        
        # 트리 아이템 생성 (동작 타입만)
        for group_name, action_types in action_groups.items():
            # 그룹 노드
            group_item = QTreeWidgetItem()
            group_item.setText(0, group_name)
            group_item.setData(0, Qt.UserRole, None)  # 그룹은 action_type이 None
            group_item.setData(0, Qt.UserRole + 1, True)  # is_group = True
            self.action_type_tree.addTopLevelItem(group_item)
            
            # 하위 동작 노드 (leaf) - 동작 타입만
            for action_type in action_types:
                action_item = QTreeWidgetItem(group_item)
                action_item.setText(0, action_type)
                action_item.setData(0, Qt.UserRole, action_type)  # action_type 저장
                action_item.setData(0, Qt.UserRole + 1, False)  # is_group = False
                # 디버깅: 추가된 동작 확인
                print(f"✅ 동작 추가: 그룹={group_name}, 동작={action_type}")
        
        # 모든 그룹 펼치기
        self.action_type_tree.expandAll()
        
        # 디버깅: 트리 구조 확인
        print(f"📊 동작 트리 구성 완료: is_upper={is_upper}, 그룹 수={self.action_type_tree.topLevelItemCount()}")
        for i in range(self.action_type_tree.topLevelItemCount()):
            group_item = self.action_type_tree.topLevelItem(i)
            group_name = group_item.text(0)
            child_count = group_item.childCount()
            print(f"  - 그룹 '{group_name}': 자식 {child_count}개")
            for j in range(child_count):
                child = group_item.child(j)
                print(f"    - {child.text(0)}")
    
    def _on_tree_action_selection_changed(self):
        """트리에서 동작 선택 변경 시"""
        current_item = self.action_type_tree.currentItem()
        if not current_item:
            return
        
        # 그룹 노드는 선택 불가 (leaf만 선택 가능)
        is_group = current_item.data(0, Qt.UserRole + 1)
        if is_group:
            self.action_type_tree.clearSelection()
            return
        
        action_type = current_item.data(0, Qt.UserRole)
        if action_type:
            self._on_type_changed(action_type)
    
    def _on_tree_action_selected(self, item, column):
        """트리에서 동작 더블클릭 시"""
        is_group = item.data(0, Qt.UserRole + 1)
        if is_group:
            # 그룹 노드는 선택 불가
            return
        
        action_type = item.data(0, Qt.UserRole)
        if action_type:
            self._on_type_changed(action_type)
    
    def _on_type_changed(self, action_type: str = None):
        """동작 타입 변경 시 파라미터 UI 업데이트 - 실제 대상은 파라미터에서 선택"""
        # action_type이 제공되지 않으면 트리에서 가져오기
        if action_type is None:
            current_item = self.action_type_tree.currentItem()
            if current_item:
                is_group = current_item.data(0, Qt.UserRole + 1)
                if not is_group:
                    action_type = current_item.data(0, Qt.UserRole)
                else:
                    action_type = None
        
        if not action_type:
            # 기존 파라미터 위젯 제거
            while self.params_layout.count():
                child = self.params_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            self.param_widgets.clear()
            return
        
        # 기존 파라미터 위젯 제거
        while self.params_layout.count():
            child = self.params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.param_widgets.clear()
        
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
            # 장면 선택
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
            scene_combo.currentTextChanged.connect(self._on_scene_changed_for_source)
            self.params_layout.addRow("장면:", scene_combo)
            self.param_widgets["scene_name"] = scene_combo
            
            # 소스 선택 (트리 구조)
            source_tree = QTreeWidget()
            source_tree.setHeaderLabel("소스 선택")
            source_tree.setMaximumHeight(250)
            source_tree.setRootIsDecorated(True)  # 트리 접기/펼치기 아이콘 표시
            source_tree.setAlternatingRowColors(False)  # 교대 행 색상 비활성화
            source_tree.setStyleSheet("""
                QTreeWidget {
                    background-color: #2a2a2a;
                    color: white;
                    border: 1px solid #4a4a4a;
                    font-size: 11pt;
                }
                QTreeWidget::item {
                    padding: 6px;
                    height: 24px;
                }
                QTreeWidget::item:selected {
                    background-color: #4a4a4a;
                    color: white;
                }
                QTreeWidget::item:hover {
                    background-color: #3a3a3a;
                }
                QTreeWidget::branch {
                    background-color: #2a2a2a;
                }
                QTreeWidget::branch:has-siblings:!adjoins-item {
                    border-image: none;
                    border: none;
                }
                QTreeWidget::branch:has-siblings:adjoins-item {
                    border-image: none;
                    border: none;
                }
                QTreeWidget::branch:!has-children:!has-siblings:adjoins-item {
                    border-image: none;
                    border: none;
                }
                QTreeWidget::branch:has-children:!closed:adjoins-item {
                    border-image: none;
                    border: none;
                }
                QTreeWidget::branch:closed:has-children:has-siblings {
                    border-image: none;
                    border: none;
                }
            """)
            source_tree.itemSelectionChanged.connect(self._on_source_tree_selection_changed)
            
            # 펼치기/접기 버튼이 있는 위젯으로 감싸기
            source_tree_widget = QWidget()
            source_tree_layout = QVBoxLayout()
            source_tree_layout.setContentsMargins(0, 0, 0, 0)
            source_tree_layout.setSpacing(4)
            
            # 펼치기/접기 버튼
            tree_buttons_layout = QHBoxLayout()
            tree_buttons_layout.setContentsMargins(0, 0, 0, 0)
            expand_btn = QPushButton("모두 펼치기")
            expand_btn.setMaximumWidth(100)
            expand_btn.clicked.connect(lambda: self._expand_all_tree_items(source_tree))
            collapse_btn = QPushButton("모두 접기")
            collapse_btn.setMaximumWidth(100)
            collapse_btn.clicked.connect(lambda: self._collapse_all_tree_items(source_tree))
            tree_buttons_layout.addWidget(expand_btn)
            tree_buttons_layout.addWidget(collapse_btn)
            tree_buttons_layout.addStretch()
            source_tree_layout.addLayout(tree_buttons_layout)
            source_tree_layout.addWidget(source_tree)
            source_tree_widget.setLayout(source_tree_layout)
            
            self.params_layout.addRow("소스:", source_tree_widget)
            self.param_widgets["source"] = source_tree
            
            # 상태 반전 옵션
            invert_check = QCheckBox("플래그 상태와 반대로 동작")
            self.params_layout.addRow("상태 반전:", invert_check)
            self.param_widgets["invert"] = invert_check
        
        elif action_type in ["필터 활성화", "필터 비활성화"]:
            # 소스 선택 (모든 장면의 소스 목록에서, 그룹 내부 포함)
            source_combo = QComboBox()
            source_combo.addItem("(선택 없음)", "")
            if self.obs_controller:
                try:
                    scenes = self.obs_controller.get_scene_list()
                    all_sources = set()
                    for scene in scenes:
                        scene_name = scene.get('name', '')
                        if scene_name:
                            try:
                                # 그룹 내부까지 포함하여 모든 소스 가져오기
                                items = self.obs_controller.get_scene_items(scene_name, include_groups=True)
                                for item in items:
                                    source_name = item.get('sourceName', '')
                                    if source_name:
                                        all_sources.add(source_name)
                            except:
                                pass
                    for source_name in sorted(all_sources):
                        source_combo.addItem(source_name, source_name)
                except:
                    pass
            source_combo.currentTextChanged.connect(self._on_source_changed_for_filter)
            self.params_layout.addRow("소스:", source_combo)
            self.param_widgets["source_name"] = source_combo
            
            # 필터 선택 (소스 선택 후 업데이트됨)
            filter_combo = QComboBox()
            filter_combo.addItem("(소스를 먼저 선택하세요)", "")
            filter_combo.setEnabled(False)
            self.params_layout.addRow("필터:", filter_combo)
            self.param_widgets["filter_name"] = filter_combo
    
    def _load_action(self):
        """기존 동작 로드"""
        if not self.action:
            return
        
        # 트리에서 동작 타입 찾아서 선택
        action_type = self.action.action_type
        def find_action_item(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                child_action_type = child.data(0, Qt.UserRole)
                if child_action_type == action_type:
                    self.action_type_tree.setCurrentItem(child)
                    self.action_type_tree.scrollToItem(child)
                    return True
            return False
        
        # 루트 아이템들에서 검색
        for i in range(self.action_type_tree.topLevelItemCount()):
            root_item = self.action_type_tree.topLevelItem(i)
            if find_action_item(root_item):
                break
        
        # 파라미터 설정
        params = self.action.params
        if "scene_name" in self.param_widgets:
            scene_combo = self.param_widgets["scene_name"]
            scene_name = params.get("scene_name", "")
            index = scene_combo.findText(scene_name) if scene_name else 0
            if index >= 0:
                scene_combo.setCurrentIndex(index)
                # 장면 선택 후 소스 목록 업데이트 (소스 표시/숨김인 경우)
                if "source" in self.param_widgets:
                    self._on_scene_changed_for_source(scene_name)
        
        if "source" in self.param_widgets:
            source_widget = self.param_widgets["source"]
            # QTreeWidget인 경우
            if isinstance(source_widget, QTreeWidget):
                if "item_id" in params or "source_name" in params:
                    source_name = params.get("source_name", "")
                    item_id = params.get("item_id", 0)
                    
                    # 트리에서 해당 소스 찾기 (그룹 노드 제외)
                    def find_item(parent_item):
                        for i in range(parent_item.childCount()):
                            child = parent_item.child(i)
                            
                            # 그룹 노드는 건너뛰기 (UserRole이 None이거나 childCount > 0)
                            if child.childCount() > 0:
                                # 그룹이면 재귀적으로 자식 검색
                                if find_item(child):
                                    return True
                                continue
                            
                            child_source = child.data(0, Qt.UserRole)
                            child_item_id = child.data(0, Qt.UserRole + 1)
                            
                            # 그룹은 UserRole이 None이므로 source_name이 None이면 건너뛰기
                            if child_source is None:
                                continue
                            
                            if (source_name and child_source == source_name) or (item_id and child_item_id == item_id):
                                source_widget.setCurrentItem(child)
                                source_widget.scrollToItem(child)
                                return True
                            
                            if find_item(child):
                                return True
                        return False
                    
                    # 루트 아이템들에서 검색
                    for i in range(source_widget.topLevelItemCount()):
                        root_item = source_widget.topLevelItem(i)
                        
                        # 그룹 노드는 건너뛰기
                        if root_item.childCount() > 0:
                            # 그룹이면 재귀적으로 자식 검색
                            if find_item(root_item):
                                break
                            continue
                        
                        root_source = root_item.data(0, Qt.UserRole)
                        root_item_id = root_item.data(0, Qt.UserRole + 1)
                        
                        # 그룹은 UserRole이 None이므로 source_name이 None이면 건너뛰기
                        if root_source is None:
                            continue
                        
                        if (source_name and root_source == source_name) or (item_id and root_item_id == item_id):
                            source_widget.setCurrentItem(root_item)
                            source_widget.scrollToItem(root_item)
                            break
                        elif find_item(root_item):
                            break
            # QComboBox인 경우 (레거시)
            elif isinstance(source_widget, QComboBox):
                if "item_id" in params:
                    scene_name = params.get("scene_name", "")
                    if scene_name and self.obs_controller:
                        try:
                            items = self.obs_controller.get_scene_items(scene_name, include_groups=True)
                            item_id = params.get("item_id", 0)
                            for item in items:
                                if item.get('itemId') == item_id:
                                    source_name = item.get('sourceName', '')
                                    index = source_widget.findData(source_name)
                                    if index >= 0:
                                        source_widget.setCurrentIndex(index)
                                    break
                        except:
                            pass
                elif "source_name" in params:
                    source_name = params.get("source_name", "")
                    index = source_widget.findData(source_name)
                    if index >= 0:
                        source_widget.setCurrentIndex(index)
        
        if "invert" in self.param_widgets:
            self.param_widgets["invert"].setChecked(params.get("invert", False))
        
        if "source_name" in self.param_widgets and isinstance(self.param_widgets["source_name"], QComboBox):
            source_combo = self.param_widgets["source_name"]
            source_name = params.get("source_name", "")
            index = source_combo.findData(source_name)
            if index >= 0:
                source_combo.setCurrentIndex(index)
                # 소스 선택 후 필터 목록 업데이트 (필터 활성화/비활성화인 경우)
                if "filter_name" in self.param_widgets:
                    self._on_source_changed_for_filter(source_name)
        
        if "filter_name" in self.param_widgets and isinstance(self.param_widgets["filter_name"], QComboBox):
            filter_combo = self.param_widgets["filter_name"]
            filter_name = params.get("filter_name", "")
            index = filter_combo.findData(filter_name)
            if index >= 0:
                filter_combo.setCurrentIndex(index)
    
    def get_action(self) -> FlagAction:
        """동작 반환"""
        # 트리에서 선택된 동작 타입 가져오기
        current_item = self.action_type_tree.currentItem()
        if not current_item:
            return FlagAction("아무 것도 하지 않기", {})
        
        is_group = current_item.data(0, Qt.UserRole + 1)
        if is_group:
            # 그룹 노드는 선택 불가
            return FlagAction("아무 것도 하지 않기", {})
        
        action_type = current_item.data(0, Qt.UserRole)
        if not action_type:
            return FlagAction("아무 것도 하지 않기", {})
        
        params = {}
        
        if action_type == "아무 것도 하지 않기":
            return FlagAction("아무 것도 하지 않기", {})
        
        # 파라미터 수집
        if "scene_name" in self.param_widgets:
            scene_widget = self.param_widgets["scene_name"]
            if isinstance(scene_widget, QComboBox):
                scene_name = scene_widget.currentText()
                if scene_name and scene_name != "(선택 없음)":
                    params["scene_name"] = scene_name
        
        if "source_name" in self.param_widgets:
            source_widget = self.param_widgets["source_name"]
            if isinstance(source_widget, QComboBox):
                source_data = source_widget.currentData()
                if source_data:
                    params["source_name"] = source_data
        
        if "source" in self.param_widgets:
            source_widget = self.param_widgets["source"]
            scene_name = ""
            if "scene_name" in self.param_widgets:
                scene_widget = self.param_widgets["scene_name"]
                if isinstance(scene_widget, QComboBox):
                    scene_name = scene_widget.currentText()
            
            # QTreeWidget인 경우
            if isinstance(source_widget, QTreeWidget):
                current_item = source_widget.currentItem()
                if current_item:
                    # childCount() > 0이면 그룹 (자식을 가짐) - 선택 불가
                    if current_item.childCount() > 0:
                        print("⚠️ 그룹 노드는 선택할 수 없습니다.")
                        return
                    
                    # is_group 플래그 확인
                    is_group = current_item.data(0, Qt.UserRole + 2)
                    if is_group:
                        # 그룹 노드는 선택 불가
                        print("⚠️ 그룹 노드는 선택할 수 없습니다.")
                        return
                    
                    # 리프 노드만 선택 가능 - UserRole에 source_name이 있어야 함
                    source_data = current_item.data(0, Qt.UserRole)
                    item_id = current_item.data(0, Qt.UserRole + 1)
                    
                    # 그룹은 UserRole이 None이므로 source_data가 None이면 그룹
                    if source_data is None:
                        print("⚠️ 그룹 노드는 선택할 수 없습니다.")
                        return
                    
                    if source_data and scene_name and scene_name != "(선택 없음)":
                        params["item_id"] = item_id
                        params["source_name"] = source_data
                        params["scene_name"] = scene_name
            # QComboBox인 경우 (레거시)
            elif isinstance(source_widget, QComboBox):
                source_data = source_widget.currentData()
                if source_data and scene_name and scene_name != "(선택 없음)" and self.obs_controller:
                    try:
                        # 그룹 내부까지 포함하여 소스 찾기
                        items = self.obs_controller.get_scene_items(scene_name, include_groups=True)
                        for item in items:
                            if item.get('sourceName') == source_data:
                                params["item_id"] = item.get('itemId', 0)
                                params["source_name"] = source_data
                                params["scene_name"] = scene_name
                                break
                    except:
                        if source_data:
                            params["source_name"] = source_data
                            if scene_name:
                                params["scene_name"] = scene_name
        
        if "invert" in self.param_widgets:
            params["invert"] = self.param_widgets["invert"].isChecked()
        
        if "source_name" in self.param_widgets:
            if isinstance(self.param_widgets["source_name"], QComboBox):
                source_combo = self.param_widgets["source_name"]
                source_data = source_combo.currentData()
                if source_data:
                    params["source_name"] = source_data
            else:
                source_name = self.param_widgets["source_name"].text().strip()
                if source_name:
                    params["source_name"] = source_name
        
        if "filter_name" in self.param_widgets:
            filter_widget = self.param_widgets["filter_name"]
            if isinstance(filter_widget, QComboBox):
                filter_combo = filter_widget
                filter_data = filter_combo.currentData()
                if filter_data:
                    params["filter_name"] = filter_data
            else:
                filter_name = filter_widget.text().strip()
                if filter_name:
                    params["filter_name"] = filter_name
        
        return FlagAction(action_type, params)
    
    def _on_scene_changed_for_source(self, scene_name: str):
        """장면 변경 시 소스 목록 업데이트 (소스 표시/숨김용) - 트리 구조 (그룹/리프 구분)"""
        if "source" not in self.param_widgets:
            return
        
        source_tree = self.param_widgets["source"]
        source_tree.clear()
        
        if not scene_name or scene_name == "(선택 없음)":
            source_tree.setEnabled(False)
            return
        
        if not self.obs_controller:
            source_tree.setEnabled(False)
            return
        
        try:
            items = self.obs_controller.get_scene_items(scene_name, include_groups=True)
            if not items:
                source_tree.setEnabled(False)
                return
            
            # 트리 구조로 소스 목록 구성
            # 그룹과 실제 소스를 명확히 구분
            source_to_item = {}  # {source_name: {'item': QTreeWidgetItem, 'parent_group': str, 'item_id': int, 'is_group': bool, 'depth': int}}
            root_items = []
            
            # 1단계: 모든 아이템 생성 (그룹과 리프 구분)
            # depth가 작은 것부터 처리 (부모를 먼저 생성)
            sorted_items = sorted(items, key=lambda x: x.get('depth', 0))
            
            for item in sorted_items:
                source_name = item.get('sourceName', '')
                item_id = item.get('itemId', 0)
                is_group = item.get('isGroup', False)
                parent_group = item.get('parentGroup')
                depth = item.get('depth', 0)
                
                if not source_name:
                    continue
                
                # 트리 아이템 생성
                tree_item = QTreeWidgetItem()
                tree_item.setText(0, source_name)
                
                # 그룹 노드와 리프 노드 구분
                if is_group:
                    # 그룹 노드: 펼치기/접기 가능, 선택 불가, UserRole = None
                    tree_item.setData(0, Qt.UserRole, None)  # 그룹은 UserRole에 None
                    tree_item.setData(0, Qt.UserRole + 1, None)  # item_id도 None
                    tree_item.setData(0, Qt.UserRole + 2, True)  # is_group = True
                    tree_item.setFlags(Qt.ItemIsEnabled)  # 선택 불가 - ItemIsSelectable 절대 사용 금지
                    # 그룹은 자식을 가진 후에 ShowIndicator 설정됨
                else:
                    # 리프 노드: 선택 가능, UserRole에 action 데이터 저장
                    tree_item.setData(0, Qt.UserRole, source_name)  # source_name 저장
                    tree_item.setData(0, Qt.UserRole + 1, item_id)  # item_id 저장
                    tree_item.setData(0, Qt.UserRole + 2, False)  # is_group = False
                    tree_item.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicator)
                    tree_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                
                # 부모-자식 관계 설정
                if parent_group and parent_group in source_to_item:
                    # 부모 그룹이 있으면 부모의 자식으로 추가
                    parent_item = source_to_item[parent_group]['item']
                    parent_item.addChild(tree_item)
                    # 부모 그룹이 자식을 가지므로 펼치기 표시 활성화 (자식을 추가한 후에 설정)
                    if parent_item.childCount() > 0:
                        parent_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                else:
                    # 부모가 없으면 루트 아이템
                    root_items.append(tree_item)
                
                # 딕셔너리에 저장 (나중에 다른 아이템이 이 아이템을 부모로 참조할 수 있음)
                source_to_item[source_name] = {
                    'item': tree_item,
                    'parent_group': parent_group,
                    'item_id': item_id,
                    'is_group': is_group,
                    'depth': depth
                }
            
            # 2단계: 루트 아이템들을 트리에 추가
            source_tree.addTopLevelItems(root_items)
            
            # 3단계: 그룹 노드에 ShowIndicator 설정 (자식을 가진 그룹만)
            def set_group_indicators(item):
                """재귀적으로 그룹 노드에 ShowIndicator 설정"""
                is_group = item.data(0, Qt.UserRole + 2)
                if is_group and item.childCount() > 0:
                    item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                for i in range(item.childCount()):
                    set_group_indicators(item.child(i))
            
            for i in range(source_tree.topLevelItemCount()):
                set_group_indicators(source_tree.topLevelItem(i))
            
            # 4단계: 모든 아이템 펼치기 (재귀적으로)
            def expand_items(item):
                if item.childCount() > 0:
                    item.setExpanded(True)
                    for i in range(item.childCount()):
                        expand_items(item.child(i))
            
            for i in range(source_tree.topLevelItemCount()):
                expand_items(source_tree.topLevelItem(i))
            
            # 5단계: 그룹 노드 선택 방지
            source_tree.itemSelectionChanged.connect(lambda: self._prevent_group_selection(source_tree))
            
            source_tree.setEnabled(True)
        except Exception as e:
            print(f"⚠️ 소스 목록 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            source_tree.setEnabled(False)
    
    def _prevent_group_selection(self, tree: QTreeWidget):
        """그룹 노드 선택 방지 - childCount() > 0이거나 is_group이면 선택 해제"""
        current_item = tree.currentItem()
        if current_item:
            # childCount() > 0이면 그룹 (자식을 가짐)
            if current_item.childCount() > 0:
                tree.clearSelection()
                return
            
            # is_group 플래그 확인
            is_group = current_item.data(0, Qt.UserRole + 2)
            if is_group:
                # 그룹 노드 선택 시 선택 해제
                tree.clearSelection()
    
    def _on_source_tree_selection_changed(self):
        """소스 트리 선택 변경 시"""
        # 선택된 아이템이 있으면 자동으로 처리됨 (get_action에서 읽음)
        pass
    
    def _expand_all_tree_items(self, tree: QTreeWidget):
        """트리의 모든 아이템 펼치기"""
        def expand_items(item):
            if item.childCount() > 0:
                item.setExpanded(True)
                for i in range(item.childCount()):
                    expand_items(item.child(i))
        
        for i in range(tree.topLevelItemCount()):
            expand_items(tree.topLevelItem(i))
    
    def _collapse_all_tree_items(self, tree: QTreeWidget):
        """트리의 모든 아이템 접기"""
        def collapse_items(item):
            if item.childCount() > 0:
                item.setExpanded(False)
                for i in range(item.childCount()):
                    collapse_items(item.child(i))
        
        for i in range(tree.topLevelItemCount()):
            collapse_items(tree.topLevelItem(i))
    
    def _on_source_changed_for_filter(self, source_name: str):
        """소스 변경 시 필터 목록 업데이트 (필터 활성화/비활성화용)"""
        if "filter_name" not in self.param_widgets:
            return
        
        filter_combo = self.param_widgets["filter_name"]
        filter_combo.clear()
        
        if not source_name or source_name == "(선택 없음)":
            filter_combo.addItem("(소스를 먼저 선택하세요)", "")
            filter_combo.setEnabled(False)
            return
        
        if not self.obs_controller:
            filter_combo.addItem("(OBS 컨트롤러 없음)", "")
            filter_combo.setEnabled(False)
            return
        
        try:
            filters = self.obs_controller.get_source_filter_list(source_name)
            if filters:
                filter_combo.addItem("(선택 없음)", "")
                for filter_data in filters:
                    filter_name = filter_data.get('name', '')
                    if filter_name:
                        filter_combo.addItem(filter_name, filter_name)
                filter_combo.setEnabled(True)
            else:
                filter_combo.addItem("(필터 없음)", "")
                filter_combo.setEnabled(False)
        except Exception as e:
            filter_combo.addItem(f"(로드 실패: {e})", "")
            filter_combo.setEnabled(False)
