import os
import json
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.brain_compressor import BrainCompressor

@pytest.fixture
def temp_workspace():
    """Fixture to set up a temporary workspace directory."""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    
    # Create wiki structure
    wiki = workspace / "wiki"
    wiki.mkdir()
    
    # Create mock plan files
    plan1 = workspace / "project_plan.md"
    plan1.write_text("# Project Plan\nObjective is to trade safely.", encoding="utf-8")
    
    plan2 = workspace / "plan_step_01.md"
    plan2.write_text("# Step 1 Plan\nImplementing pattern recognition.", encoding="utf-8")
    
    # Create mock brain directory in workspace to mock app data
    brain = workspace / "mock_appdata" / "brain"
    brain.mkdir(parents=True)
    
    conv_folder = brain / "mock_conversation_123"
    conv_folder.mkdir()
    
    logs = conv_folder / ".system_generated" / "logs"
    logs.mkdir(parents=True)
    
    # Write mock transcript
    transcript = logs / "transcript.jsonl"
    with open(transcript, "w", encoding="utf-8") as f:
        f.write(json.dumps({"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "How do we build the bot?"}) + "\n")
        f.write(json.dumps({"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "We build it by writing Python code."}) + "\n")

    yield workspace
    shutil.rmtree(temp_dir)

@pytest.mark.asyncio
async def test_brain_compressor_pipeline(temp_workspace):
    # Instantiate compressor targeting temp workspace
    compressor = BrainCompressor(workspace_root=temp_workspace)
    
    # Patch get_brain_dir to return our mock brain folder
    mock_brain_dir = temp_workspace / "mock_appdata" / "brain"
    with patch.object(compressor, "get_brain_dir", return_value=mock_brain_dir):
        # We also mock call_llm_summarize to run offline / mock summaries for speed
        with patch.object(compressor, "call_llm_summarize", side_effect=lambda text, name, is_chat: f"Summary of {name}"):
            index_path = await compressor.run_sync_and_compile()
            
            # 1. Check if raw and summaries folders are created
            assert compressor.raw_chats_dir.exists()
            assert compressor.raw_plans_dir.exists()
            assert compressor.summaries_chats_dir.exists()
            assert compressor.summaries_plans_dir.exists()
            
            # 2. Check if raw chat is copied and formatted
            raw_chat_file = compressor.raw_chats_dir / "mock_conversation_123_chat.md"
            assert raw_chat_file.exists()
            chat_content = raw_chat_file.read_text(encoding="utf-8")
            assert "User:" in chat_content
            assert "Assistant:" in chat_content
            
            # 3. Check if raw plans are copied
            raw_plan = compressor.raw_plans_dir / "project_plan.md"
            assert raw_plan.exists()
            
            # 4. Check if summaries exist
            assert (compressor.summaries_chats_dir / "mock_conversation_123_summary.md").exists()
            assert (compressor.summaries_plans_dir / "project_plan_summary.md").exists()
            
            # 5. Check consolidated index file
            assert index_path.exists()
            index_content = index_path.read_text(encoding="utf-8")
            assert "Second Brain Summaries & Index" in index_content
            assert "project_plan.md" in index_content
            assert "mock_conversation_123" in index_content

@pytest.mark.asyncio
async def test_brain_compressor_caching(temp_workspace):
    compressor = BrainCompressor(workspace_root=temp_workspace)
    mock_brain_dir = temp_workspace / "mock_appdata" / "brain"
    
    with patch.object(compressor, "get_brain_dir", return_value=mock_brain_dir):
        # Patch call_llm_summarize to count calls
        mock_summarizer = AsyncMock(return_value="Some Summary")
        with patch.object(compressor, "call_llm_summarize", mock_summarizer):
            # First run
            await compressor.run_sync_and_compile()
            first_call_count = mock_summarizer.call_count
            assert first_call_count > 0
            
            # Second run without changes
            mock_summarizer.reset_mock()
            await compressor.run_sync_and_compile()
            assert mock_summarizer.call_count == 0  # Cached, no new calls
            
            # Modify a plan file to break cache. Bump mtime explicitly so the
            # change is strictly newer than the summary even on coarse or
            # fast-clock filesystems (the cache check is mtime-based).
            plan1 = temp_workspace / "project_plan.md"
            plan1.write_text("# Project Plan\nUpdated text.", encoding="utf-8")
            import time
            future = time.time() + 5
            os.utime(plan1, (future, future))
            
            # Third run with changes
            mock_summarizer.reset_mock()
            await compressor.run_sync_and_compile()
            assert mock_summarizer.call_count == 1  # Summarizes the changed plan only
