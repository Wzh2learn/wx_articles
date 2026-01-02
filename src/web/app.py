import streamlit as st
import os
import json
import glob
import re
from datetime import datetime
import sys
from pathlib import Path

# Ensure project root is in path (supports running from anywhere)
CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR.parent
PROJECT_ROOT = SRC_DIR.parent
for p in (SRC_DIR, PROJECT_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

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

def get_recent_reports(limit=5):
    """Get recent hunt reports (sorted by mtime desc)"""
    topics_dir = Path(config.get_stage_dir("topics"))
    reports = sorted(topics_dir.glob("report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    recent = []
    for p in reports[:limit]:
        try:
            recent.append({
                "path": p,
                "name": p.name,
                "mtime": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "content": p.read_text(encoding="utf-8"),
            })
        except Exception:
            continue
    return recent

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


def read_file_safe(path: Path, max_chars=4000):
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        return text if len(text) <= max_chars else text[:max_chars] + "\n\n... (truncated)"
    except Exception:
        return None


def render_file_preview(title, path, height=220, key_suffix: str = ""):
    """Render a small read-only preview of a file if it exists"""
    st.markdown(f"**{title}**")
    p = Path(path)
    safe_suffix = key_suffix or "default"
    if p.exists():
        content = p.read_text(encoding="utf-8")
        st.text_area(
            label=f"{title} preview",
            value=content[:2000],
            height=height,
            key=f"preview_{p.name}_{safe_suffix}",
            label_visibility="collapsed",
            disabled=True
        )
    else:
        st.info(f"Not found: {p.name}")


def _urlencode_query(q: str) -> str:
    try:
        from urllib.parse import quote_plus
        return quote_plus(q)
    except Exception:
        return q


def _extract_image_placeholders(md: str):
    """Extract image placeholders from markdown."""
    todos = []
    autos = []
    covers = []

    if not md:
        return {"todo": [], "auto_img": [], "cover_prompt": []}

    for m in re.finditer(r">\s*TODO:\s*\[(.*?)\]\s*(?:\((.*?)\))?", md):
        desc = (m.group(1) or "").strip()
        params = (m.group(2) or "").strip()
        # try to read '搜索关键词: xxx'
        kw = ""
        kw_m = re.search(r"搜索关键词\s*[:：]\s*([^\)]*)", params)
        if kw_m:
            kw = kw_m.group(1).strip()
        todos.append({"desc": desc, "keywords": kw, "params": params})

    for m in re.finditer(r">\s*AUTO_IMG:\s*(.+?)(?:\n|$)", md):
        autos.append({"prompt": (m.group(1) or "").strip()})

    for m in re.finditer(r">\s*COVER_PROMPT:\s*(.+?)(?:\n|$)", md):
        covers.append({"prompt": (m.group(1) or "").strip()})

    return {"todo": todos, "auto_img": autos, "cover_prompt": covers}

# ================= Sidebar =================

st.sidebar.title("📚 History")
history = load_history()

# Date selector for workflow (affects downstream buttons)
selected_date = st.sidebar.date_input("工作日期", datetime.now())
date_str = selected_date.strftime("%Y-%m-%d")
config.set_working_date(date_str)

# Reverse to show newest first
for item in reversed(history):
    date = item.get("date", "Unknown Date")
    topic = item.get("topic", "Unknown Topic")
    angle = item.get("angle", "")
    st.sidebar.markdown(f"**{date}**")
    st.sidebar.text(f"{topic}\n({angle})")
    st.sidebar.markdown("---")

# ================= Sidebar: Editor Toolkit =================

st.sidebar.markdown("### 🧰 Editor Toolkit")

final_file_sidebar = Path(config.get_final_file())
audit_file_sidebar = Path(config.get_today_file("audit_report.md", stage="publish"))

with st.sidebar.expander("✨ Refine (润色)", expanded=False):
    refine_mode = st.radio(
        "Mode",
        ["Manual instruction", "Fix based on Audit"],
        index=0,
        key="toolkit_refine_mode",
        horizontal=False,
    )

    default_instruction = "整体润色并强化逻辑连贯，突出价值"
    if refine_mode == "Fix based on Audit":
        default_instruction = "请基于审计报告逐条修正：所有事实错误/夸大描述/缺少来源的断言，并补充必要说明；保持结构与 TODO/配图占位符不变。"

    toolkit_refine_instruction = st.text_area(
        "Instruction",
        value=default_instruction,
        height=120,
        key="toolkit_refine_instruction",
    )

    if st.button("Run Refine → writes final.md", key="toolkit_refine_btn", use_container_width=True, disabled=st.session_state.get("processing", False)):
        if not toolkit_refine_instruction.strip():
            st.warning("请输入润色指令")
        else:
            st.session_state.processing = True
            with st.spinner("Refining..."):
                try:
                    config.set_working_date(date_str)
                    refiner.refine_article(toolkit_refine_instruction.strip())
                    st.success("Refine 完成：final.md 已更新")
                except Exception as e:
                    st.error(f"Refine failed: {e}")
                finally:
                    st.session_state.processing = False
                    st.rerun()

    if final_file_sidebar.exists():
        st.caption("Preview final.md")
        st.text_area(
            "final.md preview",
            value=final_file_sidebar.read_text(encoding="utf-8")[:1500],
            height=180,
            label_visibility="collapsed",
            disabled=True,
            key="toolkit_final_preview",
        )

with st.sidebar.expander("🕵️ Audit (事实核查)", expanded=False):
    if st.button("Run Audit", key="toolkit_audit_btn", use_container_width=True, disabled=st.session_state.get("processing", False)):
        st.session_state.processing = True
        with st.spinner("Auditing..."):
            try:
                config.set_working_date(date_str)
                report = auditor.audit_article()
                if isinstance(report, str) and report.strip().startswith("## ⚠️ Audit Skipped"):
                    st.warning("Audit skipped（缺少输入或为空）。")
                else:
                    st.success("Audit completed")
            except Exception as e:
                st.error(f"Audit failed: {e}")
            finally:
                st.session_state.processing = False
                st.rerun()

    if audit_file_sidebar.exists():
        st.caption("Preview audit_report.md")
        st.text_area(
            "audit preview",
            value=audit_file_sidebar.read_text(encoding="utf-8")[:2000],
            height=220,
            label_visibility="collapsed",
            disabled=True,
            key="toolkit_audit_preview",
        )
    else:
        st.info("暂无 audit_report.md")

with st.sidebar.expander("🖼️ Images (手动控制)", expanded=False):
    st.write("已关闭 Draft 阶段的自动配图（避免浪费 token）。")
    st.caption("流程建议：先点搜索链接挑图；如果挑不到，再手动决定是否用 AI 生成。")

    if not final_file_sidebar.exists():
        st.info("先生成 draft/final 后，这里会显示配图占位符与搜索链接。")
    else:
        md = final_file_sidebar.read_text(encoding="utf-8")
        items = _extract_image_placeholders(md)

        st.write(f"COVER_PROMPT: {len(items['cover_prompt'])}")
        st.write(f"AUTO_IMG: {len(items['auto_img'])}")
        st.write(f"TODO: {len(items['todo'])}")

        st.markdown("---")
        st.markdown("**封面/素材：搜索链接（不生成、不落本地）**")

        # COVER
        if items["cover_prompt"]:
            with st.expander("COVER_PROMPT", expanded=False):
                for i, c in enumerate(items["cover_prompt"], 1):
                    q = c["prompt"]
                    g = f"https://www.google.com/search?tbm=isch&q={_urlencode_query(q)}"
                    b = f"https://www.bing.com/images/search?q={_urlencode_query(q)}"
                    st.markdown(f"**{i}.** {q}")
                    st.markdown(f"- Google: {g}")
                    st.markdown(f"- Bing: {b}")

        # AUTO_IMG
        if items["auto_img"]:
            with st.expander("AUTO_IMG", expanded=False):
                for i, a in enumerate(items["auto_img"], 1):
                    q = a["prompt"]
                    g = f"https://www.google.com/search?tbm=isch&q={_urlencode_query(q)}"
                    b = f"https://www.bing.com/images/search?q={_urlencode_query(q)}"
                    st.markdown(f"**{i}.** {q}")
                    st.markdown(f"- Google: {g}")
                    st.markdown(f"- Bing: {b}")

        # TODO
        if items["todo"]:
            with st.expander("TODO (截图/配图需求)", expanded=True):
                for i, t in enumerate(items["todo"], 1):
                    base_q = t["keywords"] or t["desc"]
                    base_q = base_q.strip() if base_q else ""
                    if not base_q:
                        continue
                    # A couple of opinionated query expansions as "AI search" hints
                    q1 = base_q
                    q2 = f"{base_q} screenshot"
                    g1 = f"https://www.google.com/search?tbm=isch&q={_urlencode_query(q1)}"
                    b1 = f"https://www.bing.com/images/search?q={_urlencode_query(q1)}"
                    g2 = f"https://www.google.com/search?tbm=isch&q={_urlencode_query(q2)}"
                    b2 = f"https://www.bing.com/images/search?q={_urlencode_query(q2)}"
                    st.markdown(f"**{i}.** {t['desc']}")
                    if t["keywords"]:
                        st.caption(f"搜索关键词: {t['keywords']}")
                    st.markdown(f"- Google: {g1}")
                    st.markdown(f"- Bing: {b1}")
                    st.markdown(f"- Google (screenshot): {g2}")
                    st.markdown(f"- Bing (screenshot): {b2}")
                    st.markdown("---")

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
            st.session_state.processing = True
            try:
                config.set_working_date(date_str)
                trend_hunter.main(topic=directed_topic if directed_topic else None)
                status.update(label="Scan Complete!", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Scan Failed", state="error")
                st.error(f"Error: {e}")
            finally:
                st.session_state.processing = False
                st.rerun()

    # Display multiple recent scans
    reports = get_recent_reports(limit=5)
    if reports:
        st.markdown("### Recent Scans (latest 5)")
        for idx, r in enumerate(reports):
            with st.expander(f"{r['name']} · {r['mtime']}", expanded=(idx == 0)):
                st.markdown("**Raw Report**")
                st.markdown(r["content"])
                
                topics = parse_topics_from_report(r["content"])
                if topics:
                    st.markdown("**Detected Topics**")
                    for i, t in enumerate(topics):
                        with st.container():
                            st.markdown(f"#### {t['title']}")
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                st.markdown(f"**Anchor:** {t['anchor']}")
                                st.markdown(f"**Value:** {t['value']}")
                                st.markdown(f"**Reason:** {t['reason']}")
                            with c2:
                                st.markdown(f"**Rating:** {t['rating']}")
                                if st.button(f"Select #{idx+1}-{i+1}", key=f"select_{idx}_{i}"):
                                    save_selection(t)
                                    st.info("已记录到历史；后续可运行 Final Decision、Research、Draft。")
                            st.divider()
                else:
                    st.info("No structured topics found in this report.")
    else:
        st.info("No reports found. Start a scan to generate topics.")

    # Workflow chain (per SOP)
    st.markdown("---")
    st.subheader("🧭 Workflow (SOP)")
    
    # Use session state to store processing status to prevent redundant clicks
    if "processing" not in st.session_state:
        st.session_state.processing = False
    
    colw1, colw2 = st.columns(2)

    topics_dir = Path(config.get_stage_dir("topics"))
    final_decision_file = topics_dir / "FINAL_DECISION.md"
    research_notes_file = Path(config.get_research_notes_file())
    draft_file = Path(config.get_draft_file())
    final_file = Path(config.get_final_file())
    html_file = Path(config.get_html_file())
    audit_file = Path(config.get_today_file("audit_report.md", stage="publish"))

    with colw1:
        st.markdown("**Step 1 · Final Decision**")
        if st.button("🏆 Generate Decision", key="btn_final_decision", use_container_width=True, disabled=st.session_state.processing):
            st.session_state.processing = True
            with st.spinner("Generating FINAL_DECISION..."):
                try:
                    config.set_working_date(date_str)
                    trend_hunter.final_summary()
                    st.success("FINAL_DECISION.md generated!")
                except Exception as e:
                    st.error(f"Failed: {e}")
            with st.spinner("Running Researcher..."):
                try:
                    config.set_working_date(date_str)
                    cli_run.run_researcher()
                    st.success("Research completed!")
                except Exception as e:
                    st.error(f"Failed: {e}")
                finally:
                    st.session_state.processing = False
                    st.rerun()
        render_file_preview("notes.txt (research)", research_notes_file, height=180, key_suffix="workflow_research")

        st.markdown("---")
        st.markdown("**Step 4 · Refine (可选)**")
        refine_instruction = st.text_input("Refine instruction", value="整体润色并强化逻辑连贯，突出价值", key="refine_instruction_workflow")
        if st.button("✨ Refine Final.md", key="btn_refine", use_container_width=True, disabled=st.session_state.processing):
            st.session_state.processing = True
            if not refine_instruction.strip():
                st.warning("请输入润色指令")
                st.session_state.processing = False
            else:
                with st.spinner("Refining..."):
                    try:
                        config.set_working_date(date_str)
                        refiner.refine_article(refine_instruction.strip())
                        st.success("Refine 完成，已写入 final.md")
                    except Exception as e:
                        st.error(f"Failed: {e}")
                    finally:
                        st.session_state.processing = False
                        st.rerun()
        render_file_preview("final.md", final_file, height=140, key_suffix="workflow_refine_final")

        st.markdown("---")
        st.markdown("**Step 5 · Audit (可选)**")
        if st.button("🕵️ Run Audit", key="btn_audit", use_container_width=True, disabled=st.session_state.processing):
            st.session_state.processing = True
            with st.spinner("Auditing..."):
                try:
                    report = auditor.audit_article()
                    if isinstance(report, str) and report.strip().startswith("## ⚠️ Audit Skipped"):
                        st.warning(report)
                    elif isinstance(report, str):
                        st.success("Audit completed. 报告见下方预览")
                    else:
                        st.info("Audit completed. See logs/output for details.")
                except Exception as e:
                    st.error(f"Audit failed: {e}")
                finally:
                    st.session_state.processing = False
                    st.rerun()
        if audit_file.exists():
            render_file_preview("audit_report.md", audit_file, height=140, key_suffix="workflow_audit")
        else:
            st.info("暂无 audit_report.md，可运行 Audit 获取。")

        st.markdown("---")
        st.markdown("**Step 6 · Format (HTML)**")
        fmt_style = st.selectbox("Style", ["green", "blue", "orange", "minimal", "purple", "livid", "vue", "typewriter"], key="fmt_style_sidebar")
        if st.button("🖨️ Generate HTML", key="btn_format", use_container_width=True, disabled=st.session_state.processing):
            st.session_state.processing = True
            with st.spinner("Formatting to HTML..."):
                try:
                    config.set_working_date(date_str)
                    cli_run.run_formatter(style=fmt_style)
                    st.success("HTML generated (output.html)!")
                except Exception as e:
                    st.error(f"Failed: {e}")
                finally:
                    st.session_state.processing = False
                    st.rerun()
        render_file_preview("final.md", final_file, height=120, key_suffix="workflow_format_final")
        render_file_preview("output.html (raw)", html_file, height=120, key_suffix="workflow_format_html")

# === Hunt Controls ===
with st.sidebar:
    st.markdown("### 🎯 选题雷达 (Hunt)")
    hunt_topic = st.text_input("定向搜索主题 (可选)", placeholder="如: Cursor 技巧", key="hunt_topic_input")
    
    # v5.1: 仿写模式输入
    st.markdown("---")
    st.markdown("📝 **仿写模式**")
    imitate_input = st.text_input("参考文章 URL 或本地路径", placeholder="https://mp.weixin.qq.com/s/...", key="imitate_input")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("开始扫描", type="primary", key="start_hunt_btn", disabled=st.session_state.get("processing", False)):
            st.session_state.processing = True
            st.session_state.hunt_mode = "normal"
            st.rerun()
    
    with col2:
        if st.button("开始仿写", key="start_imitate_btn", disabled=st.session_state.get("processing", False) or not imitate_input):
            st.session_state.processing = True
            st.session_state.hunt_mode = "imitate"
            st.rerun()

# === Process Handling ===
if st.session_state.get("processing", False):
    with st.spinner("🚀 AI 正在全网搜寻情报..."):
        try:
            config.set_working_date(date_str)
            hunt_mode = st.session_state.get("hunt_mode", "normal")
            
            if hunt_mode == "imitate":
                logger.info(f"UI: 启动仿写模式 -> {imitate_input}")
                trend_hunter.imitate_mode(imitate_input)
                st.success("✅ 极速仿写完成！已直接生成最终决策，可立即开始深度研究。")
            else:
                logger.info(f"UI: 启动扫描模式 -> {hunt_topic}")
                trend_hunter.main(topic=hunt_topic if hunt_topic else None)
                st.success("✅ 选题扫描完成！")
        except Exception as e:
            st.error(f"❌ 运行失败: {e}")
        finally:
            st.session_state.processing = False
            st.session_state.hunt_mode = None
            st.rerun()

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
