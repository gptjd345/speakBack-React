# RAG 아키텍처 설계 고민

## 1. 개인화 피드백의 필요성

Pronunciation Coach는 세션마다 독립적인 피드백을 제공합니다.
하지만 반복적으로 같은 실수를 하는 사용자에게는 **패턴을 짚어주는 피드백**이 더 유효합니다.

> "이번 세션에서 'probably'의 강세가 약했습니다."
> vs.
> "최근 5세션을 보면 다음절 내용어에서 반복적으로 강세가 약해지는 패턴이 있습니다."

후자가 학습자에게 실질적으로 더 유용합니다.

---

## 2. 어떤 데이터를 저장할 것인가

본 시스템의 목표는 강세·리듬 중심의 communicable pronunciation이므로,
저장 데이터도 이에 맞게 설계했습니다.

| 데이터 | 추출 방법 | 의미 |
|---|---|---|
| `weak_words` | GPT 평가 결과 improvements | 강세가 약했던 내용어 |
| `transcript_mismatches` | target vs STT 단어 비교 | Whisper가 다르게 인식한 단어 (심각한 발음 오류 proxy) |
| `score` | GPT 평가 점수 | 전반적 품질 |

`transcript_mismatches`는 음소 오류를 직접 잡지는 못하지만,
**Whisper조차 틀리게 인식할 만큼 심각한 발음 문제**는 간접적으로 포착합니다.

---

## 3. pgvector 선택 이유

### 왜 벡터 DB인가

단순 SQL 집계(`GROUP BY weak_words`)로도 자주 틀린 단어는 뽑을 수 있습니다.
하지만 벡터 유사도 검색을 사용하면:

- 표면적 단어가 달라도 **구조적으로 유사한 실수 패턴**을 찾을 수 있습니다
  - "probably"와 "actually"는 다른 단어지만 같은 패턴 (다음절 부사의 강세 문제)
- 현재 세션과 가장 유사한 과거 세션을 찾아 **문맥 있는 RAG context**를 구성할 수 있습니다

### 왜 별도 벡터 DB가 아닌 pgvector인가

- 이미 PostgreSQL을 사용 중 → 인프라 추가 없이 extension으로 해결 가능합니다
- 개인 사용자 데이터 규모(수만 건 이하)에서 pgvector 성능으로 충분합니다
- `session_patterns.embedding <=> :query_vec` 코사인 유사도 쿼리로 기존 ORM과 자연스럽게 통합됩니다

---

## 4. 임베딩 설계

### 무엇을 임베딩할 것인가

세션의 "발음 패턴"을 텍스트로 직렬화한 뒤 `text-embedding-3-small`로 벡터화합니다.

```python
def build_pattern_text(improvements, transcript_mismatches, score):
    # 예시 출력:
    # "weak content words: probably, numbers, thought.
    #  pronunciation mismatches: thought->dought, probably->probably.
    #  score: 78"
```

이 텍스트가 임베딩 공간에서 **발음 패턴의 의미적 위치**를 나타냅니다.
유사한 패턴(같은 단어에서 반복 실수, 비슷한 점수대)끼리 벡터 공간에서 가깝게 모입니다.

### 임베딩 저장 시점

Coach 세션 분석 완료 후 `db_save_node`에서 자동 저장합니다.

```python
# builder.py db_save_node
mismatches = extract_transcript_mismatches(target_text, user_transcript)
pattern_text = build_pattern_text(improvements, mismatches, score)
embedding = get_embedding(pattern_text)  # Redis 7일 캐시

pattern = SessionPattern(
    session_id=record.id,
    user_id=...,
    pattern_text=pattern_text,
    weak_words=improvements,
    transcript_mismatches=mismatches,
    score=score,
    embedding=embedding,
)
```

---

## 5. RAG 파이프라인

### /api/lab/feedback

현재 세션 패턴을 쿼리 벡터로 변환해 과거 유사 세션 5개를 검색합니다.
검색된 세션들의 `weak_words`, `transcript_mismatches`를 context로 GPT에 전달합니다.

```sql
SELECT sp.weak_words, sp.transcript_mismatches, sp.score, sh.target_text
FROM session_patterns sp
JOIN session_history sh ON sp.session_id = sh.id
WHERE sp.user_id = :user_id
  AND sp.session_id != :current_id
ORDER BY sp.embedding <=> :query_vec   -- 코사인 유사도
LIMIT 5
```

GPT 프롬프트:
> "이 학습자의 유사 과거 세션들을 보고 반복되는 패턴을 찾아 구체적이고 실행 가능한 조언을 해주세요."

### /api/lab/sentences

피드백 텍스트 + DB에서 집계한 상위 취약 패턴을 context로 연습 문장 3개를 생성합니다.

```python
# 최근 20개 세션에서 빈도 집계
word_count = {}
for p in patterns:
    for w in (p.weak_words or []):
        word_count[w] = word_count.get(w, 0) + 1

top_weak = sorted(word_count.items(), key=lambda x: -x[1])[:3]
```

GPT 프롬프트:
> "이 취약 단어들이 자연스럽게 포함된 문장을 casual / neutral / formal 각 1개씩 만들어주세요."

---

## 6. 현재 구현의 한계와 다음 단계

### 한계

- 세션 수가 적을 때 pgvector 유사도 검색의 가치가 낮습니다 (1개 세션이면 비교 불가)
- `transcript_mismatches`의 정확도가 Whisper의 문맥 교정 능력에 의존합니다

### 개선 방향

- **발음 코퍼스 DB 추가**: 음소별/패턴별 예문을 사전 구축해 임베딩하고, 취약 패턴과 유사한 예문을 retrieve해서 연습 문장 생성에 활용합니다. 현재는 사용자 자신의 데이터만 검색하지만, 외부 코퍼스까지 검색하면 보다 완성도 높은 RAG 구조가 됩니다.
