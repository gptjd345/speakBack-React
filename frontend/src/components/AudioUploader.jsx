import React, { useState, useRef } from "react";
import "../styles/AudioUploader.css";
import { FaMicrophone, FaPaperPlane } from "react-icons/fa"; // 아이콘 import

function AudioUploader({ file, setFile, onSendClick }) {
  const [method, setMethod] = useState("Upload"); // 업로드/녹음 선택
  const [recording, setRecording] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null); // 마이크 스트림 저장

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const stopStreamTrack = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  };

  const handleRecord = async () => {
    if (recording) {
      if(mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        // 입력스트림 먼저 종료
        stopStreamTrack();
        // 녹음 종료
        mediaRecorderRef.current.stop();
      }

      setRecording(false);
    } else {
      // 녹음 시작
      try {
        // 브라우저의 마이크 접근 권한 요청 
        // await 을 통해 사용자의 승인까지 기다림 
        // getUserMedia({audio: true}) -> 접근권한 허용시 오디오입력을 위한 스트림 파이프라인을 가짐
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
        // 스트림으로 가져온 데이터를 가지고 녹음 객체를 생성 (MediaRecorder는 실시간 오디오스트림을 다루는 객체임)
        const mediaRecorder = new MediaRecorder(stream);
        // 녹음을 위한 객체는 렌더링마다 새로 만들 필요없으니 ref에 넣음
        mediaRecorderRef.current = mediaRecorder;
        // 녹음데이터 
        audioChunksRef.current = [];

        // 녹음중 데이터 청크(chunk)가 준비 될 때마다 호출되는 이벤트
        // 데이터가 존재하면 audioChunksRef에 추가 
        mediaRecorder.ondataavailable = (event) => {
          // event.data가 Blob 형태의 작은 오디오 데이터 조각을 의미한다. 
          if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };
        
        // 바로 실행되는게 아님 onstop은 이벤트 핸들러로 MediaRecorder의 stop() 메소드가 호출될때 트리거 된다. 
        mediaRecorder.onstop = () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: "audio/wav" });
          const audioFile = new File([audioBlob], "recorded_audio.wav", { type: "audio/wav" });
          setFile(audioFile);
        };

        mediaRecorder.start();
        setRecording(true);
      } catch (err) {
        console.error("Error accessing microphone:", err);
      }
    }
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
          {recording ? "Stop Recording" : "Record Audio"}
            
        </button>
      )}

      {/*  녹음한 오디오 재생 UI */}
      {file && method === "Record" && (
        <div style={{ marginTop: "5px", marginBottom: "5px" }}>
          <p>Recorded audio:</p>
          <audio controls src={URL.createObjectURL(file)} />
        </div>
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
