"""
플래그 기반 상태 머신 시스템
- 플래그는 오직 상태 변수 (true/false)
- OBS 제어는 절대 포함하지 않음
- 상태 안정화 엔진 포함
- 플래그 우선순위 및 부모-자식 관계 지원

[절대 원칙 - 위반 불가]
1. 플래그는 "명령"이 아니라 "상태"다.
2. 플래그가 켜지거나 꺼졌다고 해서 OBS 동작이 즉시 실행되어서는 안 된다.
3. OBS 제어는 state_reflector.py에서만 수행된다.
4. 이 모듈은 플래그 상태만 관리하며, OBS 관련 코드를 절대 포함하지 않는다.

[구조적 보장]
- flag_state_changed 시그널은 알림용일 뿐, OBS 제어를 트리거하지 않는다.
- 플래그의 on_actions/off_actions는 정보 저장용이며, 여기서 실행되지 않는다.
"""
import json
import os
from typing import Dict, List, Optional, Any, Set
from PySide6.QtCore import QObject, QTimer, Signal

class FlagCondition:
    """플래그 조건 - 상태 변경 조건만 정의"""
    def __init__(self, condition_type: str, params: Dict[str, Any], delay: float = 0.0):
        self.condition_type = condition_type  # 조건 타입 (한국어)
        self.params = params  # 조건별 파라미터
        self.delay = delay  # 지연 시간 (초)
    
    def to_dict(self):
        return {
            "type": self.condition_type,
            "params": self.params,
            "delay": self.delay
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            data.get("type", ""),
            data.get("params", {}),
            data.get("delay", 0.0)
        )

class FlagAction:
    """플래그 동작 (OBS 제어 정보만 저장, 실행하지 않음)"""
    def __init__(self, action_type: str, params: Dict[str, Any]):
        self.action_type = action_type
        self.params = params
    
    def to_dict(self):
        return {
            "type": self.action_type,
            "params": self.params
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            data.get("type", ""),
            data.get("params", {})
        )

class Flag:
    """
    플래그 - 상태 변수일 뿐
    
    [절대 원칙]
    - 플래그는 "명령자"가 아니라 "상태 변수"다.
    - 플래그는 OBS API를 직접 호출하지 않는다.
    - 플래그는 다른 플래그를 직접 ON/OFF하지 않는다.
    - 플래그는 자기 자신을 즉시 다시 평가하지 않는다.
    
    [priority 필드]
    - 상위 플래그 전용: int | None
    - None = 자동 (모든 수동 priority보다 낮은 우선순위)
    - 숫자가 낮을수록 우선순위가 높다 (1 < 2 < 3 < ...)
    - 하위 플래그는 priority를 사용하지 않는다.
    """
    def __init__(self, flag_id: str, name: str, flag_type: str = "upper"):
        self.flag_id = flag_id
        self.name = name
        self.flag_type = flag_type  # "upper" 또는 "lower"
        self.state = False  # 오직 true/false만 가짐
        self.priority: Optional[int] = None  # 우선순위 (상위 플래그만, None=자동)
        
        # 상위 플래그 전용: 이 상위 플래그에 포함될 하위 플래그 ID 목록
        # 상위 플래그 상태 = OR(linked_lower_flags의 상태)
        self.linked_lower_flags: List[str] = []
        
        # 조건들 (하위 플래그만 가짐, 상위 플래그는 조건 없음)
        # 켜짐 조건들 (OR 관계: 하나라도 만족하면 켜짐)
        self.on_conditions: List[FlagCondition] = []
        
        # 꺼짐 조건들 (OR 관계: 하나라도 만족하면 꺼짐)
        self.off_conditions: List[FlagCondition] = []
        
        # 켜짐 시 동작들 (OBS 제어 정보만 저장)
        self.on_actions: List[FlagAction] = []
        
        # 꺼짐 시 동작들 (OBS 제어 정보만 저장)
        self.off_actions: List[FlagAction] = []
        
        # 마지막 상태 변경 시간 (우선순위 자동 결정용)
        self.last_state_change_time: Optional[float] = None
    
    def to_dict(self):
        """
        플래그를 JSON 직렬화 가능한 딕셔너리로 변환
        
        [완전 결정적 구조]
        - priority: 명시적으로 저장 (None이면 null로 저장)
        - last_state_change_time: winner 결정에 필요한 정보 저장
        - type: "upper" 또는 "lower" 명시
        - 모든 필수 정보 포함하여 winner 결정이 가능하도록 보장
        """
        result = {
            "id": self.flag_id,
            "name": self.name,
            "type": self.flag_type,  # "upper" 또는 "lower" 명시
            "priority": self.priority,  # None이면 null로 저장 (명시적)
            "last_state_change_time": self.last_state_change_time,  # winner 결정에 필수
            "state": self.state,  # 현재 상태도 저장 (로드 시 복원)
            "on_actions": [a.to_dict() for a in self.on_actions],
            "off_actions": [a.to_dict() for a in self.off_actions]
        }
        
        # 상위 플래그는 linked_lower_flags 저장
        if self.flag_type == "upper":
            result["linked_lower_flags"] = self.linked_lower_flags
        
        # 하위 플래그는 조건만 저장
        if self.flag_type == "lower":
            result["on_conditions"] = [c.to_dict() for c in self.on_conditions]
            result["off_conditions"] = [c.to_dict() for c in self.off_conditions]
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict):
        """
        JSON 딕셔너리에서 플래그 복원
        
        [완전 결정적 복원]
        - priority: 명시적으로 로드 (null이면 None)
        - last_state_change_time: winner 결정에 필요한 정보 복원
        - state: 저장된 상태 복원
        - 모든 필수 정보를 복원하여 winner 결정이 가능하도록 보장
        """
        flag = cls(
            data.get("id", ""),
            data.get("name", ""),
            data.get("type", "upper")  # "is_upper" 레거시 필드도 지원
        )
        # 레거시 "is_upper" 필드 지원
        if "is_upper" in data:
            flag.flag_type = "upper" if data.get("is_upper") else "lower"
        
        # priority 명시적 로드 (null이면 None)
        priority_value = data.get("priority")
        flag.priority = priority_value if priority_value is not None else None
        
        flag.last_state_change_time = data.get("last_state_change_time")
        flag.state = data.get("state", False)  # 저장된 상태 복원
        
        # 상위 플래그는 linked_lower_flags 로드
        if flag.flag_type == "upper":
            flag.linked_lower_flags = data.get("linked_lower_flags", [])
            # 상위 플래그는 조건을 가지지 않음
            flag.on_conditions = []
            flag.off_conditions = []
        
        # 하위 플래그는 조건만 로드
        if flag.flag_type == "lower":
            flag.on_conditions = [FlagCondition.from_dict(c) for c in data.get("on_conditions", [])]
            flag.off_conditions = [FlagCondition.from_dict(c) for c in data.get("off_conditions", [])]
        
        flag.on_actions = [FlagAction.from_dict(a) for a in data.get("on_actions", [])]
        flag.off_actions = [FlagAction.from_dict(a) for a in data.get("off_actions", [])]
        return flag

class FlagSystem(QObject):
    """플래그 시스템 - 상태만 관리, OBS 제어 없음"""
    flag_state_changed = Signal(str, bool)  # flag_id, new_state (알림용)
    
    def __init__(self):
        super().__init__()
        self.upper_flags: Dict[str, Flag] = {}
        self.lower_flags: Dict[str, Flag] = {}
        self.all_flags: Dict[str, Flag] = {}
        
        # 최근 이벤트 기록 (조건 확인용)
        self.recent_events: Dict[str, List[Dict]] = {}
        
        # 지연된 조건 실행을 위한 타이머 관리
        self.pending_conditions: List[Dict] = []
        
        # 상태 안정화 엔진 타이머
        self.stabilization_timer = QTimer()
        self.stabilization_timer.timeout.connect(self._stabilize_state)
        self.stabilization_timer.start(100)  # 100ms마다 안정화
        
        # 설정 파일 경로
        self.config_file = "flag_system.json"
        
        # 로드
        self.load_config()
    
    def add_flag(self, flag: Flag):
        """플래그 추가"""
        if flag.flag_type == "upper":
            self.upper_flags[flag.flag_id] = flag
        else:
            self.lower_flags[flag.flag_id] = flag
        self.all_flags[flag.flag_id] = flag
    
    def remove_flag(self, flag_id: str):
        """플래그 제거"""
        if flag_id in self.upper_flags:
            del self.upper_flags[flag_id]
        if flag_id in self.lower_flags:
            del self.lower_flags[flag_id]
        if flag_id in self.all_flags:
            del self.all_flags[flag_id]
        
        # 상위 플래그의 linked_lower_flags에서 제거
        for flag in self.all_flags.values():
            if flag.flag_type == "upper" and flag_id in flag.linked_lower_flags:
                flag.linked_lower_flags.remove(flag_id)
    
    def get_flag(self, flag_id: str) -> Optional[Flag]:
        """플래그 가져오기"""
        return self.all_flags.get(flag_id)
    
    def is_flag_active(self, flag_id: str) -> bool:
        """플래그 활성 상태 확인"""
        flag = self.get_flag(flag_id)
        return flag.state if flag else False
    
    def get_all_flags_state(self) -> Dict[str, bool]:
        """모든 플래그의 현재 상태 스냅샷 반환"""
        return {flag_id: flag.state for flag_id, flag in self.all_flags.items()}
    
    def get_active_upper_flags(self) -> List[Flag]:
        """활성 상위 플래그 목록 반환 (우선순위 정렬)
        
        정렬 규칙:
        1. priority가 설정된 플래그가 하나라도 있으면: priority 낮은 순 (낮은 숫자 = 높은 우선순위)
        2. priority가 모두 null이면: 가장 최근에 켜진 플래그 순
        3. 동일 priority: 마지막으로 켜진 플래그가 우선
        """
        active_flags = [f for f in self.upper_flags.values() if f.state]
        
        # priority가 설정된 플래그가 하나라도 있는지 확인
        has_priority = any(f.priority is not None for f in active_flags)
        
        if has_priority:
            # priority가 있으면: 낮은 숫자 순 (낮은 숫자 = 높은 우선순위)
            # 동일 priority면 마지막으로 켜진 플래그가 우선 (reverse=True로 최신순)
            active_flags.sort(key=lambda f: (
                f.priority if f.priority is not None else 999999,  # null은 가장 낮은 우선순위
                -(f.last_state_change_time if f.last_state_change_time else 0)  # 최신순 (음수로 reverse 효과)
            ))
        else:
            # priority가 모두 null이면: 가장 최근에 켜진 플래그 순
            active_flags.sort(key=lambda f: f.last_state_change_time if f.last_state_change_time else 0, reverse=True)
        
        return active_flags
    
    def _stabilize_state(self):
        """상태 안정화 엔진 - 핵심 로직"""
        import time
        current_time = time.time()
        
        # 1단계: 지연된 조건 처리
        remaining_pending = []
        for pending in self.pending_conditions:
            if current_time >= pending["time"]:
                # 지연 시간 경과, 상태 변경 예약
                flag = self.get_flag(pending["flag_id"])
                if flag:
                    pending["ready"] = True
            remaining_pending.append(pending)
        self.pending_conditions = remaining_pending
        
        # 2단계: 상태 안정화 루프
        max_iterations = 100  # 무한 루프 방지
        iteration = 0
        
        while iteration < max_iterations:
            # 3단계: 하위 플래그만 조건 평가 (상위 플래그는 조건 없음)
            pending_changes: Dict[str, bool] = {}  # {flag_id: new_state}
            
            # 하위 플래그만 조건 평가
            for flag in self.lower_flags.values():
                # 켜짐 조건 확인 (OR: 하나라도 만족하면 켜짐)
                should_turn_on = False
                if flag.on_conditions:
                    for condition in flag.on_conditions:
                        if self._check_condition(condition, flag):
                            if condition.delay > 0:
                                # 지연 시간이 있으면 예약
                                self._schedule_condition(flag.flag_id, True, condition.delay)
                            else:
                                should_turn_on = True
                            break  # OR이므로 하나만 만족하면 됨
                
                # 꺼짐 조건 확인 (OR: 하나라도 만족하면 꺼짐)
                should_turn_off = False
                if flag.off_conditions:
                    for condition in flag.off_conditions:
                        if self._check_condition(condition, flag):
                            if condition.delay > 0:
                                # 지연 시간이 있으면 예약
                                self._schedule_condition(flag.flag_id, False, condition.delay)
                            else:
                                should_turn_off = True
                            break  # OR이므로 하나만 만족하면 됨
                
                # 상태 변경 예약 (즉시 적용하지 않음)
                if should_turn_on and not flag.state:
                    pending_changes[flag.flag_id] = True
                elif should_turn_off and flag.state:
                    pending_changes[flag.flag_id] = False
            
            # 지연된 조건 처리 (ready 상태인 것만)
            for pending in self.pending_conditions:
                if pending.get("ready", False):
                    flag_id = pending["flag_id"]
                    should_activate = pending["should_activate"]
                    if flag_id not in pending_changes:
                        pending_changes[flag_id] = should_activate
                    # 처리 완료 표시
                    pending["ready"] = False
            
            # 4단계: 예약된 변경 일괄 적용 (하위 플래그만)
            any_change = False
            for flag_id, new_state in pending_changes.items():
                flag = self.get_flag(flag_id)
                if flag and flag.state != new_state:
                    flag.state = new_state
                    flag.last_state_change_time = time.time()
                    self.flag_state_changed.emit(flag_id, new_state)
                    any_change = True
            
            # 5단계: 상위 플래그 상태 계산 (하위 플래그 OR 집계)
            upper_changes = self._update_upper_flags_from_lower()
            if upper_changes:
                any_change = True
            
            # 6단계: 더 이상 변화가 없으면 안정화 완료
            if not any_change:
                break
            
            iteration += 1
        
        if iteration >= max_iterations:
            print("⚠️ 플래그 상태 안정화 최대 반복 횟수 도달")
    
    def _update_upper_flags_from_lower(self) -> bool:
        """
        상위 플래그 상태를 하위 플래그 OR 집계로 계산
        
        규칙: linked_lower_flags에 포함된 하위 플래그 중 하나라도 켜져 있으면 상위 플래그는 켜짐,
              모두 꺼져 있으면 상위 플래그는 꺼짐.
        
        Returns:
            상위 플래그 상태 변경이 있었으면 True
        """
        import time
        any_change = False
        
        for upper_flag in self.upper_flags.values():
            # 이 상위 플래그에 포함된 하위 플래그들 찾기
            linked_lower_flags = [
                self.lower_flags[lower_flag_id]
                for lower_flag_id in upper_flag.linked_lower_flags
                if lower_flag_id in self.lower_flags
            ]
            
            # OR 집계: 하나라도 켜져 있으면 True
            should_be_on = any(lower_flag.state for lower_flag in linked_lower_flags) if linked_lower_flags else False
            
            # 상태 변경이 필요한 경우
            if upper_flag.state != should_be_on:
                upper_flag.state = should_be_on
                upper_flag.last_state_change_time = time.time()
                self.flag_state_changed.emit(upper_flag.flag_id, should_be_on)
                any_change = True
        
        return any_change
    
    def _schedule_condition(self, flag_id: str, should_activate: bool, delay: float):
        """조건 실행 예약"""
        import time
        # 이미 예약된 조건이 있으면 중복 방지
        for pending in self.pending_conditions:
            if pending["flag_id"] == flag_id and pending["should_activate"] == should_activate:
                return  # 이미 예약됨
        
        self.pending_conditions.append({
            "flag_id": flag_id,
            "should_activate": should_activate,
            "delay": delay,
            "time": time.time() + delay,
            "ready": False
        })
    
    def _check_condition(self, condition: FlagCondition, flag: Flag) -> bool:
        """조건 확인"""
        condition_type = condition.condition_type
        params = condition.params
        
        # 플래그 상태 조건
        if condition_type == "다른 플래그 켜짐":
            target_flag_id = params.get("flag_id")
            if target_flag_id:
                return self.is_flag_active(target_flag_id)
        
        elif condition_type == "다른 플래그 꺼짐":
            target_flag_id = params.get("flag_id")
            if target_flag_id:
                return not self.is_flag_active(target_flag_id)
        
        # EEW 이벤트 조건 (한국어)
        elif condition_type == "EEW 신규 발표":
            if "EEW_STARTED" in self.recent_events and self.recent_events["EEW_STARTED"]:
                event_data = self.recent_events["EEW_STARTED"][-1]
                if event_data.get("is_new", False):
                    return self._check_eew_condition(params, event_data, "신규 발표")
        
        elif condition_type == "EEW 속보 발표":
            if "EEW_UPDATED" in self.recent_events and self.recent_events["EEW_UPDATED"]:
                event_data = self.recent_events["EEW_UPDATED"][-1]
                if not event_data.get("is_new", False):
                    return self._check_eew_condition(params, event_data, "속보 발표")
        
        elif condition_type == "EEW 더 정밀한 정보 소스":
            if "EEW_UPDATED" in self.recent_events and self.recent_events["EEW_UPDATED"]:
                event_data = self.recent_events["EEW_UPDATED"][-1]
                return self._check_eew_condition(params, event_data, "더 정밀한 정보 소스")
        
        elif condition_type == "EEW 최종보":
            if "EEW_FINAL" in self.recent_events and self.recent_events["EEW_FINAL"]:
                event_data = self.recent_events["EEW_FINAL"][-1]
                if event_data.get("is_final", False):
                    return self._check_eew_condition(params, event_data, "최종보")
        
        elif condition_type == "EEW 취소보":
            if "EEW_CANCELED" in self.recent_events and self.recent_events["EEW_CANCELED"]:
                event_data = self.recent_events["EEW_CANCELED"][-1]
                if event_data.get("is_canceled", False):
                    return self._check_eew_condition(params, event_data, "취소보")
        
        elif condition_type == "EEW 경보 신규 발표":
            if "EEW_WARNING" in self.recent_events and self.recent_events["EEW_WARNING"]:
                event_data = self.recent_events["EEW_WARNING"][-1]
                if event_data.get("is_warning", False) and event_data.get("is_new", False):
                    return self._check_eew_condition(params, event_data, "경보 신규 발표")
        
        elif condition_type == "EEW 경보 속보 발표":
            if "EEW_WARNING" in self.recent_events and self.recent_events["EEW_WARNING"]:
                event_data = self.recent_events["EEW_WARNING"][-1]
                if event_data.get("is_warning", False) and not event_data.get("is_new", False):
                    return self._check_eew_condition(params, event_data, "경보 속보 발표")
        
        elif condition_type == "EEW 경보 취소":
            if "EEW_CANCELED" in self.recent_events and self.recent_events["EEW_CANCELED"]:
                event_data = self.recent_events["EEW_CANCELED"][-1]
                if event_data.get("is_warning", False):
                    return self._check_eew_condition(params, event_data, "경보 취소")
        
        elif condition_type == "EEW 경보 레벨 도달":
            if "EEW_WARNING" in self.recent_events and self.recent_events["EEW_WARNING"]:
                event_data = self.recent_events["EEW_WARNING"][-1]
                if event_data.get("is_warning", False):
                    return self._check_eew_condition(params, event_data, "경보 레벨 도달")
        
        elif condition_type == "EEW 예상 최대 진도 상승":
            if "EEW_UPDATED" in self.recent_events and self.recent_events["EEW_UPDATED"]:
                event_data = self.recent_events["EEW_UPDATED"][-1]
                # 이전 이벤트와 비교 필요 (추후 구현)
                return self._check_eew_condition(params, event_data, "예상 최대 진도 상승")
        
        elif condition_type == "EEW 예상 최대 진도 하강":
            if "EEW_UPDATED" in self.recent_events and self.recent_events["EEW_UPDATED"]:
                event_data = self.recent_events["EEW_UPDATED"][-1]
                # 이전 이벤트와 비교 필요 (추후 구현)
                return self._check_eew_condition(params, event_data, "예상 최대 진도 하강")
        
        # 지진상세정보 이벤트 조건
        elif condition_type == "진원진도정보 수신":
            if "DETAIL_RECEIVED" in self.recent_events and self.recent_events["DETAIL_RECEIVED"]:
                return True
        
        elif condition_type == "진도속보 수신":
            if "SOKUHOU_RECEIVED" in self.recent_events and self.recent_events["SOKUHOU_RECEIVED"]:
                return True
        
        elif condition_type == "진원정보 수신":
            if "EPICENTER_RECEIVED" in self.recent_events and self.recent_events["EPICENTER_RECEIVED"]:
                return True
        
        # 해일정보 이벤트 조건
        elif condition_type == "해일정보 발표":
            if "TSUNAMI_RECEIVED" in self.recent_events and self.recent_events["TSUNAMI_RECEIVED"]:
                event_data = self.recent_events["TSUNAMI_RECEIVED"][-1]
                if not event_data.get("is_canceled", False):
                    return True
        
        elif condition_type == "해일정보 취소":
            if "TSUNAMI_CANCELED" in self.recent_events and self.recent_events["TSUNAMI_CANCELED"]:
                event_data = self.recent_events["TSUNAMI_CANCELED"][-1]
                if event_data.get("is_canceled", False):
                    return True
        
        return False
    
    def _check_eew_condition(self, params: Dict, event_data: Dict, announcement_type: str) -> bool:
        """EEW 조건 확인"""
        # 발표 유형 확인
        announcement_types = params.get("announcement_types", [])
        if announcement_types and announcement_type not in announcement_types:
            return False
        
        # 진도 필터 확인
        intensity_filter = params.get("intensity_filter", "필터 없음")
        if intensity_filter != "필터 없음":
            max_intensity = event_data.get("max_intensity", "")
            if not self._check_intensity_filter(max_intensity, intensity_filter):
                return False
        
        return True
    
    def _check_intensity_filter(self, max_intensity: str, filter_value: str) -> bool:
        """진도 필터 확인"""
        intensity_map = {
            "1": 1, "2": 2, "3": 3, "4": 4,
            "5-": 5, "5+": 5, "6-": 6, "6+": 6, "7": 7
        }
        
        filter_map = {
            "필터 없음": 0,
            "진도 1 이상": 1,
            "진도 2 이상": 2,
            "진도 3 이상": 3,
            "진도 4 이상": 4,
            "진도 5약 이상": 5,
            "진도 5강 이상": 5,
            "진도 6약 이상": 6,
            "진도 6강 이상": 6,
            "진도 7": 7
        }
        
        event_intensity = intensity_map.get(max_intensity, 0)
        required_intensity = filter_map.get(filter_value, 0)
        
        return event_intensity >= required_intensity
    
    def trigger_event(self, event_type: str, event_data: Dict):
        """외부 이벤트 트리거 (EEW, 지진정보 등)"""
        # 최근 이벤트 기록 (최대 10개 유지)
        if event_type not in self.recent_events:
            self.recent_events[event_type] = []
        self.recent_events[event_type].append(event_data)
        if len(self.recent_events[event_type]) > 10:
            self.recent_events[event_type].pop(0)
        
        # 상태 안정화는 타이머가 담당 (즉시 평가하지 않음)
    
    def save_config(self):
        """
        설정 저장 - 완전 결정적 JSON 구조
        
        [JSON 구조 보장]
        - 모든 상위 플래그에 priority 명시적 저장 (None이면 null)
        - last_state_change_time 저장 (winner 결정에 필수)
        - state 저장 (현재 상태 복원)
        - winner 결정 규칙 메타데이터 포함
        """
        try:
            config = {
                # 메타데이터: winner 결정 규칙 명시
                "metadata": {
                    "version": "2.0",
                    "winner_decision_rules": {
                        "priority_rule": "숫자가 낮을수록 우선순위가 높다 (1 < 2 < 3 < ...)",
                        "null_priority_rule": "priority가 null인 플래그는 모든 숫자 priority보다 항상 낮다",
                        "tie_breaker_rule": "동일 priority면 마지막으로 켜진 플래그 선택",
                        "auto_priority_rule": "priority가 모두 null이면 가장 최근에 켜진 플래그 선택"
                    },
                    "note": "이 JSON만으로 winner 결정이 100% 가능해야 함"
                },
                "upper_flags": [f.to_dict() for f in self.upper_flags.values()],
                "lower_flags": [f.to_dict() for f in self.lower_flags.values()]
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"✅ 플래그 시스템 설정 저장 완료: {self.config_file}")
        except Exception as e:
            print(f"❌ 플래그 시스템 설정 저장 실패: {e}")
    
    def load_config(self):
        """설정 로드"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 상위 플래그 로드
                for flag_data in config.get("upper_flags", []):
                    flag = Flag.from_dict(flag_data)
                    self.add_flag(flag)
                
                # 하위 플래그 로드
                for flag_data in config.get("lower_flags", []):
                    flag = Flag.from_dict(flag_data)
                    self.add_flag(flag)
                
                print(f"✅ 플래그 시스템 설정 로드 완료: {len(self.all_flags)}개 플래그")
            else:
                print("ℹ️ 플래그 시스템 설정 파일이 없습니다. 새로 생성합니다.")
        except Exception as e:
            print(f"❌ 플래그 시스템 설정 로드 실패: {e}")
