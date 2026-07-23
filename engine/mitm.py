"""
MITM certificate manager for HTTPS interception.

Generates a CA certificate (once, stored as files) and per-domain
certificates (on the fly, cached in memory) so the local proxy can
decrypt HTTPS traffic and relay it through Apps Script.

The user must install ca/ca.crt in their browser's trusted CAs once.

Requires: pip install cryptography
"""

import collections
import datetime
import logging
import os
import re
import ssl
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

log = logging.getLogger("MITM")

# CA lives at the project root (../ca/ relative to this file in engine/).
# The installed trusted root was generated there; keep using it.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
CA_DIR = os.path.join(_PROJECT_ROOT, "ca")
CA_KEY_FILE = os.path.join(CA_DIR, "ca.key")
CA_CERT_FILE = os.path.join(CA_DIR, "ca.crt")

#: Subject CN of the CA. The installer and the panel's trust check both need
#: it, and hard-coding the same string in three files is how they drifted.
CERT_COMMON_NAME = "Aras-GP"

#: How many per-host TLS contexts to keep. Each one holds an OpenSSL context
#: and a certificate, so an unbounded cache grew without limit across a long
#: browsing session — a few thousand ad/CDN hostnames is an ordinary evening.
MAX_CACHED_CONTEXTS = 512


# Filename-safe form of an SNI / hostname.  Windows forbids colons,
# question marks, etc., so IPv6 literals (and stray Unicode) must be
# rewritten before they become part of a cached cert file path.
_UNSAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_domain_filename(domain: str) -> str:
    cleaned = _UNSAFE_NAME_RE.sub("_", domain.strip(".").lower())
    return cleaned[:120] or "unknown"


class MITMCertManager:
    def __init__(self):
        self._ca_key = None
        self._ca_cert = None
        self._ctx_cache: collections.OrderedDict[str, ssl.SSLContext] = (
            collections.OrderedDict()
        )
        self._cert_dir = tempfile.mkdtemp(prefix="domainfront_certs_")
        self._ensure_ca()
        # One RSA key, shared by every leaf certificate we mint.
        #
        # Generating a fresh 2048-bit key per hostname cost ~150 ms of pure
        # CPU *on the event loop* — every new host froze the entire proxy,
        # and one page load touching thirty domains stalled it for seconds.
        # Signing with a key we already hold takes about a millisecond. This
        # is what mitmproxy and Charles do, and it costs nothing in safety:
        # the key never leaves this process, and possessing the CA key (which
        # is on the same disk) already lets an attacker mint anything.
        self._leaf_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        self._leaf_key_pem = self._leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )

    def fingerprint(self) -> str:
        """SHA-256 of the CA certificate, uppercase hex — the identity that
        matters when asking whether *this* CA is the one the OS trusts."""
        return self._ca_cert.fingerprint(hashes.SHA256()).hex().upper()

    def _ensure_ca(self):
        if os.path.exists(CA_KEY_FILE) and os.path.exists(CA_CERT_FILE):
            with open(CA_KEY_FILE, "rb") as f:
                self._ca_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )
            with open(CA_CERT_FILE, "rb") as f:
                self._ca_cert = x509.load_pem_x509_certificate(f.read())
            log.info("Loaded CA from %s", CA_DIR)
        else:
            self._create_ca()

    def _create_ca(self):
        os.makedirs(CA_DIR, exist_ok=True)

        self._ca_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, CERT_COMMON_NAME),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, CERT_COMMON_NAME),
        ])
        now = datetime.datetime.now(datetime.timezone.utc)
        self._ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(self._ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0), critical=True
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            # A Subject Key Identifier on the CA lets each leaf carry a matching
            # Authority Key Identifier. macOS/Safari builds the trust chain by
            # that link, and rejects leaves whose issuer it cannot resolve.
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(
                    self._ca_key.public_key()
                ),
                critical=False,
            )
            .sign(self._ca_key, hashes.SHA256())
        )

        with open(CA_KEY_FILE, "wb") as f:
            f.write(
                self._ca_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                )
            )
        # Restrict the CA private key to the current user on POSIX.
        # os.chmod is a no-op for permission bits on Windows.
        if os.name == "posix":
            try:
                os.chmod(CA_KEY_FILE, 0o600)
            except OSError:
                pass
        with open(CA_CERT_FILE, "wb") as f:
            f.write(self._ca_cert.public_bytes(serialization.Encoding.PEM))

        log.warning("Generated new CA certificate: %s", CA_CERT_FILE)
        log.warning(">>> Install this file in your browser's Trusted Root CAs! <<<")

    def get_dispatch_context(self, fallback_domain: str) -> ssl.SSLContext:
        """A context that picks its certificate from the client's real SNI.

        Browsers CONNECT to the hostname they want, so naming the certificate
        after the CONNECT target worked for them. Native apps often do not:
        they CONNECT to an IP address, or to one host while requesting a
        certificate for another, and then reject the certificate we minted for
        the wrong name. Deciding inside the handshake — where the SNI actually
        is — serves the right certificate to both.

        The returned context still carries a certificate for *fallback_domain*
        so a client that sends no SNI at all still completes a handshake.
        """
        ctx = self.get_server_context(fallback_domain)

        def _pick(sslobj, server_name, _ctx):
            if not server_name or server_name == fallback_domain:
                return None
            try:
                sslobj.context = self.get_server_context(server_name)
            except Exception as exc:      # never abort a handshake over this
                log.debug("SNI %r: keeping fallback certificate (%s)",
                          server_name, exc)
            return None

        # sni_callback belongs to the context, and contexts are shared through
        # the cache, so set it once per context rather than per connection.
        if getattr(ctx, "_aras_sni_wired", False) is False:
            ctx.sni_callback = _pick
            ctx._aras_sni_wired = True
        return ctx

    def get_server_context(self, domain: str) -> ssl.SSLContext:
        cached = self._ctx_cache.get(domain)
        if cached is not None:
            self._ctx_cache.move_to_end(domain)
            return cached

        key_pem, cert_pem = self._generate_domain_cert(domain)

        safe = _safe_domain_filename(domain)
        cert_file = os.path.join(self._cert_dir, f"{safe}.crt")
        key_file = os.path.join(self._cert_dir, f"{safe}.key")

        ca_pem = self._ca_cert.public_bytes(serialization.Encoding.PEM)
        with open(cert_file, "wb") as f:
            f.write(cert_pem + ca_pem)
        with open(key_file, "wb") as f:
            f.write(key_pem)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.set_alpn_protocols(["http/1.1"])
        try:
            ctx.load_cert_chain(cert_file, key_file)
        finally:
            # load_cert_chain reads both files immediately, so they are dead
            # weight afterwards. Removing them keeps the private key off disk
            # and stops the temp directory growing one pair per hostname.
            for path in (cert_file, key_file):
                try:
                    os.remove(path)
                except OSError:
                    pass

        self._ctx_cache[domain] = ctx
        while len(self._ctx_cache) > MAX_CACHED_CONTEXTS:
            self._ctx_cache.popitem(last=False)
        return ctx

    def _generate_domain_cert(self, domain: str):
        key = self._leaf_key
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, domain[:64] or "unknown"),
        ])

        # SAN: IP literal vs DNS name — x509.DNSName rejects IPv6 literals.
        import ipaddress as _ipaddress
        try:
            san_entry = x509.IPAddress(_ipaddress.ip_address(domain))
        except ValueError:
            san_entry = x509.DNSName(domain)

        # Apple caps TLS-server leaf validity at 398 days (certs issued after
        # 2020-09-01); a longer one is rejected outright by Safari and the
        # macOS trust engine. Stay comfortably under it.
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=397))
            .add_extension(
                x509.SubjectAlternativeName([san_entry]),
                critical=False,
            )
            # Everything below is what modern browsers require of a TLS server
            # cert and the previous version omitted — which is why Chrome and
            # Safari refused every intercepted site even with the CA trusted:
            #   • not a CA
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            #   • usable for a TLS handshake
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            #   • serverAuth — Chrome and Safari reject a leaf without it
            .add_extension(
                x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            #   • chain link back to the CA's Subject Key Identifier
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    self._ca_key.public_key()
                ),
                critical=False,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                critical=False,
            )
            .sign(self._ca_key, hashes.SHA256())
        )

        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        return self._leaf_key_pem, cert_pem
