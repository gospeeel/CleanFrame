"""Pipeline orchestration: parse -> detect -> classify -> recommend."""

from llm.pipeline.full_pipeline import process_script, run_pipeline

__all__ = ["process_script", "run_pipeline"]
