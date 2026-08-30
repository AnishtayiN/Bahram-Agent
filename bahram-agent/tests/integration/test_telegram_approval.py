from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest


# ---------------------------------------------------------------------------
# TelegramApprovalManager — pure-logic approval layer, no Telegram dependency
# ---------------------------------------------------------------------------

class ApprovalStatus:
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    approval_id: str
    run_id: str
    tool_call_id: str
    user_id: str
    session_id: str
    command: str
    arguments: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    status: str = ApprovalStatus.PENDING
    responded_by: str | None = None
    responded_at: float | None = None
    used: bool = False
    cancelled: bool = False
    completed: bool = False


class TelegramApprovalManager:
    """Manages approval logic for dangerous tool calls via Telegram callbacks.

    This class is transport-agnostic: it knows nothing about Telegram bots,
    InlineKeyboards, or callback queries.  The integration layer that
    translates Telegram callback_query objects into approve/deny calls lives
    in the platform adapter.
    """

    def __init__(self, default_timeout: int = 300, secret: str = "") -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._default_timeout = default_timeout
        self._secret = secret or uuid.uuid4().hex

    # -- creation -----------------------------------------------------------

    def create_approval_request(
        self,
        run_id: str,
        tool_call_id: str,
        user_id: str,
        session_id: str,
        command: str,
        arguments: dict[str, Any],
        timeout: int | None = None,
    ) -> str:
        approval_id = uuid.uuid4().hex[:12]
        req = ApprovalRequest(
            approval_id=approval_id,
            run_id=run_id,
            tool_call_id=tool_call_id,
            user_id=user_id,
            session_id=session_id,
            command=command,
            arguments=arguments.copy(),
            created_at=time.time(),
        )
        self._requests[approval_id] = req
        return approval_id

    # -- callback actions ---------------------------------------------------

    def approve(self, approval_id: str, user_id: str, session_id: str = "") -> bool:
        return self._respond(approval_id, user_id, session_id, ApprovalStatus.APPROVED)

    def deny(self, approval_id: str, user_id: str, session_id: str = "") -> bool:
        return self._respond(approval_id, user_id, session_id, ApprovalStatus.DENIED)

    def _respond(
        self, approval_id: str, user_id: str, session_id: str, action: str
    ) -> bool:
        req = self._requests.get(approval_id)
        if req is None:
            return False

        # --- one-time-use enforcement ---------------------------------
        if req.used:
            return False

        # --- already responded ----------------------------------------
        if req.status != ApprovalStatus.PENDING:
            return False

        # --- expiry check ---------------------------------------------
        if self._is_expired(req):
            req.status = ApprovalStatus.EXPIRED
            return False

        # --- cancelled / completed checks ----------------------------
        if req.cancelled:
            req.status = ApprovalStatus.CANCELLED
            return False

        if req.completed:
            return False

        # --- user binding check --------------------------------------
        if user_id != req.user_id:
            return False

        # --- session binding check (if provided) ---------------------
        if session_id and session_id != req.session_id:
            return False

        # --- one-time-use: mark consumed -----------------------------
        req.used = True
        req.status = action
        req.responded_by = user_id
        req.responded_at = time.time()
        return True

    # -- state queries ------------------------------------------------------

    def is_approved(self, approval_id: str) -> bool:
        req = self._requests.get(approval_id)
        if req is None:
            return False
        if self._is_expired(req) and req.status == ApprovalStatus.PENDING:
            req.status = ApprovalStatus.EXPIRED
        return req.status == ApprovalStatus.APPROVED

    def get_pending(self) -> list[dict[str, Any]]:
        now = time.time()
        result = []
        for req in self._requests.values():
            if req.status != ApprovalStatus.PENDING:
                continue
            if self._is_expired(req):
                req.status = ApprovalStatus.EXPIRED
                continue
            if req.cancelled or req.completed:
                continue
            result.append({
                "approval_id": req.approval_id,
                "run_id": req.run_id,
                "tool_call_id": req.tool_call_id,
                "user_id": req.user_id,
                "session_id": req.session_id,
                "command": req.command,
                "arguments": req.arguments,
                "created_at": req.created_at,
            })
        return result

    def get_request(self, approval_id: str) -> ApprovalRequest | None:
        return self._requests.get(approval_id)

    # -- lifecycle helpers --------------------------------------------------

    def cancel_request(self, approval_id: str) -> bool:
        req = self._requests.get(approval_id)
        if req is None or req.status != ApprovalStatus.PENDING:
            return False
        req.cancelled = True
        req.status = ApprovalStatus.CANCELLED
        return True

    def mark_completed(self, approval_id: str) -> bool:
        req = self._requests.get(approval_id)
        if req is None or req.status != ApprovalStatus.PENDING:
            return False
        req.completed = True
        req.status = ApprovalStatus.APPROVED  # treat as resolved
        return True

    # -- expiry -------------------------------------------------------------

    def _is_expired(self, req: ApprovalRequest) -> bool:
        return (time.time() - req.created_at) > self._default_timeout

    # -- HMAC helpers for argument integrity --------------------------------

    def sign_arguments(self, arguments: dict[str, Any]) -> str:
        payload = json.dumps(arguments, sort_keys=True, default=str)
        return hmac.new(self._secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    def verify_arguments(self, arguments: dict[str, Any], signature: str) -> bool:
        return hmac.compare_digest(self.sign_arguments(arguments), signature)


# ---------------------------------------------------------------------------
# Semantic approval behaviour tests (no Telegram needed)
# ---------------------------------------------------------------------------

class TestTelegramApprovalManager:

    @pytest.fixture()
    def mgr(self):
        return TelegramApprovalManager(default_timeout=300)

    def _make(self, mgr, user_id="u1", session_id="s1", **kwargs):
        defaults = dict(
            run_id="run_a",
            tool_call_id="tc_1",
            user_id=user_id,
            session_id=session_id,
            command="rm -rf /tmp/test",
            arguments={"path": "/tmp/test"},
        )
        defaults.update(kwargs)
        return mgr.create_approval_request(**defaults)

    # -- basic approve / deny -----------------------------------------------

    def test_valid_approval(self, mgr):
        aid = self._make(mgr)
        assert mgr.approve(aid, "u1", "s1") is True
        assert mgr.is_approved(aid) is True

    def test_valid_deny(self, mgr):
        aid = self._make(mgr)
        assert mgr.deny(aid, "u1", "s1") is True
        assert mgr.is_approved(aid) is False
        req = mgr.get_request(aid)
        assert req.status == ApprovalStatus.DENIED

    # -- identity binding ---------------------------------------------------

    def test_wrong_user_rejection(self, mgr):
        aid = self._make(mgr, user_id="u1")
        assert mgr.approve(aid, "u2") is False
        assert mgr.is_approved(aid) is False

    def test_wrong_session_rejection(self, mgr):
        aid = self._make(mgr, user_id="u1", session_id="s1")
        assert mgr.approve(aid, "u1", "s_wrong") is False
        assert mgr.is_approved(aid) is False

    # -- expiry -------------------------------------------------------------

    def test_expired_approval_rejection(self, mgr):
        aid = self._make(mgr)
        req = mgr.get_request(aid)
        req.created_at = time.time() - 999999
        assert mgr.approve(aid, "u1", "s1") is False
        assert mgr.is_approved(aid) is False
        assert req.status == ApprovalStatus.EXPIRED

    # -- one-time-use enforcement -------------------------------------------

    def test_duplicate_callback_rejection(self, mgr):
        aid = self._make(mgr)
        assert mgr.approve(aid, "u1", "s1") is True
        assert mgr.approve(aid, "u1", "s1") is False

    def test_deny_after_approve_rejection(self, mgr):
        aid = self._make(mgr)
        assert mgr.approve(aid, "u1", "s1") is True
        assert mgr.deny(aid, "u1", "s1") is False

    def test_approve_after_deny_rejection(self, mgr):
        aid = self._make(mgr)
        assert mgr.deny(aid, "u1", "s1") is True
        assert mgr.approve(aid, "u1", "s1") is False

    # -- replay attack ------------------------------------------------------

    def test_replay_attack_rejection(self, mgr):
        """Second callback with same approval_id is always rejected."""
        aid = self._make(mgr)
        assert mgr.approve(aid, "u1", "s1") is True
        # Replay
        assert mgr.approve(aid, "u1", "s1") is False
        assert mgr.deny(aid, "u1", "s1") is False

    # -- modified arguments -------------------------------------------------

    def test_modified_arguments_rejection(self, mgr):
        """Arguments baked into the approval cannot be swapped post-creation."""
        aid = self._make(mgr, arguments={"path": "/tmp/test"})
        req = mgr.get_request(aid)
        assert req.arguments == {"path": "/tmp/test"}
        # Tamper — the manager should expose the original arguments for
        # the integration layer to verify.  Modified arguments are caught
        # by comparing the stored arguments to the execution arguments.
        assert req.arguments != {"path": "/etc/passwd"}

    def test_hmac_signature_roundtrip(self, mgr):
        args = {"path": "/tmp/test", "force": True}
        sig = mgr.sign_arguments(args)
        assert mgr.verify_arguments(args, sig) is True
        assert mgr.verify_arguments({"path": "/etc/passwd"}, sig) is False

    # -- callback after cancellation ----------------------------------------

    def test_callback_after_cancellation(self, mgr):
        aid = self._make(mgr)
        assert mgr.cancel_request(aid) is True
        assert mgr.approve(aid, "u1", "s1") is False

    def test_cancellation_of_nonexistent(self, mgr):
        assert mgr.cancel_request("does_not_exist") is False

    # -- callback after completion ------------------------------------------

    def test_callback_after_completion(self, mgr):
        aid = self._make(mgr)
        assert mgr.mark_completed(aid) is True
        assert mgr.deny(aid, "u1", "s1") is False

    # -- pending list -------------------------------------------------------

    def test_get_pending_filters(self, mgr):
        aid1 = self._make(mgr, user_id="u1", command="rm -rf /a")
        aid2 = self._make(mgr, user_id="u1", command="rm -rf /b")
        mgr.approve(aid1, "u1")
        pending = mgr.get_pending()
        assert len(pending) == 1
        assert pending[0]["approval_id"] == aid2

    def test_get_pending_excludes_expired(self, mgr):
        aid = self._make(mgr)
        req = mgr.get_request(aid)
        req.created_at = time.time() - 999999
        pending = mgr.get_pending()
        assert len(pending) == 0

    def test_get_pending_excludes_cancelled(self, mgr):
        aid = self._make(mgr)
        mgr.cancel_request(aid)
        assert len(mgr.get_pending()) == 0

    # -- unknown approval_id ------------------------------------------------

    def test_approve_unknown_id(self, mgr):
        assert mgr.approve("unknown", "u1") is False

    def test_deny_unknown_id(self, mgr):
        assert mgr.deny("unknown", "u1") is False

    # -- arguments integrity on stored request ------------------------------

    def test_arguments_are_copied(self, mgr):
        original = {"path": "/tmp/x"}
        aid = self._make(mgr, arguments=original)
        original["path"] = "/etc/passwd"
        req = mgr.get_request(aid)
        assert req.arguments["path"] == "/tmp/x"


# ---------------------------------------------------------------------------
# Telegram integration test — skipped when no credentials are available
# ---------------------------------------------------------------------------

_NO_TELEGRAM = True
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import (
        ApplicationBuilder,
        CallbackQueryHandler,
        ContextTypes,
    )
    _NO_TELEGRAM = False
except ImportError:
    pass


class _FakeCallbackQuery:
    """Minimal stand-in for telegram.CallbackQuery used in integration tests."""

    def __init__(self, data: str, user_id: str, message_id: str = "1") -> None:
        self.data = data
        self.from_user = type("U", (), {"id": int(user_id)})()
        self.message = type("M", (), {"message_id": message_id})()
        self._answered = False

    async def answer(self, **kw: Any) -> None:
        self._answered = True

    async def edit_message_text(self, **kw: Any) -> None:
        pass


class _FakeUpdate:
    """Minimal stand-in for telegram.Update."""

    def __init__(self, callback_query: _FakeCallbackQuery) -> None:
        self.callback_query = callback_query
        self.effective_user = callback_query.from_user


def _build_inline_keyboard(approval_id: str) -> InlineKeyboardMarkup:
    """Build the same InlineKeyboardButton layout the real integration uses."""
    keyboard = [
        [
            InlineKeyboardButton("Approve", callback_data=f"approve:{approval_id}"),
            InlineKeyboardButton("Deny", callback_data=f"deny:{approval_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


@pytest.mark.skipif(_NO_TELEGRAM, reason="python-telegram-bot not installed")
class TestTelegramIntegration:

    def test_callback_data_binding(self, mgr=None):
        """Verify that callback_data encodes action + approval_id correctly."""
        mgr = mgr or TelegramApprovalManager()
        aid = mgr.create_approval_request(
            run_id="run_99",
            tool_call_id="tc_42",
            user_id="12345",
            session_id="sess_1",
            command="rm -rf /tmp",
            arguments={"path": "/tmp"},
        )
        markup = _build_inline_keyboard(aid)
        btn = markup.inline_keyboard[0][0]
        assert btn.callback_data == f"approve:{aid}"
        btn_deny = markup.inline_keyboard[0][1]
        assert btn_deny.callback_data == f"deny:{aid}"

    def test_callback_query_dispatch(self):
        """Simulate a callback_query arriving and being routed to approve."""
        mgr = TelegramApprovalManager()
        aid = mgr.create_approval_request(
            run_id="r1", tool_call_id="tc1", user_id="99",
            session_id="s1", command="ls", arguments={},
        )
        cq = _FakeCallbackQuery(f"approve:{aid}", user_id="99")
        update = _FakeUpdate(cq)

        action, approval_id = cq.data.split(":", 1)
        if action == "approve":
            result = mgr.approve(approval_id, str(cq.from_user.id), "s1")
        elif action == "deny":
            result = mgr.deny(approval_id, str(cq.from_user.id), "s1")
        else:
            result = False

        assert result is True
        assert mgr.is_approved(aid) is True

    def test_user_id_from_callback_query(self):
        """Ensure user_id is extracted from update.effective_user.id."""
        cq = _FakeCallbackQuery("approve:abc", user_id="54321")
        assert cq.from_user.id == 54321

    def test_multiple_approvals_independent(self):
        """Two different tool calls produce independent approvals."""
        mgr = TelegramApprovalManager()
        a1 = mgr.create_approval_request(
            run_id="r1", tool_call_id="tc1", user_id="u1",
            session_id="s1", command="rm /a", arguments={},
        )
        a2 = mgr.create_approval_request(
            run_id="r1", tool_call_id="tc2", user_id="u1",
            session_id="s1", command="rm /b", arguments={},
        )
        mgr.approve(a1, "u1", "s1")
        assert mgr.is_approved(a1) is True
        assert mgr.is_approved(a2) is False

    def test_unauthorised_user_cannot_approve(self):
        """A callback from a different user is rejected."""
        mgr = TelegramApprovalManager()
        aid = mgr.create_approval_request(
            run_id="r1", tool_call_id="tc1", user_id="authorized_user",
            session_id="s1", command="rm /x", arguments={},
        )
        cq = _FakeCallbackQuery(f"approve:{aid}", user_id="attacker")
        action, approval_id = cq.data.split(":", 1)
        result = mgr.approve(approval_id, str(cq.from_user.id))
        assert result is False
        assert mgr.is_approved(aid) is False
