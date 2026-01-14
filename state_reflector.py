"""
상태 반영기 - 플래그 상태 스냅샷을 읽어서 OBS 제어 실행
플래그 평가와 완전히 분리된 독립 모듈
중앙 winner 선택 기반 OBS 제어

[절대 원칙 - 위반 불가]
1. OBS 제어는 이 파일(state_reflector.py)에서만 이루어진다.
2. 플래그는 "명령"이 아니라 "상태"다.
3. OBS 상태 = f(현재 켜진 상위 플래그들, priority 규칙)

[구조적 보장]
- 이 파일 외부에서 OBS 웹소켓을 호출하는 코드는 존재하지 않는다.
- 플래그 on/off 이벤트는 OBS를 직접 제어하지 않는다.
- winner 결정 알고리즘은 결정적이며 항상 동일한 결과를 보장한다.
"""
from typing import Dict, Optional, List
from PySide6.QtCore import QObject, QTimer
from flag_system import FlagSystem, Flag, FlagAction
import time

class StateReflector(QObject):
    """
    상태 반영기 - 플래그 상태 스냅샷을 읽어서 OBS 제어
    
    핵심 원칙:
    1. 플래그가 켜지거나 꺼질 때 OBS를 직접 제어하지 않음
    2. 현재 켜진 상위 플래그 중 priority 기반으로 단일 winner 선택
    3. 오직 winner의 상태만 OBS에 반영
    4. winner가 없으면 기본 상태 적용 (또는 아무것도 하지 않음)
    """
    
    def __init__(self, flag_system: FlagSystem, obs_controller):
        super().__init__()
        self.flag_system = flag_system
        self.obs_controller = obs_controller
        
        # 이전 상태 스냅샷 (변화 감지용)
        self.previous_state: Dict[str, bool] = {}
        
        # 현재 적용된 winner (변화 감지용)
        self.current_winner: Optional[Flag] = None
        
        # 현재 적용된 장면/녹화/버퍼 상태 (중복 실행 방지용)
        self.current_scene: Optional[str] = None
        self.current_recording_state: Optional[bool] = None
        
        # 기본 상태 (winner가 없을 때 사용)
        self.default_scene: Optional[str] = None
        self.default_recording_state: Optional[bool] = None
        
        # 상태 반영 타이머 (플래그 평가 후 실행)
        self.reflection_timer = QTimer()
        self.reflection_timer.timeout.connect(self.reflect_state)
        self.reflection_timer.start(150)  # 플래그 평가(100ms)보다 약간 늦게 실행
    
    def reflect_state(self):
        """플래그 상태를 읽어서 OBS 제어 실행"""
        if not self.flag_system or not self.obs_controller:
            return
        
        # 현재 플래그 상태 스냅샷 가져오기
        current_state = self.flag_system.get_all_flags_state()
        
        # 상위 플래그 처리 (중앙 winner 선택 기반)
        self._reflect_upper_flags()
        
        # 하위 플래그 처리
        self._reflect_lower_flags(current_state)
        
        # 이전 상태 업데이트
        self.previous_state = current_state.copy()
    
    def _reflect_upper_flags(self):
        """
        상위 플래그 상태 반영 (중앙 winner 선택 기반)
        
        [절대 원칙]
        1. 플래그가 켜지거나 꺼질 때 OBS를 직접 제어하지 않음
        2. 현재 켜진 모든 상위 플래그를 기반으로 단일 winner 선택
        3. winner가 있으면 winner의 on_actions만 실행
        4. winner가 없으면 기본 상태 적용
        
        [OFF 이벤트 처리의 절대 규칙]
        - 어떤 상위 플래그가 OFF 되더라도 OBS를 즉시 변경하지 않는다.
        - 반드시 전체 상태를 다시 계산한다.
        - 더 높은 우선순위의 상위 플래그가 하나라도 ON 상태라면
          OBS 상태는 절대 변경되지 않는다.
        
        [구조적 보장]
        - 이 함수는 플래그 상태 변화와 무관하게 항상 현재 상태를 기준으로 winner를 재계산합니다.
        - 플래그의 off_actions는 절대 즉시 실행되지 않습니다.
        - winner가 변경되었을 때만 OBS 제어가 실행됩니다.
        """
        # 1단계: 중앙 winner 선택 (현재 켜진 플래그 기준)
        winner = self._select_winner()
        
        # 2단계: winner가 변경되었는지 확인
        winner_changed = (winner is not None and self.current_winner is None) or \
                        (winner is None and self.current_winner is not None) or \
                        (winner is not None and self.current_winner is not None and 
                         winner.flag_id != self.current_winner.flag_id)
        
        if not winner_changed and winner is not None:
            # winner가 변경되지 않았으면 스킵 (중복 실행 방지)
            return
        
        # 3단계: winner가 변경되었거나 사라졌을 때만 OBS 제어 실행
        if winner_changed:
            if winner:
                # winner가 있으면 winner의 액션 실행
                # 이전 winner의 상태는 자동으로 덮어씌워짐
                self._apply_winner_actions(winner)
            else:
                # winner가 없으면 기본 상태 적용
                self._apply_default_state()
        
        # 4단계: 현재 winner 업데이트
        self.current_winner = winner
    
    def _select_winner(self) -> Optional[Flag]:
        """
        중앙 winner 선택 로직 - 결정적 알고리즘
        
        [절대 규칙 - 이 알고리즘은 정확히 이대로 동작해야 함]
        
        1단계: 현재 켜진 모든 상위 플래그만 수집
           - is_upper == true 인 플래그만 대상
        
        2단계: priority가 지정된 플래그와 null인 플래그를 분리
           - priority가 숫자로 지정된 플래그
           - priority가 null(자동)인 플래그
        
        3단계: priority 해석 규칙
           - 숫자가 낮을수록 우선순위가 높다 (1 < 2 < 3 < ...)
           - priority가 null인 플래그는 모든 숫자 priority보다 항상 낮다
        
        4단계: winner 결정 규칙
           - 숫자 priority 플래그가 하나라도 있으면
             → priority 값이 가장 낮은 플래그 1개만 선택
             → 동일 priority면 마지막으로 켜진 플래그 선택
           - 숫자 priority 플래그가 없고 null 플래그만 있다면
             → 가장 최근에 ON 된 플래그 1개 선택
           - 켜진 상위 플래그가 하나도 없다면
             → None 반환 (기본 상태 적용)
        
        [구조적 보장]
        - 이 함수는 항상 동일한 입력에 대해 동일한 결과를 반환한다.
        - winner는 항상 단 하나만 선택된다.
        - 하위 플래그는 이 함수에서 절대 선택되지 않는다.
        
        Returns:
            선택된 winner 플래그, 없으면 None
        """
        # 1단계: 현재 켜진 모든 상위 플래그만 수집
        active_flags = [f for f in self.flag_system.upper_flags.values() if f.state]
        
        if not active_flags:
            # 켜진 상위 플래그가 없으면 None 반환
            return None
        
        # 2단계: priority가 지정된 플래그와 null인 플래그를 분리
        priority_flags = [f for f in active_flags if f.priority is not None]
        null_flags = [f for f in active_flags if f.priority is None]
        
        # 3-4단계: winner 결정
        if priority_flags:
            # priority가 지정된 플래그가 하나 이상이면
            # priority가 가장 낮은 숫자의 플래그 선택 (낮은 숫자 = 높은 우선순위)
            # 동일 priority면 마지막으로 켜진 플래그 선택
            priority_flags.sort(key=lambda f: (
                f.priority,  # 낮은 숫자 우선
                -(f.last_state_change_time if f.last_state_change_time else 0)  # 최신순 (음수로 reverse 효과)
            ))
            return priority_flags[0]
        else:
            # priority 지정 플래그가 없고 null 플래그만 있다면
            # 가장 최근에 켜진 플래그 선택
            null_flags.sort(key=lambda f: f.last_state_change_time if f.last_state_change_time else 0, reverse=True)
            return null_flags[0] if null_flags else None
    
    def _apply_winner_actions(self, winner: Flag):
        """
        winner의 액션을 OBS에 적용
        
        각 리소스(장면/녹화/버퍼)별로 winner의 액션만 실행
        """
        # winner의 모든 on_actions 실행
        for action in winner.on_actions:
            self._execute_upper_action(action, winner)
    
    def _apply_default_state(self):
        """
        기본 상태 적용 (winner가 없을 때)
        
        현재는 아무것도 하지 않지만, 필요시 기본 장면으로 전환 등의 로직 추가 가능
        """
        # 기본 상태 적용 로직 (필요시 구현)
        # 예: self.obs_controller.switch_scene(self.default_scene)
        pass
    
    def _resolve_conflict(self, conflicting_flags: List[Flag]) -> Optional[Flag]:
        """
        [사용 중단] 충돌 해결: 우선순위 기반
        
        이 메서드는 더 이상 사용되지 않습니다.
        대신 _select_winner()를 사용하세요.
        """
        if not conflicting_flags:
            return None
        
        # priority가 설정된 플래그가 하나라도 있는지 확인
        has_priority = any(f.priority is not None for f in conflicting_flags)
        
        if has_priority:
            # priority 낮은 순으로 정렬 (낮은 숫자 = 높은 우선순위)
            # 동일 priority면 마지막으로 켜진 플래그가 우선
            conflicting_flags.sort(key=lambda f: (
                f.priority if f.priority is not None else 999999,  # null은 가장 낮은 우선순위
                -(f.last_state_change_time if f.last_state_change_time else 0)  # 최신순 (음수로 reverse 효과)
            ))
        else:
            # priority가 모두 null이면 가장 최근에 켜진 플래그
            conflicting_flags.sort(key=lambda f: f.last_state_change_time if f.last_state_change_time else 0, reverse=True)
        
        return conflicting_flags[0]
    
    def _reflect_lower_flags(self, current_state: Dict[str, bool]):
        """하위 플래그 상태 반영"""
        for flag_id, is_active in current_state.items():
            flag = self.flag_system.get_flag(flag_id)
            if not flag or flag.flag_type != "lower":
                continue
            
            # 상태 변화 확인
            was_active = self.previous_state.get(flag_id, False)
            
            if is_active != was_active:
                # 상태 변화 발생
                actions = flag.on_actions if is_active else flag.off_actions
                for action in actions:
                    self._execute_lower_action(action, flag, is_active)
    
    def _execute_upper_action(self, action: FlagAction, flag: Flag):
        """
        상위 플래그 동작 실행
        
        winner의 액션만 실행되므로, 중복 실행 방지를 위한 체크 포함
        """
        action_type = action.action_type
        params = action.params
        
        if action_type == "아무 것도 하지 않기" or action_type == "none":
            return
        
        try:
            if action_type == "장면 전환":
                scene_name = params.get("scene_name")
                if scene_name and self.obs_controller:
                    # 중복 실행 방지: 현재 장면과 다를 때만 실행
                    if self.current_scene != scene_name:
                        self.obs_controller.switch_scene(scene_name)
                        self.current_scene = scene_name
                        print(f"✅ [상태 반영] Winner '{flag.name}' → 장면 전환: {scene_name}")
            
            elif action_type == "녹화 시작":
                if self.obs_controller and hasattr(self.obs_controller, 'start_recording'):
                    # 중복 실행 방지: 현재 녹화 상태가 False일 때만 실행
                    if self.current_recording_state != True:
                        self.obs_controller.start_recording()
                        self.current_recording_state = True
                        print(f"✅ [상태 반영] Winner '{flag.name}' → 녹화 시작")
            
            elif action_type == "녹화 중지":
                if self.obs_controller and hasattr(self.obs_controller, 'stop_recording'):
                    # 중복 실행 방지: 현재 녹화 상태가 True일 때만 실행
                    if self.current_recording_state != False:
                        self.obs_controller.stop_recording()
                        self.current_recording_state = False
                        print(f"✅ [상태 반영] Winner '{flag.name}' → 녹화 중지")
            
            elif action_type == "버퍼 저장":
                if self.obs_controller and hasattr(self.obs_controller, 'save_replay_buffer'):
                    # 버퍼 저장은 중복 실행 가능 (의도된 동작)
                    self.obs_controller.save_replay_buffer()
                    print(f"✅ [상태 반영] Winner '{flag.name}' → 버퍼 저장")
        
        except Exception as e:
            print(f"❌ [상태 반영] 플래그 동작 실행 실패: {e}")
    
    def _execute_lower_action(self, action: FlagAction, flag: Flag, is_active: bool):
        """
        하위 플래그 동작 실행
        
        하위 플래그는 OBS 전체 상태를 절대 직접 변경하지 않습니다.
        하위 플래그가 수행할 수 있는 동작:
        - 소스 표시 / 숨김
        - 필터 활성 / 비활성
        
        하위 플래그가 수행할 수 없는 동작 (상위 플래그 전용):
        - 장면 전환
        - 녹화 시작 / 중지
        - 버퍼 저장
        """
        action_type = action.action_type
        params = action.params
        
        if action_type == "아무 것도 하지 않기" or action_type == "none":
            return
        
        try:
            if action_type == "소스 표시":
                scene_name = params.get("scene_name")
                item_id = params.get("item_id")
                invert = params.get("invert", False)  # 상태 반전 옵션
                visible = not invert if is_active else invert
                
                if scene_name and item_id is not None and self.obs_controller:
                    self.obs_controller._set_scene_item_visible(scene_name, item_id, visible)
                    print(f"✅ [상태 반영] 플래그 '{flag.name}' → 소스 {'표시' if visible else '숨김'}: {scene_name}/{item_id}")
            
            elif action_type == "소스 숨김":
                scene_name = params.get("scene_name")
                item_id = params.get("item_id")
                invert = params.get("invert", False)  # 상태 반전 옵션
                visible = invert if is_active else not invert
                
                if scene_name and item_id is not None and self.obs_controller:
                    self.obs_controller._set_scene_item_visible(scene_name, item_id, visible)
                    print(f"✅ [상태 반영] 플래그 '{flag.name}' → 소스 {'표시' if visible else '숨김'}: {scene_name}/{item_id}")
            
            elif action_type == "필터 활성화":
                source_name = params.get("source_name")
                filter_name = params.get("filter_name")
                if source_name and filter_name and self.obs_controller:
                    self.obs_controller.set_source_filter_enabled(source_name, filter_name, True)
                    print(f"✅ [상태 반영] 플래그 '{flag.name}' → 필터 활성화: {source_name}/{filter_name}")
            
            elif action_type == "필터 비활성화":
                source_name = params.get("source_name")
                filter_name = params.get("filter_name")
                if source_name and filter_name and self.obs_controller:
                    self.obs_controller.set_source_filter_enabled(source_name, filter_name, False)
                    print(f"✅ [상태 반영] 플래그 '{flag.name}' → 필터 비활성화: {source_name}/{filter_name}")
        
        except Exception as e:
            print(f"❌ [상태 반영] 플래그 동작 실행 실패: {e}")
