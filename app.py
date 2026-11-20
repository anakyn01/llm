# Streamlit 라이브러리를 st로 임포트합니다.
import streamlit as st
# HTML/JS 컴포넌트 실행을 위해 임포트합니다.
import streamlit.components.v1 as components
import os
# 바이트 스트림 처리를 위한 io 라이브러리를 임포트합니다.
import io
# 이미지 처리를 위해 Pillow 라이브러리를 임포트합니다.
import base64
from pathlib import Path
from PIL import Image
from openai import OpenAI
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

st.set_page_config(
    page_title="AI Assistant",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 로컬 개발용 .env 로드 (Render에서는 대시보드 Environment Variables 사용)
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# Render 환경변수에서 GROQ_API_KEY를 읽어옵니다.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


@st.cache_data(ttl=3600)
def get_available_models(api_key: str):
    """Groq 서버에서 사용 가능한 모델 목록을 조회하고 캐싱합니다."""
    temp_client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key
    )
    return [m.id for m in temp_client.models.list().data]


# 엔드포인트 초기화
try:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY 환경변수가 설정되지 않았습니다.")

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY
    )
    # 기본 텍스트/문서 처리를 위한 모델명을 정의합니다.
    MODEL_NAME = "openai/gpt-oss-120b"
    # 캐싱된 모델 리스트 조회
    available_models = get_available_models(GROQ_API_KEY)
    # 사용 가능한 모델 중 비전(VLM) 관련 키워드가 포함된 모델을 자동으로 필터링합니다.
    vision_candidates = [
        m for m in available_models
        if any(k in m.lower() for k in ["vision", "scout", "maverick", "llava", "pixtral", "omni"])
    ]
    # 비전 모델이 존재하면 첫 번째 모델을 선택하고, 없으면 기본 모델로 대체합니다.
    VLM_MODEL_NAME = vision_candidates[0] if vision_candidates else MODEL_NAME
except Exception as e:
    # 초기화 실패 시 클라이언트 및 모델 변수를 안전하게 비웁니다.
    client = None
    available_models = []
    VLM_MODEL_NAME = None

# jinja2 템플릿 파일이 위치한 디렉토리(templates 폴더)를 환경 설정
env = Environment(loader=FileSystemLoader("templates"))


def render_template(template_name, **context):
    """지정된 이름의 Jinja2 HTML 템플릿을 불러와 렌더링하고 공백을 정제합니다."""
    template = env.get_template(template_name)
    cleaned_lines = [line.lstrip() for line in template.render(**context).splitlines()]
    return "\n".join(cleaned_lines).strip()


def load_css(file_path):
    """지정된 경로의 CSS 파일을 읽어와 앱 전체에 스타일을 적용합니다."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


# 토스트 팝업 부분
def show_glass_toast(title, desc, fa_icon="fa-circle-check"):
    st.markdown(
        f"""
        <div class="glass-toast">
            <div class="glass-toast-icon">
                <i class="fa-solid {fa_icon}"></i>
            </div>
            <div class="glass-toast-body">
                <span class="glass-toast-title">{title}</span>
                <span class="glass-toast-desc">{desc}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# 이미지 관련
def extract_image_info(image_bytes, image_name):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        img_format = img.format or image_name.split('.')[-1].upper()
        mode = img.mode
        rgb_img = img.convert("RGB")
        colors = rgb_img.getcolors(maxcolors=width * height)
        total_unique_colors = len(colors) if colors else "수만개 이상"

        quantized = rgb_img.quantize(colors=10).convert("RGB")
        q_colors = quantized.getcolors(maxcolors=10)
        q_colors.sort(key=lambda x: x[0], reverse=True)
        total_pixels = width * height

        top_colors_desc = []
        for count, rgb in q_colors[:5]:
            ratio = (count / total_pixels) * 100
            hex_code = '#{:02x}{:02x}{:02x}'.format(*rgb)
            top_colors_desc.append(f"HEX {hex_code} (RGB{rgb}: {ratio:.1f}%)")

        return (
            f"- 파일명: {image_name}\n"
            f"- 포맷/모드: {img_format} / {mode}\n"
            f"- 해상도(크기): {width} x {height} px\n"
            f"- 총 고유 색상(RGB) 개수: {total_unique_colors}개\n"
            f"- 주요 구성 색상 Top 5: {', '.join(top_colors_desc)}"
        )
    except Exception as e:
        return f"이미지 파일명: {image_name} (상세 분석 오류: {e})"


# 스크롤바 관련
def trigger_auto_scroll():
    components.html(
        f"""
        <script>
            const scrollDown = () => {{
                const mainSection = window.parent.document.querySelector('section.main');
                if (mainSection) {{
                    mainSection.scrollTo({{ top: mainSection.scrollHeight, behavior: 'smooth' }});
                }}
                window.parent.scrollTo({{ top: window.parent.document.body.scrollHeight, behavior: 'smooth' }});
            }};
            setTimeout(scrollDown, 120);
        </script>
        <!-- trigger:{len(st.session_state.get("chat_history", []))} -->
        """,
        height=0,
    )


# 폰트어썸 및 부트스트랩 CDN
st.markdown("""
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" rel="stylesheet">
""", unsafe_allow_html=True)

# 실제 파일명 style.css 로드
load_css("style.css")

# 대화 기록을 유지하기 위한 세션 상태 초기화
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": "안녕하세요! 애플 글래스 스타일이 적용된 Groq 통합 어시스턴트입니다. 하단 입력창 좌측의 클립 아이콘을 눌러 문서나 이미지를 첨부하고 질문해 주세요."
        }
    ]

if "uploaded_file_content" not in st.session_state:
    st.session_state.uploaded_file_content = None

if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None

if "uploaded_file_type" not in st.session_state:
    st.session_state.uploaded_file_type = None

if "uploaded_image_bytes" not in st.session_state:
    st.session_state.uploaded_image_bytes = None

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

if "toast_payload" not in st.session_state:
    st.session_state.toast_payload = None

if st.session_state.toast_payload:
    t_title, t_desc, t_icon = st.session_state.toast_payload
    show_glass_toast(t_title, t_desc, t_icon)
    st.session_state.toast_payload = None

# 상단 헤더
header_html = render_template("header.html", title="AI Studio")
st.markdown(header_html, unsafe_allow_html=True)

# 파일이 성공적으로 첨부되면 플로팅 상태바 표시
if st.session_state.uploaded_file_name:
    col_chip, col_clear = st.columns([5.2, 1.2], gap="small", vertical_alignment="center")
    with col_chip:
        icon_cls = "fa-image" if st.session_state.uploaded_file_type == "image" else "fa-file-lines"
        st.markdown(
            f"""
            <div class="active-file-chip">
                <i class="fa-solid {icon_cls} text-info"></i>
                <span>
                    <b>{st.session_state.uploaded_file_name}</b>
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col_clear:
        if st.button("첨부 해제", use_container_width=True):
            removed_name = st.session_state.uploaded_file_name
            st.session_state.uploaded_file_content = None
            st.session_state.uploaded_file_name = None
            st.session_state.uploaded_file_type = None
            st.session_state.uploaded_image_bytes = None
            st.session_state.uploader_key += 1
            st.session_state.toast_payload = ("첨부 해제 완료", f"'{removed_name}' 파일이 제외 되었습니다", "fa-trash-can")
            st.rerun()

    if st.session_state.uploaded_file_type == "image" and st.session_state.uploaded_image_bytes:
        with st.expander("첨부 이미지 미리보기", expanded=False):
            st.image(st.session_state.uploaded_image_bytes)

# 채팅 대화 기록
chat_container = st.container(border=False)
with chat_container:
    for msg in st.session_state.chat_history:
        bubble_html = render_template("chat_message.html", role=msg["role"], content=msg["content"])
        st.markdown(bubble_html, unsafe_allow_html=True)
    st.markdown("<div id='chat-bottom-anchor'></div>", unsafe_allow_html=True)

# 하단 고정 독(Dock) UI 배치를 위해 두 개의 컬럼 생성
col_dock_file, col_dock_form = st.columns([0.65, 9.35], gap="small", vertical_alignment="center")

with col_dock_file:
    st.markdown("<span id='footer-dock-marker' style='display:none;'></span>", unsafe_allow_html=True)
    unified_file = st.file_uploader(
        "파일 첨부",
        type=["pdf", "docx", "txt", "py", "js", "ts", "json", "md", "yml", "yaml", "png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
        key=f"unified_uploader_{st.session_state.uploader_key}"
    )

if unified_file is not None and unified_file.name != st.session_state.uploaded_file_name:
    file_ext = unified_file.name.split('.')[-1].lower()
    st.session_state.uploaded_file_name = unified_file.name

    if file_ext in ["png", "jpg", "jpeg", "webp"]:
        st.session_state.uploaded_image_bytes = unified_file.read()
        st.session_state.uploaded_file_type = "image"
        st.session_state.uploaded_file_content = None
        st.session_state.toast_payload = (
            "이미지 업로드 완료!",
            f"'{unified_file.name}' VLM 분석 준비가 완료되었습니다",
            "fa-image"
        )
        st.rerun()
    else:
        st.session_state.uploaded_image_bytes = None
        st.session_state.uploaded_file_type = "document"
        try:
            if file_ext == 'docx':
                import docx
                doc = docx.Document(unified_file)
                file_content = "\n".join([para.text for para in doc.paragraphs])
            elif file_ext == 'pdf':
                import pypdf
                reader = pypdf.PdfReader(unified_file)
                file_content = "\n".join([(page.extract_text() or "") for page in reader.pages])
            else:
                file_content = unified_file.read().decode("utf-8")

            if len(file_content) > 3000:
                file_content = file_content[:3000] + "\n\n...(내용이 너무 길어서 일부 생략되었습니다)"

            st.session_state.uploaded_file_content = file_content
            st.session_state.toast_payload = (
                "문서 업로드 완료!",
                f"'{unified_file.name}' 텍스트 추출 및 로드 완료!",
                "fa-file-circle-check"
            )
            st.rerun()
        except Exception as e:
            st.session_state.toast_payload = (
                "파일 읽기 오류",
                str(e),
                "fa-triangle-exclamation"
            )
            st.rerun()

with col_dock_form:
    with st.form(key="llm_chat_form", clear_on_submit=True):
        col_input, col_btn = st.columns([8.3, 1.7], gap="small", vertical_alignment="center")
        with col_input:
            user_input = st.text_input(
                "메세지 입력",
                placeholder="클립 아이콘으로 문서/이미지를 첨부하거나 메시지를 입력하세요...",
                label_visibility="collapsed"
            )

        with col_btn:
            submit_btn = st.form_submit_button("전송", use_container_width=True)

        if submit_btn and user_input.strip():
            display_user_msg = user_input

            if st.session_state.uploaded_file_name:
                display_user_msg = f"<span style='font-size:0.78rem; opacity:0.85;'><i class='fa-solid fa-paperclip me-1'></i>{st.session_state.uploaded_file_name}</span><br>{user_input}"

            st.session_state.chat_history.append({"role": "user", "content": display_user_msg})

            with st.spinner("AI가 분석 중입니다..."):
                try:
                    if client is not None:
                        prompt_to_send = user_input

                        if st.session_state.uploaded_file_type == "document" and st.session_state.uploaded_file_content:
                            prompt_to_send = f"""
                            [참고 파일: {st.session_state.uploaded_file_name}]
                            {st.session_state.uploaded_file_content}

                            [사용자 질문]
                            {user_input}
                            """

                        if st.session_state.uploaded_file_type == "image" and st.session_state.uploaded_image_bytes is not None:
                            encoded_image = base64.b64encode(st.session_state.uploaded_image_bytes).decode("utf-8")
                            img_ext = st.session_state.uploaded_file_name.split('.')[-1].lower()
                            mime_type = f"image/{'jpeg' if img_ext in ['jpg', 'jpeg'] else img_ext}"

                            try:
                                chat_completion = client.chat.completions.create(
                                    messages=[
                                        {
                                            "role": "user",
                                            "content": [
                                                {"type": "text", "text": prompt_to_send},
                                                {
                                                    "type": "image_url",
                                                    "image_url": {
                                                        "url": f"data:{mime_type};base64,{encoded_image}"
                                                    }
                                                }
                                            ]
                                        }
                                    ],
                                    model=VLM_MODEL_NAME,
                                )
                            except Exception:
                                img_analysis_text = extract_image_info(
                                    st.session_state.uploaded_image_bytes,
                                    st.session_state.uploaded_file_name
                                )
                                fallback_prompt = f"""
                                [업로드된 이미지 분석 데이터]
                                {img_analysis_text}

                                {prompt_to_send}
                                """
                                chat_completion = client.chat.completions.create(
                                    messages=[
                                        {
                                            "role": "system",
                                            "content": "You are a professional AI assistant. Use the provided image data to answer accurately in Korean."
                                        },
                                        {"role": "user", "content": fallback_prompt}
                                    ],
                                    model=MODEL_NAME,
                                )
                        else:
                            chat_completion = client.chat.completions.create(
                                messages=[
                                    {
                                        "role": "system",
                                        "content": "You are a professional AI software architect and developer assistant."
                                    },
                                    {"role": "user", "content": prompt_to_send}
                                ],
                                model=MODEL_NAME,
                            )

                        raw_text = chat_completion.choices[0].message.content or ""
                        ai_reply = raw_text.replace("\n", "<br>")
                    else:
                        ai_reply = "<i class='fa-solid fa-triangle-exclamation text-warning me-1'></i> Render 환경변수(<code>GROQ_API_KEY</code>)가 설정되지 않았거나 유효하지 않습니다."
                except Exception as e:
                    ai_reply = f"<i class='fa-solid fa-circle-exclamation text-danger me-1'></i> API 연동 중 오류가 발생했습니다: {e}"

            st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
            st.rerun()

# 앱 렌더링 후 스크롤 함수
trigger_auto_scroll()