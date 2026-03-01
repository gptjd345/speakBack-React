import React, { useState, useRef } from "react";
import "../styles/AudioUploader.css";

function AudioUploader({ file, setFile, onSendClick }) {
  const [method, setMethod] = useState("Upload"); // 업로드/녹음 선택
  const [recording, setRecording] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null); // 마이크 스트림 저장
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.type.startsWith("audio/")) setFile(dropped);
  };

  // ─── Recording ─────────────────────────────────────────────────
  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  };

  const handleRecord = async () => {
    if (recording) {
      stopStream(); // 입력스트림 먼저 종료
      if(mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop(); // 녹음 종료
      }
      setRecording(false);
    // 녹음 시작
    } else {
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

  // ─── Render ────────────────────────────────────────────────────
  return (
    <div>
      {/* Method Tabs */}
      <div className="sb-audio-tabs">
        <button
          className={`sb-audio-tab ${method === "upload" ? "active" : ""}`}
          onClick={() => setMethod("upload")}
        >
          📂 Upload
        </button>
        <button
          className={`sb-audio-tab ${method === "record" ? "active" : ""}`}
          onClick={() => setMethod("record")}
        >
          🎙 Record
        </button>
      </div>

      {/* Upload Mode */}
      {method === "upload" && (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            onChange={handleFileChange}
            className="hidden"
          />
          {file ? (
            <div className="sb-file-selected">
              🎵 <span>{file.name}</span>
              <button
                className="sb-file-selected-clear"
                onClick={() => setFile(null)}
              >
                ✕
              </button>
            </div>
          ) : (
            <div
              className={`sb-file-drop ${dragOver ? "drag-over" : ""}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <div className="sb-file-drop-icon">🎵</div>
              <div className="sb-file-drop-text">
                <strong>Click to upload</strong> or drag and drop
                <br />
                <span>MP3, WAV, M4A up to 25MB</span>
              </div>
            </div>
          )}
        </>
      )}

      {/* Record Mode */}
      {method === "record" && (
        <>
          <button
            className={`sb-record-btn ${recording ? "recording" : ""}`}
            onClick={handleRecord}
          >
            <div className="sb-rec-dot" />
            {recording ? "Stop recording" : "Start recording"}
          </button>

          {file && !recording && (
            <div className="sb-audio-preview">
              <div className="sb-audio-preview-label">Preview:</div>
              <audio controls src={URL.createObjectURL(file)} />
            </div>
          )}
        </>
      )}

    </div>
  );
}

export default AudioUploader;
