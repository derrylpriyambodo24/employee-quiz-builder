"""Employee Quiz Builder - Streamlit UI."""
import json

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from quiz_logic import generate_quiz  # noqa: E402

st.set_page_config(page_title="Employee Quiz Builder", page_icon="🏠", layout="centered")

st.markdown(
    """
<style>
.hero{padding:1.5rem 1.8rem;border-radius:18px;margin-bottom:1.2rem;color:#fff;
      background:linear-gradient(135deg,#0f766e 0%,#2563eb 100%);}
.hero h1{margin:0;font-size:2rem;color:#fff;padding:0}
.hero p{margin:.35rem 0 0;opacity:.92}
.chip{display:inline-block;padding:.15rem .75rem;border-radius:999px;font-size:.8rem;
      font-weight:600;margin:0 .4rem .6rem 0;background:rgba(127,127,127,.18)}
div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px}
.stButton>button,.stDownloadButton>button{border-radius:10px;font-weight:600}
</style>
<div class="hero"><h1>🏠 Employee Quiz Builder</h1>
<p>Turn any property-industry topic into a ready-to-take quiz in seconds.</p></div>
""",
    unsafe_allow_html=True,
)

EXAMPLES = {
    "Agent skills 2025": "Top skills of a property agent in 2025",
    "Jakarta market": "Property Market updates in Jakarta",
    "KPR basics": "Basic KPR (mortgage) knowledge for agents",
}
st.session_state.setdefault("topic", "")
st.session_state.setdefault("quiz_id", 0)


def use_example(text: str) -> None:
    st.session_state.topic = text


topic = st.text_input("Topic", key="topic", placeholder="e.g. Property Market updates in Jakarta")
cols = st.columns(len(EXAMPLES))
for col, (label, full) in zip(cols, EXAMPLES.items()):
    col.button(f"💡 {label}", key=f"ex_{label}", on_click=use_example, args=(full,), use_container_width=True)

c1, c2, c3 = st.columns(3)
n = c1.slider("Questions", 3, 15, 5)
difficulty = c2.select_slider("Difficulty", ["easy", "medium", "hard"], value="medium")
language = c3.selectbox("Language", ["English", "Bahasa Indonesia"])
generate = st.button("✨ Generate Quiz", type="primary", use_container_width=True)

if generate:
    if not topic.strip():
        st.warning("Please enter a topic first.")
    else:
        with st.spinner("Writing your quiz..."):
            try:
                st.session_state.quiz = generate_quiz(topic.strip(), n, difficulty, language)
                st.session_state.quiz_id += 1
                st.session_state.submitted = False
            except Exception as err:  # show a clear message instead of a stack trace
                st.session_state.pop("quiz", None)
                st.error(f"Could not generate the quiz: {err}")

quiz = st.session_state.get("quiz")

if not quiz:
    with st.container(border=True):
        st.markdown("#### How it works")
        st.markdown(
            "1. Type a topic above, or tap a quick example.\n"
            "2. Pick the number of questions, difficulty, and language.\n"
            "3. Press **Generate Quiz**, answer the questions, and get your score with explanations."
        )
else:
    total = len(quiz["questions"])
    st.markdown(f"### {quiz.get('topic', 'Quiz')}")
    st.markdown(
        f'<span class="chip">📝 {total} questions</span>'
        f'<span class="chip">🎯 {quiz.get("difficulty", "")}</span>',
        unsafe_allow_html=True,
    )

    st.caption("⚠️ AI-generated content. Verify facts, figures, and regulations before using it for training.")

    if quiz.get("warnings"):
        st.warning("These questions may contain unverified claims, please check them before use: " + "; ".join(quiz["warnings"]))

    with st.form("quiz_form"):
        answers = {}
        for i, q in enumerate(quiz["questions"], start=1):
            with st.container(border=True):
                st.caption(f"Question {i} of {total}")
                answers[q["id"]] = st.radio(
                    q["question"],
                    options=list(q["options"].keys()),
                    format_func=lambda letter, q=q: f"{letter}. {q['options'][letter]}",
                    index=None,
                    key=f'answer_{st.session_state.quiz_id}_{q["id"]}',
                )
        if st.form_submit_button("Submit answers", type="primary", use_container_width=True):
            st.session_state.submitted = True
            st.session_state.answers = answers

    if st.session_state.get("submitted"):
        answers = st.session_state.answers
        score = sum(1 for q in quiz["questions"] if answers.get(q["id"]) == q["correct"])
        pct = score / total
        st.divider()
        c1, c2 = st.columns([1, 2])
        c1.metric("Your score", f"{score} / {total}")
        c2.progress(pct, text=f"{round(pct * 100)}% correct")
        if pct == 1:
            st.balloons()
            st.success("Perfect score! 🎉")
        elif pct >= 0.7:
            st.success("Great job! Review the few you missed below.")
        else:
            st.info("Good start. Read the explanations below and try again.")

        for i, q in enumerate(quiz["questions"], start=1):
            chosen = answers.get(q["id"])
            ok = chosen == q["correct"]
            with st.container(border=True):
                st.markdown(f'**{"✅" if ok else "❌"} {i}. {q["question"]}**')
                correct_line = f'{q["correct"]}. {q["options"][q["correct"]]}'
                if ok:
                    st.success(f"Correct: {correct_line}")
                else:
                    mine = f'{chosen}. {q["options"][chosen]}' if chosen else "no answer"
                    st.error(f"Your answer: {mine}")
                    st.success(f"Correct: {correct_line}")
                st.caption(f'💡 {q["explanation"]}')

    st.download_button(
        "⬇️ Download quiz as JSON",
        json.dumps(quiz, ensure_ascii=False, indent=2),
        file_name="quiz.json",
        mime="application/json",
    )
