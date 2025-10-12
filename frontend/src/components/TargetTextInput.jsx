import React, { useState, useRef, useEffect } from "react";
import "../styles/TargetTextInput.css";

function TargetTextInput({ value, onChange }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    // 내용에 맞게 높이 조절
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"; // 초기화
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [value]);

  return (
    <div className="target-text-input" >
      <label style={{ fontWeight: "500", marginBottom: "5px", display: "block" }}>
        Enter the target sentence:
      </label>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Type your sentence here..."
        style={{
          width: "100%",
          padding: "10px",
          borderRadius: "8px",
          border: "1px solid #555",
          backgroundColor: "#1e1e1e",
          color: "#f0f0f0",
          resize: "none",
          fontSize: "1rem",
        }}
      />
    </div>
  );
}

export default TargetTextInput;
