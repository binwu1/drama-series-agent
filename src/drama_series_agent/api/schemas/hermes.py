# -*- coding: utf-8 -*-
"""Pydantic schemas for Hermes Agent API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    title: str
    premise: Optional[str] = None


class ConversationOut(BaseModel):
    conversation_id: str
    series_id: str
    project_dir: str
    title: str
    updated_at: str


class ConversationDetail(ConversationOut):
    status: dict[str, Any] = Field(default_factory=dict)


class PostMessageRequest(BaseModel):
    content: str


class PostMessageResponse(BaseModel):
    assistant_message: dict[str, Any]
    status: dict[str, Any]
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)


class ActionResponse(BaseModel):
    ok: bool = True
    status: dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None


class S2ActionRequest(BaseModel):
    episode_id: Optional[str] = None
    force: bool = False
    from_shot: Optional[str] = None
    run_in_background: bool = True


class JobControlRequest(BaseModel):
    job_id: Optional[str] = None
    episode_id: Optional[str] = None
    from_shot: Optional[str] = None
    force: bool = False
    run_in_background: bool = True


class LlmSettings(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class WorkflowSettings(BaseModel):
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_api_key: Optional[str] = None
    runninghub_api_key: Optional[str] = None
    runninghub_concurrent_limit: int = 1
    runninghub_instance_type: Optional[str] = None
    image_default_workflow: Optional[str] = None
    image_reference_workflow: Optional[str] = None
    video_default_workflow: Optional[str] = None
    tts_default_workflow: Optional[str] = None
    aspect: str = "9:16"


class HermesSettingsOut(BaseModel):
    llm: LlmSettings
    workflow: WorkflowSettings
    presets: list[dict[str, Any]] = Field(default_factory=list)
    configured: bool = False
    video_workflow_options: list[str] = Field(default_factory=list)
    image_workflow_options: list[str] = Field(default_factory=list)
    aspect_options: list[str] = Field(
        default_factory=lambda: ["9:16", "16:9", "1:1"]
    )


class HermesSettingsUpdate(BaseModel):
    llm: Optional[LlmSettings] = None
    workflow: Optional[WorkflowSettings] = None
    apply_to_conversation_id: Optional[str] = None


class LlmTestRequest(BaseModel):
    api_key: str = ""
    base_url: str = ""


class LlmTestResponse(BaseModel):
    ok: bool
    message: str = ""
    models: list[str] = Field(default_factory=list)


class LiteraryEpisodeOut(BaseModel):
    episode_id: str
    content: str = ""
    status: Optional[str] = None
    status_zh: Optional[str] = None
    series_id: Optional[str] = None
    title: Optional[str] = None


class LiterarySaveRequest(BaseModel):
    content: str


class CastUploadResponse(BaseModel):
    ok: bool = True
    character: str
    status: dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None


class CastGenerateRequest(BaseModel):
    character: str
    appearance: str = ""
    style: str = "cinematic portrait, front view, character design sheet"
    width: int = 1024
    height: int = 1024
