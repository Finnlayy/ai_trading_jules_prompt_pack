"""cTrader FIX API broker adapter.

Uses raw SSL socket + simplefix for message parsing.
Connects to cTrader FIX TRADE port (5212) for order execution.
"""

from __future__ import annotations

import json
import logging
import socket
import ssl
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.config import (
    CTRADER_FIX_ENABLED,
    CTRADER_FIX_HOST,
    CTRADER_FIX_LIVE_TRADING_ENABLED,
    CTRADER_FIX_PASSWORD,
    CTRADER_FIX_PORT,
    CTRADER_FIX_SENDER_COMP_ID,
    CTRADER_FIX_TARGET_COMP_ID,
)
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, FinalDecisionEnum, TradeJournalEntry, DirectionEnum
from app.schemas.m8_payload import M8Payload
from app.services.broker_interface import BaseBroker

logger = logging.getLogger(__name__)

SOH = b"\x01"


class CTraderFixError(RuntimeError):
    """Raised when FIX communication fails."""


class CTraderFixConfig:
    """Runtime settings for cTrader FIX API."""

    def __init__(
        self,
        enabled: bool = CTRADER_FIX_ENABLED,
        live_trading_enabled: bool = CTRADER_FIX_LIVE_TRADING_ENABLED,
        host: str = "",
        port: int = 5212,
        sender_comp_id: str = "",
        target_comp_id: str = "cServer",
        password: str = "",
        sender_sub_id: str = "",
    ) -> None:
        self.enabled = enabled
        self.live_trading_enabled = live_trading_enabled
        self.host = host or "demo-uk-eqx-01.p.c-trader.com"
        self.port = port
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.password = password
        self.sender_sub_id = sender_sub_id or ("TRADE" if port == 5212 or port == 5202 else "QUOTE")
        self.fix_version = "FIX.4.4"

    def has_credentials(self) -> bool:
        return bool(self.sender_comp_id and self.password)


class CTraderFixClient:
    """Minimal FIX 4.4 client for cTrader order execution."""

    def __init__(self, config: CTraderFixConfig) -> None:
        self.config = config
        self.socket: ssl.SSLSocket | None = None
        self.seq_num = 0
        self.connected = False
        self.logged_on = False
        self.last_error: str | None = None
        self._lock = threading.Lock()
        self._recv_buffer = b""

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, timeout: float = 10.0) -> dict[str, Any]:
        if not self.config.enabled:
            raise CTraderFixError("CTRADER_FIX_DISABLED")
        if not self.config.has_credentials():
            raise CTraderFixError("CTRADER_FIX_CREDENTIALS_MISSING")

        with self._lock:
            if self.logged_on:
                return {"status": "already_connected"}

            try:
                self._connect_socket(timeout)
                self._send_logon()
                self._wait_for_logon(timeout)
                return {"status": "connected", "host": self.config.host, "port": self.config.port}
            except Exception as exc:
                self.last_error = str(exc)
                self._disconnect()
                raise CTraderFixError(str(exc)) from exc

    def disconnect(self) -> dict[str, Any]:
        with self._lock:
            self._send_logout() if self.socket else None
            self._disconnect()
        return {"status": "disconnected"}

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "logged_on": self.logged_on,
            "host": self.config.host,
            "port": self.config.port,
            "last_error": self.last_error,
        }

    # ------------------------------------------------------------------
    # Order execution
    # ------------------------------------------------------------------

    def send_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        cl_ord_id: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict[str, Any]:
        """Send a market order and return the execution result."""
        self.connect()

        fix_side = "1" if side.upper() in {"BUY", "LONG"} else "2"
        # cTrader FIX uses quantity in lots * 100000 (units)
        fix_qty = int(qty * 100_000)

        msg = self._build_message("D", [
            ("11", cl_ord_id),
            ("55", symbol),
            ("54", fix_side),
            ("38", str(fix_qty)),
            ("40", "1"),  # Market
            ("59", "1"),  # GTC
        ])

        self._send_raw(msg)
        return self._wait_for_execution(cl_ord_id, timeout=15.0)

    # ------------------------------------------------------------------
    # Socket I/O
    # ------------------------------------------------------------------

    def _connect_socket(self, timeout: float) -> None:
        context = ssl.create_default_context()
        sock = socket.create_connection((self.config.host, self.config.port), timeout=timeout)
        self.socket = context.wrap_socket(sock, server_hostname=self.config.host)
        self.socket.settimeout(timeout)
        self.connected = True
        logger.info("cTrader FIX socket connected to %s:%s", self.config.host, self.config.port)

    def _disconnect(self) -> None:
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        self.socket = None
        self.connected = False
        self.logged_on = False

    def _send_raw(self, data: bytes) -> None:
        if self.socket is None:
            raise CTraderFixError("SOCKET_NOT_CONNECTED")
        self.socket.sendall(data)
        logger.debug("FIX >> %s", data.replace(SOH, b"|").decode("ascii", errors="replace"))

    def _recv_raw(self, timeout: float) -> bytes:
        if self.socket is None:
            raise CTraderFixError("SOCKET_NOT_CONNECTED")
        self.socket.settimeout(timeout)
        try:
            chunk = self.socket.recv(4096)
        except socket.timeout:
            return b""
        if not chunk:
            raise CTraderFixError("SOCKET_CLOSED_BY_SERVER")
        return chunk

    # ------------------------------------------------------------------
    # Message builders
    # ------------------------------------------------------------------

    def _build_message(self, msg_type: str, body_tags: list[tuple[str, str]]) -> bytes:
        self.seq_num += 1
        body_parts: list[bytes] = []
        for tag, value in body_tags:
            body_parts.append(f"{tag}={value}".encode("ascii"))

        # Standard header fields
        sending_time = datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
        header = [
            f"8={self.config.fix_version}".encode("ascii"),
            f"35={msg_type}".encode("ascii"),
            f"49={self.config.sender_comp_id}".encode("ascii"),
            f"56={self.config.target_comp_id}".encode("ascii"),
        ]
        if getattr(self.config, "sender_sub_id", None):
            header.append(f"50={self.config.sender_sub_id}".encode("ascii"))

        header.extend([
            f"34={self.seq_num}".encode("ascii"),
            f"52={sending_time}".encode("ascii"),
        ])

        body = SOH.join(header + body_parts) + SOH
        body_len = len(body)
        msg = f"8={self.config.fix_version}{SOH.decode()}9={body_len}{SOH.decode()}".encode("ascii") + body
        checksum = self._checksum(msg)
        msg += f"10={checksum:03d}{SOH.decode()}".encode("ascii")
        return msg

    @staticmethod
    def _checksum(data: bytes) -> int:
        return sum(data) % 256

    # ------------------------------------------------------------------
    # Logon / Logout
    # ------------------------------------------------------------------

    def _send_logon(self) -> None:
        msg = self._build_message("A", [
            ("98", "0"),   # EncryptMethod = None
            ("108", "30"), # HeartBeatInt = 30
            ("141", "Y"),  # ResetSeqNumFlag = Yes
            ("553", self.config.sender_comp_id),
            ("554", self.config.password),
        ])
        self._send_raw(msg)

    def _send_logout(self) -> None:
        try:
            msg = self._build_message("5", [])
            self._send_raw(msg)
        except Exception:
            pass

    def _wait_for_logon(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msgs = self._read_messages(timeout=2.0)
            for msg in msgs:
                msg_type = msg.get("35")
                if msg_type == "A":
                    self.logged_on = True
                    logger.info("cTrader FIX logon accepted")
                    return
                elif msg_type == "5":
                    raise CTraderFixError("LOGON_REJECTED_LOGOUT")
                elif msg_type == "3":
                    reason = msg.get("58", "unknown")
                    raise CTraderFixError(f"LOGON_REJECTED:{reason}")
        raise CTraderFixError("LOGON_TIMEOUT")

    # ------------------------------------------------------------------
    # Message parser
    # ------------------------------------------------------------------

    def _read_messages(self, timeout: float) -> list[dict[str, str]]:
        raw = self._recv_raw(timeout)
        if not raw:
            return []
        self._recv_buffer += raw
        msgs: list[dict[str, str]] = []
        while True:
            parsed, consumed = self._parse_one(self._recv_buffer)
            if parsed is None:
                break
            msgs.append(parsed)
            self._recv_buffer = self._recv_buffer[consumed:]
        return msgs

    @staticmethod
    def _parse_one(buf: bytes) -> tuple[dict[str, str] | None, int]:
        # Find BeginString (8=...)
        try:
            start = buf.index(b"8=")
        except ValueError:
            return None, 0

        # Find SOH after BeginString
        try:
            soh1 = buf.index(SOH, start)
        except ValueError:
            return None, 0

        # Find BodyLength (9=...)
        try:
            len_start = buf.index(b"9=", soh1)
            len_end = buf.index(SOH, len_start)
            body_len = int(buf[len_start + 2 : len_end])
        except (ValueError, IndexError):
            return None, 0

        # Calculate total message length
        # 8=FIX... + SOH + 9=... + SOH + body + 10=... + SOH
        header_end = len_end + 1
        total_len = header_end + body_len

        if len(buf) < total_len + 7:  # minimum for checksum tag
            return None, 0

        # Find checksum tag position
        msg_slice = buf[start : start + total_len + 7 + 10]  # generous slice
        try:
            checksum_idx = msg_slice.index(b"10=")
            checksum_end = msg_slice.index(SOH, checksum_idx)
        except ValueError:
            return None, 0

        full_msg_end = start + (checksum_end - 0) + 1
        raw_msg = buf[start:full_msg_end]

        # Parse tags
        parsed: dict[str, str] = {}
        for part in raw_msg.split(SOH):
            if b"=" in part:
                k, v = part.split(b"=", 1)
                parsed[k.decode("ascii")] = v.decode("ascii", errors="replace")

        return parsed, full_msg_end

    # ------------------------------------------------------------------
    # Execution handling
    # ------------------------------------------------------------------

    def _wait_for_execution(self, cl_ord_id: str, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        result: dict[str, Any] = {"status": "PENDING", "cl_ord_id": cl_ord_id}

        while time.monotonic() < deadline:
            msgs = self._read_messages(timeout=2.0)
            for msg in msgs:
                msg_type = msg.get("35")
                if msg_type == "0":  # Heartbeat
                    continue
                if msg_type == "1":  # TestRequest
                    self._send_heartbeat()
                    continue
                if msg_type == "8":  # ExecutionReport
                    exec_type = msg.get("150")
                    ord_status = msg.get("39")
                    report_cl_ord_id = msg.get("11", "")
                    if report_cl_ord_id == cl_ord_id or not report_cl_ord_id:
                        result["order_id"] = msg.get("37")
                        result["exec_id"] = msg.get("17")
                        result["exec_type"] = exec_type
                        result["ord_status"] = ord_status
                        result["symbol"] = msg.get("55")
                        result["side"] = msg.get("54")
                        result["qty"] = msg.get("38")
                        result["price"] = msg.get("44")
                        result["last_qty"] = msg.get("32")
                        result["last_price"] = msg.get("31")
                        result["text"] = msg.get("58")

                        if exec_type == "F" and ord_status == "2":  # Fill
                            result["status"] = "FILLED"
                            return result
                        elif exec_type == "F" and ord_status == "1":  # Partial fill
                            result["status"] = "PARTIAL"
                        elif ord_status == "0":  # New
                            result["status"] = "NEW"
                        elif ord_status in {"4", "C"}:  # Canceled / Expired
                            result["status"] = "REJECTED"
                            result["error"] = msg.get("58", "Order rejected")
                            return result
                elif msg_type == "3":  # Reject
                    result["status"] = "REJECTED"
                    result["error"] = msg.get("58", "Session reject")
                    return result
        return result

    def _send_heartbeat(self) -> None:
        msg = self._build_message("0", [])
        self._send_raw(msg)


# =============================================================================
# Broker wrapper
# =============================================================================

class CTraderFixBroker(BaseBroker):
    """Broker implementation for cTrader FIX API."""

    def __init__(
        self,
        config: CTraderFixConfig | None = None,
        client: CTraderFixClient | None = None,
        journal_path: str = "trade_journal.jsonl",
    ) -> None:
        self.config = config or CTraderFixConfig()
        self.journal_path = journal_path
        self.journal: list[TradeJournalEntry] = []
        self.client = client or CTraderFixClient(self.config)

    # ------------------------------------------------------------------
    # BaseBroker interface
    # ------------------------------------------------------------------

    def execute_trade(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str] = None,
        ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION,
    ) -> TradeJournalEntry:
        if decision != DecisionEnum.PROCEED_TO_SIMULATION:
            return self._build_entry(
                payload,
                ai_decision,
                FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reject_reason},
            )

        if not self.config.enabled:
            return self._build_entry(
                payload,
                ai_decision,
                FinalDecisionEnum.EXECUTED_SIM,
                simulated_fill={"mode": "CTRADER_FIX_DISABLED"},
                result={"status": "DRY_RUN_CTRADER_FIX_DISABLED", "reject_reason": None},
            )

        side = "BUY" if payload.direction == "LONG" else "SELL"
        lots = max(float(payload.execution_quantity or 0.01), 0.01)
        cl_ord_id = f"metricfix-{payload.signal_id}"[:20]

        result: dict[str, Any] = {
            "status": "DRY_RUN",
            "reject_reason": None,
            "cl_ord_id": cl_ord_id,
            "symbol": payload.symbol,
            "side": side,
            "lots": lots,
        }

        if not self.config.live_trading_enabled:
            return self._build_entry(
                payload,
                ai_decision,
                FinalDecisionEnum.EXECUTED_SIM,
                simulated_fill={
                    "mode": "CTRADER_FIX_DRY_RUN",
                    "symbol": payload.symbol,
                    "side": side,
                    "lots": lots,
                    "cl_ord_id": cl_ord_id,
                },
                result=result,
            )

        try:
            fix_result = self.client.send_market_order(
                symbol=payload.symbol,
                side=side,
                qty=lots,
                cl_ord_id=cl_ord_id,
            )
            result.update(fix_result)
            if result.get("status") == "FILLED":
                result["status"] = "EXECUTED"
        except Exception as exc:
            result["status"] = "FIX_ERROR"
            result["error"] = str(exc)
            return self._build_entry(
                payload,
                ai_decision,
                FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result=result,
            )
        finally:
            try:
                self.client.disconnect()
            except Exception:
                pass

        final = FinalDecisionEnum.EXECUTED_SIM if result.get("status") == "DRY_RUN" else FinalDecisionEnum.EXECUTED_SIM
        return self._build_entry(
            payload,
            ai_decision,
            final,
            simulated_fill={
                "mode": "CTRADER_FIX",
                "symbol": payload.symbol,
                "side": side,
                "lots": lots,
                "cl_ord_id": cl_ord_id,
            },
            result=result,
        )

    def get_positions(self) -> dict[str, Any]:
        return {"status": "not_implemented", "positions": []}

    def get_wallet_balances(self, account_mode: str = "SPOT") -> dict[str, Any]:
        return {"status": "not_implemented", "balances": [], "error": "FIX_API_NO_BALANCE_ENDPOINT"}

    def is_live_capable(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.live_trading_enabled
            and self.config.has_credentials()
        )

    def is_ready(self) -> bool:
        return bool(self.config.enabled and self.config.has_credentials())

    def get_broker_name(self) -> str:
        return "CTrader FIX"

    def get_broker_type(self) -> str:
        return "ctrader_fix"

    def get_broker_mode(self) -> str:
        if self.is_live_capable():
            return "live"
        if self.config.enabled:
            return "dry-run"
        return "simulation"

    def health(self) -> dict[str, Any]:
        conn = self.client.status()
        return {
            "name": self.get_broker_name(),
            "type": self.get_broker_type(),
            "mode": self.get_broker_mode(),
            "ready": self.is_ready(),
            "live_capable": self.is_live_capable(),
            "enabled": self.config.enabled,
            "live_trading_enabled": self.config.live_trading_enabled,
            "host": self.config.host,
            "port": self.config.port,
            "symbols_cached": 0,
            "sender_comp_id": self.config.sender_comp_id,
            "connection": {
                "connected": conn["connected"],
                "app_authenticated": conn["logged_on"],
                "account_authenticated": conn["logged_on"],
                "host": conn["host"],
                "port": conn["port"],
                "last_error": conn["last_error"],
                "last_connected_at": None,
            },
        }

    def place_direct_order(
        self,
        symbol: str,
        direction: str,
        volume_lots: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        if not self.config.enabled:
            return {"status": "ERROR", "error": "CTRADER_FIX_DISABLED"}
        if not self.is_ready():
            return {"status": "ERROR", "error": "CTRADER_FIX_CREDENTIALS_MISSING"}

        side = "BUY" if direction.upper() in {"BUY", "LONG"} else "SELL"
        cl_ord_id = (label or f"metricfix-direct-{datetime.now(timezone.utc).strftime('%H%M%S')}")[:20]

        if not self.config.live_trading_enabled:
            return {
                "status": "DRY_RUN_CTRADER_FIX",
                "order_id": None,
                "position_id": None,
                "symbol": symbol,
                "direction": direction,
                "volume_lots": volume_lots,
                "fill_price": None,
                "error": None,
                "preview": {
                    "symbol": symbol,
                    "side": side,
                    "qty": volume_lots,
                    "cl_ord_id": cl_ord_id,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                },
            }

        try:
            result = self.client.send_market_order(
                symbol=symbol,
                side=side,
                qty=volume_lots,
                cl_ord_id=cl_ord_id,
            )
            result["symbol"] = symbol
            result["direction"] = direction
            result["volume_lots"] = volume_lots
            return result
        except Exception as exc:
            return {"status": "FIX_ERROR", "error": str(exc), "cl_ord_id": cl_ord_id, "symbol": symbol, "direction": direction, "volume_lots": volume_lots}
        finally:
            try:
                self.client.disconnect()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_entry(
        self,
        payload: M8Payload,
        ai_decision: AIDecisionEnum,
        final_decision: FinalDecisionEnum,
        simulated_fill: dict[str, Any],
        result: dict[str, Any],
    ) -> TradeJournalEntry:
        entry = TradeJournalEntry(
            trade_id=f"ctrader-fix-{payload.signal_id}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            direction=DirectionEnum(payload.direction),
            entry_price=payload.entry_price,
            stop_price=payload.stop_price or 0.0,
            target_price=payload.target_price or 0.0,
            risk_reward=0.0,
            m8_score=payload.confluence_score,
            ai_decision=DecisionEnum(ai_decision.value),
            final_decision=final_decision,
            simulated_fill=simulated_fill,
            result=result,
        )
        self.journal.append(entry)
        return entry
