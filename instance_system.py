"""
지진 인스턴스 시스템
- 지진 인스턴스의 생성/종료를 관리
- Event ID 기반으로 인스턴스 추적
- 여러 인스턴스 동시 존재 가능
"""
import json
import os
import time
from typing import Dict, List, Optional, Any, Set
from PySide6.QtCore import QObject, QTimer, Signal
from flag_system import FlagCondition

class EarthquakeInstance:
    """지진 인스턴스 - Event ID 기반으로 관리"""
    def __init__(self, instance_id: str, instance_type: str, event_id: str, created_at: float):
        self.instance_id = instance_id  # 인스턴스 고유 ID
        self.instance_type = instance_type  # 인스턴스 종류 (예: "일본 지진", "대만 지진", "해일")
        self.event_id = event_id  # Event ID (DMDATA에서 받은 eventId)
        self.created_at = created_at  # 생성 시간
        self.is_active = True  # 활성 상태
        self.ended_at: Optional[float] = None  # 종료 시간
    
    def end(self, ended_at: float):
        """인스턴스 종료"""
        self.is_active = False
        self.ended_at = ended_at
    
    def to_dict(self):
        """JSON 직렬화"""
        return {
            "instance_id": self.instance_id,
            "instance_type": self.instance_type,
            "event_id": self.event_id,
            "created_at": self.created_at,
            "is_active": self.is_active,
            "ended_at": self.ended_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """JSON 역직렬화"""
        instance = cls(
            data["instance_id"],
            data["instance_type"],
            data["event_id"],
            data["created_at"]
        )
        instance.is_active = data.get("is_active", True)
        instance.ended_at = data.get("ended_at")
        return instance

class InstanceTypeConfig:
    """인스턴스 종류 설정"""
    def __init__(self, type_id: str, name: str):
        self.type_id = type_id  # 종류 ID (예: "japan_earthquake")
        self.name = name  # 종류 이름 (예: "일본 지진")
        
        # 생성 조건 (OR 관계: 하나라도 만족하면 생성)
        self.create_conditions: List[FlagCondition] = []
        
        # 종료 조건 (OR 관계: 하나라도 만족하면 종료)
        self.end_conditions: List[FlagCondition] = []
    
    def to_dict(self):
        """JSON 직렬화"""
        return {
            "type_id": self.type_id,
            "name": self.name,
            "create_conditions": [c.to_dict() for c in self.create_conditions],
            "end_conditions": [c.to_dict() for c in self.end_conditions]
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """JSON 역직렬화"""
        config = cls(data["type_id"], data["name"])
        config.create_conditions = [
            FlagCondition.from_dict(c) for c in data.get("create_conditions", [])
        ]
        config.end_conditions = [
            FlagCondition.from_dict(c) for c in data.get("end_conditions", [])
        ]
        return config

class EarthquakeActiveConfig:
    """EARTHQUAKE_ACTIVE 설정"""
    def __init__(self, active_id: str, name: str):
        self.active_id = active_id  # EARTHQUAKE_ACTIVE ID
        self.name = name  # 이름 (예: "일본 지진 활성")
        
        # 집계할 인스턴스 종류 목록 (OR 관계: 하나라도 활성이면 ON)
        self.aggregated_instance_types: List[str] = []  # instance_type_id 목록
    
    def to_dict(self):
        """JSON 직렬화"""
        return {
            "active_id": self.active_id,
            "name": self.name,
            "aggregated_instance_types": self.aggregated_instance_types
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """JSON 역직렬화"""
        config = cls(data["active_id"], data["name"])
        config.aggregated_instance_types = data.get("aggregated_instance_types", [])
        return config

class InstanceSystem(QObject):
    """지진 인스턴스 시스템"""
    instance_created = Signal(str, str)  # instance_id, instance_type
    instance_ended = Signal(str)  # instance_id
    active_state_changed = Signal(str, bool)  # active_id, new_state
    
    def __init__(self, flag_system=None):
        super().__init__()
        self.flag_system = flag_system
        
        # 인스턴스 종류 설정
        self.instance_types: Dict[str, InstanceTypeConfig] = {}  # {type_id: InstanceTypeConfig}
        
        # EARTHQUAKE_ACTIVE 설정
        self.active_configs: Dict[str, EarthquakeActiveConfig] = {}  # {active_id: EarthquakeActiveConfig}
        
        # 활성 인스턴스 (Event ID 기준)
        self.instances: Dict[str, EarthquakeInstance] = {}  # {instance_id: EarthquakeInstance}
        
        # Event ID -> Instance ID 매핑 (같은 Event ID로 여러 인스턴스 생성 방지)
        self.event_to_instance: Dict[str, str] = {}  # {event_id: instance_id}
        
        # EARTHQUAKE_ACTIVE 상태
        self.active_states: Dict[str, bool] = {}  # {active_id: bool}
        
        # 최근 이벤트 기록 (조건 확인용)
        self.recent_events: Dict[str, List[Dict]] = {}
        
        # 상태 안정화 타이머
        self.stabilization_timer = QTimer()
        self.stabilization_timer.timeout.connect(self._stabilize_state)
        self.stabilization_timer.start(100)  # 100ms마다 안정화
        
        # 설정 파일 경로
        self.config_file = "instance_system.json"
        
        # 로드
        self.load_config()
    
    def add_instance_type(self, config: InstanceTypeConfig):
        """인스턴스 종류 추가"""
        self.instance_types[config.type_id] = config
    
    def remove_instance_type(self, type_id: str):
        """인스턴스 종류 제거"""
        if type_id in self.instance_types:
            del self.instance_types[type_id]
    
    def add_active_config(self, config: EarthquakeActiveConfig):
        """EARTHQUAKE_ACTIVE 설정 추가"""
        self.active_configs[config.active_id] = config
        self.active_states[config.active_id] = False
    
    def remove_active_config(self, active_id: str):
        """EARTHQUAKE_ACTIVE 설정 제거"""
        if active_id in self.active_configs:
            del self.active_configs[active_id]
        if active_id in self.active_states:
            del self.active_states[active_id]
    
    def trigger_event(self, event_type: str, event_data: Dict):
        """외부 이벤트 트리거 (EEW, 지진정보 등)"""
        import time
        # 타임스탬프 추가
        event_data_with_timestamp = event_data.copy()
        event_data_with_timestamp["_timestamp"] = time.time()
        
        # 최근 이벤트 기록 (최대 10개 유지)
        if event_type not in self.recent_events:
            self.recent_events[event_type] = []
        self.recent_events[event_type].append(event_data_with_timestamp)
        if len(self.recent_events[event_type]) > 10:
            self.recent_events[event_type].pop(0)
        
        # flag_system에도 이벤트 전달 (하위 플래그 조건 평가용)
        if self.flag_system:
            self.flag_system.trigger_event(event_type, event_data)
    
    def _stabilize_state(self):
        """상태 안정화 엔진"""
        current_time = time.time()
        
        # 1단계: 인스턴스 생성 조건 확인
        for type_id, type_config in self.instance_types.items():
            # 생성 조건 확인 (OR: 하나라도 만족하면 생성)
            should_create = False
            event_id = None
            
            for condition in type_config.create_conditions:
                if self._check_condition(condition, None):
                    # 이벤트 데이터에서 event_id 추출
                    event_id = self._extract_event_id_from_recent_events()
                    if event_id:
                        should_create = True
                        break
            
            # 인스턴스 생성 (같은 event_id로 이미 생성된 경우 제외)
            if should_create and event_id:
                # 같은 event_id로 이미 생성된 인스턴스가 있는지 확인
                existing_instance_id = self.event_to_instance.get(event_id)
                if existing_instance_id:
                    # 이미 존재하는 인스턴스가 활성 상태인지 확인
                    existing_instance = self.instances.get(existing_instance_id)
                    if existing_instance and existing_instance.is_active:
                        # 이미 활성 인스턴스가 있으면 생성하지 않음
                        continue
                
                # 새 인스턴스 생성
                instance_id = f"{type_id}_{event_id}_{int(current_time * 1000)}"
                instance = EarthquakeInstance(
                    instance_id, type_id, event_id, current_time
                )
                self.instances[instance_id] = instance
                self.event_to_instance[event_id] = instance_id
                self.instance_created.emit(instance_id, type_id)
                print(f"✅ 인스턴스 생성: {instance_id} (종류: {type_config.name}, Event ID: {event_id})")
        
        # 2단계: 인스턴스 종료 조건 확인
        for instance_id, instance in list(self.instances.items()):
            if not instance.is_active:
                continue
            
            type_config = self.instance_types.get(instance.instance_type)
            if not type_config:
                continue
            
            # 종료 조건 확인 (OR: 하나라도 만족하면 종료)
            should_end = False
            for condition in type_config.end_conditions:
                if self._check_condition(condition, instance):
                    should_end = True
                    break
            
            if should_end:
                instance.end(current_time)
                # event_to_instance에서 제거하지 않음 (같은 event_id로 재생성 방지)
                self.instance_ended.emit(instance_id)
                print(f"✅ 인스턴스 종료: {instance_id} (종류: {type_config.name}, Event ID: {instance.event_id})")
        
        # 3단계: EARTHQUAKE_ACTIVE 상태 업데이트
        self._update_active_states()
    
    def _update_active_states(self):
        """EARTHQUAKE_ACTIVE 상태 업데이트"""
        for active_id, active_config in self.active_configs.items():
            # 집계할 인스턴스 종류 중 하나라도 활성 인스턴스가 있으면 ON
            has_active = False
            for instance_type_id in active_config.aggregated_instance_types:
                # 이 종류의 활성 인스턴스가 있는지 확인
                for instance in self.instances.values():
                    if (instance.instance_type == instance_type_id and 
                        instance.is_active):
                        has_active = True
                        break
                if has_active:
                    break
            
            # 상태 변경 감지
            old_state = self.active_states.get(active_id, False)
            if old_state != has_active:
                self.active_states[active_id] = has_active
                self.active_state_changed.emit(active_id, has_active)
                print(f"🔄 EARTHQUAKE_ACTIVE 상태 변경: {active_id} = {has_active}")
    
    def _check_condition(self, condition: FlagCondition, instance: Optional[EarthquakeInstance]) -> bool:
        """조건 확인 (FlagCondition과 동일한 로직)"""
        condition_type = condition.condition_type
        params = condition.params
        
        # EEW 이벤트 조건
        if condition_type == "EEW 신규 발표":
            if "EEW_STARTED" in self.recent_events and self.recent_events["EEW_STARTED"]:
                event_data = self.recent_events["EEW_STARTED"][-1]
                if event_data.get("is_new", False):
                    return self._check_eew_condition(params, event_data, "신규 발표")
        
        elif condition_type == "EEW 속보 발표":
            if "EEW_UPDATED" in self.recent_events and self.recent_events["EEW_UPDATED"]:
                event_data = self.recent_events["EEW_UPDATED"][-1]
                if not event_data.get("is_new", False):
                    return self._check_eew_condition(params, event_data, "속보 발표")
        
        elif condition_type == "EEW 취소보":
            if "EEW_CANCELED" in self.recent_events and self.recent_events["EEW_CANCELED"]:
                event_data = self.recent_events["EEW_CANCELED"][-1]
                if event_data.get("is_canceled", False):
                    return self._check_eew_condition(params, event_data, "취소보")
        
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
        
        # 무감지진 조건 (추가)
        elif condition_type == "무감지진":
            # 무감지진은 특별 처리 (추후 구현)
            return False
        
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
    
    def _extract_event_id_from_recent_events(self) -> Optional[str]:
        """최근 이벤트에서 event_id 추출"""
        # 최신 이벤트에서 event_id 찾기
        for event_type, events in self.recent_events.items():
            if events:
                latest_event = events[-1]
                event_id = latest_event.get("event_id")
                if event_id:
                    return event_id
        return None
    
    def is_active_instance(self, instance_id: str) -> bool:
        """인스턴스 활성 상태 확인"""
        instance = self.instances.get(instance_id)
        return instance.is_active if instance else False
    
    def get_active_instances_by_type(self, instance_type: str) -> List[EarthquakeInstance]:
        """특정 종류의 활성 인스턴스 목록 반환"""
        return [
            instance for instance in self.instances.values()
            if instance.instance_type == instance_type and instance.is_active
        ]
    
    def get_active_state(self, active_id: str) -> bool:
        """EARTHQUAKE_ACTIVE 상태 확인"""
        return self.active_states.get(active_id, False)
    
    def save_config(self):
        """설정 저장"""
        try:
            config = {
                "metadata": {
                    "version": "1.0",
                    "note": "지진 인스턴스 시스템 설정"
                },
                "instance_types": [t.to_dict() for t in self.instance_types.values()],
                "active_configs": [a.to_dict() for a in self.active_configs.values()]
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"✅ 인스턴스 시스템 설정 저장 완료: {self.config_file}")
        except Exception as e:
            print(f"❌ 인스턴스 시스템 설정 저장 실패: {e}")
    
    def load_config(self):
        """설정 로드"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 인스턴스 종류 로드
                for type_data in config.get("instance_types", []):
                    type_config = InstanceTypeConfig.from_dict(type_data)
                    self.add_instance_type(type_config)
                
                # EARTHQUAKE_ACTIVE 설정 로드
                for active_data in config.get("active_configs", []):
                    active_config = EarthquakeActiveConfig.from_dict(active_data)
                    self.add_active_config(active_config)
                
                print(f"✅ 인스턴스 시스템 설정 로드 완료: {len(self.instance_types)}개 종류, {len(self.active_configs)}개 EARTHQUAKE_ACTIVE")
            else:
                print("ℹ️ 인스턴스 시스템 설정 파일이 없습니다. 새로 생성합니다.")
        except Exception as e:
            print(f"❌ 인스턴스 시스템 설정 로드 실패: {e}")

