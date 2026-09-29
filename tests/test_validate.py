"""Tests for skills/remnawave-cookbook/validate.py.

One good case that must be completely clean, and one case per rule that must
raise exactly its own finding — so a rule that stops biting fails here, not in
someone's fleet. Standard library only: python -m unittest discover -s tests
"""
import copy
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "remnawave-cookbook")
sys.path.insert(0, SKILL)

import validate  # noqa: E402

with open(os.path.join(SKILL, "examples", "profile.json"), encoding="utf-8") as fh:
    EXAMPLE = json.load(fh)

GOOD_WEB = """
server {
    server_name node.example.com;
    listen unix:/dev/shm/nginx.sock ssl proxy_protocol;
    http2 on;
    root /var/www/html;
    location /p4th/ {
        access_log off;
        client_max_body_size 0;
        client_body_timeout 5m;
        grpc_read_timeout 1h;
        grpc_send_timeout 1h;
        grpc_set_header X-Real-IP $proxy_protocol_addr;
        grpc_set_header X-Forwarded-For $proxy_protocol_addr;
        grpc_pass unix:/dev/shm/xhttp.sock;
    }
}
server {
    listen unix:/dev/shm/nginx.sock ssl proxy_protocol default_server;
    server_name _;
    ssl_reject_handshake on;
}
"""

PROXY_BLOCK = """
        access_log off;
        client_max_body_size 0;
        proxy_http_version 1.1;
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $proxy_protocol_addr;
        proxy_set_header X-Forwarded-For $proxy_protocol_addr;
        proxy_pass http://unix:/dev/shm/xhttp.sock;
"""


def good_config():
    """The example profile with its placeholders filled in."""
    cfg = copy.deepcopy(EXAMPLE)
    reality, xhttp, _ = cfg["inbounds"]
    reality["streamSettings"]["realitySettings"]["privateKey"] = "a" * 43
    reality["streamSettings"]["realitySettings"]["shortIds"] = ["0123456789abcdef"]
    xhttp["streamSettings"]["xhttpSettings"]["path"] = "/p4th/"
    return cfg


def run(cfg=None, web=None, profiles=None):
    profiles = profiles if profiles is not None else [("test", cfg if cfg is not None else good_config())]
    return validate.validate(profiles, web)


def grpc_block_of(web):
    start = web.index("location /p4th/ {") + len("location /p4th/ {")
    return start, web.index("}", start)


def with_location_body(body, web=GOOD_WEB):
    start, end = grpc_block_of(web)
    return web[:start] + body + web[end:]


class GoodCases(unittest.TestCase):
    def test_example_profile_alone_has_no_errors(self):
        f = run(cfg=copy.deepcopy(EXAMPLE))
        self.assertEqual(f.ids("ERROR"), [])

    def test_good_profile_and_web_are_clean(self):
        f = run(web=GOOD_WEB)
        self.assertEqual(f.ids("ERROR"), [])
        self.assertEqual(f.ids("WARN"), [])
        self.assertEqual(f.ids("NOTE"), [])

    def test_proxy_pass_with_request_buffering_off_is_clean(self):
        f = run(web=with_location_body(PROXY_BLOCK))
        self.assertEqual(f.ids("ERROR"), [])
        self.assertEqual(f.ids("WARN"), [])

    def test_panel_profile_list_is_accepted(self):
        doc = {"response": {"configProfiles": [{"name": "A", "config": good_config()}]}}
        profiles = validate.load_profiles(doc)
        self.assertEqual([p[0] for p in profiles], ["A"])
        self.assertEqual(run(profiles=profiles).ids("ERROR"), [])


class ProfileRules(unittest.TestCase):
    def test_reality_not_on_443(self):
        cfg = good_config()
        cfg["inbounds"][0]["port"] = 8443
        self.assertEqual(run(cfg).ids("ERROR"), ["REALITY-PORT"])

    def test_reality_shortid_too_long(self):
        cfg = good_config()
        cfg["inbounds"][0]["streamSettings"]["realitySettings"]["shortIds"] = ["0" * 18]
        self.assertEqual(run(cfg).ids("ERROR"), ["REALITY-SHORTID"])

    def test_tag_duplicate_within_profile(self):
        cfg = good_config()
        cfg["inbounds"][1]["tag"] = cfg["inbounds"][0]["tag"]
        self.assertIn("TAG-DUPLICATE", run(cfg).ids("ERROR"))

    def test_tag_not_unique_across_profiles(self):
        profiles = [("A", good_config()), ("B", good_config())]
        errors = run(profiles=profiles).ids("ERROR")
        self.assertEqual(sorted(set(errors)), ["TAG-NOT-UNIQUE"])

    def test_xhttp_without_port_warns(self):
        cfg = good_config()
        del cfg["inbounds"][1]["port"]
        f = run(cfg)
        self.assertEqual(f.ids("ERROR"), [])
        self.assertEqual(f.ids("WARN"), ["XHTTP-PORT"])

    def test_xhttp_without_trusted_xff_warns(self):
        cfg = good_config()
        del cfg["inbounds"][1]["streamSettings"]["sockopt"]
        self.assertEqual(run(cfg).ids("WARN"), ["XHTTP-TRUSTED-XFF"])


class Hysteria2Rules(unittest.TestCase):
    def hy2(self, cfg):
        return cfg["inbounds"][2]

    def test_tls_missing(self):
        cfg = good_config()
        self.hy2(cfg)["streamSettings"]["security"] = "none"
        self.assertEqual(run(cfg).ids("ERROR"), ["HY2-TLS"])

    def test_inline_pem(self):
        cfg = good_config()
        self.hy2(cfg)["streamSettings"]["tlsSettings"]["certificates"] = [
            {"certificate": ["-----BEGIN CERTIFICATE-----"], "key": ["-----BEGIN PRIVATE KEY-----"]}]
        self.assertEqual(run(cfg).ids("ERROR"), ["HY2-CERT-INLINE"])

    def test_no_certificate(self):
        cfg = good_config()
        del self.hy2(cfg)["streamSettings"]["tlsSettings"]["certificates"]
        self.assertEqual(run(cfg).ids("ERROR"), ["HY2-CERT-INLINE"])

    def test_version_not_2(self):
        cfg = good_config()
        del self.hy2(cfg)["streamSettings"]["hysteriaSettings"]["version"]
        self.assertEqual(run(cfg).ids("ERROR"), ["HY2-VERSION"])

    def test_wrong_network(self):
        cfg = good_config()
        self.hy2(cfg)["streamSettings"]["network"] = "tcp"
        self.assertEqual(run(cfg).ids("ERROR"), ["HY2-NETWORK"])

    def test_other_port_warns(self):
        cfg = good_config()
        self.hy2(cfg)["port"] = 8443
        f = run(cfg)
        self.assertEqual(f.ids("ERROR"), [])
        self.assertEqual(f.ids("WARN"), ["HY2-PORT"])

    def test_moved_keys_warn(self):
        cfg = good_config()
        self.hy2(cfg)["streamSettings"]["hysteriaSettings"]["congestion"] = "bbr"
        self.assertEqual(run(cfg).ids("WARN"), ["HY2-MOVED-KEYS"])

    def test_default_masquerade_is_a_note(self):
        cfg = good_config()
        del self.hy2(cfg)["streamSettings"]["hysteriaSettings"]["masquerade"]
        f = run(cfg)
        self.assertEqual(f.ids("ERROR") + f.ids("WARN"), [])
        self.assertEqual(f.ids("NOTE"), ["HY2-MASQUERADE"])


class WebRules(unittest.TestCase):
    def test_template_markers_refused(self):
        self.assertEqual(run(web=GOOD_WEB + "\n{{ getenv \"X\" }}\n").ids("ERROR"), ["WEB-TEMPLATE"])

    def test_listener_without_proxy_protocol(self):
        web = GOOD_WEB.replace("ssl proxy_protocol;", "ssl;", 1)
        self.assertEqual(run(web=web).ids("ERROR"), ["WEB-PROXY-PROTOCOL"])

    def test_server_name_differs_from_reality(self):
        web = GOOD_WEB.replace("server_name node.example.com;", "server_name other.example.com;")
        self.assertEqual(run(web=web).ids("ERROR"), ["WEB-SERVER-NAME"])

    def test_location_path_differs(self):
        web = GOOD_WEB.replace("location /p4th/", "location /other/")
        self.assertEqual(run(web=web).ids("ERROR"), ["WEB-NO-XHTTP-LOCATION"])

    def test_socket_mismatch(self):
        web = GOOD_WEB.replace("grpc_pass unix:/dev/shm/xhttp.sock;", "grpc_pass unix:/dev/shm/other.sock;")
        self.assertEqual(run(web=web).ids("ERROR"), ["XHTTP-SOCKET-MISMATCH"])

    def test_proxy_pass_with_request_buffering_on(self):
        body = PROXY_BLOCK.replace("        proxy_request_buffering off;\n", "")
        self.assertEqual(run(web=with_location_body(body)).ids("ERROR"), ["XHTTP-PROXY-BUFFERING"])

    def test_trusted_header_not_set(self):
        web = GOOD_WEB.replace("        grpc_set_header X-Real-IP $proxy_protocol_addr;\n", "")
        self.assertEqual(run(web=web).ids("ERROR"), ["XHTTP-TRUSTED-HEADER"])

    def test_xff_not_set(self):
        web = GOOD_WEB.replace("        grpc_set_header X-Forwarded-For $proxy_protocol_addr;\n", "")
        self.assertEqual(run(web=web).ids("ERROR"), ["XHTTP-XFF-HEADER"])

    def test_access_log_on_warns(self):
        web = GOOD_WEB.replace("        access_log off;\n", "")
        f = run(web=web)
        self.assertEqual(f.ids("ERROR"), [])
        self.assertEqual(f.ids("WARN"), ["XHTTP-ACCESS-LOG"])

    def test_xtls_example_timeout_warns(self):
        # 315 s sits right at Xray's 300 s idle timeout and cut live streams.
        web = GOOD_WEB.replace("grpc_read_timeout 1h;", "grpc_read_timeout 315;")
        self.assertEqual(run(web=web).ids("WARN"), ["XHTTP-READ-TIMEOUT"])

    def test_named_location_error_page_for_request_line_errors(self):
        web = GOOD_WEB.replace("root /var/www/html;", "root /var/www/html;\n    error_page 400 414 @stock;", 1)
        self.assertEqual(run(web=web).ids("ERROR"), ["WEB-NAMED-ERROR-PAGE"])

    def test_internal_uri_error_page_is_clean(self):
        web = GOOD_WEB.replace("root /var/www/html;",
                               "root /var/www/html;\n    error_page 400 414 /__error_page/400;", 1)
        self.assertEqual(run(web=web).ids("ERROR"), [])

    def test_named_location_for_late_errors_is_not_flagged(self):
        web = GOOD_WEB.replace("root /var/www/html;", "root /var/www/html;\n    error_page 502 @down;", 1)
        self.assertEqual(run(web=web).ids("ERROR"), [])

    def test_default_timeout_warns(self):
        web = GOOD_WEB.replace("        grpc_read_timeout 1h;\n", "")
        self.assertEqual(run(web=web).ids("WARN"), ["XHTTP-READ-TIMEOUT"])


class CommandLine(unittest.TestCase):
    def _write(self, content, suffix):
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_exit_codes(self):
        good = self._write(json.dumps(good_config()), ".json")
        web = self._write(GOOD_WEB, ".conf")
        bad = good_config()
        bad["inbounds"][0]["port"] = 8443
        bad_path = self._write(json.dumps(bad), ".json")
        self.assertEqual(validate.main(["validate.py", good, web]), 0)
        self.assertEqual(validate.main(["validate.py", bad_path]), 1)
        self.assertEqual(validate.main(["validate.py", self._write("not json", ".json")]), 2)


if __name__ == "__main__":
    unittest.main()
