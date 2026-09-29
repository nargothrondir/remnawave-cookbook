#!/usr/bin/env python3
"""
validate.py — check a Remnawave config profile (and optionally the web server
config in front of it) against the invariants of this cookbook's architecture:
REALITY on :443 with a self-steal decoy on a unix socket, VLESS over xHTTP
on a unix socket behind the same web server, and Hysteria2 on UDP 443.

Usage:
    python validate.py <profile.json> [angie.conf]

<profile.json> may be:
  - a bare Xray config (has "inbounds"),
  - one profile from the panel API ({"config": {...}} or {"response": {...}}),
  - the panel's profile list (GET /api/config-profiles) — every profile is
    checked, and tags are checked for uniqueness across all of them, as the
    panel requires.
[angie.conf] must be the RENDERED file (inside the container:
/etc/angie/http.d/default.conf), not the gomplate template.

Every finding has an ID (e.g. XHTTP-SOCKET-MISMATCH), so tests and people can
refer to it. Exit codes: 0 no errors (warnings allowed) · 1 errors · 2 input
could not be read. Placeholders like <REALITY_PRIVATE_KEY> are reported as
notes, not errors. Standard library only.
"""
import json
import re
import sys

PLACEHOLDER = re.compile(r"^\s*<[^>]+>\s*$")
HEX = re.compile(r"^[0-9a-fA-F]*$")
TAG_SCHEME = re.compile(r"^[A-Z]{2}-[A-Z0-9]+(-[A-Z0-9]+)+$")
XRAY_IDLE_SECONDS = 300  # Xray policy ConnectionIdle default (v26.6.27)


class Findings:
    def __init__(self):
        self.items = []  # (level, id, message)

    def error(self, fid, msg):
        self.items.append(("ERROR", fid, msg))

    def warn(self, fid, msg):
        self.items.append(("WARN", fid, msg))

    def note(self, fid, msg):
        self.items.append(("NOTE", fid, msg))

    def ids(self, level=None):
        return [i for (lv, i, _) in self.items if level is None or lv == level]


def is_placeholder(v):
    return isinstance(v, str) and bool(PLACEHOLDER.match(v))


def socket_path(listen):
    """'/dev/shm/x.sock,0666' -> '/dev/shm/x.sock'; None if not a socket path."""
    if not isinstance(listen, str):
        return None
    path = listen.split(",", 1)[0].strip()
    return path if path.startswith("/") or path.startswith("@") else None


def normalise_path(p):
    """Xray normalises the xHTTP path to /.../ (splithttp/config.go)."""
    p = (p or "").split("?", 1)[0]
    if not p.startswith("/"):
        p = "/" + p
    if not p.endswith("/"):
        p = p + "/"
    return p


def load_profiles(doc):
    """Return a list of (name, config) from any accepted shape."""
    if isinstance(doc, dict) and "response" in doc:
        doc = doc["response"]
    if isinstance(doc, dict) and "configProfiles" in doc:
        return [(p.get("name", "?"), p.get("config") or {}) for p in doc["configProfiles"]]
    if isinstance(doc, dict) and "config" in doc and isinstance(doc["config"], dict):
        return [(doc.get("name", "profile"), doc["config"])]
    if isinstance(doc, dict) and "inbounds" in doc:
        return [("profile", doc)]
    raise ValueError("no Xray config found (expected 'inbounds', 'config' or 'configProfiles')")


# --------------------------------------------------------------------------
# Inbound checks
# --------------------------------------------------------------------------

def check_tags(profile, inbounds, f, seen_global):
    seen = set()
    for ib in inbounds:
        tag = ib.get("tag")
        if not tag:
            f.error("TAG-MISSING", f"{profile}: an inbound has no tag (the panel rejects it)")
            continue
        if "," in tag:
            f.error("TAG-COMMA", f"{profile}: tag {tag!r} contains ',' (the panel rejects it)")
        if tag in seen:
            f.error("TAG-DUPLICATE", f"{profile}: tag {tag!r} appears twice in one profile")
        seen.add(tag)
        if tag in seen_global:
            f.error("TAG-NOT-UNIQUE", f"{profile}: tag {tag!r} is also used by profile "
                                      f"{seen_global[tag]!r}; tags are unique panel-wide")
        seen_global.setdefault(tag, profile)
        if ib.get("protocol") in ("vless", "hysteria") and not TAG_SCHEME.match(tag):
            f.note("TAG-SCHEME", f"{profile}: tag {tag!r} is outside the <CC>-<PROTOCOL>-… scheme "
                                 f"(fine, but never rename it by hand — see remnawave-2.8.md)")


def check_reality(profile, ib, f):
    tag = ib.get("tag", "?")
    ss = ib.get("streamSettings") or {}
    rs = ss.get("realitySettings") or {}
    out = {"tag": tag, "dest": None, "xver": rs.get("xver", 0), "server_names": []}

    if ib.get("port") != 443:
        f.error("REALITY-PORT", f"{profile}/{tag}: REALITY listens on {ib.get('port')!r}, not 443")
    if ss.get("network", "tcp") not in ("tcp", "raw"):
        f.warn("REALITY-NETWORK", f"{profile}/{tag}: REALITY on network {ss.get('network')!r}; "
                                  f"this cookbook covers REALITY over tcp/raw")

    dest = rs.get("dest", rs.get("target"))
    if not dest:
        f.error("REALITY-DEST-MISSING", f"{profile}/{tag}: realitySettings has no dest/target")
    elif is_placeholder(dest):
        f.note("PLACEHOLDER", f"{profile}/{tag}: dest is a placeholder")
    else:
        out["dest"] = str(dest)
        if str(dest).startswith("/") and out["xver"] not in (1, 2):
            f.warn("REALITY-XVER", f"{profile}/{tag}: dest is a local socket but xver is "
                                   f"{out['xver']!r}; the decoy will not see client addresses "
                                   f"(and must then NOT listen with proxy_protocol)")

    names = rs.get("serverNames") or []
    if not names:
        f.error("REALITY-SERVERNAMES", f"{profile}/{tag}: serverNames is empty")
    out["server_names"] = [n for n in names if not is_placeholder(n)]

    pk = rs.get("privateKey")
    if not pk:
        f.error("REALITY-PRIVATEKEY", f"{profile}/{tag}: privateKey is missing")
    elif is_placeholder(pk):
        f.note("PLACEHOLDER", f"{profile}/{tag}: privateKey is a placeholder")

    for sid in rs.get("shortIds") or []:
        if is_placeholder(sid):
            f.note("PLACEHOLDER", f"{profile}/{tag}: a shortId is a placeholder")
            continue
        if len(sid) > 16 or not HEX.match(sid):
            f.error("REALITY-SHORTID", f"{profile}/{tag}: shortId {sid!r} must be hex, at most 16 characters")
        elif len(sid) % 2:
            f.warn("REALITY-SHORTID-ODD", f"{profile}/{tag}: shortId {sid!r} has an odd length")

    if rs.get("show"):
        f.warn("REALITY-SHOW", f"{profile}/{tag}: realitySettings.show is on (debug output in production)")
    return out


def check_xhttp(profile, ib, f):
    tag = ib.get("tag", "?")
    ss = ib.get("streamSettings") or {}
    xs = ss.get("xhttpSettings") or {}
    sock = socket_path(ib.get("listen"))
    out = {"tag": tag, "socket": sock, "path": None, "trusted": []}

    if sock is None:
        f.note("XHTTP-NOT-SOCKET", f"{profile}/{tag}: xHTTP does not listen on a unix socket; "
                                   f"the web-server checks of this cookbook do not apply to it")
        return out
    if ss.get("security") not in (None, "", "none"):
        f.warn("XHTTP-SECURITY", f"{profile}/{tag}: security {ss.get('security')!r} on a socket "
                                 f"inbound; in this architecture the web server terminates TLS")
    if ib.get("port") is None:
        f.warn("XHTTP-PORT", f"{profile}/{tag}: no port; Xray ignores it for a socket, but the panel's "
                             f"host form fills its required port from the inbound — set 443")

    path = xs.get("path")
    if not path:
        f.error("XHTTP-PATH-MISSING", f"{profile}/{tag}: xhttpSettings.path is empty")
    elif is_placeholder(path.strip("/")) or "<" in path:
        f.note("PLACEHOLDER", f"{profile}/{tag}: path is a placeholder")
        out["path"] = normalise_path(path)
    else:
        out["path"] = normalise_path(path)

    trusted = (ss.get("sockopt") or {}).get("trustedXForwardedFor") or []
    out["trusted"] = trusted
    if not trusted:
        f.warn("XHTTP-TRUSTED-XFF", f"{profile}/{tag}: no sockopt.trustedXForwardedFor; Xray will record "
                                    f"the socket as every client and log a warning per request")
    elif any(("/" in t or t.replace(".", "").isdigit()) for t in trusted):
        f.warn("XHTTP-TRUSTED-XFF-SHAPE", f"{profile}/{tag}: trustedXForwardedFor looks like addresses; "
                                          f"in Xray v26.6.27 it lists header NAMES")

    if xs.get("noSSEHeader"):
        f.note("XHTTP-NOSSE", f"{profile}/{tag}: noSSEHeader is set; the protocol author suggests it only "
                              f"for stream-one trouble — the default is fine behind a web server")
    return out


def check_hysteria2(profile, ib, f):
    """Xray v26.6.27 hysteria inbound (reference/hysteria2.md)."""
    tag = ib.get("tag", "?")
    ss = ib.get("streamSettings") or {}
    hs = ss.get("hysteriaSettings") or {}

    if (ib.get("settings") or {}).get("version") != 2 or hs.get("version") != 2:
        f.error("HY2-VERSION", f"{profile}/{tag}: settings.version and hysteriaSettings.version must both "
                               f"be 2 — Xray v26.6.27 refuses the config ('version != 2')")
    if ss.get("network") != "hysteria":
        f.error("HY2-NETWORK", f"{profile}/{tag}: network {ss.get('network')!r}, not 'hysteria' — the "
                               f"inbound refuses to start ('not hysteria transport')")
    if ib.get("port") != 443:
        f.warn("HY2-PORT", f"{profile}/{tag}: listens on {ib.get('port')!r}; this architecture puts "
                           f"Hysteria2 on UDP 443, next to REALITY on TCP 443")

    if ss.get("security") != "tls":
        f.error("HY2-TLS", f"{profile}/{tag}: security {ss.get('security') or 'none'!r}, not 'tls' — Xray "
                           f"does not start a Hysteria2 listener without TLS, and the node loses every protocol")
    else:
        certs = (ss.get("tlsSettings") or {}).get("certificates") or []
        if not certs or any(not c.get("certificateFile") or not c.get("keyFile") for c in certs):
            f.error("HY2-CERT-INLINE", f"{profile}/{tag}: certificate not given as certificateFile/keyFile — "
                                       f"inline PEM puts the private key in every config the panel pushes")

    moved = sorted(k for k in ("congestion", "up", "down", "udphop") if k in hs)
    if moved:
        f.warn("HY2-MOVED-KEYS", f"{profile}/{tag}: hysteriaSettings has {', '.join(moved)}; Xray v26.6.27 "
                                 f"only logs a warning for them — they belong in finalmask/quicParams")
    if (hs.get("masquerade") or {}).get("type", "") in ("", "404"):
        f.note("HY2-MASQUERADE", f"{profile}/{tag}: no masquerade (bare 404 to anything speaking HTTP/3); "
                                 f"pointing it at the decoy keeps the node one site on TCP and UDP")


# --------------------------------------------------------------------------
# Web server checks (rendered angie.conf / nginx.conf)
# --------------------------------------------------------------------------

def parse_seconds(v):
    m = re.match(r"^(\d+)(ms|s|m|h|d)?$", v or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2) or "s"
    return {"ms": n / 1000, "s": n, "m": n * 60, "h": n * 3600, "d": n * 86400}[unit]


def parse_web(text):
    """Very small nginx parser: server blocks with their listens, names and locations."""
    text = re.sub(r"#[^\n]*", "", text)
    servers = []
    for m in re.finditer(r"\bserver\s*\{", text):
        start, depth, i = m.end(), 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[start:i - 1]
        locations = {}
        for lm in re.finditer(r"\blocation\s+([^\s{]+)\s*\{", body):
            ls, ld, j = lm.end(), 1, lm.end()
            while j < len(body) and ld:
                ld += {"{": 1, "}": -1}.get(body[j], 0)
                j += 1
            locations[lm.group(1)] = body[ls:j - 1]
        top = re.sub(r"\blocation\s+[^\s{]+\s*\{.*?\}", "", body, flags=re.S)
        listens = re.findall(r"\blisten\s+([^;]+);", top)
        names = []
        for n in re.findall(r"\bserver_name\s+([^;]+);", top):
            names += n.split()
        servers.append({"listens": listens, "names": names, "locations": locations, "top": top})
    return servers


def directive(block, name):
    m = re.search(r"\b" + re.escape(name) + r"\s+([^;]+);", block)
    return m.group(1).strip() if m else None


def check_web(text, realities, xhttps, f):
    if "{{" in text:
        f.error("WEB-TEMPLATE", "the web config still contains template markers; pass the RENDERED file "
                                "(docker exec <angie> cat /etc/angie/http.d/default.conf)")
        return
    servers = parse_web(text)

    # nginx empties the URI of a request it cannot parse, and refuses to enter
    # a named location with an empty URI (ngx_http_named_location) — so an
    # error_page for request-line and header errors that points to @name turns
    # a 400 into a 500.
    for s in servers:
        for spec in re.findall(r"\berror_page\s+([^;]+);", s["top"]):
            parts = spec.split()
            target = parts[-1]
            early = sorted({p for p in parts[:-1] if p.isdigit()} & {"400", "414", "494"})
            if target.startswith("@") and early:
                f.error("WEB-NAMED-ERROR-PAGE", f"error_page {' '.join(early)} -> {target}: a request "
                                                f"whose URI nginx cannot parse has an empty URI, and a "
                                                f"named location refuses it with 500; redirect to an "
                                                f"internal URI instead")

    for r in realities:
        dest = r["dest"]
        if not dest or not dest.startswith("/"):
            continue
        on_sock = [s for s in servers if any(("unix:" + dest) in l for l in s["listens"])]
        if not on_sock:
            f.error("WEB-NO-DECOY-LISTENER", f"{r['tag']}: nothing listens on unix:{dest} (REALITY dest)")
            continue
        for s in on_sock:
            l = next(l for l in s["listens"] if ("unix:" + dest) in l)
            has_pp = "proxy_protocol" in l.split()
            if r["xver"] in (1, 2) and not has_pp:
                f.error("WEB-PROXY-PROTOCOL", f"{r['tag']}: xver {r['xver']} but the listener on {dest} "
                                              f"has no proxy_protocol — every handshake breaks")
            if r["xver"] not in (1, 2) and has_pp:
                f.error("WEB-PROXY-PROTOCOL", f"{r['tag']}: listener on {dest} expects proxy_protocol "
                                              f"but xver is {r['xver']!r}")
        named = [s for s in on_sock if "default_server" not in " ".join(s["listens"])]
        for sn in r["server_names"]:
            if not any(sn in s["names"] for s in named):
                f.error("WEB-SERVER-NAME", f"{r['tag']}: no server on {dest} has server_name {sn} "
                                           f"(= REALITY serverNames); the decoy rejects the handshake")

    for x in xhttps:
        if not x["socket"] or not x["path"]:
            continue
        found = [(s, s["locations"][p]) for s in servers for p in s["locations"]
                 if normalise_path(p) == x["path"]]
        if not found:
            f.error("WEB-NO-XHTTP-LOCATION", f"{x['tag']}: no location {x['path']} (the inbound's path, "
                                             f"normalised as Xray does)")
            continue
        for _, block in found:
            grpc = directive(block, "grpc_pass")
            proxy = directive(block, "proxy_pass")
            target = grpc or proxy or ""
            sock = target.replace("http://", "").replace("grpc://", "")
            sock = sock[len("unix:"):] if sock.startswith("unix:") else None
            if sock is None:
                f.error("XHTTP-NO-UPSTREAM", f"{x['tag']}: location {x['path']} has no grpc_pass/proxy_pass "
                                             f"to a unix socket")
                continue
            if sock.rstrip(":") != x["socket"]:
                f.error("XHTTP-SOCKET-MISMATCH", f"{x['tag']}: location passes to {sock}, the inbound "
                                                 f"listens on {x['socket']}")
            prefix = "grpc" if grpc else "proxy"
            if proxy and directive(block, "proxy_request_buffering") != "off":
                f.error("XHTTP-PROXY-BUFFERING", f"{x['tag']}: proxy_pass without proxy_request_buffering "
                                                 f"off — bodies are read whole first; stream-up never passes")
            if directive(block, "access_log") != "off":
                f.warn("XHTTP-ACCESS-LOG", f"{x['tag']}: access_log is on for the xHTTP path — one padded "
                                           f"line per packet-up POST, and a timeline of user traffic")
            if directive(block, "client_max_body_size") != "0":
                f.warn("XHTTP-BODY-SIZE", f"{x['tag']}: client_max_body_size is not 0; a packet-up POST "
                                          f"is up to 1000000 bytes, right at the 1m default")
            rt = directive(block, prefix + "_read_timeout")
            secs = parse_seconds(rt) if rt else 60  # nginx default: 60 s
            if secs is not None and secs <= XRAY_IDLE_SECONDS * 1.1:
                f.warn("XHTTP-READ-TIMEOUT", f"{x['tag']}: {prefix}_read_timeout is {rt or 'default 60s'}; "
                                             f"keep it well above Xray's {XRAY_IDLE_SECONDS}s idle timeout")
            set_headers = [h.split()[0].lower() for h in
                           re.findall(r"\b" + prefix + r"_set_header\s+([^;]+);", block)]
            for h in x["trusted"]:
                if h.lower() not in set_headers:
                    f.error("XHTTP-TRUSTED-HEADER", f"{x['tag']}: trustedXForwardedFor lists {h} but the "
                                                    f"location does not set it — client addresses are lost")
            if x["trusted"] and "x-forwarded-for" not in set_headers:
                f.error("XHTTP-XFF-HEADER", f"{x['tag']}: X-Forwarded-For is not set from the PROXY "
                                            f"protocol address — a client could supply its own")


# --------------------------------------------------------------------------

def validate(profiles, web_text=None):
    f = Findings()
    seen_global = {}
    realities, xhttps = [], []
    for name, cfg in profiles:
        inbounds = cfg.get("inbounds") or []
        if not inbounds:
            f.error("NO-INBOUNDS", f"{name}: no inbounds")
            continue
        check_tags(name, inbounds, f, seen_global)
        for ib in inbounds:
            ss = ib.get("streamSettings") or {}
            if ib.get("protocol") == "vless" and ss.get("security") == "reality":
                realities.append(check_reality(name, ib, f))
            elif ss.get("network") == "xhttp":
                xhttps.append(check_xhttp(name, ib, f))
            elif ib.get("protocol") == "hysteria":
                check_hysteria2(name, ib, f)
    if web_text is not None:
        check_web(web_text, realities, xhttps, f)
    return f


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__.strip().split("\n\n")[1])
        return 2
    try:
        with open(argv[1], encoding="utf-8") as fh:
            profiles = load_profiles(json.load(fh))
        web = None
        if len(argv) == 3:
            with open(argv[2], encoding="utf-8") as fh:
                web = fh.read()
    except (OSError, ValueError) as e:
        print(f"cannot read input: {e}")
        return 2
    f = validate(profiles, web)
    for level, fid, msg in f.items:
        print(f"{level:5} {fid}: {msg}")
    errors = len(f.ids("ERROR"))
    print(f"\n{errors} error(s), {len(f.ids('WARN'))} warning(s), {len(f.ids('NOTE'))} note(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
