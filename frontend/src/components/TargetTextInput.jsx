import React, { useRef, useEffect } from "react";

// 별도 CSS 없이 글로벌 변수와 인라인 스타일 조합 사용
// (sb-textarea 클래스는 global.css 에 정의)

function TargetTextInput({ value, onChange }) {
  const textareaRef = useRef(null);

   // 내용에 맞게 높이 조절
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"; // 초기화
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [value]);

  return (
    <textarea
      ref={textareaRef}
      className="sb-textarea"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Type the sentence you want to practice…"
    />
  );
}

export default TargetTextInput;
