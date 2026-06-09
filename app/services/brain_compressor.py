import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from app.core.config import AI_PROVIDER
from app.services.ai_kimi import get_ai_provider_config

class BrainCompressor:
    def __init__(self, workspace_root: str | Path = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.wiki_dir = self.workspace_root / "wiki"
        self.raw_dir = self.wiki_dir / "raw"
        self.raw_chats_dir = self.raw_dir / "chats"
        self.raw_plans_dir = self.raw_dir / "plans"
        
        self.summaries_dir = self.wiki_dir / "summaries"
        self.summaries_chats_dir = self.summaries_dir / "chats"
        self.summaries_plans_dir = self.summaries_dir / "plans"
        
        # Ensure directories exist
        self.raw_chats_dir.mkdir(parents=True, exist_ok=True)
        self.raw_plans_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_chats_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_plans_dir.mkdir(parents=True, exist_ok=True)

    def get_brain_dir(self) -> Path:
        """Locates the Antigravity brain directory in user profile."""
        # Check standard location C:\Users\<username>\.gemini\antigravity\brain
        home_brain = Path.home() / ".gemini" / "antigravity" / "brain"
        if home_brain.exists():
            return home_brain
        # Fallback to local or env config
        appdata_env = os.getenv("APPDATA")
        if appdata_env:
            appdata_brain = Path(appdata_env) / "antigravity" / "brain"
            if appdata_brain.exists():
                return appdata_brain
        return Path("brain_fallback")

    def parse_transcript_to_markdown(self, transcript_path: Path) -> str:
        """Parses a transcript.jsonl file into a readable markdown chat format."""
        if not transcript_path.exists():
            return ""
        
        lines = []
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                for line_str in f:
                    line_str = line_str.strip()
                    if not line_str:
                        continue
                    try:
                        step = json.loads(line_str)
                        source = step.get("source")
                        step_type = step.get("type")
                        content = step.get("content", "")
                        
                        # Filter to User and Assistant turns
                        if step_type == "USER_INPUT":
                            lines.append(f"### 👤 User:\n{content}\n")
                        elif step_type in ("PLANNER_RESPONSE", "MODEL_RESPONSE") or (source == "MODEL" and step_type == "PLANNER_RESPONSE"):
                            lines.append(f"### 🤖 Assistant:\n{content}\n")
                        elif source == "MODEL" and step_type == "PLANNER_RESPONSE":
                            lines.append(f"### 🤖 Assistant:\n{content}\n")
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            return f"Error parsing transcript: {e}"
        
        return "\n".join(lines)

    async def call_llm_summarize(self, text: str, name: str, is_chat: bool = False) -> str:
        """Calls the configured AI provider to summarize a plan or chat transcript."""
        provider = (AI_PROVIDER or "moonshot").strip().lower()
        if provider in {"mock", "offline", "none"}:
            return self._mock_summary(text, name, is_chat)

        try:
            from openai import AsyncOpenAI
            provider_config = get_ai_provider_config(provider)
            if not provider_config.api_key:
                return self._mock_summary(text, name, is_chat)

            client = AsyncOpenAI(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
            )

            system_prompt = (
                "You are an expert technical summarizer and part of a Swarm Intelligence Second Brain.\n"
                "Provide a concise, high-level summary of the provided text. Focus on key objectives, "
                "accomplished steps, decisions made, metrics, and open actions.\n"
                "Structure the summary with:\n"
                "- **Goal**: (1-2 sentences overview)\n"
                "- **Key Accomplishments**: (2-3 bullet points)\n"
                "- **Decisions & Open Items**: (1-2 bullet points)\n"
                "Return only the markdown summary, no other text."
            )
            
            doc_type = "chat conversation transcript" if is_chat else "project planning document"
            max_chars = 10000 if provider in {"lmstudio", "lm-studio", "local"} else 30000
            user_prompt = f"Please summarize this {doc_type} named '{name}':\n\n{text[:max_chars]}"
            
            response = await client.chat.completions.create(
                model=provider_config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error calling LLM for summarization: {e}")
            return self._mock_summary(text, name, is_chat)

    def _mock_summary(self, text: str, name: str, is_chat: bool) -> str:
        """Generates a structured mock summary when offline or AI provider fails."""
        lines = text.splitlines()
        headers = [line.strip("# ").strip() for line in lines if line.startswith("#") and len(line) > 2]
        
        summary = f"### [Mock Summary] {name}\n\n"
        if is_chat:
            summary += "- **Goal**: Summarize a developer-assistant interaction session.\n"
            # Count turns
            user_turns = text.count("### 👤 User:")
            assistant_turns = text.count("### 🤖 Assistant:")
            summary += f"- **Key Accomplishments**:\n"
            summary += f"  - Analyzed interaction containing {user_turns} user requests and {assistant_turns} AI turns.\n"
            summary += f"  - Captured context related to active development session.\n"
        else:
            summary += f"- **Goal**: Maintain records for project planning document: {name}.\n"
            summary += f"- **Key Accomplishments**:\n"
            if headers:
                summary += f"  - Document structure includes sections: {', '.join(headers[:5])}.\n"
            else:
                summary += f"  - Processed document of size {len(text)} characters.\n"
        
        summary += "- **Decisions & Open Items**: Needs active AI connection to perform full semantic synthesis."
        return summary

    async def compress_and_summarize_plans(self) -> list[dict[str, Any]]:
        """Scans workspace plans, copies to raw folder, and creates/updates summaries."""
        summarized_plans = []
        
        # Files to target in workspace root
        target_patterns = ["*plan*.md", "01_jules_masterprompt*.md", "AGENTS.md", "JULES_24H_SCHEDULE.md", "README.md"]
        plan_files: list[Path] = []
        for pattern in target_patterns:
            plan_files.extend(list(self.workspace_root.glob(pattern)))
            
        # Also check current brain folder for artifacts (like implementation_plan.md)
        brain_dir = self.get_brain_dir()
        if brain_dir.exists():
            for conversation_folder in brain_dir.iterdir():
                if conversation_folder.is_dir():
                    plan_files.extend(list(conversation_folder.glob("implementation_plan.md")))
                    plan_files.extend(list(conversation_folder.glob("walkthrough.md")))
                    plan_files.extend(list(conversation_folder.glob("task.md")))
                    
        # Remove duplicates based on absolute path
        unique_plans = {}
        for p in plan_files:
            unique_plans[p.resolve()] = p
            
        for plan_path in unique_plans.values():
            if not plan_path.exists() or not plan_path.is_file():
                continue
                
            try:
                content = plan_path.read_text(encoding="utf-8")
                # Save raw plan to wiki/raw/plans/
                raw_filename = f"{plan_path.name}"
                # If it is from a brain directory, prefix it with conversation folder name to avoid collisions
                if "antigravity" in str(plan_path):
                    conv_id = plan_path.parent.name
                    raw_filename = f"{conv_id}_{plan_path.name}"
                    
                raw_dest = self.raw_plans_dir / raw_filename
                raw_dest.write_text(content, encoding="utf-8")
                
                # Check summary cache
                summary_dest = self.summaries_plans_dir / f"{raw_dest.stem}_summary.md"
                needs_update = True
                if summary_dest.exists():
                    raw_mtime = plan_path.stat().st_mtime
                    sum_mtime = summary_dest.stat().st_mtime
                    if sum_mtime >= raw_mtime:
                        needs_update = False
                        
                if needs_update:
                    print(f"[BrainCompressor] Summarizing plan: {plan_path.name}...")
                    summary_content = await self.call_llm_summarize(content, plan_path.name, is_chat=False)
                    summary_dest.write_text(summary_content, encoding="utf-8")
                else:
                    summary_content = summary_dest.read_text(encoding="utf-8")
                    
                summarized_plans.append({
                    "name": plan_path.name,
                    "raw_path": raw_dest,
                    "summary_path": summary_dest,
                    "summary": summary_content,
                    "modified": datetime.fromtimestamp(plan_path.stat().st_mtime, tz=timezone.utc).isoformat()
                })
            except Exception as e:
                print(f"Error compressing plan {plan_path}: {e}")
                
        return summarized_plans

    async def compress_and_summarize_chats(self) -> list[dict[str, Any]]:
        """Scans Antigravity chats, compiles them to raw files, and summarizes them."""
        summarized_chats = []
        brain_dir = self.get_brain_dir()
        if not brain_dir.exists():
            print(f"[BrainCompressor] Brain directory not found at {brain_dir}")
            return summarized_chats
            
        for conv_folder in brain_dir.iterdir():
            if not conv_folder.is_dir():
                continue
                
            transcript_path = conv_folder / ".system_generated" / "logs" / "transcript.jsonl"
            if not transcript_path.exists():
                continue
                
            try:
                # 1. Format raw JSONL into clean markdown dialogue
                raw_markdown_chat = self.parse_transcript_to_markdown(transcript_path)
                if not raw_markdown_chat:
                    continue
                    
                # 2. Save raw chat to wiki/raw/chats/
                conv_id = conv_folder.name
                raw_dest = self.raw_chats_dir / f"{conv_id}_chat.md"
                raw_dest.write_text(raw_markdown_chat, encoding="utf-8")
                
                # 3. Check summary cache
                summary_dest = self.summaries_chats_dir / f"{conv_id}_summary.md"
                needs_update = True
                if summary_dest.exists():
                    raw_mtime = transcript_path.stat().st_mtime
                    sum_mtime = summary_dest.stat().st_mtime
                    if sum_mtime >= raw_mtime:
                        needs_update = False
                        
                if needs_update:
                    print(f"[BrainCompressor] Summarizing chat: {conv_id[:8]}...")
                    # We can use a friendly name for the conversation. Let's look for a title or use conv_id
                    title = f"Conversation {conv_id[:8]}"
                    # If we can parse a title from the first system message, use that
                    summary_content = await self.call_llm_summarize(raw_markdown_chat, title, is_chat=True)
                    summary_dest.write_text(summary_content, encoding="utf-8")
                else:
                    summary_content = summary_dest.read_text(encoding="utf-8")
                    
                summarized_chats.append({
                    "conversation_id": conv_id,
                    "raw_path": raw_dest,
                    "summary_path": summary_dest,
                    "summary": summary_content,
                    "modified": datetime.fromtimestamp(transcript_path.stat().st_mtime, tz=timezone.utc).isoformat()
                })
            except Exception as e:
                print(f"Error compressing chat {conv_folder.name}: {e}")
                
        return summarized_chats

    async def run_sync_and_compile(self) -> Path:
        """Executes full compression pipeline and writes the master consolidated index file."""
        print("[BrainCompressor] Running compression and summarization pipeline...")
        plans_data = await self.compress_and_summarize_plans()
        chats_data = await self.compress_and_summarize_chats()
        
        now_str = datetime.now(timezone.utc).isoformat()
        
        # Generate consolidated index wiki/second_brain_summaries.md
        index_file = self.wiki_dir / "second_brain_summaries.md"
        
        md = f"""# 🧠 Second Brain Summaries & Index

*Last Compiled: {now_str}*

This consolidated index serves as a fast-browse layer for the Swarm Intelligence AI.
By reading this index, the AI can scan the high-level summaries. If more details are required for a matching topic, it can access the linked raw data.

---

## 📋 Project Plans Summaries

"""
        if not plans_data:
            md += "No plans compiled.\n"
        for plan in sorted(plans_data, key=lambda x: x["name"]):
            # Format absolute file link or relative file link. Let's use file:/// scheme for absolute links
            # and standard relative markdown links as fallbacks.
            raw_url = plan["raw_path"].resolve().as_uri()
            sum_url = plan["summary_path"].resolve().as_uri()
            
            md += f"### [{plan['name']}]({raw_url})\n"
            md += f"- **Last Modified**: `{plan['modified']}`\n"
            md += f"- **Summary**: [View Full Summary]({sum_url})\n\n"
            md += f"{plan['summary']}\n\n"
            md += "---\n\n"
            
        md += "\n## 💬 Conversation & Chats Summaries\n\n"
        if not chats_data:
            md += "No conversation logs compiled.\n"
        for chat in sorted(chats_data, key=lambda x: x["modified"], reverse=True):
            raw_url = chat["raw_path"].resolve().as_uri()
            sum_url = chat["summary_path"].resolve().as_uri()
            
            md += f"### [Conversation {chat['conversation_id'][:8]}]({raw_url})\n"
            md += f"- **Conversation ID**: `{chat['conversation_id']}`\n"
            md += f"- **Last Active**: `{chat['modified']}`\n"
            md += f"- **Summary**: [View Full Summary]({sum_url})\n\n"
            md += f"{chat['summary']}\n\n"
            md += "---\n\n"
            
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(md)
            
        print(f"[BrainCompressor] Successfully wrote {index_file}!")
        return index_file
