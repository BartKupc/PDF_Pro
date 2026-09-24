"""User-visible copy and app-wide constants. Keep legal notices verbatim."""

APP_NAME = "PDF_Pro"
APP_ID = "io.github.bartkupc.pdfpro"
ORG_NAME = "BartKupc"

COVER_NOT_REDACTION = (
    "Cover-and-replace is a visual amendment, not redaction. "
    "Underlying PDF content may still be extractable."
)

VISUAL_SIGNATURE_NOTICE = (
    "Visual signature, not a certificate-backed digital signature. "
    "This appearance does not prove identity, legal validity, witnessing, "
    "or tamper-proofing. You must judge whether the recipient and jurisdiction "
    "will accept it."
)

EXISTING_SIGNATURE_WARNING = (
    "This PDF already contains a digital signature or certification. "
    "Amendments will invalidate the existing signature. "
    "The old signature will not survive export."
)

PASSWORD_PROMPT = "This PDF is password-protected. Enter the user password to open it."
PASSWORD_WRONG = "That password did not open the file. The original is unchanged."
CORRUPT_NOTICE = "This file could not be opened as a PDF. It may be corrupted or unsupported."
UNSUPPORTED_NOTICE = "This file is not a supported PDF."

VAULT_WRONG_PASSPHRASE = (
    "Wrong passphrase. The signature vault was not unlocked and no data was exposed."
)
VAULT_MIGRATE_PROMPT = (
    "Vault is now stored unencrypted — enter your passphrase one last time "
    "to migrate your signatures"
)
VAULT_MIGRATE_FORGOT = (
    "Start with an empty vault. The old encrypted file is kept on disk."
)

DEFAULT_ZOOM = 1.25
MIN_ZOOM = 0.25
MAX_ZOOM = 8.0
SNAP_THRESHOLD_PT = 5.0

VAULT_MAGIC = b"PDFPROVAULT1"
VAULT_VERSION = 1
ARGON2_TIME_COST = 3
ARGON2_MEMORY_KIB = 65536
ARGON2_PARALLELISM = 2
ARGON2_HASH_LEN = 32
AES_NONCE_LEN = 12
SALT_LEN = 16
