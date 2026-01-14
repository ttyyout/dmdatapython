# Winner 결정 보장 문서

## 절대 원칙

이 문서는 플래그 시스템의 winner 결정이 **100% 결정적**임을 보장합니다.

## 1. 단일 결정 지점

**함수**: `StateReflector.decide_upper_flag_winner(active_upper_flags: List[Flag]) -> Optional[Flag]`

- 이 함수만이 winner를 결정합니다.
- 이 함수 외부에서 winner를 결정하는 코드는 존재하지 않습니다.
- 모든 OBS 제어는 이 함수의 결과만 봅니다.

## 2. 결정 알고리즘 (절대 규칙)

### 입력
- `active_upper_flags`: 현재 켜진 상위 플래그 목록 (state == True, flag_type == "upper")

### 처리 단계

1. **입력 검증**
   - 상위 플래그만 허용 (flag_type == "upper")
   - state == True인 플래그만 대상

2. **Priority 분리**
   - priority가 숫자로 지정된 플래그
   - priority가 null(자동)인 플래그

3. **Winner 결정 규칙**
   - **숫자 priority 플래그가 하나라도 있으면**
     → priority 값이 가장 낮은 플래그 1개만 선택
     → 동일 priority면 마지막으로 켜진 플래그 선택 (last_state_change_time 기준)
   - **숫자 priority 플래그가 없고 null 플래그만 있다면**
     → 가장 최근에 ON 된 플래그 1개 선택 (last_state_change_time 기준)
   - **켜진 상위 플래그가 하나도 없다면**
     → None 반환 (기본 상태 적용)

### 출력
- 선택된 winner 플래그 (단 하나만)
- 없으면 None

## 3. Priority 해석 규칙

- **숫자가 낮을수록 우선순위가 높다** (1 < 2 < 3 < ...)
- **priority가 null인 플래그는 모든 숫자 priority보다 항상 낮다**
- **동일 priority면 마지막으로 켜진 플래그 선택** (last_state_change_time 기준)

## 4. 시나리오 보장

### 시나리오 1: 일본 EEW → 대만 EEW → 일본 EEW 종료

1. 일본 EEW 발생 (priority=1)
2. 5초 후 대만 EEW 발생 (priority=2)
3. 일본 EEW 종료 이벤트 도착

**결과 보장**: 
- 대만 EEW가 여전히 켜져 있으면 winner는 대만 EEW
- **절대 기본 화면으로 돌아가지 않음**
- `_apply_default_state()`는 실행되지 않음

### 시나리오 2: EEW 없이 진도속보 → 각지진도정보 → 하위 플래그 종료

1. 진도속보 발생 (상위 플래그 A 켜짐)
2. 각지진도정보 발생 (상위 플래그 B 켜짐)
3. 하위 플래그 종료

**결과 보장**:
- 상위 플래그 A, B가 여전히 켜져 있으면 winner는 그 중 하나
- **상위 맥락이 유지됨**
- 하위 플래그 종료는 상위 플래그에 영향을 주지 않음

## 5. JSON 구조 보장

`flag_system.json`은 다음 정보를 포함하여 **winner 결정이 100% 가능**합니다:

- `priority`: 명시적 저장 (None이면 null)
- `last_state_change_time`: winner 결정에 필수
- `state`: 현재 상태
- `type`: "upper" 또는 "lower" 명시
- `metadata.winner_decision_rules`: 결정 규칙 메타데이터

## 6. 구조적 보장

### OBS 제어 중앙화
- **모든 OBS 제어는 `state_reflector.py`에서만 수행됩니다**
- 다른 파일에서 OBS 웹소켓을 호출하는 코드는 존재하지 않습니다

### 플래그 시스템
- 플래그는 **상태 변수**일 뿐입니다
- 플래그는 OBS API를 직접 호출하지 않습니다
- 플래그의 `on_actions`/`off_actions`는 정보 저장용이며, 여기서 실행되지 않습니다

### OFF 이벤트 처리
- 플래그가 꺼질 때 `off_actions`를 즉시 실행하지 않습니다
- 반드시 전체 상태를 다시 계산하여 새로운 winner를 선택합니다
- 더 높은 우선순위 플래그가 켜져 있으면 OBS 상태는 절대 변경되지 않습니다

## 7. 완성 판정 기준

다음 문장이 코드 수준에서 항상 참입니다:

> "여러 상위 플래그가 동시에 켜져 있어도, 항상 priority 규칙에 따라 단 하나의 OBS 상태만 유지되며, 어떤 플래그가 꺼져도 더 높은 우선순위 상태는 절대 깨지지 않는다."


