"""
SSL Certificate Generator (Python)
----------------------------------
Generates self-signed SSL certificates for PostgreSQL using the `cryptography` library.
This bypasses OS-level dependency issues (OpenSSL/PowerShell versions).
"""

import datetime
import ipaddress
import os
import secrets
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def generate_certificates(certs_dir: Path):
    print(f"🔐 Generating SSL Certificates in {certs_dir}...")
    
    # 1. Generate Private Key
    print("   - Generating 2048-bit RSA private key...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # 2. Configure Certificate
    print("   - Configuring certificate details...")
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "TW"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Taipei"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AdminSystem"),
        x509.NameAttribute(NameOID.COMMON_NAME, "hsib-sop-db"),
    ])

    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True,
        )
    )

    # 3. Sign Certificate
    print("   - Signing certificate...")
    certificate = cert_builder.sign(
        private_key=private_key, algorithm=hashes.SHA256()
    )

    # 4. Write Files
    # Ensure directory exists
    certs_dir.mkdir(parents=True, exist_ok=True)
    
    key_path = certs_dir / "server.key"
    cert_path = certs_dir / "server.crt"

    print(f"   - Writing {key_path}...")
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    print(f"   - Writing {cert_path}...")
    with open(cert_path, "wb") as f:
        f.write(certificate.public_bytes(serialization.Encoding.PEM))

    print("\n✅ Certificate generation complete!")
    print(f"   Key:  {key_path} (Permissions: Read/Write for owner)")
    print(f"   Cert: {cert_path}")


if __name__ == "__main__":
    # Get project root (parent of 'scripts')
    project_root = Path(__file__).parent.parent
    certs_dir = project_root / "certs"
    
    try:
        generate_certificates(certs_dir)
    except ImportError:
        print("❌ Error: 'cryptography' library not installed.")
        print("   Please run: pip install cryptography")
    except Exception as e:
        print(f"❌ Error generating certificates: {e}")
