import React, { useState } from "react";
import "../styles/AudioUploader.css";
import { FaMicrophone, FaPaperPlane } from "react-icons/fa"; // 아이콘 import

function AudioUploader({ onSendClick }) {
  const [method, setMethod] = useState("Upload"); // 업로드/녹음 선택
  const [file, setFile] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleRecord = () => {
    // 현재는 녹음 기능 비활성화
  };

  return (
    <div className="audio-uploader" style={{ marginTop: "50px"}}>
      <h4>Upload or Record Your Voice</h4>
      
      {/* 입력 선택 영역 */}
      <div className="input-method-container">
        <label style={{ marginBottom: "5px", fontWeight: "500" }}>
          Choose input method:
        </label>
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          style={{ marginLeft:"5px", padding: "6px 10px", borderRadius: "5px", border: "1px solid #555" }}
        >
          <option value="Upload">Upload Audio File</option>
          <option value="Record">Record Audio</option>
        </select>
      </div>

      {/* 조건부 렌더링 */}
      {method === "Upload" && (
        <>
          <input type="file" accept="audio/*" onChange={handleFileChange} />
          {file && <p>Selected file: {file.name}</p>}
        </>
      )}

      {/* 녹음 버튼 */}
      {method === "Record" && (
        <button onClick={handleRecord} className="record-btn">
          <FaMicrophone style={{ marginRight: "8px" }} />
          Record Audio (Coming Soon)
            
        </button>
      )}

      {/* Send 버튼은 로그인해야 사용가능 하게 비활성화 */}
      <button 
        className="send-btn" 
        onClick={onSendClick}>
        <FaPaperPlane style={{ marginRight: "8px" }} />
        Send to LangGraph
      </button>


    </div>
  );
}

export default AudioUploader;
