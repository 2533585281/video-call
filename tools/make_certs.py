"""Create a 10-year LAN CA and a server certificate covering this computer."""
import base64
import ipaddress
import socket
import subprocess
import uuid
from pathlib import Path

OPENSSL = r"C:\Program Files\Git\mingw64\bin\openssl.exe"
ROOT = Path(r"D:\DPH\video-call")
TLS = ROOT / "tls"
TLS.mkdir(exist_ok=True)


def run(args):
    subprocess.run([OPENSSL, *args], check=True, cwd=TLS)


def lan_ips():
    found = {"127.0.0.1", "192.168.137.1"}
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            addr = ipaddress.ip_address(ip)
            if addr.is_private or addr.is_loopback:
                found.add(ip)
    except OSError:
        pass
    # Also ask Windows for the addresses actually on the adapters.
    try:
        out = subprocess.check_output(
            ["ipconfig"], text=True, encoding="utf-8", errors="ignore"
        )
    except Exception:
        out = ""
    for line in out.splitlines():
        line = line.strip()
        if "IPv4" not in line and "IP Address" not in line:
            continue
        if ":" not in line:
            continue
        ip = line.split(":")[-1].strip()
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr.version == 4 and (addr.is_private or addr.is_loopback):
            found.add(ip)
    return sorted(found, key=lambda item: ipaddress.ip_address(item))


ips = lan_ips()
san = ["DNS:localhost"] + [f"IP:{ip}" for ip in ips]
print("SAN", ", ".join(san))

if not (TLS / "ca.key").exists():
    run(["genrsa", "-out", "ca.key", "2048"])
ca_cnf = TLS / "ca.cnf"
ca_cnf.write_text(
    "[req]\n"
    "distinguished_name=dn\n"
    "x509_extensions=v3_ca\n"
    "prompt=no\n"
    "[dn]\n"
    "CN=Open-LLM-VTuber Home CA\n"
    "O=Home\n"
    "[v3_ca]\n"
    "basicConstraints=critical,CA:TRUE\n"
    "keyUsage=critical,keyCertSign,cRLSign\n"
    "subjectKeyIdentifier=hash\n"
    "authorityKeyIdentifier=keyid:always,issuer\n",
    encoding="ascii",
)
run(
    [
        "req", "-x509", "-new", "-nodes", "-key", "ca.key", "-sha256", "-days", "3650",
        "-out", "ca.crt", "-config", "ca.cnf",
    ]
)
run(["x509", "-outform", "der", "-in", "ca.crt", "-out", "ca.cer"])
run(["genrsa", "-out", "server.key", "2048"])
run(["req", "-new", "-key", "server.key", "-out", "server.csr", "-subj", "/CN=localhost"])
server_ext = TLS / "server.ext"
server_ext.write_text(
    "[v3_req]\n"
    "basicConstraints=critical,CA:FALSE\n"
    "keyUsage=critical,digitalSignature,keyEncipherment\n"
    "extendedKeyUsage=serverAuth\n"
    "subjectKeyIdentifier=hash\n"
    "authorityKeyIdentifier=keyid,issuer\n"
    "subjectAltName=" + ",".join(san) + "\n",
    encoding="ascii",
)
run(
    [
        "x509", "-req", "-in", "server.csr", "-CA", "ca.crt", "-CAkey", "ca.key",
        "-CAcreateserial", "-out", "server.crt", "-days", "3650", "-sha256",
        "-extensions", "v3_req", "-extfile", "server.ext",
    ]
)

der = (TLS / "ca.cer").read_bytes()
b64 = base64.encodebytes(der).decode("ascii")
uid_root = str(uuid.uuid4())
uid_cert = str(uuid.uuid4())
profile = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadContent</key>
  <array>
    <dict>
      <key>PayloadCertificateFileName</key>
      <string>ca.cer</string>
      <key>PayloadContent</key>
      <data>{b64}</data>
      <key>PayloadDescription</key>
      <string>Trust this computer's home certificate</string>
      <key>PayloadDisplayName</key>
      <string>Open-LLM-VTuber Home CA</string>
      <key>PayloadIdentifier</key>
      <string>com.home.open-llm-vtuber.ca</string>
      <key>PayloadType</key>
      <string>com.apple.security.root</string>
      <key>PayloadUUID</key>
      <string>{uid_cert}</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
    </dict>
  </array>
  <key>PayloadDisplayName</key>
  <string>Open-LLM-VTuber Home</string>
  <key>PayloadIdentifier</key>
  <string>com.home.open-llm-vtuber</string>
  <key>PayloadRemovalDisallowed</key>
  <false/>
  <key>PayloadType</key>
  <string>Configuration</string>
  <key>PayloadUUID</key>
  <string>{uid_root}</string>
  <key>PayloadVersion</key>
  <integer>1</integer>
</dict>
</plist>
"""
(TLS / "ca.mobileconfig").write_text(profile, encoding="utf-8")
print("certs ready")
