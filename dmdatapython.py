import sys
import math
import os
import json
import base64
import gzip
import threading
import requests
import websocket
import time
import subprocess
from datetime import datetime
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QMenu, QTabWidget, QTextEdit, QPushButton, QScrollArea, QComboBox, QFrame, QListWidget, QLineEdit, QDialog, QDialogButtonBox, QDoubleSpinBox, QCheckBox, QRadioButton, QButtonGroup, QGroupBox, QSizePolicy
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QObject, Signal, QRect, Property, QThread
from PySide6.QtGui import QColor, QPalette, QCursor, QFont, QPainter, QPen, QBrush

# 플래그 시스템 import
try:
    from flag_system import FlagSystem, Flag, FlagCondition, FlagAction
except ImportError as e:
    print(f"⚠️ 플래그 시스템 모듈을 불러올 수 없습니다: {e}")
    FlagSystem = None
    Flag = None
    FlagCondition = None
    FlagAction = None

# ------------------ 번역 사전 로더 ------------------

class EpicenterTranslator:
    def __init__(self, json_path="epi.json"):
        self.dictionary = {}
        self.load_dictionary(json_path)
    
    def load_dictionary(self, json_path):
        """JSON 파일에서 진원지 번역 사전 로드"""
        try:
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    self.dictionary = json.load(f)
                print(f"✅ 진원지 번역 사전 로드 성공: {len(self.dictionary)}개 항목")
            else:
                print(f"⚠️ 진원지 번역 사전 파일을 찾을 수 없음: {json_path}")
        except Exception as e:
            print(f"❌ 진원지 번역 사전 로드 실패: {e}")
            self.dictionary = {}
    
    def translate(self, code, fallback_name=None):
        """진원지 코드를 한국어로 번역"""
        try:
            if code in self.dictionary:
                korean_name = self.dictionary[code].get("korean", fallback_name)
                return korean_name
            else:
                return fallback_name if fallback_name else f"코드 {code}"
        except Exception as e:
            print(f"❌ 번역 오류: {e}")
            return fallback_name if fallback_name else f"코드 {code}"

# 전역 번역기 인스턴스
epicenter_translator = EpicenterTranslator()

# ------------------ GUI ------------------

class IndicatorLight(QWidget):
    """아날로그 스타일 표시등"""
    def __init__(self, label_text="상태", parent=None):
        super().__init__(parent)
        self.status = "disconnected"
        self.label_text = label_text
        self.blink_state = False
        
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_blink)
        
        self.setFixedSize(200, 60)
        
    def set_status(self, status):
        """상태 변경"""
        self.status = status
        if status == "active":
            self.blink_timer.start(500)
        else:
            self.blink_timer.stop()
            self.blink_state = False
        self.update()
    
    def toggle_blink(self):
        """점멸 토글"""
        self.blink_state = not self.blink_state
        self.update()
    
    def paintEvent(self, event):
        """커스텀 페인팅"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(self.rect(), QColor("#2a2a2a"))
        
        painter.setPen(QColor("#cccccc"))
        painter.setFont(QFont("맑은 고딕", 10, QFont.Bold))
        painter.drawText(10, 20, self.label_text)
        
        light_x = 10
        light_y = 30
        light_radius = 12
        
        if self.status == "disconnected":
            light_color = QColor("#444444")
        elif self.status == "connecting":
            light_color = QColor("#ffaa00")
        elif self.status == "connected":
            light_color = QColor("#00ff00")
        elif self.status == "active":
            if self.blink_state:
                light_color = QColor("#ff0000")
            else:
                light_color = QColor("#660000")
        else:
            light_color = QColor("#444444")
        
        for i in range(3, 0, -1):
            alpha = 50 * (4 - i)
            glow_color = QColor(light_color)
            glow_color.setAlpha(alpha)
            painter.setBrush(glow_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(light_x - i, light_y - i, 
                              (light_radius + i) * 2, (light_radius + i) * 2)
        
        painter.setBrush(light_color)
        painter.setPen(QColor("#ffffff"))
        painter.drawEllipse(light_x, light_y, light_radius * 2, light_radius * 2)
        
        status_text = {
            "disconnected": "연결 끊김",
            "connecting": "연결 중...",
            "connected": "대기",
            "active": "데이터 수신 중"
        }.get(self.status, "알 수 없음")
        
        painter.setPen(QColor("#aaaaaa"))
        painter.setFont(QFont("맑은 고딕", 8))
        painter.drawText(light_x + light_radius * 2 + 10, light_y + light_radius + 4, status_text)

class ConnectionStatusPanel(QWidget):
    """연결 상태 패널"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        title = QLabel("시스템 연결 상태")
        title.setFont(QFont("맑은 고딕", 12, QFont.Bold))
        title.setStyleSheet("color: #ffffff; background-color: #1a1a1a; padding: 5px;")
        layout.addWidget(title)
        
        self.dmdata_light = IndicatorLight("DMDATA (일본)")
        self.exptech_light = IndicatorLight("ExpTech (대만)")
        
        layout.addWidget(self.dmdata_light)
        layout.addWidget(self.exptech_light)
        
        self.last_data_label = QLabel("마지막 데이터 수신: 없음")
        self.last_data_label.setFont(QFont("맑은 고딕", 9))
        self.last_data_label.setStyleSheet("color: #888888; padding: 5px;")
        layout.addWidget(self.last_data_label)
        
        layout.addStretch()
        self.setLayout(layout)
        self.setStyleSheet("background-color: #1a1a1a;")
        self.setMaximumHeight(250)
    
    def update_dmdata_status(self, status):
        """DMDATA 상태 업데이트"""
        self.dmdata_light.set_status(status)
    
    def update_exptech_status(self, status):
        """ExpTech 상태 업데이트"""
        self.exptech_light.set_status(status)
    
    def update_last_data_time(self, source):
        """마지막 데이터 수신 시간 업데이트"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.last_data_label.setText(f"마지막 데이터 수신: [{source}] {timestamp}")

class AlertBox(QWidget):
    """긴급지진속보 표시용 둥근 박스 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.text = "대기중"
        self.alert_type = "normal"  # "normal", "warning", "canceled"
        self._blink_opacity = 0.0
        self.is_blinking = False
        
        # 박스 색상
        self.normal_color = QColor("#F9D34C")  # 예보: 노란색
        self.warning_color = QColor("#EA3829")  # 경보: 빨간색
        self.base_bg_color = QColor("#2f4f4f")  # 기본 배경색 (진한 초록색)
        self.fg_color = QColor("#bba878")  # 텍스트 색상 (원래 색상)
        
    def set_text(self, text):
        self.text = text
        self.update()
    
    def set_alert_type(self, alert_type):
        self.alert_type = alert_type
        self.update()
    
    def set_blink_opacity(self, opacity):
        self._blink_opacity = opacity
        self.update()
    
    def get_blink_opacity(self):
        return self._blink_opacity
    
    blink_opacity = Property(float, get_blink_opacity, set_blink_opacity)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # 박스 색상 결정
        if self.alert_type == "warning":
            box_color = self.warning_color
        elif self.alert_type == "canceled":
            box_color = QColor("#0000ff")  # 취소: 파란색
        else:
            box_color = self.normal_color
        
        # 점멸 효과 적용 (사인곡선)
        if self.is_blinking:
            smooth_opacity = math.sin(self._blink_opacity * math.pi)
            # 기본 배경색과 박스 색상을 블렌딩
            blend_factor = smooth_opacity * 0.5
            r = int(self.base_bg_color.red() + (box_color.red() - self.base_bg_color.red()) * blend_factor)
            g = int(self.base_bg_color.green() + (box_color.green() - self.base_bg_color.green()) * blend_factor)
            b = int(self.base_bg_color.blue() + (box_color.blue() - self.base_bg_color.blue()) * blend_factor)
            final_color = QColor(r, g, b)
        else:
            final_color = box_color
        
        # 둥근 박스 그리기
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(final_color))
        painter.drawRoundedRect(rect, 10, 10)  # 둥근 모서리
        
        # 텍스트 그리기 (원래 색상)
        painter.setPen(self.fg_color)
        painter.setFont(QFont("맑은 고딕", 24, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, self.text)

class DetailBox(QWidget):
    """상세정보 표시용 박스 위젯 (점멸하지 않음)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.text = ""
        self.bg_color = QColor("#2f4f4f")
        self.fg_color = QColor("#bba878")
        
    def set_text(self, text):
        self.text = text
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # 배경 박스 그리기
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawRoundedRect(rect, 10, 10)
        
        # 텍스트 그리기
        if self.text:
            painter.setPen(self.fg_color)
            painter.setFont(QFont("맑은 고딕", 24))
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, self.text)

class BroadcastWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("방송용 창")
        self.setFixedSize(1920, 50)
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.bg_color = QColor("#2f4f4f")
        self.fg_color = QColor("#bba878")
        
        # 배경 설정
        self.update_palette(self.bg_color, self.fg_color)
        
        # 긴급지진속보 박스 (위에 표시, 점멸함)
        self.alert_box = AlertBox(self)
        self.alert_box.setGeometry(0, 0, 0, 50)
        self.alert_box.hide()
        
        # 상세정보 박스 (아래에 표시, 점멸하지 않음)
        self.detail_box = DetailBox(self)
        self.detail_box.setGeometry(0, 0, 0, 50)
        self.detail_box.hide()
        
        # 텍스트 스크롤을 위한 타이머
        self.scroll_timer = QTimer()
        self.scroll_timer.timeout.connect(self.scroll_detail_text)
        self.scroll_offset = 0
        self.full_detail_text = ""
        
        # 점멸 애니메이션
        self._blink_opacity = 0.0
        self.blink_animation = QPropertyAnimation(self.alert_box, b"blink_opacity")
        self.blink_animation.setDuration(1200)  # 한 번 점멸 시간
        self.blink_animation.setStartValue(0.0)
        self.blink_animation.setEndValue(1.0)
        self.blink_animation.setEasingCurve(QEasingCurve.Linear)
        self.blink_animation.setLoopCount(3)  # 3회 점멸
        self.blink_animation.finished.connect(self.on_blink_finished)
        
        # 박스 크기/위치 애니메이션
        self.box_animation = QPropertyAnimation(self.alert_box, b"geometry")
        self.box_animation.setDuration(1000)
        self.box_animation.setEasingCurve(QEasingCurve.InOutSine)  # 사인곡선 easing
        self.box_animation.finished.connect(self.on_box_animation_finished)
        
        self.is_testing = False
        self.pending_info_text = None
        self.current_event_id = None
        self.final_timer = None
        self.alert_type = "normal"
        self.current_source = None
        
        # 여러 지진 관리 구조
        self.active_earthquakes = {}  # {event_id: earthquake_data}
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_earthquakes)
        self.current_rotation_index = 0
        
        # 대기중 표시
        self.show_waiting()
        self.show()

    def update_palette(self, bg, fg):
        pal = self.palette()
        pal.setColor(QPalette.Window, bg)
        self.setAutoFillBackground(True)
        self.setPalette(pal)
    
    def show_waiting(self):
        """대기중 상태 표시"""
        self.alert_box.hide()
        self.detail_box.hide()
        self.alert_box.set_text("대기중")
        self.alert_box.set_alert_type("normal")
        self.alert_box.set_blink_opacity(0.0)
        self.alert_box.is_blinking = False

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        stop_action = menu.addAction("알림 끄기")
        menu.addSeparator()
        test_forecast_action = menu.addAction("예보 테스트")
        test_warning_action = menu.addAction("경보 테스트")
        action = menu.exec(QCursor.pos())
        if action == stop_action:
            self.stop_alert()
        elif action == test_forecast_action:
            self.test_eew_alert(is_warning=False)
        elif action == test_warning_action:
            self.test_eew_alert(is_warning=True)
    
    def test_eew_alert(self, is_warning=False):
        """테스트용 EEW 알림"""
        test_event_id = f"TEST_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        test_info_text = "테스트용 지진 정보입니다. 이것은 긴급지진속보 테스트 메시지입니다."
        
        self.start_eew_alert(
            test_info_text,
            event_id=test_event_id,
            serial_no=1,
            is_warning=is_warning,
            is_canceled=False,
            is_update=False,
            source="TEST",
            is_final=False,
            final_serial=None,
            author=None
        )

    def start_eew_alert(self, info_text, event_id=None, serial_no=None, is_warning=False, is_canceled=False, is_update=False, source="DMDATA", is_final=False, final_serial=None, author=None):
        """긴급지진속보 알림 시작 또는 업데이트"""
        print(f"🔥 start_eew_alert 호출됨: {info_text}, event_id={event_id}, is_update={is_update}, source={source}, author={author}")
        
        # event_id가 없으면 무시
        if not event_id:
            return

        # 같은 이벤트의 업데이트인 경우
        if is_update and event_id in self.active_earthquakes:
            print(f"🔄 정보 업데이트 중...")
            eq_data = self.active_earthquakes[event_id]
            eq_data['info_text'] = info_text
            eq_data['serial_no'] = serial_no
            eq_data['is_warning'] = is_warning
            eq_data['is_canceled'] = is_canceled
            eq_data['is_final'] = is_final
            eq_data['final_serial'] = final_serial
            
            # 현재 표시 중인 지진이 업데이트된 경우 즉시 반영
            if self.current_event_id == event_id:
                self._update_display_for_earthquake(eq_data)
            
            print(f"✅ 정보 업데이트 완료: {info_text}")
            return
        
        # 취소된 경우 active_earthquakes에서 제거
        if is_canceled and event_id in self.active_earthquakes:
            del self.active_earthquakes[event_id]
            # 현재 표시 중인 지진이 취소된 경우 다음 지진으로 전환
            if self.current_event_id == event_id:
                if len(self.active_earthquakes) > 0:
                    self.current_rotation_index = 0
                    self.rotate_earthquakes()
                else:
                    self.stop_alert()
            return
        
        # 새로운 지진 추가
        eq_key = f"{source}_{event_id}"
        earthquake_data = {
            'event_id': event_id,
            'info_text': info_text,
            'serial_no': serial_no,
            'is_warning': is_warning,
            'is_canceled': is_canceled,
            'source': source,
            'author': author,
            'is_final': is_final,
            'final_serial': final_serial
        }
        
        self.active_earthquakes[event_id] = earthquake_data
        
        # 1보(serial_no == 1)인 경우만 중앙 표시 + 점멸
        is_first_alert = (serial_no == 1 or serial_no is None)
        
        # 첫 번째 지진이면 즉시 표시 시작
        if not self.is_testing:
            if is_first_alert:
                print(f"🚨 새로운 알림 시작! (1보 - 중앙 표시)")
                self.is_testing = True
                self.current_event_id = event_id
                self.current_rotation_index = 0
                self._update_display_for_earthquake(earthquake_data)
                self.start_blinking()  # 3회 점멸 후 자동으로 이동
                
                # 여러 지진이 있으면 rotation 시작
                if len(self.active_earthquakes) > 1:
                    self.rotation_timer.start(5000)  # 5초마다 rotation
            else:
                # 1보가 아닌 경우 바로 왼쪽으로 이동 (점멸 없음)
                print(f"🚨 새로운 알림 시작! (2보 이상 - 바로 이동)")
                self.is_testing = True
                self.current_event_id = event_id
                self.current_rotation_index = 0
                self._update_display_for_earthquake(earthquake_data)
                # 바로 왼쪽으로 이동 (점멸 없이)
                QTimer.singleShot(100, self.start_move_animation)
                
                # 여러 지진이 있으면 rotation 시작
                if len(self.active_earthquakes) > 1:
                    self.rotation_timer.start(5000)
        else:
            # 이미 알림 중이면 rotation 시작
            if len(self.active_earthquakes) > 1 and not self.rotation_timer.isActive():
                self.rotation_timer.start(5000)
    
    def _update_display_for_earthquake(self, eq_data):
        """특정 지진 데이터로 화면 업데이트"""
        event_id = eq_data['event_id']
        info_text = eq_data['info_text']
        serial_no = eq_data['serial_no']
        is_warning = eq_data['is_warning']
        is_canceled = eq_data['is_canceled']
        source = eq_data['source']
        is_final = eq_data.get('is_final', False)
        final_serial = eq_data.get('final_serial')
        author = eq_data.get('author')
        
        self.current_event_id = event_id
        self.current_source = source
        self.pending_info_text = info_text
        
        # 여러 지진이 있을 때 (n/m) 표시
        total_count = len(self.active_earthquakes)
        current_index = list(self.active_earthquakes.keys()).index(event_id) + 1
        count_prefix = f"({current_index}/{total_count}) " if total_count > 1 else ""
        
        source_prefix = "[대만] " if source == "EXPTECH" else "[일본] "
        
        # 용어 선택 (대만: 강진즉시경보, 한국: 지진조기경보, 일본: 긴급지진속보)
        if source == "EXPTECH":
            if author == "kma":
                alert_name = "지진조기경보"
            else:
                alert_name = "강진즉시경보"
        else:
            alert_name = "긴급지진속보"
        
        # 최종보 표시
        final_suffix = ""
        if is_final and final_serial:
            final_suffix = f" #최종{final_serial}"
        elif serial_no:
            final_suffix = f" #{serial_no}"
        
        if is_canceled:
            self.alert_type = "canceled"
            status_text = source_prefix + count_prefix + f"{alert_name}가 취소되었습니다"
        elif is_warning:
            self.alert_type = "warning"
            status_text = source_prefix + count_prefix + f"{alert_name}(경보){final_suffix}"
        else:
            self.alert_type = "normal"
            status_text = source_prefix + count_prefix + f"{alert_name}(예보){final_suffix}"
        
        # alert_box 텍스트 업데이트
        self.alert_box.set_text(status_text)
        self.alert_box.set_alert_type(self.alert_type)
        
        # detail_box 텍스트 업데이트
        self.full_detail_text = info_text
        self.detail_box.set_text(info_text)
    
    def rotate_earthquakes(self):
        """여러 지진을 5초마다 번갈아가며 표시"""
        if not self.is_testing or len(self.active_earthquakes) == 0:
            self.rotation_timer.stop()
            return
        
        eq_list = list(self.active_earthquakes.values())
        if len(eq_list) == 0:
            self.stop_alert()
            return
        
        # 다음 지진으로 rotation
        self.current_rotation_index = (self.current_rotation_index + 1) % len(eq_list)
        current_eq = eq_list[self.current_rotation_index]
        
        self._update_display_for_earthquake(current_eq)
        
        # detail_box가 보이지 않으면 애니메이션 시작
        if not self.detail_box.isVisible() and not current_eq.get('is_canceled'):
            QTimer.singleShot(100, self.start_move_animation)

    def schedule_final_return(self):
        """최종보 후 3분 뒤 대기중으로 복귀"""
        print("📅 최종보 수신 - 3분 후 대기중으로 복귀 예정")
        # rotation 중지 (최종보는 계속 표시)
        if self.rotation_timer.isActive():
            self.rotation_timer.stop()
        
        if self.final_timer:
            self.final_timer.stop()
        self.final_timer = QTimer()
        self.final_timer.setSingleShot(True)
        self.final_timer.timeout.connect(self.stop_alert)
        self.final_timer.start(180000)

    def start_blinking(self):
        """3회 점멸 시작"""
        print(f"💡 점멸 시작: alert_type={self.alert_type}")
        # alert_box를 전체 창 크기로 설정
        self.alert_box.setGeometry(0, 0, self.width(), 50)
        self.alert_box.show()
        self.alert_box.raise_()  # 맨 앞으로
        
        # 점멸 애니메이션 초기화
        self.alert_box.is_blinking = True
        self.blink_animation.setStartValue(0.0)
        self.blink_animation.setEndValue(1.0)
        self.blink_animation.setEasingCurve(QEasingCurve.Linear)
        self.blink_animation.setLoopCount(3)  # 3회 점멸
        self.blink_animation.start()
    
    def on_blink_finished(self):
        """3회 점멸 완료 후 무한 반복으로 전환하고 이동 애니메이션 시작"""
        if self.is_testing:
            # 3회 점멸 후 무한 반복으로 전환 (대기중으로 복귀할 때까지 계속)
            self.blink_animation.setLoopCount(-1)
            self.blink_animation.start()
            self.start_move_animation()

    def start_move_animation(self):
        """박스를 왼쪽으로 이동 (사인곡선 easing)"""
        if not self.is_testing:
            return
        
        # 텍스트 너비 계산
        from PySide6.QtGui import QFontMetrics
        font = QFont("맑은 고딕", 24, QFont.Bold)
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(self.alert_box.text)
        target_width = text_width + 40  # 좌우 여백 20px씩
        
        # 이동 애니메이션
        self.box_animation.setStartValue(QRect(0, 0, self.width(), 50))
        self.box_animation.setEndValue(QRect(0, 0, target_width, 50))
        self.box_animation.start()

    def on_box_animation_finished(self):
        """박스 이동 완료 후 상세정보 표시"""
        if not self.is_testing:
            return
        
        # alert_box 너비 가져오기
        alert_box_width = self.alert_box.width()
        detail_start_x = alert_box_width + 10
        available_width = self.width() - detail_start_x - 20
        
        # detail_box 설정
        self.detail_box.setGeometry(
            detail_start_x, 0,
            available_width, 50
        )
        self.detail_box.set_text(self.full_detail_text)
        self.detail_box.show()
        
        # 텍스트가 영역을 넘어가면 스크롤 시작
        from PySide6.QtGui import QFontMetrics
        font = QFont("맑은 고딕", 24)
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(self.full_detail_text)
        if text_width > available_width:
            self.scroll_offset = 0
            self.scroll_timer.start(50)  # 50ms마다 스크롤
        else:
            self.scroll_timer.stop()
            self.scroll_offset = 0
    
    def scroll_detail_text(self):
        """상세 정보 텍스트 자동 스크롤 (좌우 이동)"""
        if not self.is_testing or not self.detail_box.isVisible():
            self.scroll_timer.stop()
            return
        
        alert_box_width = self.alert_box.width()
        detail_start_x = alert_box_width + 10
        max_width = self.width() - detail_start_x - 20
        
        # 텍스트가 영역보다 길면 스크롤
        text = self.full_detail_text
        if len(text) > 0:
            # 텍스트를 자르고 앞부분을 제거하는 방식 (좌우 스크롤 효과)
            if self.scroll_offset < len(text):
                # 텍스트를 자르고 앞부분 제거
                display_text = text[self.scroll_offset:]
                
                # QFontMetrics를 사용하여 실제 너비 계산
                from PySide6.QtGui import QFontMetrics
                font = QFont("맑은 고딕", 24)
                metrics = QFontMetrics(font)
                
                # 너비에 맞게 텍스트 자르기
                elided_text = metrics.elidedText(display_text, Qt.ElideRight, max_width)
                self.detail_box.set_text(elided_text)
                
                self.scroll_offset += 2  # 2글자씩 이동
                
                # 끝까지 가면 처음으로 (2초 대기 후)
                if self.scroll_offset >= len(text):
                    self.scroll_offset = 0
                    self.scroll_timer.stop()
                    QTimer.singleShot(2000, lambda: self.scroll_timer.start(50) if self.is_testing else None)
            else:
                self.scroll_offset = 0
        else:
            self.scroll_timer.stop()

    def stop_alert(self):
        if not self.is_testing:
            return
            
        self.is_testing = False
        self.pending_info_text = None
        self.current_event_id = None
        self.current_source = None
        self.alert_type = "normal"
        self.active_earthquakes.clear()
        self.current_rotation_index = 0
        
        if self.final_timer:
            self.final_timer.stop()
            self.final_timer = None
        
        if self.rotation_timer.isActive():
            self.rotation_timer.stop()
        
        if self.scroll_timer.isActive():
            self.scroll_timer.stop()
        
        if self.box_animation.state() == QPropertyAnimation.Running:
            self.box_animation.stop()
        self.blink_animation.stop()
        
        # 위젯 숨김 및 초기화
        self.alert_box.hide()
        self.alert_box.is_blinking = False
        self.alert_box.set_blink_opacity(0.0)
        self.detail_box.hide()
        self.scroll_offset = 0
        self.full_detail_text = ""
        
        # 대기중 상태로 복귀
        self.show_waiting()

class EarthquakeInfoWidget(QWidget):
    """JQuake 스타일의 지진 정보 위젯"""
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                color: #ffffff;
                font-family: 'Malgun Gothic';
                border: 2px solid #444444;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                border: none;
                padding: 2px;
            }
        """)
        
        self.title_label = QLabel("지진 속보 정보")
        self.title_label.setFont(QFont("맑은 고딕", 14, QFont.Bold))
        self.title_label.setStyleSheet("color: #ff6666; background-color: transparent;")
        self.layout.addWidget(self.title_label)
        
        self.source_label = QLabel("소스: -")
        self.author_label = QLabel("발신처: -")
        self.event_id_label = QLabel("이벤트 ID: -")
        self.serial_no_label = QLabel("시리얼 번호: -")
        self.origin_time_label = QLabel("발생시각: -")
        self.epicenter_label = QLabel("진원지: -")
        self.magnitude_label = QLabel("규모: -")
        self.depth_label = QLabel("깊이: -")
        self.max_intensity_label = QLabel("최대예측진도: -")
        self.max_lg_intensity_label = QLabel("최대예측장주기지진동계급: -")
        self.status_label = QLabel("상태: 대기중")
        
        for label in [self.source_label, self.author_label, self.event_id_label, self.serial_no_label, self.origin_time_label,
                      self.epicenter_label, self.magnitude_label, self.depth_label,
                      self.max_intensity_label, self.max_lg_intensity_label, self.status_label]:
            label.setFont(QFont("맑은 고딕", 10))
            label.setStyleSheet("background-color: transparent;")
            self.layout.addWidget(label)
            
        self.setMaximumHeight(350)
        
    def update_info(self, earthquake_data):
        """지진 정보 업데이트"""
        try:
            source = earthquake_data.get('source', '-')
            source_display = "대만 (ExpTech)" if source == "EXPTECH" else "일본 (DMDATA)"
            self.source_label.setText(f"소스: {source_display}")
            
            # author 정보 표시
            author = earthquake_data.get('author', '')
            if author:
                author_names = {
                    "cwa": "대만 중앙기상국 (CWA)",
                    "trem": "TREM",
                    "jma": "일본 기상청 (JMA)",
                    "nied": "NIED",
                    "kma": "한국 기상청 (KMA)",
                    "scdzj": "쓰촨성 지진국",
                    "fjdzj": "푸젠성 지진국"
                }
                author_display = author_names.get(author.lower(), author.upper())
                self.author_label.setText(f"발신처: {author_display}")
            else:
                self.author_label.setText("발신처: -")
            
            self.event_id_label.setText(f"이벤트 ID: {earthquake_data.get('event_id', '-')}")
            
            # 최종보 표시
            serial_no = earthquake_data.get('serial_no', '-')
            is_final = earthquake_data.get('is_final', False)
            if is_final:
                serial_display = f"{serial_no} (최종보)"
            else:
                serial_display = serial_no
            self.serial_no_label.setText(f"시리얼 번호: {serial_display}")
            
            self.origin_time_label.setText(f"발생시각: {earthquake_data.get('origin_time', '-')}")
            self.epicenter_label.setText(f"진원지: {earthquake_data.get('epicenter', '-')}")
            self.magnitude_label.setText(f"규모: {earthquake_data.get('magnitude', '-')}")
            self.depth_label.setText(f"깊이: {earthquake_data.get('depth', '-')}")
            self.max_intensity_label.setText(f"최대예측진도: {earthquake_data.get('max_intensity', '-')}")
            self.max_lg_intensity_label.setText(f"최대예측장주기지진동계급: {earthquake_data.get('max_lg_intensity', '-')}")
            
            status = "긴급지진속보 발령 중"
            if earthquake_data.get('is_canceled'):
                status = "취소됨"
                self.title_label.setStyleSheet("color: #6666ff; background-color: transparent;")
            elif earthquake_data.get('is_warning'):
                status = "경보 발령 중"
                self.title_label.setStyleSheet("color: #ff3333; background-color: transparent;")
            else:
                self.title_label.setStyleSheet("color: #ff6666; background-color: transparent;")
                
            self.status_label.setText(f"상태: {status}")
            
        except Exception as e:
            print(f"❌ 지진 정보 업데이트 오류: {e}")

class FlowDiagramWidget(QWidget):
    """OBS 상황 흐름도 위젯 (아날로그 형식)"""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(300)
        self.setStyleSheet("background-color: #1a1a1a; border: 2px solid #444; border-radius: 10px;")
        
        self.current_state = "일반"  # 일반, 지진, 해일
        self.active_flags = {
            "eew": False,
            "sokuhou": False,
            "epicenter": False,
            "detail": False,
            "tsunami": False
        }
    
    def update_state(self, state, flags):
        """상태 업데이트"""
        self.current_state = state
        self.active_flags = flags.copy()
        self.update()
    
    def paintEvent(self, event):
        """흐름도 그리기"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 배경
        painter.fillRect(0, 0, width, height, QColor("#1a1a1a"))
        
        # 박스 크기 및 위치
        box_width = 120
        box_height = 60
        box_spacing = 20
        start_x = 20
        start_y = height // 2 - box_height // 2
        
        # 상태 박스들
        states = [
            ("일반", "#00ff00", start_x, start_y),
            ("지진", "#ffff00", start_x + box_width + box_spacing, start_y),
            ("해일", "#ff0000", start_x + (box_width + box_spacing) * 2, start_y)
        ]
        
        # 화살표 색상
        arrow_color = QColor("#888888")
        active_arrow_color = QColor("#00ffff")
        
        # 박스 그리기
        for i, (state_name, color, x, y) in enumerate(states):
            # 현재 상태 강조
            if state_name == self.current_state:
                pen = QPen(QColor(color), 3)
                brush = QBrush(QColor(color))
            else:
                pen = QPen(QColor("#666666"), 2)
                brush = QBrush(QColor("#2a2a2a"))
            
            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawRoundedRect(x, y, box_width, box_height, 5, 5)
            
            # 텍스트
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("맑은 고딕", 10, QFont.Bold))
            text_rect = QRect(x, y, box_width, box_height)
            painter.drawText(text_rect, Qt.AlignCenter, state_name)
            
            # 화살표 그리기 (오른쪽)
            if i < len(states) - 1:
                arrow_x = x + box_width
                arrow_y = y + box_height // 2
                arrow_end_x = states[i + 1][2]
                
                # 활성 상태에 따라 화살표 색상 변경
                if state_name == self.current_state:
                    painter.setPen(QPen(active_arrow_color, 3))
                else:
                    painter.setPen(QPen(arrow_color, 2))
                
                # 화살표 선
                painter.drawLine(arrow_x, arrow_y, arrow_end_x - 10, arrow_y)
                
                # 화살표 머리
                arrow_size = 8
                painter.drawPolygon([
                    QPoint(arrow_end_x - 10, arrow_y),
                    QPoint(arrow_end_x - 10 - arrow_size, arrow_y - arrow_size // 2),
                    QPoint(arrow_end_x - 10 - arrow_size, arrow_y + arrow_size // 2)
                ])
        
        # 플래그 표시 (하단)
        flag_y = start_y + box_height + 30
        flag_x = start_x
        flag_spacing = 100
        
        flags_list = [
            ("EEW", self.active_flags["eew"]),
            ("진도속보", self.active_flags["sokuhou"]),
            ("진원정보", self.active_flags["epicenter"]),
            ("진원진도", self.active_flags["detail"]),
            ("해일", self.active_flags["tsunami"])
        ]
        
        for i, (flag_name, is_active) in enumerate(flags_list):
            flag_color = QColor("#00ff00") if is_active else QColor("#666666")
            painter.setPen(QPen(flag_color, 2))
            painter.setBrush(QBrush(flag_color))
            painter.drawEllipse(flag_x + i * flag_spacing, flag_y, 12, 12)
            
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("맑은 고딕", 8))
            painter.drawText(flag_x + i * flag_spacing + 18, flag_y + 10, flag_name)

class StatusPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.setStyleSheet("background-color: #f0f0f0; padding: 10px; border: 1px solid #ccc;")
        
        self.status_label = QLabel("현재 상황: 대기중")
        self.status_label.setFont(QFont("맑은 고딕", 12, QFont.Bold))
        self.layout.addWidget(self.status_label)
        
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_blink)
        self.blink_state = False
        self.alert_type = "normal"
        
    def update_status(self, status_text, alert_type="normal"):
        self.status_label.setText(f"현재 상황: {status_text}")
        self.alert_type = alert_type
        if alert_type != "normal":
            self.start_blink()
        else:
            self.stop_blink()
    
    def start_blink(self):
        self.blink_timer.start(500)
    
    def stop_blink(self):
        self.blink_timer.stop()
        self.status_label.setStyleSheet("color: black;")
    
    def toggle_blink(self):
        if self.blink_state:
            if self.alert_type == "warning":
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
            elif self.alert_type == "canceled":
                self.status_label.setStyleSheet("color: blue; font-weight: bold;")
            else:
                self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: black;")
        self.blink_state = not self.blink_state

class DetailWindow(QWidget):
    # Signal 정의 (스레드 안전한 UI 업데이트용) - 클래스 레벨에서 정의
    update_earthquake_info_signal = Signal(dict, str)
    update_obs_status_signal = Signal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("상세 정보 창")
        self.resize(800, 600)
        # 최소 크기 설정 (크기 조절 가능하도록)
        self.setMinimumSize(600, 400)
        
        # 이벤트 상태 관리자 및 OBS 제어기 초기화
        self.event_state_manager = EventStateManager()
        self.obs_controller = OBSController(use_websocket=True)
        self.event_state_manager.set_obs_controller(self.obs_controller)
        
        # 플래그 시스템 초기화
        try:
            if FlagSystem:
                self.flag_system = FlagSystem()
                # EventStateManager에 플래그 시스템 연결
                self.event_state_manager.set_flag_system(self.flag_system)
                
                # 상태 반영기 초기화 (플래그 평가와 완전히 분리)
                from state_reflector import StateReflector
                self.state_reflector = StateReflector(self.flag_system, self.obs_controller)
            else:
                self.flag_system = None
                self.state_reflector = None
                print("⚠️ 플래그 시스템을 사용할 수 없습니다.")
        except Exception as e:
            self.flag_system = None
            self.state_reflector = None
            print(f"⚠️ 플래그 시스템 초기화 실패: {e}")
        
        # Signal 연결 (메인 스레드에서만 UI 업데이트)
        self.update_earthquake_info_signal.connect(self._update_earthquake_info_slot)
        self.update_obs_status_signal.connect(self._update_obs_status_slot)
        
        main_layout = QVBoxLayout()
        
        self.status_panel = StatusPanel()
        main_layout.addWidget(self.status_panel)
        
        self.connection_panel = ConnectionStatusPanel()
        main_layout.addWidget(self.connection_panel)
        
        self.tab_widget = QTabWidget()
        
        self.main_tab = QWidget()
        main_tab_layout = QVBoxLayout()
        
        self.current_info_label = QLabel("현재 발생 중인 지진 정보")
        self.current_info_label.setFont(QFont("맑은 고딕", 14, QFont.Bold))
        main_tab_layout.addWidget(self.current_info_label)
        
        self.earthquake_info_widget = EarthquakeInfoWidget()
        main_tab_layout.addWidget(self.earthquake_info_widget)
        
        self.recent_label = QLabel("최근 발생한 지진 목록")
        self.recent_label.setFont(QFont("맑은 고딕", 12, QFont.Bold))
        main_tab_layout.addWidget(self.recent_label)
        
        self.recent_earthquakes = QTextEdit()
        self.recent_earthquakes.setReadOnly(True)
        self.recent_earthquakes.setText("최근 발생한 지진이 없습니다.")
        main_tab_layout.addWidget(self.recent_earthquakes)
        
        self.main_tab.setLayout(main_tab_layout)
        self.tab_widget.addTab(self.main_tab, "메인")
        
        self.obs_tab = QWidget()
        obs_layout = QVBoxLayout()
        obs_layout.setSpacing(15)
        
        # ========== OBS 탭: 읽기 전용 상태 표시만 ==========
        
        # 현재 상위 플래그 표시
        upper_flags_group = QGroupBox("현재 활성 상위 플래그")
        upper_flags_group.setFont(QFont("맑은 고딕", 11, QFont.Bold))
        upper_flags_layout = QVBoxLayout()
        self.upper_flags_display = QTextEdit()
        self.upper_flags_display.setReadOnly(True)
        self.upper_flags_display.setMaximumHeight(100)
        self.upper_flags_display.setText("활성 상위 플래그 없음")
        upper_flags_layout.addWidget(self.upper_flags_display)
        upper_flags_group.setLayout(upper_flags_layout)
        
        # 현재 하위 플래그 표시
        lower_flags_group = QGroupBox("현재 활성 하위 플래그")
        lower_flags_group.setFont(QFont("맑은 고딕", 11, QFont.Bold))
        lower_flags_layout = QVBoxLayout()
        self.lower_flags_display = QTextEdit()
        self.lower_flags_display.setReadOnly(True)
        self.lower_flags_display.setMaximumHeight(100)
        self.lower_flags_display.setText("활성 하위 플래그 없음")
        lower_flags_layout.addWidget(self.lower_flags_display)
        lower_flags_group.setLayout(lower_flags_layout)
        
        # 현재 선택된 장면 표시
        current_scene_group = QGroupBox("현재 선택된 장면")
        current_scene_group.setFont(QFont("맑은 고딕", 11, QFont.Bold))
        current_scene_layout = QVBoxLayout()
        self.current_scene_display = QLabel("일반")
        self.current_scene_display.setFont(QFont("맑은 고딕", 14, QFont.Bold))
        self.current_scene_display.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                padding: 12px;
                border-radius: 5px;
                color: #00ff00;
            }
        """)
        current_scene_layout.addWidget(self.current_scene_display)
        current_scene_group.setLayout(current_scene_layout)
        
        # 현재 활성화된 소스/필터 상태 표시
        sources_filters_group = QGroupBox("현재 활성화된 소스/필터")
        sources_filters_group.setFont(QFont("맑은 고딕", 11, QFont.Bold))
        sources_filters_layout = QVBoxLayout()
        self.sources_filters_display = QTextEdit()
        self.sources_filters_display.setReadOnly(True)
        self.sources_filters_display.setMaximumHeight(150)
        self.sources_filters_display.setText("활성 소스/필터 없음")
        sources_filters_layout.addWidget(self.sources_filters_display)
        sources_filters_group.setLayout(sources_filters_layout)
        
        # 첫 번째 행: 상위 플래그 + 하위 플래그
        first_row = QHBoxLayout()
        first_row.setSpacing(15)
        first_row.addWidget(upper_flags_group, 1)
        first_row.addWidget(lower_flags_group, 1)
        obs_layout.addLayout(first_row)
        
        # 두 번째 행: 현재 장면 + 소스/필터
        second_row = QHBoxLayout()
        second_row.setSpacing(15)
        second_row.addWidget(current_scene_group, 1)
        second_row.addWidget(sources_filters_group, 1)
        obs_layout.addLayout(second_row)
        
        # ========== 설정 버튼 (유일한 조작 가능 요소) ==========
        settings_button = QPushButton("플래그 시스템 설정")
        settings_button.setFont(QFont("맑은 고딕", 12, QFont.Bold))
        settings_button.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                padding: 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5aaeff;
            }
        """)
        settings_button.clicked.connect(self.open_flag_system_settings)
        obs_layout.addWidget(settings_button)
        
        # 기존 변수들 제거 (더 이상 사용하지 않음)
        # self.current_state_info는 self.current_scene_display로 대체
        # self.active_events_text는 제거
        
        obs_layout.addStretch()
        self.obs_tab.setLayout(obs_layout)
        self.tab_widget.addTab(self.obs_tab, "방송 화면 상태")
        
        self.tts_tab = QWidget()
        tts_layout = QVBoxLayout()
        tts_layout.addWidget(QLabel("TTS 관리 (준비 중)"))
        self.tts_tab.setLayout(tts_layout)
        self.tab_widget.addTab(self.tts_tab, "TTS")
        
        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)
        
        # 크기 조절 정책 설정 (상하 길이 조절 가능)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # OBS 상태 업데이트 타이머 (1초마다)
        self.obs_status_timer = QTimer()
        self.obs_status_timer.timeout.connect(self.update_obs_status)
        self.obs_status_timer.start(1000)  # 1초마다 업데이트
        
        self.show()
    
    def update_earthquake_info(self, earthquake_data, event_id):
        """현재 지진 정보 업데이트 (스레드 안전)"""
        # Signal을 통해 메인 스레드에서만 실행되도록 함
        self.update_earthquake_info_signal.emit(earthquake_data, event_id)
    
    def _update_earthquake_info_slot(self, earthquake_data, event_id):
        """메인 스레드에서 실행되는 실제 업데이트 메서드"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.earthquake_info_widget.update_info(earthquake_data)
        
        source = earthquake_data.get('source', '-')
        source_display = "🇹🇼 대만" if source == "EXPTECH" else "🇯🇵 일본"
        
        info_text = f"[{timestamp}] [{source_display}] 이벤트 ID: {event_id}\n"
        info_text += f"진원지: {earthquake_data.get('epicenter', '미상')}, "
        info_text += f"규모: {earthquake_data.get('magnitude', '미상')}, "
        info_text += f"최대예측진도: {earthquake_data.get('max_intensity', '미상')}\n"
        
        current_text = self.recent_earthquakes.toPlainText()
        if current_text == "최근 발생한 지진이 없습니다.":
            current_text = ""
        new_text = info_text + "\n" + current_text
        self.recent_earthquakes.setText(new_text[:2000])
        
        if source == "EXPTECH":
            self.connection_panel.update_exptech_status("active")
            self.connection_panel.update_last_data_time("대만")
        else:
            self.connection_panel.update_dmdata_status("active")
            self.connection_panel.update_last_data_time("일본")
    
    def update_status(self, status_text, alert_type="normal"):
        """상황판 업데이트"""
        self.status_panel.update_status(status_text, alert_type)
    
    def update_obs_status(self):
        """OBS 탭 상태 업데이트 (스레드 안전)"""
        # Signal을 통해 메인 스레드에서만 실행되도록 함
        self.update_obs_status_signal.emit()
    
    def _update_obs_status_slot(self):
        """메인 스레드에서 실행되는 실제 업데이트 메서드"""
        # 플래그 시스템이 있으면 플래그 상태 표시
        if hasattr(self, 'flag_system') and self.flag_system:
            # 상위 플래그 표시
            active_upper = [f.name for f in self.flag_system.upper_flags.values() if f.state]
            if active_upper:
                self.upper_flags_display.setText("\n".join([f"• {name}" for name in active_upper]))
            else:
                self.upper_flags_display.setText("활성 상위 플래그 없음")
            
            # 하위 플래그 표시
            active_lower = [f.name for f in self.flag_system.lower_flags.values() if f.state]
            if active_lower:
                self.lower_flags_display.setText("\n".join([f"• {name}" for name in active_lower]))
            else:
                self.lower_flags_display.setText("활성 하위 플래그 없음")
            
            # 현재 장면 표시 (OBS 컨트롤러에서 가져오기)
            if self.obs_controller:
                current_scene = self.obs_controller.current_scene or "일반"
                self.current_scene_display.setText(current_scene)
                
                # 장면 색상 설정
                scene_colors = {
                    "일반": "#00ff00",
                    "일본": "#ffff00",
                    "해일": "#ff0000"
                }
                scene_color = scene_colors.get(current_scene, "#00ff00")
                self.current_scene_display.setStyleSheet(f"""
                    QLabel {{
                        background-color: #1a1a1a;
                        padding: 12px;
                        border-radius: 5px;
                        color: {scene_color};
                    }}
                """)
            
            # 소스/필터 상태 표시 (추후 구현)
            self.sources_filters_display.setText("활성 소스/필터 없음")
        else:
            # 플래그 시스템이 없으면 기본 표시
            if hasattr(self, 'upper_flags_display'):
                self.upper_flags_display.setText("플래그 시스템 미초기화")
            if hasattr(self, 'lower_flags_display'):
                self.lower_flags_display.setText("플래그 시스템 미초기화")
            if hasattr(self, 'current_scene_display'):
                self.current_scene_display.setText("일반")
            if hasattr(self, 'sources_filters_display'):
                self.sources_filters_display.setText("플래그 시스템 미초기화")
    
    def get_event_state_manager(self):
        """이벤트 상태 관리자 반환"""
        return self.event_state_manager
    
    # 플래그 상태 변경 핸들러 제거 - StateReflector가 담당
    
    def open_flag_system_settings(self):
        """플래그 시스템 설정 창 열기"""
        if not hasattr(self, 'flag_system') or not self.flag_system:
            # 플래그 시스템 초기화
            try:
                if FlagSystem:
                    self.flag_system = FlagSystem()
                    self.event_state_manager.set_flag_system(self.flag_system)
                    
                    # 상태 반영기 초기화
                    from state_reflector import StateReflector
                    self.state_reflector = StateReflector(self.flag_system, self.obs_controller)
                else:
                    print("❌ 플래그 시스템을 사용할 수 없습니다.")
                    return
            except Exception as e:
                print(f"❌ 플래그 시스템 초기화 실패: {e}")
                return
        
        try:
            from flag_settings_window import FlagSystemSettingsWindow
            settings_window = FlagSystemSettingsWindow(self.flag_system, self.obs_controller, self)
            settings_window.exec()
        except ImportError as e:
            print(f"❌ 플래그 설정 창을 불러올 수 없습니다: {e}")
    
    def open_workflow_settings(self):
        """OBS 워크플로우 설정 창 열기 (레거시 - 호환성 유지)"""
        workflow_window = OBSWorkflowSettingsWindow(self.obs_controller, self.event_state_manager, self)
        workflow_window.exec()
    
    def save_scene_rules(self):
        """장면 전환 규칙 저장"""
        import json
        rules = {
            "rule1": {
                "flag": self.rule1_flag_combo.currentText(),
                "scene": self.rule1_scene_combo.currentText()
            },
            "rule2": {
                "flag": self.rule2_flag_combo.currentText(),
                "scene": self.rule2_scene_combo.currentText()
            },
            "rule3": {
                "scene": self.rule3_scene_combo.currentText()
            }
        }
        try:
            with open("scene_rules.json", 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            print("✅ 장면 전환 규칙 저장 완료")
        except Exception as e:
            print(f"❌ 장면 전환 규칙 저장 실패: {e}")
    
    def load_scene_rules(self):
        """장면 전환 규칙 로드"""
        import json
        import os
        try:
            if os.path.exists("scene_rules.json"):
                with open("scene_rules.json", 'r', encoding='utf-8') as f:
                    rules = json.load(f)
                
                # 1순위
                if "rule1" in rules:
                    rule1 = rules["rule1"]
                    index = self.rule1_flag_combo.findText(rule1.get("flag", "해일 상태"))
                    if index >= 0:
                        self.rule1_flag_combo.setCurrentIndex(index)
                    index = self.rule1_scene_combo.findText(rule1.get("scene", "해일"))
                    if index >= 0:
                        self.rule1_scene_combo.setCurrentIndex(index)
                
                # 2순위
                if "rule2" in rules:
                    rule2 = rules["rule2"]
                    index = self.rule2_flag_combo.findText(rule2.get("flag", "지진/EEW/상세정보 상태"))
                    if index >= 0:
                        self.rule2_flag_combo.setCurrentIndex(index)
                    index = self.rule2_scene_combo.findText(rule2.get("scene", "일본"))
                    if index >= 0:
                        self.rule2_scene_combo.setCurrentIndex(index)
                
                # 3순위
                if "rule3" in rules:
                    rule3 = rules["rule3"]
                    index = self.rule3_scene_combo.findText(rule3.get("scene", "일반"))
                    if index >= 0:
                        self.rule3_scene_combo.setCurrentIndex(index)
            else:
                # 기본값 설정
                self.rule1_flag_combo.setCurrentText("해일 상태")
                self.rule1_scene_combo.setCurrentText("해일")
                self.rule2_flag_combo.setCurrentText("지진/EEW/상세정보 상태")
                self.rule2_scene_combo.setCurrentText("일본")
                self.rule3_scene_combo.setCurrentText("일반")
        except Exception as e:
            print(f"❌ 장면 전환 규칙 로드 실패: {e}")
            # 기본값 설정
            self.rule1_flag_combo.setCurrentText("해일 상태")
            self.rule1_scene_combo.setCurrentText("해일")
            self.rule2_flag_combo.setCurrentText("지진/EEW/상세정보 상태")
            self.rule2_scene_combo.setCurrentText("일본")
            self.rule3_scene_combo.setCurrentText("일반")
    
    def save_flag_settings(self):
        """플래그 설정 저장"""
        import json
        flags = {}
        for label, widgets in self.flag_settings.items():
            flags[label] = {
                "flag_name": widgets['name_edit'].text(),
                "flag_value": widgets['value_combo'].currentText() == "true"
            }
        try:
            with open("flag_settings.json", 'w', encoding='utf-8') as f:
                json.dump(flags, f, ensure_ascii=False, indent=2)
            print("✅ 플래그 설정 저장 완료")
        except Exception as e:
            print(f"❌ 플래그 설정 저장 실패: {e}")
    
    def load_flag_settings(self):
        """플래그 설정 로드"""
        import json
        import os
        try:
            if os.path.exists("flag_settings.json"):
                with open("flag_settings.json", 'r', encoding='utf-8') as f:
                    flags = json.load(f)
                
                for label, widgets in self.flag_settings.items():
                    if label in flags:
                        flag_data = flags[label]
                        widgets['name_edit'].setText(flag_data.get("flag_name", ""))
                        widgets['value_combo'].setCurrentIndex(0 if flag_data.get("flag_value", True) else 1)
        except Exception as e:
            print(f"❌ 플래그 설정 로드 실패: {e}")

# ------------------ OBS 연동 및 이벤트 상태 관리 ------------------

class EventStateManager(QObject):
    """지진 이벤트 상태 관리 클래스 - 통합 지진 플래그 방식
    
    상태 머신 구조:
    - 상태 변경: 여러 곳에서 가능 (handle_eew, handle_report, handle_tsunami, 타이머 등)
    - 장면 재계산: 주기적 타이머에서만 실행 (단일 트리거)
    - 워크플로우: 상태만 변경하고 장면 재계산에 관여하지 않음
    """
    def __init__(self):
        super().__init__()
        self.earthquake_states = {}  # {event_id: state_dict}
        self.global_flags = {
            "has_tsunami": False,
            "has_earthquake": False,  # 긴급지진속보 + 지진상세정보 통합
            "has_active_earthquake": False
        }
        self.current_scene = "일반"
        self.obs_controller = None
        self.workflow_engine = None  # 워크플로우 실행 엔진
        
        # 무감지진 타이머 관리 {event_id: timer}
        self.undetected_timers = {}
        
        # 진원진도정보 수신 후 5초 타이머 {event_id: timer}
        self.detail_complete_timers = {}
        
        # 장면 재계산 타이머 (주기적 실행 - 단일 트리거)
        self.scene_recompute_timer = None
        self._init_scene_recompute_timer()
    
    def _init_scene_recompute_timer(self):
        """장면 재계산 타이머 초기화 - 주기적으로 장면을 재계산"""
        # QTimer를 사용하여 주기적으로 장면 재계산 (100ms마다)
        # 이렇게 하면 상태 변경과 장면 재계산이 완전히 분리됨
        self.scene_recompute_timer = QTimer()
        self.scene_recompute_timer.timeout.connect(self.recompute_scene)
        self.scene_recompute_timer.start(100)  # 100ms마다 실행
    
    def _load_scene_rules(self):
        """장면 전환 규칙 로드"""
        import json
        import os
        try:
            if os.path.exists("scene_rules.json"):
                with open("scene_rules.json", 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"❌ 장면 전환 규칙 로드 실패: {e}")
        
        # 기본값
        return {
            "rule1": {"flag": "해일 상태", "scene": "해일"},
            "rule2": {"flag": "지진/EEW/상세정보 상태", "scene": "일본"},
            "rule3": {"scene": "일반"}
        }
    
    def set_obs_controller(self, obs_controller):
        """OBS 제어기를 설정하고 워크플로우 엔진 초기화"""
        self.obs_controller = obs_controller
        if obs_controller:
            # 워크플로우 엔진은 이벤트 사실만 상태 관리자에 전달하는 콜백을 받음
            # 워크플로우는 상태만 변경하고, 장면 재계산은 주기적 타이머가 담당
            self.workflow_engine = WorkflowEngine(self._handle_workflow_event_fact)
    
    def set_flag_system(self, flag_system):
        """플래그 시스템 설정"""
        self.flag_system = flag_system
    
    def create_state(self, event_id, source="DMDATA"):
        """새로운 지진 상태 생성"""
        return {
            "tsunami_active": False,
            "tsunami_canceled": False,
            "eew_active": False,
            "eew_canceled": False,  # 긴급지진속보 취소보
            "eew_final": False,
            "eew_first_received_time": None,  # 첫 긴급지진속보 수신 시간 (무감지진 판단용)
            "report_sokuhou": False,  # 진도속보 수신 여부
            "report_epicenter": False,  # 진원정보 수신 여부
            "report_detail": False,  # 진원진도정보 수신 여부
            "report_detail_received_time": None,  # 진원진도정보 수신 시간
            "earthquake_completed": False,  # 지진 플래그 완료 여부
            "source": source
        }
    
    def handle_tsunami(self, event_id, is_canceled=False, source="DMDATA"):
        """해일정보 처리"""
        if event_id not in self.earthquake_states:
            self.earthquake_states[event_id] = self.create_state(event_id, source)
        
        # 상태 업데이트 (워크플로우와 무관하게 항상 수행)
        if is_canceled:
            self.earthquake_states[event_id]["tsunami_canceled"] = True
            self.earthquake_states[event_id]["tsunami_active"] = False
        else:
            self.earthquake_states[event_id]["tsunami_active"] = True
            self.earthquake_states[event_id]["tsunami_canceled"] = False
        
        # 워크플로우 엔진에 이벤트 사실 전달 (조건 확인 후 상태 관리자에 전달)
        if self.workflow_engine:
            event_data = {
                'event_id': event_id,
                'is_canceled': is_canceled,
                'source': source
            }
            
            fact_type = 'TSUNAMI_CANCELED' if is_canceled else 'TSUNAMI_RECEIVED'
            self.workflow_engine.trigger_event_fact(fact_type, event_data)
        
        # 플래그 시스템에 이벤트 트리거
        if hasattr(self, 'flag_system') and self.flag_system:
            event_data = {
                'event_id': event_id,
                'is_canceled': is_canceled,
                'source': source
            }
            fact_type = 'TSUNAMI_CANCELED' if is_canceled else 'TSUNAMI_RECEIVED'
            self.flag_system.trigger_event(fact_type, event_data)
        
        # 상태만 업데이트 (장면 재계산은 주기적 타이머가 담당)
        self.update_global_flags()
    
    def handle_eew(self, event_id, serial_no, is_final=False, is_warning=False, is_canceled=False, source="DMDATA"):
        """긴급지진속보 처리"""
        is_new = event_id not in self.earthquake_states
        
        if is_new:
            self.earthquake_states[event_id] = self.create_state(event_id, source)
            # 첫 긴급지진속보 수신 시간 기록
            self.earthquake_states[event_id]["eew_first_received_time"] = time.time()
            # 무감지진 타이머 시작 (10분)
            self.start_undetected_timer(event_id)
        
        # 상태 업데이트 (워크플로우와 무관하게 항상 수행)
        if is_canceled:
            self.earthquake_states[event_id]["eew_canceled"] = True
            self.earthquake_states[event_id]["eew_active"] = False
            self.stop_undetected_timer(event_id)
        elif is_final:
            self.earthquake_states[event_id]["eew_final"] = True
            self.earthquake_states[event_id]["eew_active"] = False
        else:
            self.earthquake_states[event_id]["eew_active"] = True
            self.earthquake_states[event_id]["eew_final"] = False
            self.earthquake_states[event_id]["eew_canceled"] = False
        
        # 워크플로우 엔진에 이벤트 사실 전달 (조건 확인 후 상태 관리자에 전달)
        if self.workflow_engine:
            event_data = {
                'event_id': event_id,
                'is_new': is_new,
                'is_warning': is_warning,
                'is_canceled': is_canceled,
                'is_final': is_final,
                'source': source
            }
            
            if is_canceled:
                fact_type = 'EEW_CANCELED'
            elif is_final:
                fact_type = 'EEW_FINAL'
            elif is_warning:
                fact_type = 'EEW_WARNING'
            elif is_new:
                fact_type = 'EEW_STARTED'
            else:
                fact_type = 'EEW_UPDATED'
            
            self.workflow_engine.trigger_event_fact(fact_type, event_data)
        
        # 플래그 시스템에 이벤트 트리거
        if hasattr(self, 'flag_system') and self.flag_system:
            event_data = {
                'event_id': event_id,
                'is_new': is_new,
                'is_warning': is_warning,
                'is_canceled': is_canceled,
                'is_final': is_final,
                'source': source,
                'max_intensity': None  # EEW 데이터에서 가져와야 함
            }
            
            if is_canceled:
                fact_type = 'EEW_CANCELED'
            elif is_final:
                fact_type = 'EEW_FINAL'
            elif is_warning:
                fact_type = 'EEW_WARNING'
            elif is_new:
                fact_type = 'EEW_STARTED'
            else:
                fact_type = 'EEW_UPDATED'
            
            self.flag_system.trigger_event(fact_type, event_data)
        
        # 상태만 업데이트 (장면 재계산은 주기적 타이머가 담당)
        self.update_global_flags()
    
    def handle_report(self, event_id, report_type, source="DMDATA", is_update_epicenter=False, has_tsunami=False, has_lpgm=False):
        """지진상세정보 처리 (진도속보, 진원정보, 진원진도정보 등) - 갱신 지원, 긴급지진속보 없이 발표되는 경우도 처리"""
        is_first_report = event_id not in self.earthquake_states
        if is_first_report:
            # 긴급지진속보 없이 지진상세정보가 발표된 경우
            self.earthquake_states[event_id] = self.create_state(event_id, source)
            # 지진 플래그 활성화 (긴급지진속보 없이도 지진으로 인식)
            self.earthquake_states[event_id]["report_first_received_time"] = time.time()
            # 긴급지진속보 없이 발표된 경우임을 표시
            self.earthquake_states[event_id]["no_eew"] = True
        
        # 무감지진 타이머 중지 (정보가 들어왔으므로)
        self.stop_undetected_timer(event_id)
        
        # 갱신 처리: 같은 event_id로 여러 번 발표될 수 있음
        if report_type == "sokuhou":
            self.earthquake_states[event_id]["report_sokuhou"] = True
        elif report_type == "epicenter":
            self.earthquake_states[event_id]["report_epicenter"] = True
        elif report_type == "detail":
            # 진원진도정보 수신: 5초 후 지진 플래그 해제 (다른 플래그 없을 때)
            self.earthquake_states[event_id]["report_detail"] = True
            self.earthquake_states[event_id]["report_detail_received_time"] = time.time()
            self.start_detail_complete_timer(event_id)
        
        # 워크플로우 엔진에 이벤트 사실 전달 (조건 확인 후 상태 관리자에 전달)
        if self.workflow_engine:
            event_data = {
                'event_id': event_id,
                'report_type': report_type,
                'is_update_epicenter': is_update_epicenter,
                'has_tsunami': has_tsunami,
                'has_lpgm': has_lpgm,
                'source': source
            }
            
            if report_type == "sokuhou":
                fact_type = 'SOKUHOU_RECEIVED'
            elif report_type == "epicenter":
                fact_type = 'EPICENTER_RECEIVED'
            elif report_type == "detail":
                fact_type = 'DETAIL_RECEIVED'
            else:
                fact_type = None
            
            if fact_type:
                self.workflow_engine.trigger_event_fact(fact_type, event_data)
        
        # 상태만 업데이트 (장면 재계산은 주기적 타이머가 담당)
        self.update_global_flags()
    
    def start_undetected_timer(self, event_id):
        """무감지진 타이머 시작 (10분) - 주기적으로 체크"""
        self.stop_undetected_timer(event_id)  # 기존 타이머가 있으면 중지
        
        def check_undetected():
            if event_id not in self.earthquake_states:
                return
            
            state = self.earthquake_states[event_id]
            
            # 이미 완료되었거나 취소되었으면 중지
            if state["earthquake_completed"] or state["eew_canceled"]:
                self.stop_undetected_timer(event_id)
                return
            
            # 상세정보가 들어왔으면 중지
            if state["report_sokuhou"] or state["report_epicenter"] or state["report_detail"]:
                self.stop_undetected_timer(event_id)
                return
            
            # 10분 경과 확인
            if state.get("eew_first_received_time"):
                elapsed = time.time() - state["eew_first_received_time"]
                if elapsed >= 600:  # 10분 = 600초
                    print(f"⚠️ 무감지진 판단: {event_id} (10분간 정보 없음)")
                    # 지진 플래그 해제 (상태 변경만 수행)
                    self.earthquake_states[event_id]["earthquake_completed"] = True
                    self.update_global_flags()
                    # 장면 재계산은 주기적 타이머가 담당
                    self.stop_undetected_timer(event_id)
                    return
            
            # 아직 10분이 안 지났으면 1초 후 다시 체크
            timer = threading.Timer(1.0, check_undetected)
            timer.daemon = True
            timer.start()
            self.undetected_timers[event_id] = timer
        
        # 첫 체크 시작
        check_undetected()
    
    def stop_undetected_timer(self, event_id):
        """무감지진 타이머 중지"""
        if event_id in self.undetected_timers:
            self.undetected_timers[event_id].cancel()
            del self.undetected_timers[event_id]
    
    def start_detail_complete_timer(self, event_id):
        """진원진도정보 수신 후 5초 타이머 시작"""
        self.stop_detail_complete_timer(event_id)  # 기존 타이머가 있으면 중지
        
        def complete_earthquake():
            if event_id not in self.earthquake_states:
                return
            
            state = self.earthquake_states[event_id]
            
            # 다른 플래그(해일정보)가 없으면 지진 플래그 해제 (상태 변경만 수행)
            if not state["tsunami_active"] or state["tsunami_canceled"]:
                print(f"✅ 지진 완료: {event_id} (진원진도정보 수신 후 5초 경과)")
                self.earthquake_states[event_id]["earthquake_completed"] = True
                self.update_global_flags()
                # 장면 재계산은 주기적 타이머가 담당
        
        timer = threading.Timer(5.0, complete_earthquake)
        timer.daemon = True
        timer.start()
        self.detail_complete_timers[event_id] = timer
    
    def stop_detail_complete_timer(self, event_id):
        """진원진도정보 완료 타이머 중지"""
        if event_id in self.detail_complete_timers:
            self.detail_complete_timers[event_id].cancel()
            del self.detail_complete_timers[event_id]
    
    def update_global_flags(self):
        """전역 플래그 업데이트"""
        # 해일정보: 하나라도 발령 중이고 해제되지 않았으면 True
        self.global_flags["has_tsunami"] = any(
            state["tsunami_active"] and not state["tsunami_canceled"]
            for state in self.earthquake_states.values()
        )
        
        # 지진 플래그: 긴급지진속보 또는 지진상세정보가 있고, 완료되지 않았으면 True
        self.global_flags["has_earthquake"] = any(
            not state["earthquake_completed"] and (
                (state["eew_active"] and not state["eew_canceled"]) or  # 긴급지진속보 진행 중
                state["report_sokuhou"] or  # 진도속보 수신
                state["report_epicenter"] or  # 진원정보 수신
                state["report_detail"]  # 진원진도정보 수신
            )
            for state in self.earthquake_states.values()
        )
        
        # 진행 중인 지진이 있는가?
        self.global_flags["has_active_earthquake"] = (
            self.global_flags["has_tsunami"] or
            self.global_flags["has_earthquake"]
        )
    
    def _handle_workflow_event_fact(self, fact_type, event_data):
        """
        워크플로우에서 전달받은 이벤트 사실 처리
        
        워크플로우는 조건을 만족하면 이벤트 사실을 이 함수로 전달합니다.
        이 함수는 상태만 업데이트합니다. 장면 재계산은 주기적 타이머가 담당합니다.
        """
        # 이벤트 사실에 따라 상태 업데이트만 수행
        event_id = event_data.get('event_id')
        if not event_id:
            return
        
        # 이벤트 상태가 없으면 생성
        if event_id not in self.earthquake_states:
            source = event_data.get('source', 'DMDATA')
            self.earthquake_states[event_id] = self.create_state(event_id, source)
        
        # 이벤트 사실에 따라 상태 업데이트 (장면 재계산 호출하지 않음)
        if fact_type == 'EEW_STARTED':
            self.earthquake_states[event_id]["eew_active"] = True
            self.earthquake_states[event_id]["eew_canceled"] = False
            self.earthquake_states[event_id]["eew_final"] = False
        elif fact_type == 'EEW_UPDATED':
            self.earthquake_states[event_id]["eew_active"] = True
            self.earthquake_states[event_id]["eew_canceled"] = False
            self.earthquake_states[event_id]["eew_final"] = False
        elif fact_type == 'EEW_FINAL':
            self.earthquake_states[event_id]["eew_final"] = True
            self.earthquake_states[event_id]["eew_active"] = False
        elif fact_type == 'EEW_CANCELED':
            self.earthquake_states[event_id]["eew_canceled"] = True
            self.earthquake_states[event_id]["eew_active"] = False
        elif fact_type == 'DETAIL_RECEIVED':
            self.earthquake_states[event_id]["report_detail"] = True
        elif fact_type == 'SOKUHOU_RECEIVED':
            self.earthquake_states[event_id]["report_sokuhou"] = True
        elif fact_type == 'EPICENTER_RECEIVED':
            self.earthquake_states[event_id]["report_epicenter"] = True
        elif fact_type == 'TSUNAMI_RECEIVED':
            self.earthquake_states[event_id]["tsunami_active"] = True
            self.earthquake_states[event_id]["tsunami_canceled"] = False
        elif fact_type == 'TSUNAMI_CANCELED':
            self.earthquake_states[event_id]["tsunami_canceled"] = True
            self.earthquake_states[event_id]["tsunami_active"] = False
        
        # 상태만 업데이트 (장면 재계산은 주기적 타이머가 담당)
        self.update_global_flags()
    
    def recompute_scene(self):
        """
        OBS 장면 재계산 - 단일 결정 함수 (주기적 타이머에서만 호출)
        
        전체 상태 스냅샷을 보고 장면을 결정합니다.
        이 함수는 오직 "활성 이벤트가 하나라도 있는가"만을 기준으로 판단합니다.
        
        활성 이벤트 집합을 명시적으로 계산하고,
        활성 이벤트가 0개일 때만 기본 화면으로 전환합니다.
        """
        # 활성 이벤트 집합 계산
        active_event_ids = []
        
        for event_id, state in self.earthquake_states.items():
            # 해일정보 활성 여부
            has_tsunami = state["tsunami_active"] and not state["tsunami_canceled"]
            
            # 지진 활성 여부
            has_earthquake = (
                not state["earthquake_completed"] and (
                    (state["eew_active"] and not state["eew_canceled"]) or
                    state["report_sokuhou"] or
                    state["report_epicenter"] or
                    state["report_detail"]
                )
            )
            
            # 활성 이벤트인지 확인
            if has_tsunami or has_earthquake:
                active_event_ids.append(event_id)
        
        # 사용자 설정된 규칙에 따라 장면 결정
        # 규칙 재로드 (설정 변경 반영)
        self.scene_rules = self._load_scene_rules()
        
        # 플래그 상태 확인
        has_tsunami = any(
            state["tsunami_active"] and not state["tsunami_canceled"]
            for state in self.earthquake_states.values()
        )
        
        has_earthquake = any(
            not state["earthquake_completed"] and (
                (state["eew_active"] and not state["eew_canceled"]) or
                state["report_sokuhou"] or
                state["report_epicenter"] or
                state["report_detail"]
            )
            for state in self.earthquake_states.values()
        )
        
        # 사용자 설정 규칙에 따라 장면 결정
        target_scene = None
        
        # 1순위 규칙 확인
        if "rule1" in self.scene_rules:
            rule1 = self.scene_rules["rule1"]
            flag_type = rule1.get("flag", "해일 상태")
            if flag_type == "해일 상태" and has_tsunami:
                target_scene = rule1.get("scene", "해일")
            elif flag_type == "지진/EEW/상세정보 상태" and has_earthquake:
                target_scene = rule1.get("scene", "일본")
        
        # 2순위 규칙 확인 (1순위가 적용되지 않았을 때)
        if target_scene is None and "rule2" in self.scene_rules:
            rule2 = self.scene_rules["rule2"]
            flag_type = rule2.get("flag", "지진/EEW/상세정보 상태")
            if flag_type == "해일 상태" and has_tsunami:
                target_scene = rule2.get("scene", "해일")
            elif flag_type == "지진/EEW/상세정보 상태" and has_earthquake:
                target_scene = rule2.get("scene", "일본")
        
        # 3순위 규칙 (1, 2순위가 모두 적용되지 않았을 때)
        if target_scene is None:
            if len(active_event_ids) == 0:
                if "rule3" in self.scene_rules:
                    target_scene = self.scene_rules["rule3"].get("scene", "일반")
                else:
                    target_scene = "일반"
            else:
                # 활성 이벤트가 있으면 현재 장면 유지
                target_scene = self.current_scene
        
        # [레거시 코드] 장면 전환은 이제 플래그 시스템의 StateReflector가 담당합니다.
        # OBS 직접 제어는 state_reflector.py에서만 수행됩니다.
        # self.current_scene은 참고용으로만 유지합니다.
        if self.current_scene != target_scene:
            self.current_scene = target_scene
            print(f"ℹ️ [레거시] 장면 결정: {target_scene} (활성 이벤트: {len(active_event_ids)}개) - 실제 전환은 StateReflector가 수행")
    
    def get_status_summary(self):
        """현재 상태 요약 반환"""
        active_events = []
        for event_id, state in self.earthquake_states.items():
            if not state["earthquake_completed"]:
                flags = []
                if state["tsunami_active"] and not state["tsunami_canceled"]:
                    flags.append("해일정보")
                if (state["eew_active"] and not state["eew_canceled"]) or state["report_sokuhou"] or state["report_epicenter"] or state["report_detail"]:
                    flags.append("지진")
                
                if flags:
                    active_events.append({
                        "event_id": event_id,
                        "source": state["source"],
                        "flags": flags
                    })
        
        return {
            "current_scene": self.current_scene,
            "global_flags": self.global_flags.copy(),
            "active_events": active_events,
            "total_events": len(self.earthquake_states)
        }

class WorkflowEngine:
    """워크플로우 실행 엔진 - 이벤트 사실(Event fact)만 상태 관리자에 전달
    
    워크플로우는 절대 OBS를 직접 또는 간접적으로 제어하지 않습니다.
    워크플로우의 유일한 역할은 이벤트 사실을 EventStateManager에 전달하는 것입니다.
    """
    def __init__(self, state_manager_callback, workflows_file="obs_workflows.json"):
        """
        Args:
            state_manager_callback: EventStateManager의 이벤트 사실 처리 콜백 함수
            workflows_file: 워크플로우 설정 파일 경로
        """
        self.state_manager_callback = state_manager_callback
        self.workflows_file = workflows_file
        self.workflows = []
        self.load_workflows()
    
    def load_workflows(self):
        """워크플로우 로드"""
        try:
            if os.path.exists(self.workflows_file):
                with open(self.workflows_file, 'r', encoding='utf-8') as f:
                    self.workflows = json.load(f)
                print(f"✅ 워크플로우 로드 완료: {len(self.workflows)}개")
            else:
                self.workflows = []
                print("⚠️ 워크플로우 파일이 없습니다.")
        except Exception as e:
            print(f"❌ 워크플로우 로드 실패: {e}")
            self.workflows = []
    
    def trigger_event_fact(self, fact_type, event_data):
        """
        이벤트 사실(Event fact) 발생 시 워크플로우 조건 확인 후 상태 관리자에 전달
        
        워크플로우는 조건을 확인하고, 조건이 만족되면 이벤트 사실을 상태 관리자에 전달합니다.
        워크플로우는 절대 OBS를 제어하지 않습니다.
        
        Args:
            fact_type: 이벤트 사실 타입 (EEW_STARTED, EEW_UPDATED, DETAIL_RECEIVED 등)
            event_data: 이벤트 데이터 딕셔너리
        """
        # 워크플로우 재로드 (설정 변경 반영)
        self.load_workflows()
        
        # 워크플로우 조건 확인
        for workflow in self.workflows:
            if not workflow.get('enabled', True):
                continue
            
            trigger = workflow.get('trigger', {})
            trigger_type = trigger.get('type', '')
            
            # 트리거 타입이 일치하는지 확인
            if not self._matches_trigger_type(fact_type, trigger_type):
                continue
            
            # 조건 확인
            if self._check_conditions(trigger.get('conditions', {}), fact_type, event_data):
                print(f"✅ 워크플로우 조건 만족: {workflow.get('name', 'Unknown')} (이벤트: {fact_type})")
                # 이벤트 사실을 상태 관리자에 전달 (워크플로우는 OBS를 제어하지 않음)
                if self.state_manager_callback:
                    self.state_manager_callback(fact_type, event_data)
    
    def _matches_trigger_type(self, fact_type, trigger_type):
        """이벤트 사실 타입이 트리거 타입과 일치하는지 확인"""
        mapping = {
            'EEW_STARTED': '긴급지진속보 (EEW)',
            'EEW_UPDATED': '긴급지진속보 (EEW)',
            'EEW_WARNING': '긴급지진속보 (EEW)',
            'EEW_FINAL': '긴급지진속보 (EEW)',
            'EEW_CANCELED': '긴급지진속보 (EEW)',
            'DETAIL_RECEIVED': '지진상세정보',
            'SOKUHOU_RECEIVED': '지진상세정보',
            'EPICENTER_RECEIVED': '지진상세정보',
            'TSUNAMI_RECEIVED': '해일정보',
            'TSUNAMI_CANCELED': '해일정보'
        }
        return mapping.get(fact_type) == trigger_type
    
    def _check_conditions(self, conditions, fact_type, event_data):
        """워크플로우 조건 확인"""
        try:
            # EEW 조건 확인
            if fact_type.startswith('EEW_'):
                return self._check_eew_conditions(conditions, fact_type, event_data)
            # 지진상세정보 조건 확인
            elif fact_type in ['DETAIL_RECEIVED', 'SOKUHOU_RECEIVED', 'EPICENTER_RECEIVED']:
                return self._check_earthquake_info_conditions(conditions, fact_type, event_data)
            # 해일정보 조건 확인
            elif fact_type.startswith('TSUNAMI_'):
                return self._check_tsunami_conditions(conditions, fact_type, event_data)
            return False
        except Exception as e:
            print(f"❌ 조건 확인 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _check_eew_conditions(self, conditions, fact_type, event_data):
        """EEW 조건 확인"""
        announcement = conditions.get('announcement', {})
        
        # 신규 발표
        if fact_type == 'EEW_STARTED' and event_data.get('is_new', False):
            if announcement.get('新規発表 (신규 발표)', False):
                return True
        
        # 속보 발표
        if fact_type == 'EEW_UPDATED' and not event_data.get('is_new', False):
            if announcement.get('続報発表 (속보 발표)', False):
                return True
        
        # 최종보
        if fact_type == 'EEW_FINAL' and event_data.get('is_final', False):
            if announcement.get('最終報 (최종보)', False):
                return True
        
        # 취소보
        if fact_type == 'EEW_CANCELED' and event_data.get('is_canceled', False):
            if announcement.get('キャンセル報 (취소보)', False):
                return True
        
        # 경보 신규 발표
        if fact_type == 'EEW_WARNING' and event_data.get('is_warning', False) and event_data.get('is_new', False):
            if announcement.get('警報新規発表 (경보 신규 발표)', False):
                return True
        
        # 경보 속보 발표
        if fact_type == 'EEW_WARNING' and event_data.get('is_warning', False) and not event_data.get('is_new', False):
            if announcement.get('警報続報発表 (경보 속보 발표)', False):
                return True
        
        # 경보 취소
        if fact_type == 'EEW_CANCELED' and event_data.get('is_warning', False):
            if announcement.get('警報キャンセル (경보 취소)', False):
                return True
        
        return False
    
    def _check_earthquake_info_conditions(self, conditions, fact_type, event_data):
        """지진상세정보 조건 확인"""
        report_type = event_data.get('report_type', '')
        
        # 리포트 타입 확인
        if fact_type == 'DETAIL_RECEIVED' and report_type == 'detail':
            return True
        elif fact_type == 'SOKUHOU_RECEIVED' and report_type == 'sokuhou':
            return True
        elif fact_type == 'EPICENTER_RECEIVED' and report_type == 'epicenter':
            return True
        
        return False
    
    def _check_tsunami_conditions(self, conditions, fact_type, event_data):
        """해일정보 조건 확인"""
        if fact_type == 'TSUNAMI_RECEIVED' and not event_data.get('is_canceled', False):
            return True
        elif fact_type == 'TSUNAMI_CANCELED' and event_data.get('is_canceled', False):
            return True
        return False
    

class OBSController:
    """OBS 제어 클래스 - 워크플로우 기반 WebSocket 제어"""
    def __init__(self, use_websocket=True):
        self.use_websocket = use_websocket
        self.obs_ws = None
        self.current_scene = "일반"
        
        # OBS WebSocket 설정 (참고 파일에서)
        self.obs_host = "[2406:5900:7065:20c1:fdfe:48ce:2e0b:c7f7]"
        self.obs_port = 4455
        self.obs_password = "wdBUgokO09rBAceF"
        self.connected = False
        
        # 하단 글자 스크롤 소스 상태 추적 (토글용)
        self.scroll_source_states = {}  # {f"{scene_name}_{item_id}": visible}
        
        # 초기 연결 시도
        if self.use_websocket:
            self.connect_websocket()
    
    def connect_websocket(self):
        """OBS WebSocket 연결 (옵션)"""
        try:
            # obs-websocket-py 패키지 사용
            try:
                from obswebsocket import obsws
            except ImportError:
                # 대체 import 시도
                try:
                    from obs_websocket_py import obsws
                except ImportError:
                    raise ImportError("obswebsocket 모듈을 찾을 수 없습니다. 'pip install obs-websocket-py'를 실행하세요.")
            
            self.obs_ws = obsws(self.obs_host, self.obs_port, self.obs_password)
            self.obs_ws.connect()
            self.connected = True
            print("✅ OBS WebSocket 연결 성공")
            return True
        except ImportError as e:
            print(f"⚠️ obswebsocket 모듈이 설치되지 않음: {e}")
            print("   다음 명령어로 설치하세요: pip install obs-websocket-py")
            return False
        except Exception as e:
            print(f"⚠️ OBS WebSocket 연결 실패: {e}")
            return False
    
    def get_scene_list(self):
        """OBS 장면 목록 가져오기"""
        if not self.connected or not self.obs_ws:
            if not self.connect_websocket():
                return []
        
        try:
            try:
                from obswebsocket import requests as obs_requests
            except ImportError:
                from obs_websocket_py import requests as obs_requests
            
            response = self.obs_ws.call(obs_requests.GetSceneList())
            scenes = []
            if hasattr(response, 'datain') and 'scenes' in response.datain:
                for scene in response.datain['scenes']:
                    scenes.append({
                        'name': scene.get('sceneName', ''),
                        'index': scene.get('sceneIndex', 0)
                    })
            return scenes
        except Exception as e:
            print(f"❌ 장면 목록 가져오기 실패: {e}")
            return []
    
    def get_scene_items(self, scene_name):
        """특정 장면의 소스 아이템 목록 가져오기"""
        if not self.connected or not self.obs_ws:
            if not self.connect_websocket():
                return []
        
        try:
            try:
                from obswebsocket import requests as obs_requests
            except ImportError:
                from obs_websocket_py import requests as obs_requests
            
            response = self.obs_ws.call(obs_requests.GetSceneItemList(sceneName=scene_name))
            items = []
            if hasattr(response, 'datain') and 'sceneItems' in response.datain:
                for item in response.datain['sceneItems']:
                    items.append({
                        'itemId': item.get('sceneItemId', 0),
                        'sourceName': item.get('sourceName', ''),
                        'sourceType': item.get('sourceType', ''),
                        'inputKind': item.get('inputKind', ''),
                        'isGroup': item.get('isGroup', False),
                        'enabled': item.get('sceneItemEnabled', True)
                    })
            return items
        except Exception as e:
            print(f"❌ 장면 아이템 목록 가져오기 실패: {e}")
            return []
    
    def switch_scene(self, scene_name):
        """장면 전환"""
        if not self.connected or not self.obs_ws:
            if not self.connect_websocket():
                return
        
        try:
            try:
                from obswebsocket import requests as obs_requests
            except ImportError:
                from obs_websocket_py import requests as obs_requests
            request = obs_requests.SetCurrentProgramScene(sceneName=scene_name)
            self.obs_ws.call(request)
            self.current_scene = scene_name
            print(f"✅ OBS 장면 전환: {scene_name}")
        except Exception as e:
            print(f"❌ OBS 장면 전환 실패: {e}")
    
    def start_recording(self):
        """녹화 시작"""
        if not self.connected or not self.obs_ws:
            if not self.connect_websocket():
                return
        
        try:
            try:
                from obswebsocket import requests as obs_requests
            except ImportError:
                from obs_websocket_py import requests as obs_requests
            request = obs_requests.StartRecord()
            self.obs_ws.call(request)
            print("✅ OBS 녹화 시작")
        except Exception as e:
            print(f"❌ OBS 녹화 시작 실패: {e}")
    
    def stop_recording(self):
        """녹화 중지"""
        if not self.connected or not self.obs_ws:
            if not self.connect_websocket():
                return
        
        try:
            try:
                from obswebsocket import requests as obs_requests
            except ImportError:
                from obs_websocket_py import requests as obs_requests
            request = obs_requests.StopRecord()
            self.obs_ws.call(request)
            print("✅ OBS 녹화 중지")
        except Exception as e:
            print(f"❌ OBS 녹화 중지 실패: {e}")
    
    def save_replay_buffer(self):
        """버퍼 저장"""
        if not self.connected or not self.obs_ws:
            if not self.connect_websocket():
                return
        
        try:
            try:
                from obswebsocket import requests as obs_requests
            except ImportError:
                from obs_websocket_py import requests as obs_requests
            request = obs_requests.SaveReplayBuffer()
            self.obs_ws.call(request)
            print("✅ OBS 버퍼 저장")
        except Exception as e:
            print(f"❌ OBS 버퍼 저장 실패: {e}")
    
    def get_source_filter_list(self, source_name):
        """소스의 필터 목록 가져오기"""
        if not self.connected or not self.obs_ws:
            if not self.connect_websocket():
                return []
        
        try:
            try:
                from obswebsocket import requests as obs_requests
            except ImportError:
                from obs_websocket_py import requests as obs_requests
            response = self.obs_ws.call(obs_requests.GetSourceFilterList(sourceName=source_name))
            filters = []
            if hasattr(response, 'datain') and 'filters' in response.datain:
                for filter_data in response.datain['filters']:
                    filters.append({
                        'name': filter_data.get('filterName', ''),
                        'enabled': filter_data.get('filterEnabled', False),
                        'type': filter_data.get('filterType', '')
                    })
            return filters
        except Exception as e:
            print(f"❌ 필터 목록 가져오기 실패: {e}")
            return []
    
    def set_source_filter_enabled(self, source_name, filter_name, enabled):
        """소스 필터 활성화/비활성화"""
        if not self.connected or not self.obs_ws:
            if not self.connect_websocket():
                return
        
        try:
            try:
                from obswebsocket import requests as obs_requests
            except ImportError:
                from obs_websocket_py import requests as obs_requests
            request = obs_requests.SetSourceFilterEnabled(sourceName=source_name, filterName=filter_name, filterEnabled=enabled)
            self.obs_ws.call(request)
            print(f"✅ 필터 {'활성화' if enabled else '비활성화'}: {source_name}/{filter_name}")
        except Exception as e:
            print(f"❌ 필터 설정 실패: {e}")
    
    def handle_eew(self, is_new=False, is_warning=False, is_cancel=False, is_final=False):
        """긴급지진속보 처리 - 워크플로우 실행 엔진 사용"""
        # 하드코딩된 워크플로우 제거됨 - 워크플로우 실행 엔진 사용
        # EventStateManager에서 워크플로우를 실행하도록 변경됨
        pass
    
    def handle_earthquake_info(self, report_type, is_update_epicenter=False, has_tsunami=False, has_lpgm=False, no_eew_detail_only=False):
        """지진상세정보 처리 - 워크플로우 실행 엔진 사용"""
        # 하드코딩된 워크플로우 제거됨 - 워크플로우 실행 엔진 사용
        # EventStateManager에서 워크플로우를 실행하도록 변경됨
        pass
    
    def handle_tsunami_info(self):
        """해일정보 처리 - 워크플로우 실행 엔진 사용"""
        # 하드코딩된 워크플로우 제거됨 - 워크플로우 실행 엔진 사용
        # EventStateManager에서 워크플로우를 실행하도록 변경됨
        pass
    
    def _set_scene_item_visible(self, scene_name, item_id, visible):
        """장면 아이템 표시/숨김 설정"""
        try:
            try:
                from obswebsocket import requests as obs_requests
            except ImportError:
                from obs_websocket_py import requests as obs_requests
            request = obs_requests.SetSceneItemEnabled(
                sceneName=scene_name,
                sceneItemId=item_id,
                sceneItemEnabled=visible
            )
            self.obs_ws.call(request)
        except Exception as e:
            print(f"⚠️ 소스 아이템 {item_id} 표시/숨김 설정 실패: {e}")
    
    def _toggle_scroll_source(self, scene_name, item_id, auto_hide_seconds=None):
        """하단 글자 스크롤 소스 토글 표시/숨김 (30초 자동 숨김 지원)"""
        try:
            # 현재 상태 확인 (토글용)
            state_key = f"{scene_name}_{item_id}"
            current_visible = self.scroll_source_states.get(state_key, False)
            
            # 토글: 현재 숨김 상태면 표시, 표시 상태면 숨김
            new_visible = not current_visible
            
            # 소스 표시/숨김
            self._set_scene_item_visible(scene_name, item_id, new_visible)
            self.scroll_source_states[state_key] = new_visible
            
            # 자동 숨김 타이머 설정
            if auto_hide_seconds and new_visible:
                def hide_after_delay():
                    # 타이머 실행 시점에 다시 확인 (다른 곳에서 변경되었을 수 있음)
                    if self.scroll_source_states.get(state_key, False):
                        self._set_scene_item_visible(scene_name, item_id, False)
                        self.scroll_source_states[state_key] = False
                        print(f"⏰ 하단 글자 스크롤 소스 {item_id} 자동 숨김 ({auto_hide_seconds}초 경과)")
                
                threading.Timer(auto_hide_seconds, hide_after_delay).start()
                print(f"✅ 하단 글자 스크롤 소스 {item_id} {'표시' if new_visible else '숨김'} ({auto_hide_seconds}초 후 자동 숨김)")
            else:
                print(f"✅ 하단 글자 스크롤 소스 {item_id} {'표시' if new_visible else '숨김'}")
        except Exception as e:
            print(f"❌ 하단 글자 스크롤 소스 {item_id} 토글 실패: {e}")

# ------------------ DMDATA (일본) ------------------

DMDATA_CLIENT_ID = "CId.5GSaTia6xTTn6fJ9LHr4mXBfXrb1lYXw1w1iinHlg9dR"
DMDATA_CLIENT_SECRET = "CSt.PSsoDgt3RzKKgXOm2I-AUWG1DypVXQK8QMHBFsCT917j"
DMDATA_SCOPE = "socket.start telegram.get.earthquake eew.get.forecast"
DMDATA_SOCKET_CLASSIFICATIONS = ["telegram.earthquake", "eew.forecast"]
DMDATA_SOCKET_TYPES = [
    "VXSE42", "VXSE44", "VXSE45", "VZSE40", "VTSE41", "VTSE51", "VTSE52",
    "WEPA60", "VXSE51", "VXSE52", "VXSE53", "VXSE56", "VXSE60", "VXSE61",
    "VXSE62", "IXAC41", "VYSE50", "VYSE51", "VYSE52", "VYSE60"
]
DMDATA_APP_NAME = "EarthquakeAlert"

# ------------------ ExpTech (대만) ------------------

# WebSocket 방식 (실시간) - 여러 경로 시도
EXPTECH_WS_URLS = [
    "wss://exptech.com.tw/api",      # 원래 문서 URL (subscriptionService 방식)
    "wss://api.exptech.dev/api",     # api.exptech.dev
    "wss://api.exptech.dev/ws",      # /ws 경로 시도
    "wss://lb.exptech.dev/ws",       # 로드 밸런서 /ws 경로
    "wss://lb-1.exptech.dev/ws",
    "wss://lb-2.exptech.dev/ws",
    "wss://lb-3.exptech.dev/ws",
    "wss://lb-4.exptech.dev/ws",
]
EXPTECH_WS_SERVICES = ["eew-v1"]  # EEW 서비스 구독

# 폴백용 REST API (WebSocket 실패 시)
EXPTECH_LB_URLS = [
    "https://lb-1.exptech.dev",
    "https://lb-2.exptech.dev",
    "https://lb-3.exptech.dev",
    "https://lb-4.exptech.dev",
]
EXPTECH_EEW_ENDPOINT = "/api/v2/eq/eew"
EXPTECH_POLL_INTERVAL = 0.5  # WebSocket 실패 시 0.5초 폴링

# 일본 author 목록 (ExpTech에서 무시할 author)
JAPAN_AUTHORS = ["jma", "nied"]  # 일본 기상청, NIED

class DMDataHandler(QObject):
    eew_real_received = Signal(dict, str, bool)
    eew_test_received = Signal()
    final_info_received = Signal()
    connection_status_changed = Signal(str)

    def __init__(self, broadcast_window, detail_window):
        super().__init__()
        self.broadcast_window = broadcast_window
        self.detail_window = detail_window
        self.ws = None
        
        self.eew_real_received.connect(self.handle_eew_real_gui)
        self.eew_test_received.connect(self.handle_eew_test_gui)
        self.final_info_received.connect(self.handle_final_info_gui)
        self.connection_status_changed.connect(self.update_connection_status)

    def update_connection_status(self, status):
        """연결 상태 업데이트"""
        self.detail_window.connection_panel.update_dmdata_status(status)

    def on_message(self, ws, message):
        """웹소켓 메시지 처리"""
        try:
            data = json.loads(message)

            if data.get("type") == "ping":
                ping_id = data.get("pingId")
                ws.send(json.dumps({"type": "pong", "pingId": ping_id}))
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"🔄 [{timestamp}] DMDATA PING/PONG - ID: {ping_id}")
                self.connection_status_changed.emit("connected")
                return

            if data.get("type") == "data":
                head = data.get("head", {})
                body_data = data.get("body", {})

                print(f"📨 DMDATA 데이터 수신 - Type: {head.get('type')}")
                self.connection_status_changed.emit("active")

                # 전문 타입별 처리 및 터미널 표시
                telegram_type = head.get("type", "UNKNOWN")
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 전문명 매핑
                telegram_names = {
                    "VXSE42": "緊急地震速報配信テスト (긴급지진속보 테스트)",
                    "VXSE44": "緊急地震速報(予報) (긴급지진속보 예보)",
                    "VXSE45": "緊急地震速報(地震動予報) (긴급지진속보 경보)",
                    "VZSE40": "地震·津波に関するお知らせ (지진・해일 관련 안내)",
                    "VTSE41": "津波警報·注意報·予報 (해일 경보・주의보・예보)",
                    "VTSE51": "津波情報 (해일 정보)",
                    "VTSE52": "沖合の津波情報 (외해 해일 정보)",
                    "WEPA60": "国際津波関連情報(国内向け) (국제 해일 관련 정보)",
                    "VXSE51": "震度速報 (진도속보)",
                    "VXSE52": "震源に関する情報 (진원정보)",
                    "VXSE53": "震源·震度に関する情報 (진원・진도정보)",
                    "VXSE56": "地震の活動状況等に関する情報 (지진 활동 상황 등 관련 정보)",
                    "VXSE60": "地震回数に関する情報 (지진 횟수 관련 정보)",
                    "VXSE61": "顕著な地震の震源要素更新のお知らせ (현저한 지진의 진원 요소 갱신 안내)",
                    "VXSE62": "長周期地震動に関する観測情報 (장주기 지진동 관련 관측 정보)",
                    "IXAC41": "推計震度分布図作図用データ (추정 진도 분포도 작도용 데이터)",
                    "VYSE50": "南海トラフ地震臨時情報 (남해해구 지진 임시 정보)",
                    "VYSE51": "南海トラフ地震関連解説情報(定例外) (남해해구 지진 관련 해설 정보 정례 외)",
                    "VYSE52": "南海トラフ地震関連解説情報(定例) (남해해구 지진 관련 해설 정보 정례)",
                    "VYSE60": "北海道·三陸沖後発地震注意情報 (홋카이도・산리쿠 해역 후발 지진 주의 정보)"
                }
                
                telegram_name = telegram_names.get(telegram_type, f"알 수 없는 전문 ({telegram_type})")
                
                # 터미널에 전문 수신 표시
                print(f"\n{'='*80}")
                print(f"📨 [{timestamp}] DMDATA 전문 수신")
                print(f"   코드: {telegram_type}")
                print(f"   전문명: {telegram_name}")
                print(f"{'='*80}\n")
                
                # 전문 타입별 처리
                if telegram_type == "VXSE45":
                    print("🔥 VXSE45 (실제 긴급지진속보 - 경보) 처리 시작")
                    self.process_eew_real(head, body_data)
                elif telegram_type == "VXSE44":
                    print("🔥 VXSE44 (실제 긴급지진속보 - 예보) 처리 시작")
                    # VXSE44 (예보)는 VXSE45 (경보)와 동일한 구조로 처리
                    # 매뉴얼 기준: 緊急地震（警報）区分은 緊急地震（予報）区分에 포함
                    self.process_eew_real(head, body_data)
                elif telegram_type == "VXSE42":
                    print("🧪 VXSE42 (테스트 긴급지진속보) 처리 시작 - 무시됨")
                    self.process_eew_test(head, body_data)
                elif telegram_type == "VXSE51":
                    print("📊 VXSE51 (진도속보) 처리 시작")
                    self.process_earthquake_info(head, body_data, "sokuhou")
                elif telegram_type == "VXSE52":
                    print("📍 VXSE52 (진원정보) 처리 시작")
                    self.process_earthquake_info(head, body_data, "epicenter")
                elif telegram_type == "VXSE53":
                    print("📋 VXSE53 (진원진도정보) 처리 시작")
                    self.process_earthquake_info(head, body_data, "detail")
                elif telegram_type == "VTSE41":
                    print("🌊 VTSE41 (해일 경보・주의보・예보) 처리 시작")
                    self.process_tsunami_info(head, body_data)
                elif telegram_type == "VTSE51":
                    print("🌊 VTSE51 (해일 정보) 처리 시작")
                    # VTSE51은 해일 정보 (VTSE41과 다른 구조일 수 있음)
                    self.process_tsunami_info(head, body_data)
                elif telegram_type == "VTSE52":
                    print("🌊 VTSE52 (외해 해일 정보) 처리 시작")
                    # VTSE52는 외해 해일 정보
                    self.process_tsunami_info(head, body_data)
                elif telegram_type == "VZSE40":
                    print("ℹ️ VZSE40 (지진・해일 관련 안내) 처리 시작")
                    # 안내 정보는 로그만 출력
                    print(f"   안내 내용: {json.dumps(body_data, ensure_ascii=False, indent=2)[:200]}...")
                elif telegram_type == "WEPA60":
                    print("🌊 WEPA60 (국제 해일 관련 정보) 처리 시작")
                    # 국제 해일 정보는 해일정보로 처리
                    self.process_tsunami_info(head, body_data)
                elif telegram_type in ["VXSE56", "VXSE60", "VXSE61", "VXSE62"]:
                    print(f"📋 {telegram_type} (지진 정보) 처리 시작")
                    # 지진 정보는 지진상세정보로 처리
                    self.process_earthquake_info(head, body_data, "info")
                elif telegram_type == "IXAC41":
                    print("📊 IXAC41 (추정 진도 분포도 작도용 데이터) 처리 시작")
                    # 진도 분포 데이터는 로그만 출력
                    print(f"   데이터 타입: Binary 데이터 (처리 생략)")
                elif telegram_type in ["VYSE50", "VYSE51", "VYSE52", "VYSE60"]:
                    print(f"📋 {telegram_type} (남해해구/후발 지진 정보) 처리 시작")
                    # 남해해구 지진 정보는 로그만 출력 (필요시 처리 로직 추가)
                    print(f"   정보 내용: {json.dumps(body_data, ensure_ascii=False, indent=2)[:200]}...")
                else:
                    print(f"⚠️ 미처리 전문 타입: {telegram_type}")
                    print(f"   전문명: {telegram_name}")
                    print(f"   Head: {json.dumps(head, ensure_ascii=False, indent=2)[:200]}...")
        except Exception as e:
            print(f"❌ 메시지 처리 오류: {e}")
            import traceback
            traceback.print_exc()

    def get_access_token(self):
        """DMDATA API 액세스 토큰 발급"""
        try:
            self.connection_status_changed.emit("connecting")
            url = "https://manager.dmdata.jp/account/oauth2/v1/token"
            data = {
                "grant_type": "client_credentials",
                "client_id": DMDATA_CLIENT_ID,
                "client_secret": DMDATA_CLIENT_SECRET,
                "scope": DMDATA_SCOPE
            }
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                print("✅ DMDATA 인증 성공")
                return response.json()["access_token"]
            print(f"❌ 토큰 발급 실패: {response.status_code}")
            self.connection_status_changed.emit("disconnected")
            return None
        except Exception as e:
            print(f"❌ 토큰 발급 오류: {e}")
            self.connection_status_changed.emit("disconnected")
            return None

    def start_socket(self, access_token):
        """DMDATA 소켓 세션 시작"""
        try:
            url = "https://api.dmdata.jp/v2/socket"
            headers = {"Authorization": f"Bearer {access_token}"}
            body = {
                "classifications": DMDATA_SOCKET_CLASSIFICATIONS,
                "types": DMDATA_SOCKET_TYPES,
                "test": "including",
                "appName": DMDATA_APP_NAME,
                "formatMode": "json"
            }
            response = requests.post(url, headers=headers, json=body, timeout=10)
            if response.status_code == 200:
                print("✅ 소켓 시작 성공")
                return response.json()
            print(f"❌ 소켓 시작 실패: {response.status_code}")
            self.connection_status_changed.emit("disconnected")
            return None
        except Exception as e:
            print(f"❌ 소켓 시작 오류: {e}")
            self.connection_status_changed.emit("disconnected")
            return None

    def handle_eew_real_gui(self, earthquake_data, event_id, is_update):
        """메인 스레드에서 실제 EEW GUI 처리"""
        try:
            print(f"🎯 GUI 핸들러 호출: {event_id}, {is_update}")
            
            info_text = earthquake_data.get('display_text', '지진 정보')
            serial_no = earthquake_data.get('serial_no')
            is_warning = earthquake_data.get('is_warning', False)
            is_canceled = earthquake_data.get('is_canceled', False)
            source = earthquake_data.get('source', 'DMDATA')
            is_final = earthquake_data.get('is_final', False)
            final_serial = earthquake_data.get('final_serial')
            
            # 이벤트 상태 관리자에 긴급지진속보 처리
            state_manager = self.detail_window.get_event_state_manager()
            state_manager.handle_eew(event_id, serial_no, is_final, is_warning, is_canceled, source)
            # Signal을 통해 메인 스레드에서 UI 업데이트
            self.detail_window.update_obs_status_signal.emit()
            
            self.broadcast_window.start_eew_alert(
                info_text, event_id, serial_no, is_warning, is_canceled, is_update, source,
                is_final=is_final, final_serial=final_serial, author=None
            )
            
            # Signal을 통해 메인 스레드에서 UI 업데이트
            self.detail_window.update_earthquake_info_signal.emit(earthquake_data, event_id)
            
            source_display = "대만" if source == "EXPTECH" else "일본"
            # 용어 선택
            alert_name = "긴급지진속보"  # DMDATA 기본값
            if is_canceled:
                status_text = f"[{source_display}] {alert_name} 취소 (ID: {event_id})"
                alert_type = "canceled"
            elif is_warning:
                status_text = f"[{source_display}] {alert_name} 경보 발령 중 (ID: {event_id})"
                alert_type = "warning"
            else:
                status_text = f"[{source_display}] {alert_name} 예보 발령 중 (ID: {event_id})"
                alert_type = "normal"
                
            self.detail_window.update_status(status_text, alert_type)
            
        except Exception as e:
            print(f"❌ GUI 핸들러 오류: {e}")
            import traceback
            traceback.print_exc()
        
    def handle_eew_test_gui(self):
        """메인 스레드에서 테스트 EEW GUI 처리"""
        print(f"🧪 테스트 GUI 핸들러 호출 - 무시됨")
        
    def handle_final_info_gui(self):
        """메인 스레드에서 최종보 처리"""
        print(f"📚 최종보 GUI 핸들러 호출")
        self.broadcast_window.schedule_final_return()
        self.detail_window.update_status("최종보 수신 - 3분 후 대기중으로 복귀", "normal")

    def process_eew_real(self, head, body):
        """
        실제 긴급지진속보 처리 (VXSE45)
        
        DMDATA 매뉴얼 참고: https://dmdata.jp/docs/manual/earthquake/
        VXSE45 전문 구조:
        - eventId: 이벤트 ID
        - serialNo: 시리얼 번호
        - body.isWarning: 경보 여부 (true=경보, false=예보)
        - body.isCanceled: 취소 여부
        - body.isLastInfo: 최종보 여부
        - body.earthquake: 지진 정보 (hypocenter, magnitude 등)
        - body.intensity: 진도 정보
        """
        try:
            print(f"📋 [VXSE45] 실제 EEW 데이터 수신")

            processed_body = body
            if isinstance(body, str):
                try:
                    compressed_data = base64.b64decode(body)
                    decompressed_data = gzip.decompress(compressed_data)
                    processed_body = json.loads(decompressed_data.decode('utf-8'))
                    print(f"✅ 압축 해제 성공")
                except Exception as decode_error:
                    print(f"❌ BODY 압축 해제 실패: {decode_error}")
                    processed_body = {}

            if not isinstance(processed_body, dict):
                processed_body = {}

            event_id = processed_body.get("eventId", head.get("eventId", "UNKNOWN"))
            serial_no = processed_body.get("serialNo", "-")
            body_main = processed_body.get("body", {})
            
            # 구조 로깅 (디버깅용)
            print(f"   - Event ID: {event_id}, Serial No: {serial_no}")
            print(f"   - Body 구조 키: {list(body_main.keys())}")

            is_warning = body_main.get("isWarning", False)
            is_canceled = body_main.get("isCanceled", False)
            is_last_info = body_main.get("isLastInfo", False)

            eq = body_main.get("earthquake", {})
            hypocenter = eq.get("hypocenter", {})
            magnitude = eq.get("magnitude", {})
            intensity = body_main.get("intensity", {})

            area_code = hypocenter.get("code", "")
            area_name_original = hypocenter.get("name", "미상")
            area_name = epicenter_translator.translate(area_code, area_name_original)

            mag_value = magnitude.get("value", "미상")
            depth_value = hypocenter.get("depth", {}).get("value", "미상")

            forecast_max = intensity.get("forecastMaxInt", {})
            max_int_from = forecast_max.get("from")
            max_int_to = forecast_max.get("to")
            if max_int_from and max_int_to:
                if max_int_to == "over":
                    max_intensity = f"{max_int_from}정도 이상"
                else:
                    max_intensity = f"{max_int_from}"
            else:
                max_intensity = "미상"

            forecast_lg = intensity.get("forecastMaxLgInt", {})
            lg_from = forecast_lg.get("from")
            lg_to = forecast_lg.get("to")
            if lg_from and lg_to:
                if lg_to == "over":
                    max_lg_intensity = f"{lg_from}정도 이상"
                else:
                    max_lg_intensity = f"{lg_from}"
            else:
                max_lg_intensity = "미상"

            display_text = (
                f"{area_name}에서 지진, "
                f"최대예측진도 {max_intensity}, "
                f"규모 {mag_value}, "
                f"깊이 {depth_value}km, "
                f"최대예측장주기지진동계급 {max_lg_intensity}"
            )

            earthquake_data = {
                "event_id": event_id,
                "serial_no": serial_no,
                "origin_time": eq.get("originTime", "-"),
                "epicenter": area_name,
                "magnitude": mag_value,
                "depth": depth_value,
                "max_intensity": max_intensity,
                "max_lg_intensity": max_lg_intensity,
                "is_warning": is_warning,
                "is_canceled": is_canceled,
                "display_text": display_text,
                "source": "DMDATA",
                "is_final": is_last_info,
                "final_serial": serial_no if is_last_info else None
            }

            is_update = (event_id in self.broadcast_window.active_earthquakes)

            self.eew_real_received.emit(earthquake_data, event_id, is_update)

            if is_last_info:
                print(f"📚 최종보 수신됨 (시리얼: {serial_no})")
                self.final_info_received.emit()

        except Exception as e:
            print(f"❌ 실제 EEW 처리 오류: {e}")
            import traceback
            traceback.print_exc()

    def process_eew_test(self, head, body):
        """테스트 긴급지진속보 처리 (VXSE42)"""
        try:
            print(f"📋 테스트 EEW 데이터 수신 (VXSE42) - 무시됨")
        except Exception as e:
            print(f"❌ 테스트 EEW 처리 오류: {e}")
    
    def process_earthquake_info(self, head, body, report_type):
        """
        지진상세정보 처리 (VXSE51, VXSE52, VXSE53)
        
        DMDATA 매뉴얼 참고: https://dmdata.jp/docs/manual/
        - VXSE51: 震度速報 (진도속보)
        - VXSE52: 震源に関する情報 (진원정보)
        - VXSE53: 震源・震度に関する情報 (진원진도정보)
        
        전문 구조:
        - body.earthquakes[]: 지진 정보 배열
        - body.tsunami: 해일정보 (있는 경우)
        - body.lpgm: 장주기지진동 정보 (있는 경우)
        """
        try:
            print(f"📋 [{head.get('type', 'UNKNOWN')}] 지진상세정보 처리 시작 (타입: {report_type})")
            processed_body = body
            if isinstance(body, str):
                try:
                    compressed_data = base64.b64decode(body)
                    decompressed_data = gzip.decompress(compressed_data)
                    processed_body = json.loads(decompressed_data.decode('utf-8'))
                except Exception as decode_error:
                    print(f"❌ BODY 압축 해제 실패: {decode_error}")
                    processed_body = {}
            
            if not isinstance(processed_body, dict):
                processed_body = {}
            
            # Event ID 추출 (JSON head의 최상위 레벨에 있음)
            # processed_body는 이미 JSON 파싱된 데이터 (head + body 포함)
            event_id = (
                processed_body.get("eventId") or
                head.get("eventId") or
                f"EQ_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            
            print(f"📊 지진상세정보 수신: {report_type}, Event ID: {event_id}")
            
            # 갱신 여부 확인 (같은 event_id로 이미 정보가 있는 경우)
            state_manager = self.detail_window.get_event_state_manager()
            is_update = event_id in state_manager.earthquake_states
            if is_update:
                existing_state = state_manager.earthquake_states[event_id]
                # 진원정보 갱신 여부 확인
                is_update_epicenter = (
                    report_type == "epicenter" and 
                    existing_state.get("report_epicenter", False)
                )
            else:
                is_update_epicenter = False
            
            # 해일정보 포함 여부 확인 (body에서 확인)
            body_main = processed_body.get("body", {})
            
            # 상세 로깅
            print(f"   - Body 구조 키: {list(body_main.keys())}")
            
            # 해일정보 확인
            tsunami = body_main.get("tsunami", {})
            has_tsunami = bool(tsunami) and len(tsunami.get("forecasts", [])) > 0
            if tsunami:
                forecasts = tsunami.get("forecasts", [])
                print(f"   - 해일정보 포함: {has_tsunami} (forecasts 개수: {len(forecasts)})")
                if forecasts:
                    for i, forecast in enumerate(forecasts[:2]):  # 최대 2개만 출력
                        grade = forecast.get("grade", "N/A")
                        print(f"     - Forecast[{i}]: Grade={grade}")
            else:
                print(f"   - 해일정보 없음")
            
            # 장주기지진동 정보 포함 여부 확인
            has_lpgm = "lpgm" in body_main or "longPeriodGroundMotion" in body_main
            if has_lpgm:
                print(f"   - 장주기지진동 정보 포함: {has_lpgm}")
            
            # 이벤트 상태 관리자에 상세정보 처리
            state_manager.handle_report(
                event_id, 
                report_type, 
                "DMDATA",
                is_update_epicenter=is_update_epicenter,
                has_tsunami=has_tsunami,
                has_lpgm=has_lpgm
            )
            # Signal을 통해 메인 스레드에서 UI 업데이트
            self.detail_window.update_obs_status_signal.emit()
            
        except Exception as e:
            print(f"❌ 지진상세정보 처리 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def process_tsunami_info(self, head, body):
        """
        해일정보 처리 (VTSE41)
        
        DMDATA 매뉴얼 참고: https://dmdata.jp/docs/manual/tsunami/
        VTSE41 전문 구조:
        - body.earthquakes[]: 관련 지진 정보 배열
        - body.tsunami.forecasts[]: 해일 예보 배열
          - 각 forecast는 지역별 해일 경보/주의보/예보 정보 포함
          - forecasts가 비어있으면 모든 해일 경보/주의보/예보가 해제된 상태
        """
        try:
            processed_body = body
            if isinstance(body, str):
                try:
                    compressed_data = base64.b64decode(body)
                    decompressed_data = gzip.decompress(compressed_data)
                    processed_body = json.loads(decompressed_data.decode('utf-8'))
                    print(f"✅ 해일정보 압축 해제 성공")
                except Exception as decode_error:
                    print(f"❌ BODY 압축 해제 실패: {decode_error}")
                    processed_body = {}
            
            if not isinstance(processed_body, dict):
                processed_body = {}
            
            # 전체 구조 로깅 (디버깅용)
            print(f"🌊 [VTSE41] 해일정보 전문 수신")
            print(f"   - Head: {json.dumps(head, ensure_ascii=False, indent=2)[:200]}...")
            print(f"   - Body 구조 키: {list(processed_body.keys())}")
            
            # Event ID 추출
            body_main = processed_body.get("body", {})
            earthquakes = body_main.get("earthquakes", [])
            
            # 해일정보는 관련 지진의 Event ID 사용
            if earthquakes and len(earthquakes) > 0:
                event_id = earthquakes[0].get("eventId") or head.get("eventId") or f"TS_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                print(f"   - 관련 지진 Event ID: {earthquakes[0].get('eventId')}")
            else:
                event_id = head.get("eventId") or f"TS_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                print(f"   - Head에서 Event ID 추출: {head.get('eventId')}")
            
            # 해일정보 해제 여부 확인
            # DMDATA VTSE41 전문 구조 (매뉴얼 기준):
            # - body.tsunami.forecasts: 해일 예보 배열
            #   - 각 forecast는 지역별 해일 경보/주의보/예보 정보
            #   - forecasts가 비어있으면 모든 해일 경보/주의보/예보가 해제된 상태
            tsunami = body_main.get("tsunami", {})
            forecasts = tsunami.get("forecasts", [])
            
            # 해일정보 발표/해제 판단
            # 매뉴얼 기준: forecasts 배열이 비어있으면 해제, 있으면 발표
            is_canceled = len(forecasts) == 0
            
            # 상세 로깅
            print(f"   - Event ID: {event_id}")
            print(f"   - Tsunami 객체 키: {list(tsunami.keys())}")
            print(f"   - Forecasts 개수: {len(forecasts)}")
            if forecasts:
                print(f"   - 첫 번째 예보 구조: {json.dumps(forecasts[0], ensure_ascii=False, indent=2)[:300]}...")
                # 각 예보의 grade 확인 (Major Tsunami Warning, Tsunami Warning, Tsunami Advisory 등)
                for i, forecast in enumerate(forecasts[:3]):  # 최대 3개만 출력
                    grade = forecast.get("grade", "N/A")
                    area = forecast.get("area", {}).get("name", "N/A")
                    print(f"   - Forecast[{i}]: Grade={grade}, Area={area}")
            else:
                print(f"   - ⚠️ Forecasts 배열이 비어있음 → 해일정보 해제로 판단")
            
            print(f"   - 최종 판단: {'해제' if is_canceled else '발표'}")
            
            # 이벤트 상태 관리자에 해일정보 처리
            state_manager = self.detail_window.get_event_state_manager()
            state_manager.handle_tsunami(event_id, is_canceled, "DMDATA")
            # Signal을 통해 메인 스레드에서 UI 업데이트
            self.detail_window.update_obs_status_signal.emit()
            
        except Exception as e:
            print(f"❌ 해일정보 처리 오류: {e}")
            import traceback
            traceback.print_exc()

    def connect_websocket(self, ws_url, token):
        try:
            headers = [f"X-DMData-Token: {token}"]
            self.ws = websocket.WebSocketApp(
                ws_url,
                header=headers,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            print("🔌 웹소켓 연결 시도 중...")
            self.ws.run_forever()
        except Exception as e:
            print(f"❌ 웹소켓 연결 오류: {e}")
            self.connection_status_changed.emit("disconnected")

    def on_open(self, ws):
        print("✅ DMDATA 웹소켓 연결 성공")
        self.connection_status_changed.emit("connected")

    def on_error(self, ws, error):
        print(f"❌ 웹소켓 오류: {error}")
        self.connection_status_changed.emit("disconnected")

    def on_close(self, ws, close_status_code, close_msg):
        print(f"🔌 웹소켓 연결 종료: {close_status_code}, {close_msg}")
        self.connection_status_changed.emit("disconnected")

    def start(self):
        """DMDATA 연결 시작"""
        print("🚀 DMDATA 연결 시작")
        token = self.get_access_token()
        if not token:
            print("❌ 토큰 발급 실패")
            return

        socket_info = self.start_socket(token)
        if not socket_info:
            print("❌ 소켓 시작 실패")
            return

        ws_url = socket_info["websocket"]["url"]
        ticket = socket_info["ticket"]
        print(f"🔗 웹소켓 URL: {ws_url}")
        self.connect_websocket(ws_url, ticket)


class ExpTechHandler(QObject):
    """ExpTech API 핸들러 (대만 지진 정보) - WebSocket 실시간 방식"""
    eew_received = Signal(dict, str, bool)
    connection_status_changed = Signal(str)
    
    def __init__(self, broadcast_window, detail_window):
        super().__init__()
        self.broadcast_window = broadcast_window
        self.detail_window = detail_window
        self.current_event_id = None
        self.is_running = False
        self.last_eew_time = 0
        self.ws = None
        self.use_websocket = True  # WebSocket 사용 여부
        self.uuid = None  # WebSocket UUID
        # 서비스 토큰 (발급받은 토큰 사용)
        self.service_token = "4a43ba98449c7462f34485431da56c08e7fa6b25534eec14df565d3964953265"
        
        self.eew_received.connect(self.handle_eew_gui)
        self.connection_status_changed.connect(self.update_connection_status)

    def update_connection_status(self, status):
        """연결 상태 업데이트"""
        self.detail_window.connection_panel.update_exptech_status(status)

    def get_uuid(self):
        """UUID 생성 또는 가져오기"""
        import uuid
        if not self.uuid:
            # UUID 생성 (한 번만 생성하고 계속 사용)
            self.uuid = str(uuid.uuid4())
            print(f"🆔 ExpTech UUID 생성: {self.uuid}")
        return self.uuid
    
    def get_service_token(self):
        """서비스 토큰 가져오기 (옵션 - 로그인 정보가 있으면 사용)"""
        # 현재는 토큰 없이 시도 (필요시 나중에 로그인 기능 추가 가능)
        # TREM-ExpTech-Plugin처럼 로그인 후 서비스 토큰을 받을 수 있음
        # 하지만 기본적으로는 토큰 없이도 작동할 수 있음
        return self.service_token if self.service_token else ""
    
    def fetch_eew_data(self):
        """ExpTech EEW 데이터 가져오기 (REST API 폴백) - 로드 밸런서 사용"""
        import random
        try:
            # 로드 밸런서 중 랜덤 선택
            base_url = random.choice(EXPTECH_LB_URLS)
            url = base_url + EXPTECH_EEW_ENDPOINT
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data:
                    self.connection_status_changed.emit("active")
                else:
                    self.connection_status_changed.emit("connected")
                return data
            else:
                print(f"⚠️ ExpTech API 응답 오류: {response.status_code}")
                self.connection_status_changed.emit("disconnected")
                return None
        except Exception as e:
            print(f"❌ ExpTech API 요청 오류: {e}")
            self.connection_status_changed.emit("disconnected")
            return None
    
    def process_eew(self, data):
        """ExpTech EEW 처리 - 여러 지진 지원 및 author 필터링"""
        try:
            print("🔥 ExpTech EEW 처리 시작")
            
            if not isinstance(data, list):
                if isinstance(data, dict):
                    data = [data]
                else:
                    return
            
            # 여러 지진 처리
            for eq_data in data:
                if not isinstance(eq_data, dict):
                    continue
                
                # author 확인
                author = eq_data.get("author", "").lower()
                
                # 일본 author 필터링 (DMDATA가 더 정확하므로 무시)
                if author in JAPAN_AUTHORS:
                    print(f"🚫 일본 author ({author}) 필터링 - DMDATA 사용")
                    continue
                
                event_id = str(eq_data.get("id", eq_data.get("eq", {}).get("id", "UNKNOWN")))
                if event_id == "UNKNOWN":
                    continue
                
                serial = eq_data.get("serial", eq_data.get("serial_no", 1))
                is_final = eq_data.get("final", False)
                
                eq_info = eq_data.get("eq", eq_data.get("earthquake", {}))
                epicenter = eq_info.get("loc", eq_info.get("location", "미상"))
                magnitude = eq_info.get("mag", eq_info.get("magnitude", eq_info.get("mag", "미상")))
                depth = eq_info.get("depth", "미상")
                
                origin_time = eq_info.get("time", eq_data.get("time", "-"))
                
                max_intensity = eq_data.get("max", {})
                if isinstance(max_intensity, dict):
                    max_intensity = max_intensity.get("intensity", eq_data.get("max_intensity", "미상"))
                else:
                    max_intensity = eq_data.get("max_intensity", "미상")
                
                # status 확인 (0=예보, 1=경보, 3=취소)
                status = eq_data.get("status", 0)
                is_canceled = (status == 3 or eq_data.get("cancel", False))
                is_warning = (status == 1)
                
                # author 표시용 이름
                author_names = {
                    "cwa": "대만 중앙기상국",
                    "trem": "TREM",
                    "jma": "일본 기상청",
                    "nied": "NIED",
                    "kma": "한국 기상청",
                    "scdzj": "쓰촨성 지진국",
                    "fjdzj": "푸젠성 지진국"
                }
                author_display = author_names.get(author, author.upper() if author else "알 수 없음")
                
                display_text = (
                    f"{epicenter}에서 지진, "
                    f"규모 {magnitude}, "
                    f"깊이 {depth}km, "
                    f"최대예측진도 {max_intensity} ({author_display})"
                )
                
                earthquake_data = {
                    "event_id": event_id,
                    "serial_no": str(serial),
                    "origin_time": origin_time,
                    "epicenter": epicenter,
                    "magnitude": magnitude,
                    "depth": depth,
                    "max_intensity": max_intensity,
                    "max_lg_intensity": "-",
                    "is_warning": is_warning,
                    "is_canceled": is_canceled,
                    "display_text": display_text,
                    "source": "EXPTECH",
                    "author": author,
                    "is_final": is_final,
                    "final_serial": str(serial) if is_final else None
                }
                
                is_update = (event_id in self.broadcast_window.active_earthquakes)
                
                self.eew_received.emit(earthquake_data, event_id, is_update)
            
        except Exception as e:
            print(f"❌ ExpTech EEW 처리 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def handle_eew_gui(self, earthquake_data, event_id, is_update):
        """메인 스레드에서 EEW GUI 처리"""
        try:
            print(f"🎯 ExpTech GUI 핸들러 호출: {event_id}, {is_update}")
            
            info_text = earthquake_data.get('display_text', '지진 정보')
            serial_no = earthquake_data.get('serial_no')
            is_warning = earthquake_data.get('is_warning', False)
            is_canceled = earthquake_data.get('is_canceled', False)
            is_final = earthquake_data.get('is_final', False)
            final_serial = earthquake_data.get('final_serial')
            author = earthquake_data.get('author')
            
            # 이벤트 상태 관리자에 긴급지진속보 처리
            state_manager = self.detail_window.get_event_state_manager()
            state_manager.handle_eew(event_id, serial_no, is_final, is_warning, is_canceled, "EXPTECH")
            # Signal을 통해 메인 스레드에서 UI 업데이트
            self.detail_window.update_obs_status_signal.emit()
            
            self.broadcast_window.start_eew_alert(
                info_text, event_id, serial_no, is_warning, is_canceled, is_update, "EXPTECH",
                is_final=is_final, final_serial=final_serial, author=author
            )
            
            # Signal을 통해 메인 스레드에서 UI 업데이트
            self.detail_window.update_earthquake_info_signal.emit(earthquake_data, event_id)
            
            author_display = ""
            if author:
                author_names = {
                    "cwa": "대만 중앙기상국",
                    "trem": "TREM",
                    "kma": "한국 기상청",
                    "scdzj": "쓰촨성 지진국",
                    "fjdzj": "푸젠성 지진국"
                }
                author_display = f" [{author_names.get(author, author.upper())}]"
            
            # 용어 선택 (대만: 강진즉시경보, 한국: 지진조기경보)
            if author == "kma":
                alert_name = "지진조기경보"
            else:
                alert_name = "강진즉시경보"
            
            if is_canceled:
                status_text = f"[대만{author_display}] {alert_name} 취소 (ID: {event_id})"
                alert_type = "canceled"
            elif is_warning:
                status_text = f"[대만{author_display}] {alert_name} 경보 발령 중 (ID: {event_id})"
                alert_type = "warning"
            else:
                status_text = f"[대만{author_display}] {alert_name} 예보 발령 중 (ID: {event_id})"
                alert_type = "normal"
                
            self.detail_window.update_status(status_text, alert_type)
            
        except Exception as e:
            print(f"❌ ExpTech GUI 핸들러 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def on_ws_message(self, ws, message):
        """WebSocket 메시지 처리"""
        try:
            data = json.loads(message)
            print(f"📨 ExpTech WebSocket 메시지 수신: {type(data)}")
            
            # EEW 데이터 처리
            if isinstance(data, dict):
                # 단일 EEW 데이터
                self.connection_status_changed.emit("active")
                self.process_eew([data])
            elif isinstance(data, list):
                # 여러 EEW 데이터
                if len(data) > 0:
                    self.connection_status_changed.emit("active")
                    self.process_eew(data)
            else:
                print(f"ℹ️ 알 수 없는 메시지 타입: {type(data)}")
                
        except Exception as e:
            print(f"❌ WebSocket 메시지 처리 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def on_ws_open(self, ws):
        """WebSocket 연결 성공"""
        print("✅ ExpTech WebSocket 연결 성공")
        self.connection_status_changed.emit("connected")
        
        # 구독 메시지 전송
        uuid_str = self.get_uuid()
        service_token = self.get_service_token()
        subscribe_msg = {
            "uuid": uuid_str,
            "function": "subscriptionService",
            "value": EXPTECH_WS_SERVICES,
            "key": service_token  # 서비스 토큰 사용 (없으면 빈 문자열)
        }
        ws.send(json.dumps(subscribe_msg))
        print(f"📤 구독 메시지 전송: {subscribe_msg}")
    
    def on_ws_error(self, ws, error):
        """WebSocket 오류"""
        print(f"❌ ExpTech WebSocket 오류: {error}")
        self.connection_status_changed.emit("disconnected")
        # WebSocket 실패 시 폴링으로 전환
        if self.use_websocket:
            print("🔄 WebSocket 실패, 폴링 방식으로 전환")
            self.use_websocket = False
            if self.ws:
                self.ws.close()
            self.start_polling()
    
    def on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket 연결 종료"""
        print(f"🔌 ExpTech WebSocket 연결 종료: {close_status_code}, {close_msg}")
        self.connection_status_changed.emit("disconnected")
        # 재연결은 connect_websocket에서 처리 (무한 반복 방지)
    
    def connect_websocket(self):
        """WebSocket 연결 시도 - 여러 URL 순차 시도 (한 번만)"""
        import ssl
        import threading
        
        if not self.use_websocket:
            return
        
        self.connection_status_changed.emit("connecting")
        
        connection_success = threading.Event()
        ws_connected = threading.Event()
        current_try = [0]  # 현재 시도 중인 URL 인덱스
        
        def try_connect_url(ws_url, url_index):
            """특정 URL에 연결 시도"""
            try:
                print(f"🔌 ExpTech WebSocket 연결 시도 ({url_index + 1}/{len(EXPTECH_WS_URLS)}): {ws_url}")
                
                def on_open_wrapper(ws):
                    ws_connected.set()
                    connection_success.set()
                    self.on_ws_open(ws)
                
                def on_error_wrapper(ws, error):
                    error_str = str(error)
                    if not ws_connected.is_set():
                        # 연결 실패 시 다음 URL 시도
                        if "scheme https" in error_str or "404" in error_str or "521" in error_str:
                            print(f"⚠️ {ws_url}: 연결 실패")
                            connection_success.set()  # 다음 URL 시도를 위해 이벤트 설정
                        else:
                            self.on_ws_error(ws, error)
                
                def on_close_wrapper(ws, close_status_code, close_msg):
                    if not ws_connected.is_set():
                        # 연결 실패 시 다음 URL 시도
                        connection_success.set()
                    else:
                        self.on_ws_close(ws, close_status_code, close_msg)
                
                ws_app = websocket.WebSocketApp(
                    ws_url,
                    on_open=on_open_wrapper,
                    on_message=self.on_ws_message,
                    on_error=on_error_wrapper,
                    on_close=on_close_wrapper
                )
                
                # 연결 시도 (별도 스레드)
                ws_thread = threading.Thread(
                    target=lambda: ws_app.run_forever(
                        sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False},
                        ping_interval=30,
                        ping_timeout=3
                    ),
                    daemon=True
                )
                ws_thread.start()
                
                # 3초 대기
                connection_success.wait(timeout=3)
                
                if ws_connected.is_set():
                    # 연결 성공
                    self.ws = ws_app
                    return True
                else:
                    # 연결 실패 - WebSocket 종료
                    ws_app.close()
                    connection_success.clear()
                    return False
                    
            except Exception as e:
                error_str = str(e)
                print(f"❌ {ws_url} 연결 오류: {error_str}")
                connection_success.set()
                return False
        
        # 모든 URL을 순차적으로 시도
        for idx, ws_url in enumerate(EXPTECH_WS_URLS):
            if not self.use_websocket:
                break
                
            if try_connect_url(ws_url, idx):
                # 연결 성공
                print(f"✅ WebSocket 연결 성공: {ws_url}")
                return
        
        # 모든 URL 실패 시 폴링으로 전환
        print("🔄 모든 WebSocket URL 실패, 폴링 방식으로 전환")
        if self.use_websocket:
            self.use_websocket = False
            self.start_polling()
    
    def polling_loop(self):
        """폴링 루프 - 주기적으로 API 호출 (WebSocket 실패 시 폴백)"""
        print("🔄 ExpTech 폴링 시작 (폴백 모드)")
        self.connection_status_changed.emit("connecting")
        
        while self.is_running and not self.use_websocket:
            try:
                data = self.fetch_eew_data()
                if data:
                    # 리스트가 아니면 리스트로 변환
                    if not isinstance(data, list):
                        data = [data] if isinstance(data, dict) else []
                    
                    if len(data) > 0:
                        self.process_eew(data)
                
                time.sleep(EXPTECH_POLL_INTERVAL)
                
            except Exception as e:
                print(f"❌ ExpTech 폴링 오류: {e}")
                self.connection_status_changed.emit("disconnected")
                time.sleep(EXPTECH_POLL_INTERVAL)
    
    def start_polling(self):
        """폴링 시작 (별도 스레드)"""
        self.is_running = True
        polling_thread = threading.Thread(target=self.polling_loop, daemon=True)
        polling_thread.start()
    
    def start(self):
        """ExpTech 연결 시작 (WebSocket 우선, 실패 시 폴링)"""
        if self.use_websocket:
            print("🚀 ExpTech WebSocket 연결 시작")
            self.is_running = True
            ws_thread = threading.Thread(target=self.connect_websocket, daemon=True)
            ws_thread.start()
        else:
            print("🚀 ExpTech 폴링 시작")
            self.start_polling()
    
    def stop(self):
        """ExpTech 연결 중지"""
        print("🛑 ExpTech 연결 중지")
        self.is_running = False
        if self.ws:
            self.ws.close()
        self.connection_status_changed.emit("disconnected")


# ------------------ OBS 워크플로우 설정 ------------------

class OBSWorkflowSettingsWindow(QDialog):
    """이벤트 상태 변경 규칙 설정 창
    
    이 창은 OBS를 직접 제어하지 않습니다.
    이벤트를 감지하고 상태 플래그만 변경하는 규칙을 설정합니다.
    방송 화면은 시스템이 전체 상태를 종합하여 자동으로 결정합니다.
    """
    # Signal 정의 (스레드 안전한 UI 업데이트용)
    test_finished_signal = Signal()
    
    def __init__(self, obs_controller, event_state_manager, parent=None):
        super().__init__(parent)
        self.obs_controller = obs_controller
        self.event_state_manager = event_state_manager
        self.workflows = []  # 워크플로우 목록
        self.workflows_file = "obs_workflows.json"
        self.current_condition_widgets = {}  # 현재 조건 위젯 참조 저장
        self.test_running = False  # 테스트 실행 중 플래그
        self.test_stop_flag = False  # 테스트 중지 플래그
        
        # Signal 연결
        self.test_finished_signal.connect(self._on_test_finished)
        
        self.setWindowTitle("이벤트 상태 변경 규칙 설정")
        self.resize(1000, 700)
        
        # 다크 테마 스타일
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
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        
        # 상단: 규칙 목록
        top_layout = QHBoxLayout()
        
        # 왼쪽: 규칙 목록
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("이벤트 상태 변경 규칙 목록"))
        
        self.workflow_list = QListWidget()
        self.workflow_list.currentItemChanged.connect(self.on_workflow_selected)
        left_panel.addWidget(self.workflow_list)
        
        workflow_buttons = QHBoxLayout()
        add_workflow_btn = QPushButton("규칙 추가")
        add_workflow_btn.clicked.connect(self.add_workflow)
        remove_workflow_btn = QPushButton("규칙 삭제")
        remove_workflow_btn.clicked.connect(self.remove_workflow)
        workflow_buttons.addWidget(add_workflow_btn)
        workflow_buttons.addWidget(remove_workflow_btn)
        left_panel.addLayout(workflow_buttons)
        
        top_layout.addLayout(left_panel, 1)
        
        # 오른쪽: 규칙 편집
        right_panel = QVBoxLayout()
        
        # 규칙 이름
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("규칙 이름:"))
        self.workflow_name_edit = QLineEdit()
        self.workflow_name_edit.textChanged.connect(self.on_workflow_name_changed)
        name_layout.addWidget(self.workflow_name_edit)
        self.workflow_enabled_checkbox = QComboBox()
        self.workflow_enabled_checkbox.addItems(["활성화", "비활성화"])
        name_layout.addWidget(self.workflow_enabled_checkbox)
        
        # 테스트 버튼
        self.test_btn = QPushButton("상태 변경 테스트")
        self.test_btn.clicked.connect(self.test_workflow)
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5aaeff;
            }
            QPushButton:pressed {
                background-color: #3a8eef;
            }
        """)
        name_layout.addWidget(self.test_btn)
        
        right_panel.addLayout(name_layout)
        
        # 이벤트 감지 규칙 설정
        trigger_group = QGroupBox("이벤트 감지 규칙 (어떤 이벤트를 감지할지)")
        trigger_group.setFont(QFont("맑은 고딕", 11, QFont.Bold))
        trigger_layout = QVBoxLayout()
        
        self.trigger_type_combo = QComboBox()
        self.trigger_type_combo.addItems([
            "긴급지진속보 (EEW)",
            "지진상세정보",
            "해일정보",
            "모든 이벤트"
        ])
        self.trigger_type_combo.currentTextChanged.connect(self.on_trigger_type_changed)
        trigger_layout.addWidget(self.trigger_type_combo)
        
        # 이벤트 감지 세부 조건 (동적으로 변경됨)
        self.trigger_conditions_widget = QWidget()
        self.trigger_conditions_layout = QVBoxLayout()
        self.trigger_conditions_widget.setLayout(self.trigger_conditions_layout)
        trigger_layout.addWidget(self.trigger_conditions_widget)
        
        trigger_note = QLabel("※ 감지된 이벤트는 상태 플래그만 변경하며, 방송 화면을 직접 변경하지 않습니다.")
        trigger_note.setFont(QFont("맑은 고딕", 9))
        trigger_note.setStyleSheet("color: #888888; font-style: italic;")
        trigger_note.setWordWrap(True)
        trigger_layout.addWidget(trigger_note)
        
        trigger_group.setLayout(trigger_layout)
        right_panel.addWidget(trigger_group)
        
        # 상태 변경 규칙 설정
        action_group = QGroupBox("상태 변경 규칙 (감지된 이벤트에 따라 어떤 상태를 변경할지)")
        action_group.setFont(QFont("맑은 고딕", 11, QFont.Bold))
        action_layout = QVBoxLayout()
        
        self.action_list = QListWidget()
        self.action_list.setMaximumHeight(200)
        action_layout.addWidget(self.action_list)
        
        action_buttons = QHBoxLayout()
        add_action_btn = QPushButton("상태 변경 추가")
        add_action_btn.clicked.connect(self.add_action)
        remove_action_btn = QPushButton("상태 변경 삭제")
        remove_action_btn.clicked.connect(self.remove_action)
        action_buttons.addWidget(add_action_btn)
        action_buttons.addWidget(remove_action_btn)
        action_layout.addLayout(action_buttons)
        
        
        action_group.setLayout(action_layout)
        right_panel.addWidget(action_group)
        
        top_layout.addLayout(right_panel, 2)
        main_layout.addLayout(top_layout)
        
        # 하단: 저장/로드 버튼
        bottom_buttons = QHBoxLayout()
        load_btn = QPushButton("불러오기")
        load_btn.clicked.connect(self.load_workflows)
        save_btn = QPushButton("저장")
        save_btn.clicked.connect(self.save_workflows)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        bottom_buttons.addWidget(load_btn)
        bottom_buttons.addWidget(save_btn)
        bottom_buttons.addStretch()
        bottom_buttons.addWidget(close_btn)
        main_layout.addLayout(bottom_buttons)
        
        self.setLayout(main_layout)
        
        # OBS 장면/소스 정보 로드
        self.load_obs_info()
        
        # 저장된 워크플로우 로드
        self.load_workflows()
    
    def load_obs_info(self):
        """OBS 장면 및 소스 정보 로드"""
        if not self.obs_controller:
            print("⚠️ OBS 컨트롤러가 없습니다.")
            self.obs_scenes = {}
            self.obs_scene_items = {}
            return
        
        try:
            print("📡 OBS 장면 정보 로드 중...")
            scenes = self.obs_controller.get_scene_list()
            if not scenes:
                print("⚠️ OBS 장면이 없습니다.")
                self.obs_scenes = {}
                self.obs_scene_items = {}
                return
            
            self.obs_scenes = {scene['name']: scene for scene in scenes}
            print(f"✅ OBS 장면 {len(self.obs_scenes)}개 로드 완료: {list(self.obs_scenes.keys())}")
            
            # 각 장면의 소스 아이템 정보도 로드
            self.obs_scene_items = {}
            for scene_name in self.obs_scenes.keys():
                try:
                    items = self.obs_controller.get_scene_items(scene_name)
                    self.obs_scene_items[scene_name] = items
                    print(f"  - {scene_name}: {len(items)}개 소스")
                except Exception as e:
                    print(f"⚠️ 장면 '{scene_name}' 소스 로드 실패: {e}")
                    self.obs_scene_items[scene_name] = []
        except Exception as e:
            print(f"❌ OBS 정보 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            self.obs_scenes = {}
            self.obs_scene_items = {}
    
    def add_workflow(self):
        """새 이벤트 상태 변경 규칙 추가"""
        try:
            workflow = {
                'name': f'상태 변경 규칙 {len(self.workflows) + 1}',
                'enabled': True,
                'trigger': {
                    'type': '긴급지진속보 (EEW)',
                    'conditions': {}
                },
                'actions': []
            }
            self.workflows.append(workflow)
            self.refresh_workflow_list()
            if len(self.workflows) > 0:
                self.workflow_list.setCurrentRow(len(self.workflows) - 1)
        except Exception as e:
            print(f"❌ 워크플로우 추가 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def remove_workflow(self):
        """선택된 규칙 삭제"""
        current_row = self.workflow_list.currentRow()
        if current_row >= 0:
            del self.workflows[current_row]
            self.refresh_workflow_list()
            if len(self.workflows) > 0:
                self.workflow_list.setCurrentRow(min(current_row, len(self.workflows) - 1))
            else:
                self.clear_workflow_editor()
    
    def refresh_workflow_list(self):
        """규칙 목록 새로고침"""
        try:
            self.workflow_list.clear()
            for i, workflow in enumerate(self.workflows):
                status = "✓" if workflow.get('enabled', True) else "✗"
                self.workflow_list.addItem(f"{status} {workflow['name']}")
        except Exception as e:
            print(f"❌ 규칙 목록 새로고침 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def on_workflow_selected(self, current, previous):
        """워크플로우 선택 시 편집 영역 업데이트"""
        try:
            if current is None:
                self.clear_workflow_editor()
                return
            
            row = self.workflow_list.currentRow()
            if row < 0 or row >= len(self.workflows):
                return
            
            workflow = self.workflows[row]
            # 시그널 연결을 일시적으로 차단하여 무한 루프 방지
            self.workflow_name_edit.blockSignals(True)
            self.workflow_name_edit.setText(workflow['name'])
            self.workflow_name_edit.blockSignals(False)
            
            self.workflow_enabled_checkbox.setCurrentIndex(0 if workflow.get('enabled', True) else 1)
            
            # 트리거 설정
            trigger_type = workflow.get('trigger', {}).get('type', '긴급지진속보 (EEW)')
            index = self.trigger_type_combo.findText(trigger_type)
            if index >= 0:
                # 시그널 차단하여 update_trigger_conditions가 자동 호출되지 않도록
                self.trigger_type_combo.blockSignals(True)
                self.trigger_type_combo.setCurrentIndex(index)
                self.trigger_type_combo.blockSignals(False)
                # 수동으로 트리거 조건 업데이트 (저장된 조건 포함)
                saved_conditions = workflow.get('trigger', {}).get('conditions', {})
                self.update_trigger_conditions(trigger_type, saved_conditions)
            
            # 액션 목록
            self.action_list.clear()
            for action in workflow.get('actions', []):
                action_text = self.format_action_text(action)
                self.action_list.addItem(action_text)
        except Exception as e:
            print(f"❌ 워크플로우 선택 처리 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_workflow_editor(self):
        """워크플로우 편집 영역 초기화"""
        self.workflow_name_edit.clear()
        self.workflow_enabled_checkbox.setCurrentIndex(0)
        self.trigger_type_combo.setCurrentIndex(0)
        self.action_list.clear()
    
    def on_workflow_name_changed(self, text):
        """규칙 이름 변경"""
        row = self.workflow_list.currentRow()
        if row >= 0 and row < len(self.workflows):
            self.workflows[row]['name'] = text
            self.refresh_workflow_list()
            self.workflow_list.setCurrentRow(row)
    
    def on_trigger_type_changed(self, text):
        """이벤트 감지 타입 변경"""
        try:
            # 현재 규칙에 저장된 조건 로드
            row = self.workflow_list.currentRow()
            saved_conditions = {}
            if row >= 0 and row < len(self.workflows):
                if 'trigger' not in self.workflows[row]:
                    self.workflows[row]['trigger'] = {}
                self.workflows[row]['trigger']['type'] = text
                saved_conditions = self.workflows[row]['trigger'].get('conditions', {})
            
            # 트리거 조건 위젯 업데이트
            self.update_trigger_conditions(text, saved_conditions)
        except Exception as e:
            print(f"❌ 트리거 타입 변경 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def update_trigger_conditions(self, trigger_type, saved_conditions=None):
        """트리거 타입에 따른 조건 위젯 업데이트 (가이드 문서와 동일)"""
        try:
            # 기존 위젯 제거
            while self.trigger_conditions_layout.count():
                child = self.trigger_conditions_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            if trigger_type == "긴급지진속보 (EEW)":
                # EEW 조건 (가이드 문서 159-207줄 참조)
                conditions_widget = QWidget()
                conditions_layout = QVBoxLayout()
                
                # 위젯 참조 저장용 딕셔너리
                widgets_dict = {'announcement_checks': [], 'change_checks': []}
                
                # 조건(発表･更新) - 체크박스 그룹
                announcement_group = QGroupBox("조건(발표･업데이트)")
                announcement_layout = QVBoxLayout()
                
                announcement_texts = [
                    "新規発表 (신규 발표)",
                    "続報発表 (속보 발표)",
                    "より精度の高い情報ソースからの情報 (더 정밀한 정보 소스로부터의 정보)",
                    "最終報 (최종보)",
                    "キャンセル報 (취소보)",
                    "警報新規発表 (경보 신규 발표)",
                    "警報続報発表 (경보 속보 발표)",
                    "警報キャンセル (경보 취소)"
                ]
                
                saved_announcement = saved_conditions.get('announcement', {}) if saved_conditions else {}
                for text in announcement_texts:
                    checkbox = QCheckBox(text)
                    checkbox.setChecked(saved_announcement.get(text, False))
                    announcement_layout.addWidget(checkbox)
                    widgets_dict['announcement_checks'].append(checkbox)
                
                announcement_group.setLayout(announcement_layout)
                conditions_layout.addWidget(announcement_group)
                
                # 조건(変更等) - 체크박스 그룹
                change_group = QGroupBox("조건(변경 등)")
                change_layout = QVBoxLayout()
                
                change_texts = [
                    "警報レベル到達 (경보 레벨 도달)",
                    "予想最大震度上昇 (예상 최대 진도 상승)",
                    "予想最大震度低下 (예상 최대 진도 하강)"
                ]
                
                saved_change = saved_conditions.get('change', {}) if saved_conditions else {}
                for text in change_texts:
                    checkbox = QCheckBox(text)
                    checkbox.setChecked(saved_change.get(text, False))
                    change_layout.addWidget(checkbox)
                    widgets_dict['change_checks'].append(checkbox)
                
                change_group.setLayout(change_layout)
                conditions_layout.addWidget(change_group)
                
                # 震度フィルター (진도 필터)
                intensity_layout = QHBoxLayout()
                intensity_layout.addWidget(QLabel("震度フィルター (진도 필터):"))
                intensity_combo = QComboBox()
                intensity_combo.addItems(["필터 없음", "震度0 이상", "震度1 이상", "震度2 이상", "震度3 이상", 
                                         "震度4 이상", "震度5弱 이상", "震度5強 이상", "震度6弱 이상", "震度6強 이상", "震度7 이상"])
                saved_intensity = saved_conditions.get('intensity_filter', '필터 없음') if saved_conditions else '필터 없음'
                index = intensity_combo.findText(saved_intensity)
                if index >= 0:
                    intensity_combo.setCurrentIndex(index)
                intensity_layout.addWidget(intensity_combo)
                conditions_layout.addLayout(intensity_layout)
                widgets_dict['intensity_combo'] = intensity_combo
                
                conditions_widget.setLayout(conditions_layout)
                self.trigger_conditions_layout.addWidget(conditions_widget)
                self.current_condition_widgets[trigger_type] = widgets_dict
            
            elif trigger_type == "지진상세정보":
                # 지진정보 조건 (가이드 문서 280-312줄 참조)
                conditions_widget = QWidget()
                conditions_layout = QVBoxLayout()
                
                widgets_dict = {'info_type_checks': []}
                
                # 정보 수신 조건 라디오 버튼
                receive_group = QGroupBox("정보 수신 조건")
                receive_layout = QVBoxLayout()
                
                receive_radio_group = QButtonGroup()
                receive_at_radio = QRadioButton("情報受信時 (정보 수신 시)")
                max_intensity_radio = QRadioButton("最大震度変更時 (최대 진도 변경 시)")
                receive_radio_group.addButton(receive_at_radio)
                receive_radio_group.addButton(max_intensity_radio)
                
                saved_receive = saved_conditions.get('receive_condition', '정보 수신 시') if saved_conditions else '정보 수신 시'
                if saved_receive == '최대 진도 변경 시':
                    max_intensity_radio.setChecked(True)
                else:
                    receive_at_radio.setChecked(True)
                
                receive_layout.addWidget(receive_at_radio)
                
                # 최대 진도 변경 시 옵션
                intensity_change_layout = QHBoxLayout()
                intensity_change_layout.addSpacing(30)
                intensity_change_checkbox = QCheckBox("震度が上昇したときのみ (진도가 상승했을 때만)")
                saved_intensity_rise = saved_conditions.get('intensity_rise_only', False) if saved_conditions else False
                intensity_change_checkbox.setChecked(saved_intensity_rise)
                intensity_change_layout.addWidget(intensity_change_checkbox)
                receive_layout.addLayout(intensity_change_layout)
                receive_layout.addWidget(max_intensity_radio)
                widgets_dict['intensity_change_check'] = intensity_change_checkbox
                widgets_dict['receive_radio'] = receive_at_radio
                
                receive_group.setLayout(receive_layout)
                conditions_layout.addWidget(receive_group)
                
                # 震度フィルター (진도 필터)
                intensity_layout = QHBoxLayout()
                intensity_layout.addWidget(QLabel("震度フィルター (진도 필터):"))
                intensity_combo = QComboBox()
                intensity_combo.addItems(["필터 없음", "震度0 이상", "震度1 이상", "震度2 이상", "震度3 이상", 
                                         "震度4 이상", "震度5弱 이상", "震度5強 이상", "震度6弱 이상", "震度6強 이상", "震度7 이상"])
                saved_intensity = saved_conditions.get('intensity_filter', '필터 없음') if saved_conditions else '필터 없음'
                index = intensity_combo.findText(saved_intensity)
                if index >= 0:
                    intensity_combo.setCurrentIndex(index)
                intensity_layout.addWidget(intensity_combo)
                conditions_layout.addLayout(intensity_layout)
                widgets_dict['intensity_combo'] = intensity_combo
                
                # 情報種別 (정보 종류) - 체크박스 그룹
                info_type_group = QGroupBox("情報種別 (정보 종류)")
                info_type_layout = QVBoxLayout()
                
                info_type_texts = [
                    "震度速報 (진도 속보)",
                    "震源に関する情報 (진원에 관한 정보)",
                    "震源・震度に関する情報 (진원・진도에 관한 정보)",
                    "顕著な地震の震源要素更新のお知らせ (현저한 지진의 진원 요소 업데이트 알림)",
                    "津波警報・注意報・予報 (해일 경보・주의보・예보)",
                    "長周期地震動に関する観測情報 (장주기 지진동에 관한 관측 정보)"
                ]
                
                saved_info_types = saved_conditions.get('info_types', {}) if saved_conditions else {}
                for text in info_type_texts:
                    checkbox = QCheckBox(text)
                    checkbox.setChecked(saved_info_types.get(text, True))  # 기본값은 True
                    info_type_layout.addWidget(checkbox)
                    widgets_dict['info_type_checks'].append(checkbox)
                
                info_type_group.setLayout(info_type_layout)
                conditions_layout.addWidget(info_type_group)
                
                conditions_widget.setLayout(conditions_layout)
                self.trigger_conditions_layout.addWidget(conditions_widget)
                self.current_condition_widgets[trigger_type] = widgets_dict
            
            elif trigger_type == "해일정보":
                # 津波情報 조건 (가이드 문서 365-382줄 참조)
                conditions_widget = QWidget()
                conditions_layout = QVBoxLayout()
                
                widgets_dict = {'condition_checks': []}
                
                # レベルフィルター (레벨 필터)
                level_layout = QHBoxLayout()
                level_layout.addWidget(QLabel("レベルフィルター (레벨 필터):"))
                level_combo = QComboBox()
                level_combo.addItems(["필터 없음", "なし (None)", "津波予報 (Forecast)", "津波注意報 (Advisory)", 
                                     "津波警報 (Warning)", "大津波警報 (MajorWarning)"])
                saved_level = saved_conditions.get('level_filter', '필터 없음') if saved_conditions else '필터 없음'
                index = level_combo.findText(saved_level)
                if index >= 0:
                    level_combo.setCurrentIndex(index)
                level_layout.addWidget(level_combo)
                
                # レベルが一致しているときのみ実行する (레벨이 일치할 때만 실행)
                level_exact_checkbox = QCheckBox("レベルが一致しているときのみ実行する (레벨이 일치할 때만 실행)")
                saved_level_exact = saved_conditions.get('level_exact_match', False) if saved_conditions else False
                level_exact_checkbox.setChecked(saved_level_exact)
                level_layout.addWidget(level_exact_checkbox)
                conditions_layout.addLayout(level_layout)
                widgets_dict['level_combo'] = level_combo
                widgets_dict['level_exact_check'] = level_exact_checkbox
                
                # 조건 체크박스 그룹
                condition_group = QGroupBox("조건")
                condition_layout = QVBoxLayout()
                
                condition_texts = [
                    "発表時 (발표 시)",
                    "警報種別が上昇したとき (경보 종류가 상승했을 때)",
                    "警報種別が下降したとき (경보 종류가 하강했을 때)",
                    "その他更新 (기타 업데이트)"
                ]
                
                saved_conditions_dict = saved_conditions.get('conditions', {}) if saved_conditions else {}
                for text in condition_texts:
                    checkbox = QCheckBox(text)
                    checkbox.setChecked(saved_conditions_dict.get(text, True))  # 기본값은 True
                    condition_layout.addWidget(checkbox)
                    widgets_dict['condition_checks'].append(checkbox)
                
                condition_group.setLayout(condition_layout)
                conditions_layout.addWidget(condition_group)
                
                conditions_widget.setLayout(conditions_layout)
                self.trigger_conditions_layout.addWidget(conditions_widget)
                self.current_condition_widgets[trigger_type] = widgets_dict
        except Exception as e:
            print(f"❌ 트리거 조건 업데이트 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def add_action(self):
        """상태 변경 규칙 추가 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle("상태 변경 규칙 추가")
        dialog.resize(500, 400)
        
        layout = QVBoxLayout()
        
        # 안내 문구
        notice_label = QLabel(
            "⚠️ 이 규칙은 이벤트 상태 플래그만 변경합니다.\n"
            "방송 화면은 시스템이 전체 상태를 종합하여 자동으로 결정합니다."
        )
        notice_label.setFont(QFont("맑은 고딕", 9))
        notice_label.setStyleSheet("color: #ffaaaa; padding: 10px; background-color: #2a1a1a; border-radius: 5px;")
        notice_label.setWordWrap(True)
        layout.addWidget(notice_label)
        
        # 상태 변경 타입 선택
        layout.addWidget(QLabel("상태 변경 타입:"))
        action_type_combo = QComboBox()
        action_type_combo.addItems([
            "소스 표시",
            "소스 숨김",
            "소스 토글",
            "몇초 기다리기",
            "녹화 시작",
            "녹화 중지",
            "버퍼 저장"
        ])
        layout.addWidget(action_type_combo)
        
        # 액션 파라미터 (동적으로 변경)
        params_widget = QWidget()
        params_layout = QVBoxLayout()
        params_widget.setLayout(params_layout)
        layout.addWidget(params_widget)
        
        def update_params(action_type):
            # 기존 위젯 제거
            while params_layout.count():
                child = params_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            if action_type in ["소스 표시", "소스 숨김", "소스 토글"]:
                scene_combo = QComboBox()
                scene_combo.addItems(list(self.obs_scenes.keys()) if self.obs_scenes else ["일반", "일본", "해일"])
                params_layout.addWidget(QLabel("장면:"))
                params_layout.addWidget(scene_combo)
                
                item_combo = QComboBox()
                params_layout.addWidget(QLabel("소스:"))
                params_layout.addWidget(item_combo)
                
                def update_items():
                    scene_name = scene_combo.currentText()
                    items = self.obs_scene_items.get(scene_name, [])
                    item_combo.clear()
                    for item in items:
                        item_combo.addItem(f"{item['sourceName']} (ID: {item['itemId']})", item['itemId'])
                
                scene_combo.currentTextChanged.connect(update_items)
                if scene_combo.count() > 0:
                    update_items()
                
                params_widget.scene_combo = scene_combo
                params_widget.item_combo = item_combo
            
            elif action_type == "몇초 기다리기":
                seconds_spinbox = QDoubleSpinBox()
                seconds_spinbox.setMinimum(0.1)
                seconds_spinbox.setMaximum(3600.0)
                seconds_spinbox.setSingleStep(0.1)
                seconds_spinbox.setValue(1.0)
                seconds_spinbox.setDecimals(1)
                params_layout.addWidget(QLabel("기다릴 시간 (초):"))
                params_layout.addWidget(seconds_spinbox)
                params_widget.seconds_spinbox = seconds_spinbox
        
        action_type_combo.currentTextChanged.connect(update_params)
        if action_type_combo.count() > 0:
            update_params(action_type_combo.currentText())
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.Accepted:
            action_type = action_type_combo.currentText()
            action = {'type': action_type}
            
            if action_type in ["소스 표시", "소스 숨김", "소스 토글"]:
                action['scene'] = params_widget.scene_combo.currentText()
                action['itemId'] = params_widget.item_combo.currentData()
                action['sourceName'] = params_widget.item_combo.currentText()
            
            elif action_type == "몇초 기다리기":
                action['seconds'] = params_widget.seconds_spinbox.value()
            
            # 현재 규칙에 상태 변경 추가
            row = self.workflow_list.currentRow()
            if row >= 0 and row < len(self.workflows):
                if 'actions' not in self.workflows[row]:
                    self.workflows[row]['actions'] = []
                self.workflows[row]['actions'].append(action)
                self.action_list.addItem(self.format_action_text(action))
    
    def remove_action(self):
        """선택된 상태 변경 규칙 삭제"""
        current_row = self.action_list.currentRow()
        if current_row >= 0:
            workflow_row = self.workflow_list.currentRow()
            if workflow_row >= 0 and workflow_row < len(self.workflows):
                if 'actions' in self.workflows[workflow_row]:
                    del self.workflows[workflow_row]['actions'][current_row]
                    self.action_list.takeItem(current_row)
    
    def format_action_text(self, action):
        """상태 변경 규칙 텍스트 포맷"""
        action_type = action.get('type', '')
        if action_type in ["소스 표시", "소스 숨김", "소스 토글"]:
            return f"{action_type} → {action.get('sourceName', '')} (장면: {action.get('scene', '')})"
        elif action_type == "몇초 기다리기":
            seconds = action.get('seconds', 1.0)
            return f"대기 → {seconds}초"
        elif action_type in ["녹화 시작", "녹화 중지", "버퍼 저장"]:
            return action_type
        return str(action)
    
    def save_conditions_from_ui(self):
        """현재 UI의 조건 상태를 규칙 데이터에 저장"""
        try:
            row = self.workflow_list.currentRow()
            if row < 0 or row >= len(self.workflows):
                return
            
            workflow = self.workflows[row]
            if 'trigger' not in workflow:
                workflow['trigger'] = {}
            
            trigger_type = workflow.get('trigger', {}).get('type', '')
            if not trigger_type:
                return
            
            conditions = {}
            widgets = self.current_condition_widgets.get(trigger_type, {})
            
            if trigger_type == "긴급지진속보 (EEW)":
                # 조건(발표･업데이트) 체크박스들
                announcement_checks = widgets.get('announcement_checks', [])
                conditions['announcement'] = {check.text(): check.isChecked() for check in announcement_checks}
                
                # 조건(변경 등) 체크박스들
                change_checks = widgets.get('change_checks', [])
                conditions['change'] = {check.text(): check.isChecked() for check in change_checks}
                
                # 진도 필터
                intensity_combo = widgets.get('intensity_combo')
                if intensity_combo:
                    conditions['intensity_filter'] = intensity_combo.currentText()
            
            elif trigger_type == "지진상세정보":
                # 정보 수신 조건
                receive_radio = widgets.get('receive_radio')
                if receive_radio:
                    conditions['receive_condition'] = '정보 수신 시' if receive_radio.isChecked() else '최대 진도 변경 시'
                
                intensity_change_check = widgets.get('intensity_change_check')
                if intensity_change_check:
                    conditions['intensity_rise_only'] = intensity_change_check.isChecked()
                
                # 진도 필터
                intensity_combo = widgets.get('intensity_combo')
                if intensity_combo:
                    conditions['intensity_filter'] = intensity_combo.currentText()
                
                # 정보 종류 체크박스들
                info_type_checks = widgets.get('info_type_checks', [])
                conditions['info_types'] = {check.text(): check.isChecked() for check in info_type_checks}
            
            elif trigger_type == "해일정보":
                # 레벨 필터
                level_combo = widgets.get('level_combo')
                if level_combo:
                    conditions['level_filter'] = level_combo.currentText()
                
                level_exact_check = widgets.get('level_exact_check')
                if level_exact_check:
                    conditions['level_exact_match'] = level_exact_check.isChecked()
                
                # 조건 체크박스들
                condition_checks = widgets.get('condition_checks', [])
                conditions['conditions'] = {check.text(): check.isChecked() for check in condition_checks}
            
            workflow['trigger']['conditions'] = conditions
        except Exception as e:
            print(f"❌ 조건 저장 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def save_workflows(self):
        """워크플로우 저장"""
        try:
            # 저장 전에 현재 UI 상태를 워크플로우 데이터에 반영
            self.save_conditions_from_ui()
            
            with open(self.workflows_file, 'w', encoding='utf-8') as f:
                json.dump(self.workflows, f, ensure_ascii=False, indent=2)
            print(f"✅ 워크플로우 저장 완료: {self.workflows_file}")
        except Exception as e:
            print(f"❌ 워크플로우 저장 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def load_workflows(self):
        """워크플로우 불러오기"""
        try:
            if os.path.exists(self.workflows_file):
                with open(self.workflows_file, 'r', encoding='utf-8') as f:
                    self.workflows = json.load(f)
                self.refresh_workflow_list()
                print(f"✅ 상태 변경 규칙 불러오기 완료: {len(self.workflows)}개")
            else:
                self.workflows = []
                print("ℹ️ 상태 변경 규칙 파일이 없습니다. 새로 생성합니다.")
        except Exception as e:
            print(f"❌ 상태 변경 규칙 불러오기 실패: {e}")
            self.workflows = []
    
    def test_workflow(self):
        """상태 변경 규칙 테스트 실행/중지"""
        if self.test_running:
            # 테스트 중지
            self.test_stop_flag = True
            self.test_btn.setText("상태 변경 테스트")
            self.test_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a9eff;
                    color: white;
                    padding: 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5aaeff;
                }
                QPushButton:pressed {
                    background-color: #3a8eef;
                }
            """)
            print("⏹️ 테스트 중지 요청")
        else:
            # 테스트 시작
            row = self.workflow_list.currentRow()
            if row < 0 or row >= len(self.workflows):
                print("⚠️ 규칙을 선택해주세요.")
                return
            
            workflow = self.workflows[row]
            if not workflow.get('enabled', True):
                print("⚠️ 비활성화된 규칙은 테스트할 수 없습니다.")
                return
            
            self.test_running = True
            self.test_stop_flag = False
            self.test_btn.setText("테스트 중지")
            self.test_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff4a4a;
                    color: white;
                    padding: 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #ff5a5a;
                }
                QPushButton:pressed {
                    background-color: #ef3a3a;
                }
            """)
            
            # 별도 스레드에서 테스트 실행
            import threading
            test_thread = threading.Thread(target=self._execute_test_workflow, args=(workflow,), daemon=True)
            test_thread.start()
    
    def _execute_test_workflow(self, workflow):
        """상태 변경 규칙 테스트 실행 (별도 스레드)"""
        try:
            print(f"🧪 상태 변경 규칙 테스트 시작: {workflow.get('name', 'Unknown')}")
            
            # 현재 UI 상태를 규칙 데이터에 반영
            self.save_conditions_from_ui()
            
            # 상태 변경 규칙 실행
            actions = workflow.get('actions', [])
            if not actions:
                print("⚠️ 실행할 상태 변경 규칙이 없습니다.")
                self._test_finished()
                return
            
            for i, action in enumerate(actions):
                if self.test_stop_flag:
                    print("⏹️ 테스트가 중지되었습니다.")
                    break
                
                print(f"▶️ 상태 변경 {i+1}/{len(actions)} 실행: {self.format_action_text(action)}")
                self._execute_action(action)
                
                # 상태 변경 간 짧은 대기 (UI 업데이트를 위해)
                import time
                time.sleep(0.1)
            
            if not self.test_stop_flag:
                print("✅ 상태 변경 규칙 테스트 완료")
            
            self._test_finished()
        except Exception as e:
            print(f"❌ 테스트 실행 오류: {e}")
            import traceback
            traceback.print_exc()
            self._test_finished()
    
    def _test_finished(self):
        """테스트 종료 처리 (스레드 안전)"""
        self.test_running = False
        self.test_stop_flag = False
        # Signal을 통해 메인 스레드에서 UI 업데이트
        self.test_finished_signal.emit()
    
    def _on_test_finished(self):
        """테스트 종료 UI 업데이트 (메인 스레드에서 실행)"""
        self.test_btn.setText("상태 변경 테스트")
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5aaeff;
            }
            QPushButton:pressed {
                background-color: #3a8eef;
            }
        """)
    
    def _execute_action(self, action):
        """
        [레거시 테스트 메서드] 상태 변경 규칙 실행 (테스트용)
        
        ⚠️ 주의: OBS 직접 제어는 이제 state_reflector.py에서만 수행됩니다.
        이 메서드는 레거시 워크플로우 테스트용이며, 실제 OBS 제어는 하지 않습니다.
        """
        action_type = action.get('type', '')
        
        try:
            # 모든 OBS 제어는 StateReflector가 담당하므로, 여기서는 로그만 출력
            print(f"  ⚠️ [레거시 테스트] 액션 타입: {action_type}")
            print(f"  ℹ️ 실제 OBS 제어는 StateReflector가 플래그 시스템 기반으로 수행합니다.")
            
            # 장면 전환은 시스템이 자동으로 결정
            if action_type == "장면 전환":
                print(f"  ⚠️ 장면 전환은 무시됩니다 (플래그 시스템이 자동으로 결정)")
                return
            
            # 나머지 액션들도 실제 OBS 제어 없이 로그만 출력
            elif action_type in ["소스 표시", "소스 숨김", "소스 토글"]:
                print(f"  ℹ️ 소스 제어는 하위 플래그를 통해 StateReflector가 수행합니다.")
            
            elif action_type == "몇초 기다리기":
                seconds = action.get('seconds', 1.0)
                import time
                # 중지 플래그를 확인하면서 대기
                elapsed = 0.0
                while elapsed < seconds and not self.test_stop_flag:
                    time.sleep(0.1)
                    elapsed += 0.1
                if not self.test_stop_flag:
                    print(f"  ✓ {seconds}초 대기 완료")
            
            elif action_type in ["녹화 시작", "녹화 중지", "버퍼 저장"]:
                print(f"  ℹ️ {action_type}는 상위 플래그를 통해 StateReflector가 수행합니다.")
            
            else:
                print(f"  ⚠️ 알 수 없는 액션 타입: {action_type}")
        
        except Exception as e:
            print(f"  ❌ 액션 실행 오류: {e}")
            import traceback
            traceback.print_exc()


# ------------------ 실행 ------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)

    detail_win = DetailWindow()
    broadcast_win = BroadcastWindow()

    dmdata_handler = DMDataHandler(broadcast_win, detail_win)
    exptech_handler = ExpTechHandler(broadcast_win, detail_win)

    def start_dmdata():
        try:
            dmdata_handler.start()
        except Exception as e:
            print(f"❌ DMDATA 스레드 오류: {e}")
            import traceback
            traceback.print_exc()

    dmdata_thread = threading.Thread(target=start_dmdata, daemon=True)
    dmdata_thread.start()
    
    def start_exptech():
        try:
            exptech_handler.start()
        except Exception as e:
            print(f"❌ ExpTech 스레드 오류: {e}")
            import traceback
            traceback.print_exc()
    
    exptech_thread = threading.Thread(target=start_exptech, daemon=True)
    exptech_thread.start()

    print("🚀 지진 알림 시스템 시작")
    print("DMDATA (일본) 연결 중...")
    print("ExpTech (대만) 연결 중...")
    print("🖱️ 방송용 창에서 우클릭하여 알림 종료 가능")
    print("📋 상세 정보창에서 현재 상황과 지진 정보를 확인할 수 있습니다")
    print("💡 연결 상태가 표시등으로 표시됩니다")

    sys.exit(app.exec())