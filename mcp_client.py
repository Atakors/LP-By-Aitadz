"""
mcp_client.py
=============
Cloudflare MCP Server Portal client for AITADZ Teacher Assistant.

Routes lesson-plan generation requests through the centralized Cloudflare MCP
Server Portal using Cloudflare Access Service Token authentication headers:
  - CF-Access-Client-Id
  - CF-Access-Client-Secret

Supports MCP JSON-RPC 2.0 (tools/call), Streamable HTTP / SSE responses via
httpx + official mcp SDK, and Cloudflare AI Gateway / OpenAI-compatible JSON
endpoints, with strict schema normalization via didactic_rules.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, Optional

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from didactic_rules import (
    build_system_prompt,
    get_grade_meta,
    get_section_by_id,
    get_sequence_by_id,
    get_session_blueprint,
    normalize_grade,
    validate_and_normalize_lesson_plan,
)

logger = logging.getLogger(__name__)


def extract_json_payload(raw_text: Any) -> Optional[Dict[str, Any]]:
    """
    Extract a JSON dictionary from raw text, markdown-fenced JSON blocks,
    MCP tool results (`content[0].text` / `structuredContent`), or AI Gateway
    chat completion envelopes (`choices[0].message.content`).
    """
    if isinstance(raw_text, dict):
        # 1. Direct lesson-plan payload
        if any(k in raw_text for k in ("header", "stages", "whiteboard_layout")):
            return raw_text

        # 2. MCP JSON-RPC 2.0 envelope: {"jsonrpc": "2.0", "result": {...}}
        if "result" in raw_text and isinstance(raw_text["result"], dict):
            nested = extract_json_payload(raw_text["result"])
            if nested is not None:
                return nested

        # 3. MCP structuredContent
        if "structuredContent" in raw_text and isinstance(raw_text["structuredContent"], dict):
            nested = extract_json_payload(raw_text["structuredContent"])
            if nested is not None:
                return nested

        # 4. MCP tool content array: {"content": [{"type": "text", "text": "..."}]}
        content = raw_text.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    nested = extract_json_payload(item["text"])
                    if nested is not None:
                        return nested

        # 5. OpenAI / Cloudflare AI Gateway envelope
        choices = raw_text.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict) and msg.get("content"):
                    nested = extract_json_payload(msg["content"])
                    if nested is not None:
                        return nested
                if isinstance(first.get("text"), str):
                    nested = extract_json_payload(first["text"])
                    if nested is not None:
                        return nested
        return None

    if not isinstance(raw_text, str):
        return None

    text = raw_text.strip()
    if not text:
        return None

    # Handle SSE stream payloads ("data: {...}")
    if "data:" in text and not text.startswith("{"):
        sse_chunks = []
        for line in text.splitlines():
            line_s = line.strip()
            if line_s.startswith("data:"):
                data_part = line_s[5:].strip()
                if data_part and data_part != "[DONE]":
                    sse_chunks.append(data_part)
        for chunk in reversed(sse_chunks):
            parsed = extract_json_payload(chunk)
            if parsed is not None:
                return parsed

    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        parsed_obj = json.loads(text)
        if isinstance(parsed_obj, dict):
            return extract_json_payload(parsed_obj) or parsed_obj
    except json.JSONDecodeError:
        pass

    # Fallback: locate outermost {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed_obj = json.loads(text[start : end + 1])
            if isinstance(parsed_obj, dict):
                return extract_json_payload(parsed_obj) or parsed_obj
        except json.JSONDecodeError:
            return None

    return None


class CloudflareMCPClient:
    """Client for the centralized Cloudflare MCP Server Portal."""

    def __init__(
        self,
        portal_url: Optional[str] = None,
        cf_client_id: Optional[str] = None,
        cf_client_secret: Optional[str] = None,
        tool_name: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 45.0,
    ) -> None:
        self.portal_url = (portal_url or os.environ.get("CLOUDFLARE_MCP_PORTAL_URL", "")).strip()
        self.cf_client_id = (cf_client_id or os.environ.get("CF_ACCESS_CLIENT_ID", "")).strip()
        self.cf_client_secret = (
            cf_client_secret or os.environ.get("CF_ACCESS_CLIENT_SECRET", "")
        ).strip()
        self.tool_name = (
            tool_name or os.environ.get("CF_MCP_TOOL_NAME", "generate_lesson_plan")
        ).strip()
        self.model = (model or os.environ.get("CF_MCP_MODEL", "")).strip()
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.portal_url)

    def get_auth_headers(self) -> Dict[str, str]:
        """Return Cloudflare Access Service Token headers required by the MCP Portal."""
        return {
            "CF-Access-Client-Id": self.cf_client_id,
            "CF-Access-Client-Secret": self.cf_client_secret,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _build_mcp_arguments(
        self,
        grade: str,
        sequence_id: str,
        section_id: str,
        session_id: str,
        topic: str,
    ) -> Dict[str, Any]:
        g = normalize_grade(grade)
        grade_meta = get_grade_meta(g)
        seq = get_sequence_by_id(g, sequence_id)
        sec = get_section_by_id(g, sequence_id, section_id)
        bp = get_session_blueprint(g, session_id)
        system_prompt, user_prompt = build_system_prompt(g, sequence_id, section_id, session_id, topic)

        return {
            "grade": g,
            "sequence": f"Sequence {seq['number']}: {seq['title']}",
            "sequence_id": seq["id"],
            "section": sec["title"],
            "section_id": sec["id"],
            "session": bp["title"],
            "session_id": bp["id"],
            "topic": (topic or "").strip() or sec["title"],
            "duration_minutes": int(grade_meta["session_duration_minutes"]),
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "didactic_schema": {
                "reading_word_target": sec["reading_word_target"],
                "writing_word_target": sec["writing_word_target"],
                "phonics_target": sec["phonics_target"],
                "implicit_grammar": sec["implicit_grammar"],
                "stages": [
                    {"stage": st["stage"], "minutes": st["minutes"], "interaction": st["interaction"]}
                    for st in bp["stages"]
                ],
                "non_monetary_gamification_only": True,
            },
        }

    async def _invoke_via_mcp_sdk(self, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Invoke the portal using the official MCP Streamable HTTP client session."""
        headers = self.get_auth_headers()
        async with streamablehttp_client(
            self.portal_url,
            headers=headers,
            timeout=self.timeout,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.call_tool(self.tool_name, arguments=arguments)
                if getattr(tool_result, "structuredContent", None):
                    parsed = extract_json_payload(tool_result.structuredContent)
                    if parsed is not None:
                        return parsed
                for item in getattr(tool_result, "content", []) or []:
                    text = getattr(item, "text", None)
                    if text:
                        parsed = extract_json_payload(text)
                        if parsed is not None:
                            return parsed
        return None

    async def _invoke_via_http(
        self,
        arguments: Dict[str, Any],
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[Dict[str, Any]]:
        """Invoke MCP JSON-RPC 2.0 (tools/call) or AI Gateway chat completions over HTTP."""
        headers = self.get_auth_headers()
        is_chat_gateway = self.portal_url.rstrip("/").endswith("/chat/completions")

        if is_chat_gateway:
            payload: Dict[str, Any] = {
                "messages": [
                    {"role": "system", "content": arguments["system_prompt"]},
                    {"role": "user", "content": arguments["user_prompt"]},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            }
            if self.model:
                payload["model"] = self.model
        else:
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": self.tool_name,
                    "arguments": arguments,
                },
            }

        async def _post(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(self.portal_url, headers=headers, json=payload)

        if http_client is not None:
            response = await _post(http_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await _post(client)

        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()

        if "text/event-stream" in content_type:
            return extract_json_payload(response.text)

        try:
            body_json = response.json()
            return extract_json_payload(body_json)
        except ValueError:
            return extract_json_payload(response.text)

    async def generate_lesson_plan(
        self,
        grade: str,
        sequence_id: str,
        section_id: str,
        session_id: str,
        topic: str = "",
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """
        Request a structured Didactic-compliant lesson plan from the Cloudflare
        MCP Server Portal, falling back gracefully to local Didactic synthesis
        if the portal is unconfigured or temporarily unreachable.
        """
        g = normalize_grade(grade)
        arguments = self._build_mcp_arguments(g, sequence_id, section_id, session_id, topic)
        raw_plan: Optional[Dict[str, Any]] = None

        if self.is_configured():
            try:
                raw_plan = await self._invoke_via_http(arguments, http_client=http_client)
                if raw_plan is None and http_client is None:
                    raw_plan = await self._invoke_via_mcp_sdk(arguments)
            except Exception as exc:
                logger.warning(
                    "Cloudflare MCP Portal call failed (%s); falling back to Didactic Guide synthesizer.",
                    exc,
                )
        else:
            logger.info(
                "CLOUDFLARE_MCP_PORTAL_URL is not configured; using local Didactic Guide synthesizer."
            )

        return validate_and_normalize_lesson_plan(
            raw_plan,
            grade=g,
            sequence_id=sequence_id,
            section_id=section_id,
            session_id=session_id,
            topic=topic,
        )

    def generate_lesson_plan_sync(
        self,
        grade: str,
        sequence_id: str,
        section_id: str,
        session_id: str,
        topic: str = "",
    ) -> Dict[str, Any]:
        """Synchronous wrapper suitable for Flask/Telegram background worker threads."""
        coro = self.generate_lesson_plan(grade, sequence_id, section_id, session_id, topic)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        # If an event loop is already running in this thread, execute in a fresh thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
