"""Tests for GF(2^8) arithmetic and Reed-Solomon encoding."""

import pytest

from mixi_cut.gf256 import (
    GF_EXP,
    GF_LOG,
    gf_inverse,
    gf_mul,
    gf_pow,
    rs_check,
    rs_encode,
    rs_generator_poly,
)


class TestGFArithmetic:
    """GF(2^8) multiplication, power, inverse."""

    def test_mul_identity(self):
        """a * 1 = a for all a."""
        for a in range(256):
            assert gf_mul(a, 1) == a

    def test_mul_zero(self):
        """a * 0 = 0 for all a."""
        for a in range(256):
            assert gf_mul(a, 0) == 0
            assert gf_mul(0, a) == 0

    def test_mul_commutative(self):
        """a * b = b * a."""
        for a in range(1, 50):
            for b in range(1, 50):
                assert gf_mul(a, b) == gf_mul(b, a)

    def test_mul_associative(self):
        """(a * b) * c = a * (b * c)."""
        for a in [1, 2, 17, 128, 255]:
            for b in [1, 3, 42, 200]:
                for c in [1, 7, 100, 254]:
                    assert gf_mul(gf_mul(a, b), c) == gf_mul(a, gf_mul(b, c))

    def test_pow_zero(self):
        """a^0 = 1 for all a != 0."""
        for a in range(1, 256):
            assert gf_pow(a, 0) == 1

    def test_pow_one(self):
        """a^1 = a for all a."""
        for a in range(256):
            assert gf_pow(a, 1) == a

    def test_pow_consistency(self):
        """a^n = a * a^(n-1)."""
        for a in [2, 3, 17, 128]:
            for n in range(2, 10):
                assert gf_pow(a, n) == gf_mul(a, gf_pow(a, n - 1))

    def test_inverse(self):
        """a * a^(-1) = 1 for all a != 0."""
        for a in range(1, 256):
            assert gf_mul(a, gf_inverse(a)) == 1

    def test_inverse_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            gf_inverse(0)

    def test_exp_log_roundtrip(self):
        """exp(log(a)) = a for all a != 0."""
        for a in range(1, 256):
            assert GF_EXP[GF_LOG[a]] == a

    def test_exp_table_period(self):
        """exp table is periodic with period 255."""
        for i in range(255):
            assert GF_EXP[i] == GF_EXP[i + 255]


class TestReedSolomon:
    """Reed-Solomon encoding and validation."""

    def test_encode_length(self):
        """Output length = input + nsym."""
        for n_data in [1, 3, 5, 10]:
            for nsym in [2, 4, 6]:
                data = list(range(n_data))
                result = rs_encode(data, nsym)
                assert len(result) == n_data + nsym

    def test_encode_preserves_data(self):
        """First bytes of output are the original data."""
        data = [0x12, 0x34, 0x56]
        result = rs_encode(data, nsym=4)
        assert result[:3] == data

    def test_encode_check_valid(self):
        """Encoded codeword passes rs_check."""
        data = [0x00, 0x01, 0x5E]
        codeword = rs_encode(data, nsym=4)
        assert rs_check(codeword, nsym=4)

    def test_check_detects_single_error(self):
        """rs_check detects a single-byte error."""
        data = [0x00, 0x01, 0x5E]
        codeword = rs_encode(data, nsym=4)
        # Corrupt one byte
        codeword[2] ^= 0xFF
        assert not rs_check(codeword, nsym=4)

    def test_check_detects_parity_error(self):
        """rs_check detects corruption in parity bytes."""
        data = [0xAB, 0xCD, 0xEF]
        codeword = rs_encode(data, nsym=4)
        codeword[-1] ^= 0x01
        assert not rs_check(codeword, nsym=4)

    def test_encode_all_zeros(self):
        """All-zeros data produces all-zeros codeword."""
        data = [0, 0, 0]
        codeword = rs_encode(data, nsym=4)
        assert all(b == 0 for b in codeword)

    def test_encode_deterministic(self):
        """Same input produces same output."""
        data = [0x12, 0x34, 0x56]
        r1 = rs_encode(data, nsym=4)
        r2 = rs_encode(data, nsym=4)
        assert r1 == r2

    def test_different_data_different_parity(self):
        """Different data produces different parity."""
        d1 = [0x00, 0x00, 0x01]
        d2 = [0x00, 0x00, 0x02]
        r1 = rs_encode(d1, nsym=4)
        r2 = rs_encode(d2, nsym=4)
        assert r1[3:] != r2[3:]

    def test_generator_poly_degree(self):
        """Generator polynomial has degree nsym."""
        for nsym in [2, 4, 6, 8]:
            gen = rs_generator_poly(nsym)
            assert len(gen) == nsym + 1
            assert gen[0] == 1  # monic

    def test_large_nsym(self):
        """Works with larger parity sizes."""
        data = [0x42]
        codeword = rs_encode(data, nsym=8)
        assert rs_check(codeword, nsym=8)
        codeword[0] ^= 0x01
        assert not rs_check(codeword, nsym=8)
