"""
In-memory Wireshark packet-capture simulator for training labs.

Models a realistic captured packet set so a learner can open an in-app
Wireshark-like UI: a packet list, a capture filter (BPF-like, decides what was
captured off the wire), a display filter (Wireshark display syntax, decides what
is shown of the capture), "Follow TCP Stream" reassembly, and packet
selection/marking. The engine tracks the applied filters and the resulting
filtered view in session state.

Mirrors the cache-backed pattern of the sibling engines (vmware_sim/engine.py,
k8s_engine.py, docker_engine.py, monitoring_engine.py): SESSION_TTL=7200,
_session_key, _load_session/_save_session via the Django cache as JSON,
_base_inventory, per-scenario presets, _ensure_session, get_state, apply_action,
drop_session — plus validate_wireshark_lab(session_id, slug)->(bool, message).

Public API:
    get_state(session_id, scenario_slug) ->
        {session_id, scenario_slug, inventory, summary, events}
    apply_action(session_id, action, payload) -> {ok, message, ...}
    drop_session(session_id)
    validate_wireshark_lab(session_id, scenario_slug) -> (bool, message)

No external Wireshark/tshark process; everything is mock state in the Django
cache (Redis in production) for multi-worker safety.
"""

from __future__ import annotations

import copy
import json
import re
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200  # 2-hour TTL matching VMware/K8s/Docker/monitoring sessions


def _session_key(session_id: str) -> str:
    return f"wireshark_session:{session_id}"


def _load_session(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save_session(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _event(message: str, severity: str = "info") -> dict:
    return {"time": _now_iso(), "message": message, "severity": severity}


# ---------------------------------------------------------------------------
# Packet model
# ---------------------------------------------------------------------------
#
# A packet is a flat dict so it serializes cleanly to/from the cache:
#   no, time, src, dst, protocol, src_port, dst_port, length, info,
#   tcp_flags (e.g. "SYN", "SYN, ACK", "PSH, ACK", "RST"), stream_id.
# HTTP/DNS/TLS packets ride on TCP/UDP and carry the same stream_id as their
# transport so "Follow TCP Stream" reassembles the application exchange.

# Well-known hosts used across scenarios.
_CLIENT = "10.0.0.15"
_WEB = "93.184.216.34"        # example.com web server
_API = "10.0.0.80"            # internal API host
_DNS = "10.0.0.1"             # local resolver
_BADHOST = "198.51.100.23"    # a host that resets connections


def _pkt(no, t, src, dst, proto, sport, dport, length, info, flags="", stream=None):
    return {
        "no": no,
        "time": round(t, 6),
        "src": src,
        "dst": dst,
        "protocol": proto,
        "src_port": sport,
        "dst_port": dport,
        "length": length,
        "info": info,
        "tcp_flags": flags,
        "stream_id": stream,
    }


def _full_packet_set() -> list[dict]:
    """The complete set of packets present *on the wire* before any capture
    filter is applied. The capture filter selects a subset of these; the display
    filter then narrows what is shown of the captured subset.

    Streams:
      0  HTTP GET to example.com (port 80) — the headline web conversation
      1  DNS A lookup for example.com (UDP 53)
      2  HTTPS/TLS handshake to the API host (port 443)
      3  SSH noise (port 22) — background traffic to filter out
      4  A broken TCP conversation: retransmissions then a RST (port 8080)
    """
    p: list[dict] = []
    n = 1

    # --- Stream 1: DNS lookup for example.com (UDP 53) ---
    p.append(_pkt(n, 0.000000, _CLIENT, _DNS, "DNS", 51514, 53, 74,
                  "Standard query 0x1a2b A example.com", stream=1)); n += 1
    p.append(_pkt(n, 0.012300, _DNS, _CLIENT, "DNS", 53, 51514, 90,
                  "Standard query response 0x1a2b A example.com A 93.184.216.34", stream=1)); n += 1

    # --- Stream 0: HTTP GET to example.com (TCP 80) ---
    p.append(_pkt(n, 0.050000, _CLIENT, _WEB, "TCP", 49170, 80, 74,
                  "49170 > 80 [SYN] Seq=0 Win=64240 Len=0 MSS=1460", "SYN", stream=0)); n += 1
    p.append(_pkt(n, 0.078000, _WEB, _CLIENT, "TCP", 80, 49170, 74,
                  "80 > 49170 [SYN, ACK] Seq=0 Ack=1 Win=65535 Len=0", "SYN, ACK", stream=0)); n += 1
    p.append(_pkt(n, 0.078500, _CLIENT, _WEB, "TCP", 49170, 80, 66,
                  "49170 > 80 [ACK] Seq=1 Ack=1 Win=64240 Len=0", "ACK", stream=0)); n += 1
    p.append(_pkt(n, 0.079000, _CLIENT, _WEB, "HTTP", 49170, 80, 187,
                  "GET /index.html HTTP/1.1 Host: example.com", "PSH, ACK", stream=0)); n += 1
    p.append(_pkt(n, 0.110000, _WEB, _CLIENT, "TCP", 80, 49170, 66,
                  "80 > 49170 [ACK] Seq=1 Ack=122 Win=65535 Len=0", "ACK", stream=0)); n += 1
    p.append(_pkt(n, 0.140000, _WEB, _CLIENT, "HTTP", 80, 49170, 512,
                  "HTTP/1.1 200 OK (text/html) Content-Length: 1256", "PSH, ACK", stream=0)); n += 1
    p.append(_pkt(n, 0.140500, _CLIENT, _WEB, "TCP", 49170, 80, 66,
                  "49170 > 80 [ACK] Seq=122 Ack=447 Win=63794 Len=0", "ACK", stream=0)); n += 1
    p.append(_pkt(n, 0.300000, _CLIENT, _WEB, "TCP", 49170, 80, 66,
                  "49170 > 80 [FIN, ACK] Seq=122 Ack=447 Win=63794 Len=0", "FIN, ACK", stream=0)); n += 1
    p.append(_pkt(n, 0.330000, _WEB, _CLIENT, "TCP", 80, 49170, 66,
                  "80 > 49170 [FIN, ACK] Seq=447 Ack=123 Win=65535 Len=0", "FIN, ACK", stream=0)); n += 1

    # --- Stream 2: TLS handshake to API host (TCP 443) ---
    p.append(_pkt(n, 0.400000, _CLIENT, _API, "TCP", 49180, 443, 74,
                  "49180 > 443 [SYN] Seq=0 Win=64240 Len=0", "SYN", stream=2)); n += 1
    p.append(_pkt(n, 0.420000, _API, _CLIENT, "TCP", 443, 49180, 74,
                  "443 > 49180 [SYN, ACK] Seq=0 Ack=1 Win=65535 Len=0", "SYN, ACK", stream=2)); n += 1
    p.append(_pkt(n, 0.420500, _CLIENT, _API, "TCP", 49180, 443, 66,
                  "49180 > 443 [ACK] Seq=1 Ack=1 Win=64240 Len=0", "ACK", stream=2)); n += 1
    p.append(_pkt(n, 0.421000, _CLIENT, _API, "TLS", 49180, 443, 583,
                  "Client Hello (SNI=api.internal.lab)", "PSH, ACK", stream=2)); n += 1
    p.append(_pkt(n, 0.450000, _API, _CLIENT, "TLS", 443, 49180, 1414,
                  "Server Hello, Certificate, Server Key Exchange", "PSH, ACK", stream=2)); n += 1
    p.append(_pkt(n, 0.470000, _CLIENT, _API, "TLS", 49180, 443, 140,
                  "Client Key Exchange, Change Cipher Spec, Finished", "PSH, ACK", stream=2)); n += 1
    p.append(_pkt(n, 0.490000, _API, _CLIENT, "TLS", 443, 49180, 300,
                  "Application Data", "PSH, ACK", stream=2)); n += 1

    # --- Stream 3: SSH background noise (TCP 22) ---
    p.append(_pkt(n, 0.500000, _CLIENT, _API, "TCP", 49200, 22, 74,
                  "49200 > 22 [SYN] Seq=0 Win=64240 Len=0", "SYN", stream=3)); n += 1
    p.append(_pkt(n, 0.520000, _API, _CLIENT, "TCP", 22, 49200, 74,
                  "22 > 49200 [SYN, ACK] Seq=0 Ack=1 Win=65535 Len=0", "SYN, ACK", stream=3)); n += 1
    p.append(_pkt(n, 0.520500, _CLIENT, _API, "SSH", 49200, 22, 120,
                  "Client: Protocol (SSH-2.0-OpenSSH_9.2)", "PSH, ACK", stream=3)); n += 1
    p.append(_pkt(n, 0.540000, _API, _CLIENT, "SSH", 22, 49200, 120,
                  "Server: Protocol (SSH-2.0-OpenSSH_9.2)", "PSH, ACK", stream=3)); n += 1

    # --- Stream 4: BROKEN TCP conversation — retransmissions then RST (TCP 8080) ---
    p.append(_pkt(n, 0.600000, _CLIENT, _BADHOST, "TCP", 49210, 8080, 74,
                  "49210 > 8080 [SYN] Seq=0 Win=64240 Len=0", "SYN", stream=4)); n += 1
    p.append(_pkt(n, 1.600000, _CLIENT, _BADHOST, "TCP", 49210, 8080, 74,
                  "[TCP Retransmission] 49210 > 8080 [SYN] Seq=0 Win=64240 Len=0", "SYN", stream=4)); n += 1
    p.append(_pkt(n, 3.600000, _CLIENT, _BADHOST, "TCP", 49210, 8080, 74,
                  "[TCP Retransmission] 49210 > 8080 [SYN] Seq=0 Win=64240 Len=0", "SYN", stream=4)); n += 1
    p.append(_pkt(n, 3.650000, _BADHOST, _CLIENT, "TCP", 8080, 49210, 66,
                  "[TCP RST] 8080 > 49210 [RST, ACK] Seq=1 Ack=1 Win=0 Len=0", "RST, ACK", stream=4)); n += 1

    return p


def _stream_payload(stream_id: int) -> list[dict]:
    """Reassembled application-layer payload for Follow TCP Stream. Each turn is
    {direction: 'c2s'|'s2c', data: str}. Only application streams have content."""
    if stream_id == 0:
        return [
            {"direction": "c2s", "data": (
                "GET /index.html HTTP/1.1\r\n"
                "Host: example.com\r\n"
                "User-Agent: curl/8.4.0\r\n"
                "Accept: */*\r\n\r\n"
            )},
            {"direction": "s2c", "data": (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=UTF-8\r\n"
                "Content-Length: 1256\r\n"
                "Server: ECS (nyb/1D2E)\r\n\r\n"
                "<!doctype html><html><head><title>Example Domain</title></head>"
                "<body><h1>Example Domain</h1></body></html>"
            )},
        ]
    if stream_id == 2:
        return [
            {"direction": "c2s", "data": "Client Hello  SNI=api.internal.lab  (encrypted thereafter)"},
            {"direction": "s2c", "data": "Server Hello, Certificate (CN=api.internal.lab), ..."},
            {"direction": "c2s", "data": "Application Data (encrypted)"},
        ]
    if stream_id == 4:
        return [
            {"direction": "c2s", "data": "SYN ... (no SYN/ACK) ... retransmit ... retransmit ... RST received"},
        ]
    return []


# ---------------------------------------------------------------------------
# Filter engines: capture filter (BPF) + display filter (Wireshark syntax)
# ---------------------------------------------------------------------------

_PROTO_NUM = {"tcp", "udp", "icmp"}


def _normalize(expr: str) -> str:
    return re.sub(r"\s+", " ", (expr or "").strip()).strip()


def _canon_display_ops(expr: str) -> str:
    """Canonicalise the human-typed comparison operators Wireshark accepts.

    Real Wireshark treats ``eq``/``ne`` as word-synonyms for ``==``/``!=`` (and
    ``and``/``or``/``not`` for ``&&``/``||``/``!``). Learners routinely type
    ``ip.addr eq 10.0.0.1`` or ``tcp.port ne 22`` — canonicalise those to the
    symbol forms this engine's grammar already understands so they parse instead
    of turning the filter bar red. Only rewrites the operators; boolean keywords
    (``and``/``or``/``not``) are handled by the term/split logic below."""
    # `field eq value` -> `field == value`, `field ne value` -> `field != value`.
    expr = re.sub(r"\s+eq\s+", " == ", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\s+ne\s+", " != ", expr, flags=re.IGNORECASE)
    return expr


def matches_capture_filter(pkt: dict, expr: str) -> bool:
    """Evaluate a BPF-style capture filter against an on-the-wire packet.

    Supports a teaching subset: `tcp`, `udp`, `icmp`, `port N`, `tcp port N`,
    `udp port N`, `host A`, `src host A`, `dst host A`, and `and`/`or`
    combinations. An empty filter captures everything (default tcpdump/dumpcap
    behaviour). Application protocols (HTTP/DNS/TLS/SSH) ride on their transport,
    so `tcp` captures HTTP/TLS/SSH and `udp` captures DNS."""
    expr = _normalize(expr).lower()
    if not expr:
        return True

    transport = "udp" if pkt["protocol"] in ("DNS",) else (
        "tcp" if pkt["protocol"] in ("TCP", "HTTP", "TLS", "SSH") else
        pkt["protocol"].lower()
    )

    def eval_term(term: str) -> bool:
        term = term.strip()
        if not term:
            return True
        # BPF negation: `not <primitive>` / `!<primitive>` (e.g. `not port 22`).
        m_not = re.match(r"^(?:!|not\b)\s*(.+)$", term)
        if m_not:
            inner = m_not.group(1).strip()
            if inner.startswith("(") and inner.endswith(")"):
                inner = inner[1:-1].strip()
            return not eval_term(inner)
        # tcp / udp / icmp
        if term in _PROTO_NUM:
            return transport == term
        # [src|dst] host A
        m = re.match(r"^(src|dst)\s+host\s+(\S+)$", term)
        if m:
            which, addr = m.group(1), m.group(2)
            return (pkt["src"] == addr) if which == "src" else (pkt["dst"] == addr)
        m = re.match(r"^host\s+(\S+)$", term)
        if m:
            addr = m.group(1)
            return pkt["src"] == addr or pkt["dst"] == addr
        # [tcp|udp] port N  /  [src|dst] port N
        m = re.match(r"^(tcp|udp)\s+port\s+(\d+)$", term)
        if m:
            proto, port = m.group(1), int(m.group(2))
            return transport == proto and (pkt["src_port"] == port or pkt["dst_port"] == port)
        m = re.match(r"^(src|dst)\s+port\s+(\d+)$", term)
        if m:
            which, port = m.group(1), int(m.group(2))
            return (pkt["src_port"] == port) if which == "src" else (pkt["dst_port"] == port)
        m = re.match(r"^port\s+(\d+)$", term)
        if m:
            port = int(m.group(1))
            return pkt["src_port"] == port or pkt["dst_port"] == port
        # Unknown term: do not match (mirrors a too-restrictive/garbage filter).
        return False

    # Split on `or` (lowest precedence) then `and`.
    for or_part in re.split(r"\bor\b", expr):
        and_terms = re.split(r"\band\b", or_part)
        if all(eval_term(t) for t in and_terms):
            return True
    return False


def matches_display_filter(pkt: dict, expr: str) -> bool:
    """Evaluate a Wireshark *display* filter against an already-captured packet.

    Supports a teaching subset:
      http, dns, tls, ssl, tcp, udp, icmp, ssh           (protocol presence)
      tcp.port==N, udp.port==N, tcp.srcport==N, tcp.dstport==N
      ip.addr==A, ip.src==A, ip.dst==A
      tcp.stream==N
      tcp.flags.reset==1 / tcp.flags.syn==1               (flag predicates)
      tcp.analysis.retransmission                         (expert info)
      and/&&, or/||, not/!  combinations; eq/ne operator words
    An empty display filter shows everything captured."""
    expr = _canon_display_ops(_normalize(expr))
    if not expr:
        return True

    def eval_term(term: str) -> bool:
        t = term.strip().lower()
        if not t:
            return True
        # Negation: `!term`, `not term`, or a leading `!(term)` wrapper. Real
        # Wireshark negates a subexpression; we support the common single-term
        # form a learner types to hide noise (e.g. `!ssh`, `not tcp.port==22`).
        neg = False
        m_not = re.match(r"^(?:!|not\b)\s*(.+)$", t)
        if m_not:
            neg = True
            t = m_not.group(1).strip()
            if t.startswith("(") and t.endswith(")"):
                t = t[1:-1].strip()
        if not t:
            return True
        result = _eval_display_atom(t, pkt)
        return (not result) if neg else result

    def _eval_display_atom(t: str, pkt: dict) -> bool:
        proto = pkt["protocol"].lower()
        info = (pkt.get("info") or "")
        flags = (pkt.get("tcp_flags") or "")

        # `field != value` — invert the corresponding `==` comparison so
        # `tcp.port != 22` / `ip.addr != 10.0.0.1` behave like Wireshark.
        m_ne = re.match(r"^(.+?)\s*!=\s*(.+)$", t)
        if m_ne:
            return not _eval_display_atom(f"{m_ne.group(1).strip()} == {m_ne.group(2).strip()}", pkt)

        # Bare field-presence filters (a field name with no comparison shows any
        # packet that carries that field), matching Wireshark's semantics.
        if t in ("tcp.port", "tcp.srcport", "tcp.dstport", "tcp.stream", "tcp.flags"):
            return proto in ("tcp", "http", "tls", "ssh")
        if t in ("udp.port", "udp.srcport", "udp.dstport", "udp.stream"):
            return proto in ("udp", "dns")
        if t in ("ip.addr", "ip.src", "ip.dst"):
            return bool(pkt.get("src") or pkt.get("dst"))
        if t == "http.request":
            return proto == "http" and info.upper().startswith(("GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"))
        if t == "http.response":
            return proto == "http" and "HTTP/1" in info and "GET" not in info.split(" ")[0].upper()

        # Protocol-name filters.
        if t == "http":
            return proto == "http"
        if t == "dns":
            return proto == "dns"
        if t in ("tls", "ssl"):
            return proto == "tls"
        if t == "ssh":
            return proto == "ssh"
        if t == "icmp":
            return proto == "icmp"
        if t == "tcp":
            return proto in ("tcp", "http", "tls", "ssh")
        if t == "udp":
            return proto in ("udp", "dns")

        # Expert-info: retransmissions.
        if t in ("tcp.analysis.retransmission", "tcp.analysis.flags"):
            return "retransmission" in info.lower()

        # Flag predicates.
        m = re.match(r"^tcp\.flags\.(reset|syn|fin|ack|push)\s*==\s*(\d)$", t)
        if m:
            flag, val = m.group(1), m.group(2)
            present = {
                "reset": "RST" in flags,
                "syn": "SYN" in flags,
                "fin": "FIN" in flags,
                "ack": "ACK" in flags,
                "push": "PSH" in flags,
            }[flag]
            return present if val == "1" else (not present)
        # tcp.flags.reset (bare, treated as ==1)
        m = re.match(r"^tcp\.flags\.(reset|syn|fin|ack|push)$", t)
        if m:
            flag = m.group(1)
            return {"reset": "RST", "syn": "SYN", "fin": "FIN",
                    "ack": "ACK", "push": "PSH"}[flag] in flags

        # tcp.stream==N / udp.stream==N
        m = re.match(r"^(?:tcp|udp)\.stream\s*==\s*(\d+)$", t)
        if m:
            return pkt.get("stream_id") == int(m.group(1))

        # [tcp|udp].port / .srcport / .dstport == N
        m = re.match(r"^(tcp|udp)\.(port|srcport|dstport)\s*==\s*(\d+)$", t)
        if m:
            l4, which, port = m.group(1), m.group(2), int(m.group(3))
            is_l4 = (proto in ("tcp", "http", "tls", "ssh")) if l4 == "tcp" else (proto in ("udp", "dns"))
            if not is_l4:
                return False
            if which == "port":
                return pkt["src_port"] == port or pkt["dst_port"] == port
            if which == "srcport":
                return pkt["src_port"] == port
            return pkt["dst_port"] == port

        # ip.addr / ip.src / ip.dst == A
        m = re.match(r"^ip\.(addr|src|dst)\s*==\s*([0-9a-f:.]+)$", t)
        if m:
            which, addr = m.group(1), m.group(2)
            if which == "addr":
                return pkt["src"] == addr or pkt["dst"] == addr
            if which == "src":
                return pkt["src"] == addr
            return pkt["dst"] == addr

        # Unknown term: do not match.
        return False

    # or / || lowest precedence, then and / &&.
    for or_part in re.split(r"\bor\b|\|\|", expr):
        and_terms = re.split(r"\band\b|&&", or_part)
        if all(eval_term(t) for t in and_terms):
            return True
    return False


# ---------------------------------------------------------------------------
# Base inventory + scenario presets
# ---------------------------------------------------------------------------

def _base_inventory() -> dict:
    return {
        "interface": "eth0",
        "capture_active": True,
        # The full wire is fixed; the capture filter decides what gets captured.
        "all_packets": _full_packet_set(),
        "capture_filter": "",       # BPF — empty captures everything on the wire
        "display_filter": "",       # Wireshark display syntax — empty shows all
        "selected_packet": None,    # packet number currently selected
        "marked_packets": [],       # list of packet numbers the user marked
        "followed_stream": None,    # stream_id currently followed, or None
        "hosts": {
            _CLIENT: "client-workstation",
            _WEB: "example.com",
            _API: "api.internal.lab",
            _DNS: "resolver",
            _BADHOST: "stuck-service-8080",
        },
        # Filled by the preset: the question and the grading rules.
        "task": "",
        "validation": {},
    }


def _apply_preset(state: dict, slug: str) -> None:
    """Configure the scenario: set the broken/initial capture and the grading
    rules in state['validation']. validate_wireshark_lab reads these rules.

    Each scenario starts in a state where validation returns False; the learner
    must apply the documented filter / follow the right stream / mark the
    offending packet to make it pass."""
    s = (slug or "").lower()
    v = state["validation"]

    # 1) Capture and find the HTTP traffic.
    #    Initial: capture filter is empty so the HTTP packets ARE on the capture,
    #    but the learner must apply the `http` display filter to isolate them.
    if "find-http" in s or s == "wireshark-find-http-traffic":
        state["task"] = (
            "The capture contains a mix of DNS, HTTP, TLS and SSH traffic. "
            "Apply a display filter that shows ONLY the HTTP packets so you can "
            "confirm the web request to example.com was made."
        )
        v["require_display_filter_proto"] = "http"
        v["min_filtered_packets"] = 1
        return

    # 2) Isolate a single conversation with a display filter.
    #    The learner must narrow to the HTTP conversation on TCP port 80 (or the
    #    example.com host) so only that conversation remains.
    if "isolate-conversation" in s or "conversation" in s:
        state["task"] = (
            "Multiple conversations are mixed in the capture. Isolate the single "
            "conversation between the client and the web server on TCP port 80 "
            "using a display filter (e.g. tcp.port==80 or ip.addr==93.184.216.34)."
        )
        v["require_display_filter_isolates_stream"] = 0
        return

    # 3) Follow a TCP stream to read the request/response.
    if "follow-stream" in s or "follow-tcp" in s:
        state["task"] = (
            "Reconstruct the application-layer exchange for the HTTP request to "
            "example.com. Follow the correct TCP stream so you can read the raw "
            "GET request and the 200 OK response."
        )
        v["require_followed_stream"] = 0
        return

    # 4) Fix the wrong capture filter that captured nothing useful.
    #    Initial: a too-narrow capture filter (`udp port 53`) captured only DNS,
    #    so the HTTP traffic is missing from the capture entirely. The learner
    #    must correct the capture filter (e.g. `tcp port 80`, `tcp`, or empty/
    #    `host example.com`) and re-capture so HTTP packets appear.
    if "wrong-capture" in s or "fix-capture" in s or "capture-filter" in s:
        state["capture_filter"] = "udp port 53"   # broken: only DNS captured
        state["task"] = (
            "The on-call set a capture filter of 'udp port 53' and the capture "
            "has no web traffic at all — only DNS. Fix the capture filter so the "
            "HTTP traffic to the web server on TCP port 80 is actually captured, "
            "then confirm HTTP packets are present."
        )
        v["require_captured_proto"] = "http"
        v["min_captured_packets"] = 1
        v["forbid_initial_capture_filter"] = "udp port 53"
        return

    # 5) Diagnose TCP retransmissions / RST.
    #    The learner must surface the broken stream-4 conversation (retransmits
    #    then RST) with a display filter AND mark the RST packet as the culprit.
    if "retransmission" in s or "rst" in s or "tcp-reset" in s or "diagnose-tcp" in s:
        state["task"] = (
            "Users report the service on port 8080 is unreachable. The capture "
            "holds the failed connection. Use a display filter to surface the TCP "
            "retransmissions and the RST, then MARK the packet where the server "
            "reset the connection (the TCP RST)."
        )
        v["require_display_filter_shows_rst"] = True
        v["require_marked_rst"] = True
        return

    # Default catch-all: at minimum require some display filter to be applied.
    state["task"] = (
        "Investigate the capture: apply display filters, follow streams, and "
        "mark the packets of interest to characterise the traffic."
    )
    v["require_any_display_filter"] = True


# ---------------------------------------------------------------------------
# Capture / view derivation
# ---------------------------------------------------------------------------

def _captured_packets(state: dict) -> list[dict]:
    """Packets that the current capture filter selected off the wire."""
    cf = state.get("capture_filter", "")
    return [p for p in state["all_packets"] if matches_capture_filter(p, cf)]


def _filtered_view(state: dict) -> list[dict]:
    """Captured packets that also pass the current display filter."""
    df = state.get("display_filter", "")
    return [p for p in _captured_packets(state) if matches_display_filter(p, df)]


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    entry = _load_session(key)
    if entry is None:
        state = _base_inventory()
        _apply_preset(state, scenario_slug)
        entry = {"session_id": key, "scenario_slug": scenario_slug, "state": state,
                 "created_at": _now_iso(), "events": [_event("Capture started on eth0")]}
        _save_session(key, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    state = copy.deepcopy(entry["state"])
    captured = _captured_packets(state)
    view = _filtered_view(state)
    followed = state.get("followed_stream")
    stream_packets = (
        [p for p in captured if p.get("stream_id") == followed] if followed is not None else []
    )
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "inventory": {
            "interface": state.get("interface", "eth0"),
            "capture_active": state.get("capture_active", True),
            "capture_filter": state.get("capture_filter", ""),
            "display_filter": state.get("display_filter", ""),
            "hosts": state.get("hosts", {}),
            "task": state.get("task", ""),
            # Captured packets (post-capture-filter) and the displayed view.
            "captured_packets": captured,
            "packets": view,                 # the filtered view shown in the list
            "selected_packet": state.get("selected_packet"),
            "marked_packets": state.get("marked_packets", []),
            "followed_stream": followed,
            "stream_packets": stream_packets,
            "stream_payload": _stream_payload(followed) if followed is not None else [],
            "protocols": sorted({p["protocol"] for p in captured}),
        },
        "summary": {
            "wire_packets": len(state["all_packets"]),
            "captured_packets": len(captured),
            "displayed_packets": len(view),
            "marked_packets": len(state.get("marked_packets", [])),
            "followed_stream": followed,
            "capture_filter": state.get("capture_filter", ""),
            "display_filter": state.get("display_filter", ""),
            "task": state.get("task", ""),
        },
        "events": entry.get("events", []),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load_session(str(session_id))
    if not entry:
        return {"ok": False, "error": "Wireshark simulation session not found"}
    state = entry["state"]
    events = entry.setdefault("events", [])

    if action == "set_capture_filter":
        expr = _normalize(payload.get("filter") or payload.get("expr") or "")
        state["capture_filter"] = expr
        # Re-capturing resets the followed stream / selection of the old view.
        state["followed_stream"] = None
        state["selected_packet"] = None
        captured = _captured_packets(state)
        events.append(_event(f"Capture filter set to '{expr or '(none)'}' — {len(captured)} packets captured"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Capture filter applied: {expr or '(none)'}",
                "captured_packets": len(captured)}

    if action == "set_display_filter":
        expr = _normalize(payload.get("filter") or payload.get("expr") or "")
        # Validate against the supported display grammar so the UI can flag a bad
        # filter (Wireshark turns the bar red for invalid syntax).
        if expr and not _display_filter_valid(expr):
            return {"ok": False, "error": f"Invalid display filter syntax: {expr}"}
        state["display_filter"] = expr
        view = _filtered_view(state)
        events.append(_event(f"Display filter set to '{expr or '(none)'}' — {len(view)} packets shown"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Display filter applied: {expr or '(none)'}",
                "displayed_packets": len(view)}

    if action == "follow_tcp_stream":
        stream_id = payload.get("stream_id")
        if stream_id is None:
            # Allow following by selecting a packet's stream.
            pkt = _find_pkt(state, payload.get("packet_no"))
            stream_id = pkt.get("stream_id") if pkt else None
        if stream_id is None:
            return {"ok": False, "error": "No stream_id provided"}
        stream_id = int(stream_id)
        captured = _captured_packets(state)
        if not any(p.get("stream_id") == stream_id for p in captured):
            return {"ok": False, "error": f"Stream {stream_id} is not in the capture"}
        state["followed_stream"] = stream_id
        # Following a stream applies the equivalent display filter, like Wireshark.
        state["display_filter"] = f"tcp.stream=={stream_id}"
        events.append(_event(f"Following TCP stream {stream_id}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Following TCP stream {stream_id}",
                "stream_payload": _stream_payload(stream_id)}

    if action == "select_packet":
        no = payload.get("packet_no")
        pkt = _find_pkt(state, no)
        if not pkt:
            return {"ok": False, "error": f"Packet {no} not found"}
        state["selected_packet"] = pkt["no"]
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Selected packet {pkt['no']}", "packet": pkt}

    if action == "mark_packet":
        no = payload.get("packet_no")
        pkt = _find_pkt(state, no)
        if not pkt:
            return {"ok": False, "error": f"Packet {no} not found"}
        marked = state.setdefault("marked_packets", [])
        if pkt["no"] in marked:
            marked.remove(pkt["no"])
            msg = f"Unmarked packet {pkt['no']}"
        else:
            marked.append(pkt["no"])
            msg = f"Marked packet {pkt['no']}"
        events.append(_event(msg))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": msg, "marked_packets": marked}

    if action == "clear_filters":
        state["display_filter"] = ""
        state["followed_stream"] = None
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Display filter cleared"}

    return {"ok": False, "error": f"Unknown action: {action}"}


def _find_pkt(state: dict, no: Any) -> dict | None:
    if no is None:
        return None
    try:
        no = int(no)
    except (ValueError, TypeError):
        return None
    for p in state["all_packets"]:
        if p["no"] == no:
            return p
    return None


def _display_filter_valid(expr: str) -> bool:
    """A filter is 'valid' if every term parses against our supported grammar.
    Used to mimic Wireshark's red invalid-filter bar."""
    expr = _canon_display_ops(_normalize(expr))
    if not expr:
        return True
    for or_part in re.split(r"\bor\b|\|\|", expr):
        for term in re.split(r"\band\b|&&", or_part):
            t = term.strip().lower()
            if not t:
                continue
            # Strip a leading negation (`!term` / `not term` / `!(term)`).
            m_not = re.match(r"^(?:!|not\b)\s*(.+)$", t)
            if m_not:
                t = m_not.group(1).strip()
                if t.startswith("(") and t.endswith(")"):
                    t = t[1:-1].strip()
            if not t:
                return False
            # Normalise a `field != value` to `field == value` for validity.
            m_ne = re.match(r"^(.+?)\s*!=\s*(.+)$", t)
            if m_ne:
                t = f"{m_ne.group(1).strip()} == {m_ne.group(2).strip()}"
            known = (
                t in ("http", "dns", "tls", "ssl", "ssh", "icmp", "tcp", "udp",
                       "http.request", "http.response",
                       "tcp.analysis.retransmission", "tcp.analysis.flags")
                # Bare field-presence (a field name with no comparison).
                or t in ("ip.addr", "ip.src", "ip.dst", "tcp.port", "tcp.srcport",
                         "tcp.dstport", "tcp.stream", "tcp.flags", "udp.port",
                         "udp.srcport", "udp.dstport", "udp.stream")
                or re.match(r"^tcp\.flags\.(reset|syn|fin|ack|push)(\s*==\s*\d)?$", t)
                or re.match(r"^(?:tcp|udp)\.stream\s*==\s*\d+$", t)
                or re.match(r"^(tcp|udp)\.(port|srcport|dstport)\s*==\s*\d+$", t)
                or re.match(r"^ip\.(addr|src|dst)\s*==\s*[0-9a-f:.]+$", t)
            )
            if not known:
                return False
    return True


# ---------------------------------------------------------------------------
# Validation — mirrors validate_vmware_lab(session_id, slug) -> (bool, message)
# ---------------------------------------------------------------------------

def validate_wireshark_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    """Grade the lab from the applied filters / followed stream / marked packets.
    Returns (passed, message). PASS only after the learner performs the correct
    actions; a fresh session always fails."""
    entry = _load_session(str(session_id)) or _ensure_session(session_id, scenario_slug)
    state = entry["state"]
    rules = state.get("validation") or {}
    df = state.get("display_filter", "")
    captured = _captured_packets(state)
    view = _filtered_view(state)

    # 1) Find HTTP traffic: a display filter that isolates HTTP, with results.
    if rules.get("require_display_filter_proto"):
        proto = rules["require_display_filter_proto"]
        if not df:
            return False, "Apply a display filter to isolate the traffic"
        # Every displayed packet must be of the target protocol, and there must
        # be at least the required count.
        target = [p for p in view if _proto_matches(p, proto)]
        if not target:
            return False, f"No {proto.upper()} packets are shown — check your display filter"
        if len(view) != len(target):
            return False, f"The display filter still shows non-{proto.upper()} packets — narrow it to '{proto}'"
        if len(view) < rules.get("min_filtered_packets", 1):
            return False, f"Expected at least {rules.get('min_filtered_packets', 1)} {proto.upper()} packet(s)"
        return True, f"Display filter isolates {len(view)} {proto.upper()} packet(s)"

    # 2) Isolate a single conversation (one stream remains in the view).
    if "require_display_filter_isolates_stream" in rules:
        want = rules["require_display_filter_isolates_stream"]
        if not df:
            return False, "Apply a display filter to isolate the conversation"
        streams = {p.get("stream_id") for p in view}
        if not view:
            return False, "The display filter shows no packets"
        if streams != {want}:
            return False, ("The view still mixes conversations — isolate only the "
                           "client↔web-server stream (tcp.port==80 or ip.addr==93.184.216.34)")
        return True, f"Conversation isolated: {len(view)} packets, single TCP stream"

    # 3) Follow the correct TCP stream.
    if "require_followed_stream" in rules:
        want = rules["require_followed_stream"]
        if state.get("followed_stream") != want:
            return False, "Follow the TCP stream of the HTTP request to example.com"
        return True, f"Followed TCP stream {want} — request/response reassembled"

    # 4) Fix the wrong capture filter so HTTP is actually captured.
    if rules.get("require_captured_proto"):
        proto = rules["require_captured_proto"]
        bad = rules.get("forbid_initial_capture_filter")
        if bad and _normalize(state.get("capture_filter", "")) == _normalize(bad):
            return False, f"The capture filter is still '{bad}' — it captures no {proto.upper()}"
        got = [p for p in captured if _proto_matches(p, proto)]
        if len(got) < rules.get("min_captured_packets", 1):
            return False, f"No {proto.upper()} packets captured — fix the capture filter to include TCP port 80"
        return True, f"Capture now contains {len(got)} {proto.upper()} packet(s)"

    # 5) Diagnose TCP retransmissions / RST: surface them AND mark the RST.
    if rules.get("require_display_filter_shows_rst") or rules.get("require_marked_rst"):
        if rules.get("require_display_filter_shows_rst"):
            if not df:
                return False, "Apply a display filter to surface the retransmissions / RST"
            has_rst = any("RST" in (p.get("tcp_flags") or "") for p in view)
            has_retx = any("retransmission" in (p.get("info") or "").lower() for p in view)
            if not (has_rst or has_retx):
                return False, ("The view does not show the RST or retransmissions — try "
                               "'tcp.flags.reset==1' or 'tcp.analysis.retransmission'")
        if rules.get("require_marked_rst"):
            marked = state.get("marked_packets", [])
            rst_pkts = {p["no"] for p in state["all_packets"] if "RST" in (p.get("tcp_flags") or "")}
            if not (set(marked) & rst_pkts):
                return False, "Mark the TCP RST packet where the server reset the connection"
        return True, "Retransmissions surfaced and the RST packet is marked"

    # Default catch-all.
    if rules.get("require_any_display_filter"):
        if not df:
            return False, "Apply a display filter to characterise the traffic"
        return True, "Display filter applied"

    return False, "No validation rules defined for this scenario"


def _proto_matches(pkt: dict, proto: str) -> bool:
    proto = proto.lower()
    p = pkt["protocol"].lower()
    if proto == "http":
        return p == "http"
    if proto in ("tls", "ssl"):
        return p == "tls"
    if proto == "dns":
        return p == "dns"
    if proto == "ssh":
        return p == "ssh"
    if proto == "tcp":
        return p in ("tcp", "http", "tls", "ssh")
    if proto == "udp":
        return p in ("udp", "dns")
    return p == proto
