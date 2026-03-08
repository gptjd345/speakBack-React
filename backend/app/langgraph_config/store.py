# langgraph_config/store.py
class GlobalStore:
    def __init__(self):
        self.target_text = None   # 사용자가 말하고자 하는 목표 문장  
        self.audio_file = None    # BytesIO 같은 파일 객체
        self.original_filename = None # 업로드 파일명 (확장자 감지용) 
        self.tmp_path = None       # 원본파일 저장위치

        self.user_id = None        # DB 저장용 user pk
        self.user_name = None      # 사용자계정명
        self.saved_session_id = None  # 저장된 session_history id
        # 필요하면 더 추가 (예: 세션 ID 등)

        self.score = None # score
        self.us_feedback = None # us_feedback
        self.tts_us_audio = None # reference 참고용 음성
        self.user_transcript = None # user_transcript

        self.user_duration = None # 사용자 발화 시간
        self.us_ref_duration = None  # us tutor 발화시간

        self.tts_uk_audio = None   # uk tutor 가 만든 교정데이터
        self.tts_uk_comment = None # uk tutor 가 만든 교정데이터

        self.strengths: None       # 강점
        self.improvements: None    # 개선점
        self.rhythm_feedback: None # 리듬 피드백

# 전역 싱글톤처럼 import해서 씀
global_store = GlobalStore()

