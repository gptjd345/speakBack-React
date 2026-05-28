import React, { useRef, useEffect } from "react";

// 별도 CSS 없이 글로벌 변수와 인라인 스타일 조합 사용
// (sb-textarea 클래스는 global.css 에 정의)

const MIN_LEN = 10;
const MAX_LEN = 500;

function TargetTextInput({ value, onChange }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [value]);

  const len = value.length;
  const tooShort = len > 0 && len < MIN_LEN;
  const tooLong = len > MAX_LEN;

  return (
    <div>
      <textarea
        ref={textareaRef}
        className="sb-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Type the sentence you want to practice…"
        maxLength={MAX_LEN}
      />
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px", fontSize: "12px" }}>
        <span style={{ color: tooShort ? "#e53e3e" : "transparent" }}>
          At least {MIN_LEN} characters required.
        </span>
        <span style={{ color: tooLong ? "#e53e3e" : "#999" }}>
          {len} / {MAX_LEN}
        </span>
      </div>
    </div>
  );
}

export default TargetTextInput;
