# 문장 제안 에이전트 설계

---

## 1. 기능 목적

사용자가 연습할 목표 문장을 입력하면, 해당 문장의 어조를 분석하고 문법을 교정한 뒤,
나머지 두 가지 어조(formal / neutral / informal)로 변환한 문장을 함께 제안합니다.

사용자는 본인이 원래 연습하려 했던 문장뿐만 아니라,
같은 내용을 다른 맥락에서 어떻게 표현하는지도 함께 익힐 수 있습니다.

---

## 2. 왜 LangGraph인가

발음 분석 파이프라인은 `오디오 변환 → STT → 음향 분석 → AI 평가 → DB 저장` 순서가 고정된
단방향 흐름이라 LangGraph가 줄 수 있는 가치가 없습니다. 순차 함수 호출이 더 명확합니다.

반면 문장 제안은 다음과 같은 이유로 LangGraph가 적합합니다.

- LLM이 입력 문장의 어조를 **런타임에 판단**해서 실행할 툴을 동적으로 선택
- 어조가 formal이면 `convert_neutral` + `convert_informal`을 호출
- 어조가 neutral이면 `convert_formal` + `convert_informal`을 호출
- **실행 전까지 경로가 결정되지 않음** → 조건부 라우팅이 필요

ThreadPoolExecutor로는 이 동적 툴 선택 구조를 자연스럽게 표현할 수 없습니다.

---

## 3. 그래프 구조

```
analysis_node (LLM + 4개 툴 바인딩)
    ↓ tool_calls 존재 여부로 라우팅
  [tools 있음] → ToolNode (툴 실행)
  [tools 없음] → aggregate_node
    ↓
aggregate_node (툴 결과 수집 → 최종 출력)
    ↓
   END
```

**노드 설명**

| 노드 | 역할 |
|---|---|
| `analysis_node` | LLM이 문장 분석 후 툴 호출 결정 |
| `ToolNode` | 선택된 툴 실행 (LangGraph 내장) |
| `aggregate_node` | ToolMessage 결과를 dict로 수집 |

---

## 4. 툴 설계

LLM에 3개의 툴을 바인딩합니다.

| 툴 | 역할 |
|---|---|
| `report_analysis` | 어조 감지 + 문법 교정 결과 보고 |
| `convert_formal` | 문장을 formal 어조로 변환 |
| `convert_informal` | 문장을 informal 어조로 변환 |

`convert_neutral`은 제거했습니다. neutral은 스펙트럼(formal 쪽 neutral, informal 쪽 neutral)이라
독립적인 추천 범주로 쓰기 애매하기 때문입니다. 어조 판단 기준으로만 활용합니다.

---

## 5. LLM 동작 규칙 (시스템 프롬프트)

```
1. 입력 문장의 어조를 formal / neutral / informal 중 하나로 판단
2. report_analysis 호출: 어조, 교정 문장, 문법 오류 여부, 변경 내역
3. 어조에 따라 convert 툴 호출:
   - formal   → convert_informal 1개
   - informal → convert_formal 1개
   - neutral  → convert_formal + convert_informal 2개
4. convert 툴의 입력은 원문이 아닌 교정된 문장 사용
```

formal의 기준은 어휘 수준이 아닌 **상황 적절성**입니다.
공식 자리·업무 맥락에 적합한가(formal) vs 친한 사이의 대화에 적합한가(informal).

---

## 6. 최종 출력 구조

```json
{
  "tone": "neutral",
  "corrected_text": "I was wondering if you could help me.",
  "has_grammar_error": false,
  "grammar_changes": [],
  "suggestions": {
    "formal":   { "converted": "I would appreciate your assistance with this matter.", "changes": ["..."] },
    "informal": { "converted": "Hey, could you help me out?", "changes": ["..."] }
  }
}
```

neutral 입력이면 formal + informal 둘 다 제안합니다.
formal/informal 입력이면 반대 어조 1개만 제안합니다.

---

## 7. 설계 결정 기록

**convert_neutral을 제거한 이유**

neutral은 formal과 informal 사이의 스펙트럼이라 독립적인 변환 목표로 삼기 어렵습니다.
"formal에 가까운 neutral"과 "informal에 가까운 neutral"이 존재하므로, neutral을 추천하면 오히려 방향이 모호해집니다.
사용자에게 의미 있는 선택지는 formal ↔ informal 두 방향이고, neutral은 현재 문장의 위치를 판단하는 기준으로만 씁니다.

**formal 정의를 어휘 수준이 아닌 상황 적절성으로 잡은 이유**

"assist" 같은 전문 어휘를 쓰는 것이 formal의 필요조건이 아닙니다.
"I would like to help you"는 단순한 어휘지만 formal하고, "I wanna help"는 쉬운 어휘지만 informal합니다.
formal의 본질은 공식 맥락에서의 예의·구조·절제이지 어휘 난이도가 아닙니다.

**문법 교정을 별도 LLM 호출로 분리하지 않은 이유**

`report_analysis` 툴 안에 교정 결과를 포함시키면 LLM 호출 1회로 어조 감지 + 교정을 동시에 처리할 수 있습니다.
convert 툴은 교정된 문장을 입력으로 받으므로 교정과 변환이 자연스럽게 연결됩니다.
