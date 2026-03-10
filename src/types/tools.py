"""Shared tool request/response structures used by the MCP endpoints."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class ToolBaseModel(BaseModel):
    """Shared configuration for tool schemas."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=False)


class ToolMeta(ToolBaseModel):
    """Describes static metadata that identifies a tool."""

    name: str = Field(..., description="Tool identifier used in MCP registration")
    description: str | None = Field(
        None, description="Human-readable explanation of the tool"
    )
    tags: list[str] = Field(
        default_factory=list, description="Optional tags that categorize the tool"
    )


class ToolRequest(ToolBaseModel):
    """Generic request payload issued to a tool."""

    tool: str = Field(..., description="Name of the tool being invoked")
    payload: dict[str, object] = Field(
        default_factory=dict, description="Tool-specific parameters"
    )
    metadata: dict[str, object] = Field(
        default_factory=dict, description="Caller-managed metadata"
    )


class ToolResult(ToolBaseModel):
    """Base response envelope returned by MCP tools."""

    success: bool = Field(
        True, description="Indicates if the tool completed without errors"
    )
    data: dict[str, object] = Field(
        default_factory=dict, description="Tool-specific result payload"
    )
    meta: dict[str, object] = Field(
        default_factory=dict, description="Additional metadata returned by the tool"
    )
    error: str | None = Field(
        None, description="Human-readable error message when success=False"
    )


class ToolError(ToolBaseModel):
    """Rich error detail that tools can log or propagate."""

    message: str = Field(..., description="Short message explaining the failure")
    code: str | int | None = Field(
        None, description="Optional machine-friendly error code"
    )
    details: dict[str, object] = Field(
        default_factory=dict, description="Diagnostic details that help debugging"
    )
