# import streamlit as st
# from io import BytesIO
# import base64
# from audiorecorder import audiorecorder
# from langgraph_config.graph_runner import run_pipeline
# from dotenv import load_dotenv
# load_dotenv()  # .env 파일 읽어서 환경변수 자동 등록

# st.title("Pronunciation Coach 🎤")

# # ------------------------------
# # 햄버거 메뉴 숨기기 (Deploy 버튼 유지)
# # ------------------------------
# hide_menu_style = """
#     <style>
#     #MainMenu {visibility: hidden;}
#     footer {visibility: hidden;}
#     </style>
# """
# st.markdown(hide_menu_style, unsafe_allow_html=True)

# # ------------------------------
# # 상단 로그인 버튼 (Deploy 오른쪽에 고정 느낌)
# # ------------------------------
# st.markdown(
#     """
#     <style>
#     .login-button {
#         position: fixed;
#         top: 12px;          /* header 높이에 맞춤 */
#         right: 15px;        /* Deploy 버튼 위치 */
#         z-index: 100;

#         /* 회색 배경 */
#         background-color: #d3d3d3;  /* 연한 회색 */
#         color: #262730;             /* 글자색: Streamlit 기본 텍스트 색상 */
#         border: 1px solid #a9a9a9; /* 테두리: 조금 진한 회색 */
#         padding: 6px 12px;
#         border-radius: 6px;
#         font-weight: 500;
#         cursor: pointer;
#     }

#     .login-button:hover {
#         background-color: #e6e6e6; /* 마우스 오버 시 살짝 진하게 */
#     }
#     </style>
#     <!-- HTML 버튼 -->
#     <button class="login-button" onclick="window.streamlitSendMessage('login_clicked', '')">
#         Login / Register
#     </button>
#     """,
#     unsafe_allow_html=True
# )

# # ------------------------------
# # 0️⃣ 모달 로그인/회원가입 상태 관리
# # ------------------------------
# if "logged_in" not in st.session_state:
#     st.session_state.logged_in = False
# if "show_modal" not in st.session_state:
#     st.session_state.show_modal = False

# # ------------------------------
# # 1️⃣ 모달 열기 버튼 (오른쪽 상단 느낌)
# # ------------------------------
# # ------------------------------
# # 1️⃣ 상단 Deploy 버튼, 햄버거 메뉴, footer 숨기기, 로그인 버튼 (상단 오른쪽 고정)
# # ------------------------------
# hide_ui_style = """
#     <style>
#     header {visibility: hidden;}   /* Deploy 버튼 + 상단 배너 숨김 */
#     #MainMenu {visibility: hidden;} /* 햄버거 메뉴 숨김 */
#     footer {visibility: hidden;}   /* 하단 Streamlit 문구 숨김 */
#     </style>
# """
# st.markdown(hide_ui_style, unsafe_allow_html=True)

# st.markdown(
#     """
#     <style>
#     /* 로그인 버튼을 header 오른쪽 끝, Deploy 버튼 자리로 이동 */
#     .login-button {
#         position: fixed;
#         top: 12px;          /* header 높이에 맞춤 */
#         right: 15px;        /* Deploy 버튼이 있던 위치 */
#         z-index: 100;
#         background-color: #f0f0f0;
#         padding: 6px 12px;
#         border-radius: 5px;
#         border: 1px solid #ccc;
#     }
#     </style>
#     """,
#     unsafe_allow_html=True
# )

# # 실제 버튼 HTML을 직접 넣어 위치 고정
# st.markdown(
#     """
#     <button class="login-button" onclick="window.streamlitSendMessage('login_clicked', '')">
#         Login / Register
#     </button>
#     """,
#     unsafe_allow_html=True
# )

# # Streamlit 버튼 클릭 이벤트 처리
# if "login_clicked" not in st.session_state:
#     st.session_state.login_clicked = False

# # 기존 st.button 클릭 처리 대신 session_state로 트리거
# if st.session_state.login_clicked:
#     st.session_state.show_modal = True

# # ------------------------------
# # 2️⃣ 모달 구현
# # ------------------------------
# if st.session_state.show_modal:
#     modal_placeholder = st.empty()  # 모달 자리 확보
#     with modal_placeholder.container():
#         st.markdown("### 🔒 Login or Register")
#         option = st.radio("Select option:", ["Login", "Register"])

#         username = st.text_input("Username")
#         password = st.text_input("Password", type="password")

#         if option == "Register":
#             email = st.text_input("Email")

#         if st.button("Submit", key="submit_auth"):
#             if option == "Login":
#                 # TODO: FastAPI JWT 로그인 호출
#                 st.success(f"Welcome back, {username}!")
#             else:
#                 # TODO: FastAPI 회원가입 호출
#                 st.success(f"Account created for {username}!")

#             st.session_state.logged_in = True
#             st.session_state.show_modal = False
#             modal_placeholder.empty()  # 모달 닫기

# # ------------------------------
# # 경고 메시지 여백 제거
# # ------------------------------
# st.markdown(
#     """
#     <style>
#     .stAlert {
#         margin-top: 0px !important;  /* 위쪽 여백 제거 */
#         margin-bottom: 10px !important;  /* 아래쪽은 약간 여유 */
#     }
#     </style>
#     """,
#     unsafe_allow_html=True
# )

# # ------------------------------
# # 3️⃣ 로그인 전/후 UI
# # ------------------------------
# if not st.session_state.logged_in:
#     st.warning("Please login to access the pronunciation coach.")
# else:
#     name = st.text_input("Your Name")

#     # Target Text 입력
#     target_text = st.text_area(
#         "Enter the target sentence (for pronunciation practice)",
#         height=300
#     )
#     st.write("Upload your voice or record directly for corrections from US & UK tutors.")

#     # 상태 초기화
#     if "audio_file" not in st.session_state:
#         st.session_state.audio_file = None
#     if "audio_name" not in st.session_state:
#         st.session_state.audio_name = None

#     # 선택: 업로드 vs 녹음
#     input_method = st.radio("Choose input method:", ["Upload Audio File", "Record Audio"])

#     # ------------------------------
#     # 1️⃣ 오디오 업로드 선택
#     # ------------------------------
#     if input_method == "Upload Audio File":
#         uploaded_file = st.file_uploader("Upload your voice file", type=["wav", "mp3", "m4a"])
#         if uploaded_file:
#             st.session_state.audio_file = uploaded_file
#             st.session_state.audio_name = uploaded_file.name

#             st.markdown(f"**Uploaded File:** {st.session_state.audio_name} ✅")
#             st.audio(uploaded_file, format=f"audio/{uploaded_file.name.split('.')[-1]}")

#     # ------------------------------
#     # 2️⃣ 브라우저 녹음 선택
#     # ------------------------------
#     elif input_method == "Record Audio":
#         st.write("Click below to record your voice:")

#         audio = audiorecorder("Start Recording 🎙️", "Stop Recording ⏹️")

#         if len(audio) > 0:
#             buf = BytesIO()
#             audio.export(buf, format="wav")
#             audio_bytes = buf.getvalue()

#             audio_file = BytesIO(audio_bytes)
#             audio_file.name = "recorded_audio.wav"

#             st.session_state.audio_file = audio_file
#             st.session_state.audio_name = audio_file.name

#             # 디버깅용 출력
#             st.write(f"DEBUG: audio byte size = {len(audio_bytes)}")

#             st.audio(audio_bytes, format="audio/wav")
#             st.markdown(f"**Recording Complete ✅** File: {st.session_state.audio_name}")

#     # ------------------------------
#     # 3️⃣ 전송 버튼
#     # ------------------------------
#     col1, col2 = st.columns([3, 1])
#     with col2:
#         send_clicked = st.button("Send to LangGraph")

#     st.markdown("---")

#     # 결과는 전체 폭 컨테이너에서 출력   
#     if send_clicked:
#             audio_file = st.session_state.audio_file
#             audio_name = st.session_state.audio_name

#             if name and target_text and audio_file:
#                 # 실제 LangGraph 처리 함수 호출 자리
#                 result = run_pipeline(audio_file, name, target_text)  # 🚀 LangGraph 실행
                
#                 st.markdown(f"## 🎯 Pronunciation Result for **{name}**")
#                 st.markdown(f"**Target Sentence:** {target_text}")

#                 st.markdown("---")
                
#                 with st.container():
#                     # US Tutor Section
#                     st.markdown("### 🇺🇸 US Tutor Feedback")
#                     st.write(result.get("us_feedback", "No feedback available"))
#                     if result.get("score"):
#                         st.write(f"**Score:** {result['score']} / 100")

#                     # US TTS 음성 재생
#                     us_audio_bytes = result.get("us_audio")
#                     if us_audio_bytes:
#                         st.audio(us_audio_bytes, format="audio/wav")

#                     # 추가 정보
#                     if result.get("user_duration"):
#                         st.write(f"User duration: {result['user_duration']} seconds")
#                     if result.get("us_ref_duration"):
#                         st.write(f"US reference duration: {result['us_ref_duration']} seconds")    
                
#                 st.markdown("---")

#                 with st.container():
#                     # UK Tutor Section
#                     st.write("### UK Tutor Feedback")
#                     st.markdown(result.get("uk_comment", "No UK comment available"))

#                     # UK TTS 음성 재생 (가짜일 경우 빈 바이트 체크)
#                     uk_audio_bytes = result.get("uk_audio")
#                     if uk_audio_bytes:
#                         st.audio(uk_audio_bytes, format="audio/wav")
#                 st.markdown("---")    

#             else:
#                 st.warning("Please enter your name and upload/record an audio file!")

