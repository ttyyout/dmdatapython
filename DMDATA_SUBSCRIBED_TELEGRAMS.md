# DMDATA 구독 전문 구조 문서

## 구독한 전문 구분

1. **緊急地震（予報）区分** (긴급지진속보 예보 구분)
   - VXSE44: 緊急地震速報（予報） - 예보
   - VXSE45: 緊急地震速報（警報） - 경보 (예보 구분에 포함)
   - VXSE42: 緊急地震速報テスト - 테스트 (무시)

2. **地震・津波関連 区分** (지진・해일 관련 구분)
   - VXSE51: 震度速報 (진도속보)
   - VXSE52: 震源に関する情報 (진원정보)
   - VXSE53: 震源・震度に関する情報 (진원진도정보)
   - VTSE41: 津波警報・注意報・予報 (해일 경보・주의보・예보)

## 각 전문의 구조 (DMDATA 매뉴얼 기준)

### 1. VXSE44 / VXSE45 (긴급지진속보)

**매뉴얼**: https://dmdata.jp/docs/manual/earthquake/

**JSON 구조**:
```json
{
  "eventId": "이벤트 ID",
  "serialNo": "시리얼 번호",
  "body": {
    "isWarning": true/false,  // true=경보, false=예보
    "isCanceled": true/false,  // 취소 여부
    "isLastInfo": true/false,  // 최종보 여부
    "earthquake": {
      "hypocenter": {
        "code": "지역 코드",
        "name": "지역명",
        "depth": {
          "value": 깊이값
        }
      },
      "magnitude": {
        "value": "규모값"
      },
      "originTime": "발생 시각"
    },
    "intensity": {
      "forecastMaxInt": {
        "from": "최소 진도",
        "to": "최대 진도"
      }
    }
  }
}
```

**처리 로직**:
- `body.isWarning`: 경보(true) 또는 예보(false) 구분
- `body.isCanceled`: 취소 여부
- `body.isLastInfo`: 최종보 여부
- VXSE44와 VXSE45는 동일한 구조로 처리

### 2. VXSE51 (진도속보)

**매뉴얼**: https://dmdata.jp/docs/manual/intensity/

**JSON 구조**:
```json
{
  "eventId": "이벤트 ID",
  "body": {
    "earthquakes": [
      {
        "eventId": "이벤트 ID",
        "originTime": "발생 시각",
        ...
      }
    ],
    "tsunami": {  // 선택적: 해일정보가 포함된 경우
      "forecasts": [...]
    },
    "lpgm": {...}  // 선택적: 장주기지진동 정보
  }
}
```

**처리 로직**:
- `report_type`: "sokuhou"
- 해일정보 포함 여부: `body.tsunami.forecasts` 배열 확인

### 3. VXSE52 (진원정보)

**매뉴얼**: https://dmdata.jp/docs/manual/hypocenter/

**JSON 구조**:
```json
{
  "eventId": "이벤트 ID",
  "body": {
    "earthquakes": [
      {
        "eventId": "이벤트 ID",
        "hypocenter": {...},
        "magnitude": {...}
      }
    ],
    "tsunami": {...},  // 선택적
    "lpgm": {...}  // 선택적
  }
}
```

**처리 로직**:
- `report_type`: "epicenter"
- 기존 진원정보 업데이트 여부 확인 필요

### 4. VXSE53 (진원진도정보)

**매뉴얼**: https://dmdata.jp/docs/manual/hypocenter/

**JSON 구조**:
```json
{
  "eventId": "이벤트 ID",
  "body": {
    "earthquakes": [
      {
        "eventId": "이벤트 ID",
        "hypocenter": {...},
        "magnitude": {...},
        "intensity": {...}
      }
    ],
    "tsunami": {...},  // 선택적
    "lpgm": {...}  // 선택적
  }
}
```

**처리 로직**:
- `report_type`: "detail"
- 진원정보와 진도정보를 모두 포함

### 5. VTSE41 (해일정보)

**매뉴얼**: https://dmdata.jp/docs/manual/tsunami/

**JSON 구조**:
```json
{
  "eventId": "이벤트 ID",
  "body": {
    "earthquakes": [
      {
        "eventId": "관련 지진 이벤트 ID"
      }
    ],
    "tsunami": {
      "forecasts": [
        {
          "grade": "Major Tsunami Warning" | "Tsunami Warning" | "Tsunami Advisory" | "Tsunami Forecast",
          "area": {
            "name": "지역명",
            "code": "지역 코드"
          },
          "firstHeight": {
            "arrivalTime": "도달 예상 시각",
            "condition": "조건"
          },
          "maxHeight": {
            "value": "최대 높이",
            "condition": "조건"
          }
        }
      ]
    }
  }
}
```

**처리 로직**:
- **해일정보 발표**: `body.tsunami.forecasts` 배열에 항목이 있는 경우
- **해일정보 해제**: `body.tsunami.forecasts` 배열이 비어있는 경우
- 관련 지진의 Event ID 사용: `body.earthquakes[0].eventId`

## 현재 코드의 처리 방식

### 해일정보 감지 (VTSE41)
```python
tsunami = body_main.get("tsunami", {})
forecasts = tsunami.get("forecasts", [])
is_canceled = len(forecasts) == 0  # forecasts가 비어있으면 해제
```

### 지진상세정보의 해일정보 포함 여부
```python
tsunami = body_main.get("tsunami", {})
has_tsunami = bool(tsunami) and len(tsunami.get("forecasts", [])) > 0
```

### EEW 처리
```python
is_warning = body_main.get("isWarning", False)  # 경보/예보 구분
is_canceled = body_main.get("isCanceled", False)
is_last_info = body_main.get("isLastInfo", False)
```

## 개선 사항

1. **상세 로깅 추가**: 실제 수신 데이터 구조를 상세히 로깅하여 정확한 구조 확인
2. **VXSE44 처리 추가**: 예보 구분에 포함되므로 VXSE45와 동일하게 처리
3. **해일정보 해제 판단 개선**: forecasts 배열이 비어있으면 해제로 판단 (매뉴얼 기준)

## 참고 링크

- DMDATA 매뉴얼: https://dmdata.jp/docs/manual/
- 긴급지진속보: https://dmdata.jp/docs/manual/earthquake/
- 해일정보: https://dmdata.jp/docs/manual/tsunami/
- 진도속보: https://dmdata.jp/docs/manual/intensity/
- 진원정보: https://dmdata.jp/docs/manual/hypocenter/

