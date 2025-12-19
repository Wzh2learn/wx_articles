import streamlit as st
import os
import json
import glob
import re
from datetime import datetime
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import run as cli_run
from agents import trend_hunter, formatter, refiner, auditor

# Set page config
st.set_page_config(
    page_title="AI Writing Agent Admin",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= Helper Functions =================

def load_history():
    history_file = config.get_history_file()
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def get_latest_report_content():
    # Find latest report in 1_topics
    topics_dir = config.get_stage_dir("topics")
    reports = glob.glob(os.path.join(topics_dir, "report_*.md"))
    if not reports:
        return None
    latest_report = max(reports, key=os.path.getmtime)
    with open(latest_report, "r", encoding="utf-8") as f:
        return f.read()

def parse_topics_from_report(content):
    """Parse topics from the report markdown content"""
    if not content:
        return []
    
    # Simple regex to find topics in the analysis section
    # Assuming format roughly like "### 选题 1：Title"
    topics = []
    
    # Regex to capture topic blocks
    topic_pattern = re.compile(r'### 选题 \d+[：:]\s*(.*?)\n(.*?)(?=### 选题|## |$)', re.DOTALL)
    matches = topic_pattern.findall(content)
    
    for title, body in matches:
        # Extract fields from body
        anchor = re.search(r'\*\s*\*\*心理锚点\*\*[：:]\s*(.*)', body)
        value = re.search(r'\*\s*\*\*核心价值\*\*[：:]\s*(.*)', body)
        rating = re.search(r'\*\s*\*\*热度评级\*\*[：:]\s*(.*)', body)
        reason = re.search(r'\*\s*\*\*推荐理由\*\*[：:]\s*(.*)', body)
        
        topics.append({
            "title": title.strip(),
            "body": body.strip(),
            "anchor": anchor.group(1).strip() if anchor else "N/A",
            "value": value.group(1).strip() if value else "N/A",
            "rating": rating.group(1).strip() if rating else "N/A",
            "reason": reason.group(1).strip() if reason else "N/A"
        })
    
    return topics

def save_selection(topic):
    """Save selected topic to history and potentially trigger next steps"""
    # For now, just save to history to mark as 'selected'
    # In a real app, this might trigger the Research agent
    trend_hunter.save_topic_to_history(topic['title'], topic['anchor'])
    st.success(f"Selected: {topic['title']}")

# ================= Sidebar =================

st.sidebar.title("📚 History")
history = load_history()

# Reverse to show newest first
for item in reversed(history):
    date = item.get("date", "Unknown Date")
    topic = item.get("topic", "Unknown Topic")
    angle = item.get("angle", "")
    st.sidebar.markdown(f"**{date}**")
    st.sidebar.text(f"{topic}\n({angle})")
    st.sidebar.markdown("---")

# Workflow actions
st.sidebar.markdown("### ⚙️ Workflow Actions")
if st.sidebar.button("🏆 1. Generate Decision", use_container_width=True):
    with st.sidebar.spinner("Generating FINAL_DECISION..."):
        try:
            trend_hunter.final_summary()
            st.sidebar.success("Decision generated!")
        except Exception as e:
            st.sidebar.error(f"Failed: {e}")

if st.sidebar.button("🔬 2. Start Research", use_container_width=True):
    with st.sidebar.spinner("Running Researcher..."):
        try:
            cli_run.run_researcher()
            st.sidebar.success("Research completed!")
        except Exception as e:
            st.sidebar.error(f"Failed: {e}")

if st.sidebar.button("✍️ 3. Write Draft", use_container_width=True):
    with st.sidebar.spinner("Running Drafter..."):
        try:
            cli_run.run_drafter()
            st.sidebar.success("Draft generated!")
        except Exception as e:
            st.sidebar.error(f"Failed: {e}")

# ================= Main Interface =================

tab1, tab2 = st.tabs(["📡 Topic Radar", "📝 Editor & Preview"])

# --- Tab 1: Topic Radar ---
with tab1:
    st.header("Topic Radar")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        directed_topic = st.text_input("Directed Topic (Optional)", placeholder="e.g. DeepSeek")
    with col2:
        st.write("") # Spacer
        st.write("") 
        start_btn = st.button("🚀 Start Scan", type="primary", use_container_width=True)

    if start_btn:
        with st.status("Scanning Trends...", expanded=True) as status:
            st.write("Initializing Hunter Agent...")
            # Capture output if possible, but trend_hunter logs to stdout/file
            # We will just run it and let it produce the file
            try:
                trend_hunter.main(topic=directed_topic if directed_topic else None)
                status.update(label="Scan Complete!", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Scan Failed", state="error")
                st.error(f"Error: {e}")

    # Display Results
    report_content = get_latest_report_content()
    
    if report_content:
        st.markdown("### Latest Scan Results")
        with st.expander("Raw Report Content", expanded=False):
            st.markdown(report_content)
        
        topics = parse_topics_from_report(report_content)
        
        if topics:
            st.subheader("Detected Topics")
            for i, t in enumerate(topics):
                # Create a card-like layout
                with st.container():
                    st.markdown(f"#### {t['title']}")
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**Anchor:** {t['anchor']}")
                        st.markdown(f"**Value:** {t['value']}")
                        st.markdown(f"**Reason:** {t['reason']}")
                    with c2:
                        st.markdown(f"**Rating:** {t['rating']}")
                        if st.button(f"Select #{i+1}", key=f"select_{i}"):
                            save_selection(t)
                    st.divider()
        else:
            st.info("No structured topics found in the latest report.")
    else:
        st.info("No reports found. Start a scan to generate topics.")

# --- Tab 2: Editor & Preview ---
with tab2:
    st.header("Article Editor")
    
    # File Selection
    draft_file = config.get_draft_file()
    final_file = config.get_final_file()
    
    file_options = {
        "Draft (draft.md)": draft_file,
        "Final (final.md)": final_file
    }
    
    selected_file_label = st.selectbox("Select File", list(file_options.keys()), index=1)
    selected_file_path = file_options[selected_file_label]
    
    # Load Content
    if "editor_content" not in st.session_state:
        st.session_state.editor_content = ""
        
    def load_file_content():
        if os.path.exists(selected_file_path):
            with open(selected_file_path, "r", encoding="utf-8") as f:
                st.session_state.editor_content = f.read()
        else:
            st.session_state.editor_content = ""
            st.warning(f"File not found: {selected_file_path}")

    # Load initially or when file changes
    if st.session_state.get("last_selected_file") != selected_file_path:
        load_file_content()
        st.session_state.last_selected_file = selected_file_path

    # Editor and Preview Layout
    col_edit, col_prev = st.columns(2)
    
    with col_edit:
        st.subheader("Markdown Editor")
        new_content = st.text_area(
            "Content",
            value=st.session_state.editor_content,
            height=600,
            label_visibility="collapsed"
        )
        
        # Save Button
        if new_content != st.session_state.editor_content:
            st.session_state.editor_content = new_content
            # Auto-save to file
            with open(selected_file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            st.toast("Saved!", icon="💾")

        # Refine Section
        st.markdown("---")
        st.subheader("✨ One-click Polish")
        refine_instruction = st.text_input("Refinement Instruction", placeholder="e.g. Make the intro more engaging")
        if st.button("Refine Article"):
            if not refine_instruction:
                st.warning("Please enter an instruction.")
            else:
                with st.spinner("Refining..."):
                    # Save current content first to ensure refiner sees latest
                    with open(selected_file_path, "w", encoding="utf-8") as f:
                        f.write(st.session_state.editor_content)
                    
                    # Call refiner
                    try:
                        # Depending on implementation, refiner modifies final.md or draft.md
                        # We should make sure we are editing the right file context
                        # refiner.refine_article writes to final.md usually
                        refiner.refine_article(refine_instruction)
                        
                        # Reload content from FINAL file (since refiner outputs there)
                        # Switch selection to Final if not already
                        target_file = final_file
                        with open(target_file, "r", encoding="utf-8") as f:
                            refined_content = f.read()
                        
                        st.session_state.editor_content = refined_content
                        # Update the file if we were looking at draft
                        if selected_file_path != target_file:
                            st.toast("Refined content saved to Final.md. Please switch to Final to view.", icon="ℹ️")
                        else:
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Refinement failed: {e}")

    with col_prev:
        st.subheader("Real-time Preview")
        
        # Format Style Selection (keep in sync with agents/formatter.py STYLE_TEMPLATES)
        style_options = ["green", "blue", "orange", "minimal", "purple", "livid", "vue", "typewriter"]
        selected_style = st.selectbox("Style", style_options, index=0)
        
        # Render HTML
        if st.session_state.editor_content:
            try:
                html_content = formatter.convert_md_to_html(st.session_state.editor_content)
                final_html = formatter.inline_css(html_content, style_name=selected_style)
                
                # Display in iframe
                st.components.v1.html(final_html, height=600, scrolling=True)
                
                # Copy Button (simulated help text)
                st.info("To copy: Click inside the preview, Ctrl+A, Ctrl+C")
            except Exception as e:
                st.error(f"Preview Error: {e}")
        else:
            st.write("No content to preview.")

    st.markdown("---")
    st.subheader("🕵️ Fact Check (Audit)")
    if st.button("Run Audit"):
        with st.spinner("Auditing..."):
            try:
                report = auditor.audit_article()
                if isinstance(report, str) and report.strip().startswith("## ⚠️ Audit Skipped"):
                    st.warning(report)
                elif isinstance(report, str):
                    with st.expander("Audit Report", expanded=True):
                        st.markdown(report)
                else:
                    st.info("Audit completed. See logs/output for details.")
            except Exception as e:
                st.error(f"Audit failed: {e}")
