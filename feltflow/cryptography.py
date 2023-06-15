"""Module for managing encryption/decryption using keys."""
import json
from base64 import b64decode, b64encode

from nacl.public import Box, PrivateKey, PublicKey


def encrypt_nacl(data: str, public_key: str) -> str:
    """Encryption function using NaCl box for encrypting auth tokens
    Implementation is compatible with FELT Labs backend

    Args:
        data: message data
        public_key: public key of recipient

    Returns:
        encrypted data
    """
    public_key_decoded = b64decode(public_key)

    emph_key = PrivateKey.generate()
    enc_box = Box(emph_key, PublicKey(public_key_decoded))
    # Encryption is required to work with MetaMask decryption (requires utf8)
    encrypted_message = enc_box.encrypt(data.encode("utf-8"))
    return json.dumps(
        {
            "nonce": b64encode(encrypted_message.nonce),
            "ephemPublicKey": b64encode(bytes(emph_key.public_key)),
            "ciphertext": b64encode(encrypted_message.ciphertext),
        },
        separators=(",", ":"),
    )


def decrypt_nacl(data: str, private_key: str) -> str:
    """Decryption function using NaCl box for decrypting auth tokens
    Implementation is compatible with FELT Labs backend

    Args:
        data: encrypted message data
        private_key: private key as hex string to use for decryption

    Returns:
        decrypted data
    """
    data_dict = json.loads(data)
    emph_key = b64decode(data_dict["ephemPublicKey"])
    box = Box(PrivateKey(bytes.fromhex(private_key)), PublicKey(emph_key))
    return box.decrypt(
        b64decode(data_dict["ciphertext"], b64decode(data_dict["nonce"]))
    ).decode("utf-8")
