from __future__ import annotations

"""Galois Field GF(2^8) arithmetic and Reed-Solomon encoder.

Standalone module — no dependencies beyond Python stdlib.
Used for position frame error correction in the MIXI-CUT protocol.

GF(2^8) with primitive polynomial x^8 + x^4 + x^3 + x^2 + 1 (0x11D).
"""

from mixi_cut.protocol import GF_PRIMITIVE_POLY

# ── Lookup tables ─────────────────────────────────────────────

GF_EXP = [0] * 512
GF_LOG = [0] * 256
_GF_INITIALIZED = False


def _init_gf():
    """Initialize GF(2^8) exp/log lookup tables."""
    global _GF_INITIALIZED
    if _GF_INITIALIZED:
        return
    x = 1
    for i in range(255):
        GF_EXP[i] = x
        GF_LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= GF_PRIMITIVE_POLY
    for i in range(255, 512):
        GF_EXP[i] = GF_EXP[i - 255]
    _GF_INITIALIZED = True


# Initialize on import
_init_gf()


def gf_mul(a: int, b: int) -> int:
    """Multiply two elements in GF(2^8).

    Args:
        a: First element (0-255)
        b: Second element (0-255)

    Returns:
        Product in GF(2^8)
    """
    if a == 0 or b == 0:
        return 0
    return GF_EXP[GF_LOG[a] + GF_LOG[b]]


def gf_pow(x: int, power: int) -> int:
    """Raise element x to the given power in GF(2^8)."""
    if power == 0:
        return 1
    if x == 0:
        return 0
    return GF_EXP[(GF_LOG[x] * power) % 255]


def gf_inverse(x: int) -> int:
    """Multiplicative inverse in GF(2^8)."""
    if x == 0:
        raise ZeroDivisionError("Cannot invert zero in GF(2^8)")
    return GF_EXP[255 - GF_LOG[x]]


def rs_generator_poly(nsym: int) -> list[int]:
    """Compute the Reed-Solomon generator polynomial.

    Args:
        nsym: Number of parity symbols

    Returns:
        Coefficients of the generator polynomial (highest degree first)
    """
    gen = [1]
    for i in range(nsym):
        new_gen = [0] * (len(gen) + 1)
        for j, g in enumerate(gen):
            new_gen[j] ^= g
            new_gen[j + 1] ^= gf_mul(g, GF_EXP[i])
        gen = new_gen
    return gen


def rs_encode(data: list[int] | bytes, nsym: int = 4) -> list[int]:
    """Reed-Solomon encode: append nsym parity bytes to data.

    Args:
        data: Input data bytes (each 0-255)
        nsym: Number of parity symbols to append

    Returns:
        data + parity bytes (total length = len(data) + nsym)

    Example:
        >>> rs_encode([0x00, 0x01, 0x5E], nsym=4)
        [0, 1, 94, ...]  # 3 data + 4 parity = 7 bytes
    """
    gen = rs_generator_poly(nsym)
    feedback = list(data) + [0] * nsym

    for i in range(len(data)):
        if feedback[i] != 0:
            for j in range(1, len(gen)):
                feedback[i + j] ^= gf_mul(gen[j], feedback[i])

    return list(data) + feedback[len(data):]


def rs_check(codeword: list[int] | bytes, nsym: int = 4) -> bool:
    """Check if a Reed-Solomon codeword is valid (no errors).

    Args:
        codeword: Full codeword (data + parity)
        nsym: Number of parity symbols

    Returns:
        True if codeword is valid (all syndromes are zero)
    """
    syndromes = []
    for i in range(nsym):
        s = 0
        for c in codeword:
            s = gf_mul(s, GF_EXP[i]) ^ c
        syndromes.append(s)
    return all(s == 0 for s in syndromes)


# ── CRC-16 (v0.3) ────────────────────────────────────────────

def crc16(data: list[int] | bytes, poly: int = 0x8005, init: int = 0xFFFF) -> int:
    """Compute CRC-16 over data bytes.

    Uses bit-by-bit computation (no table needed — portable).

    Args:
        data: Input data bytes
        poly: CRC polynomial (default: CRC-16/ARC 0x8005)
        init: Initial CRC value

    Returns:
        16-bit CRC value
    """
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def crc16_bytes(data: list[int] | bytes, poly: int = 0x8005, init: int = 0xFFFF) -> list[int]:
    """Compute CRC-16 and return as 2-byte list [high, low].

    Args:
        data: Input data bytes
        poly: CRC polynomial
        init: Initial CRC value

    Returns:
        [crc_high, crc_low] — 2 bytes
    """
    c = crc16(data, poly, init)
    return [(c >> 8) & 0xFF, c & 0xFF]


def crc16_check(data: list[int] | bytes, expected_crc: list[int] | bytes,
                poly: int = 0x8005, init: int = 0xFFFF) -> bool:
    """Verify CRC-16 of data against expected value.

    Args:
        data: Input data bytes (without CRC)
        expected_crc: Expected [crc_high, crc_low]
        poly: CRC polynomial
        init: Initial CRC value

    Returns:
        True if CRC matches
    """
    computed = crc16(data, poly, init)
    expected = (expected_crc[0] << 8) | expected_crc[1]
    return computed == expected

