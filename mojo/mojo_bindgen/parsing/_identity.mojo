"""Stable source identity hashing; independent of process-randomized hashes."""
from std.collections.string import chr


def _rotr(x: UInt32, n: Int) -> UInt32:
    return (x >> UInt32(n)) | (x << UInt32(32 - n))


def sha256_prefix(text: String) -> String:
    var data = List[UInt8]()
    for b in text.as_bytes():
        data.append(b)
    var bits = UInt64(len(data)) * 8
    data.append(128)
    while len(data) % 64 != 56:
        data.append(0)
    for i in range(8):
        data.append(UInt8(bits >> UInt64(56 - i * 8)))
    var h: List[UInt32] = [
        0x6A09E667,
        0xBB67AE85,
        0x3C6EF372,
        0xA54FF53A,
        0x510E527F,
        0x9B05688C,
        0x1F83D9AB,
        0x5BE0CD19,
    ]
    var k: List[UInt32] = [
        0x428A2F98,
        0x71374491,
        0xB5C0FBCF,
        0xE9B5DBA5,
        0x3956C25B,
        0x59F111F1,
        0x923F82A4,
        0xAB1C5ED5,
        0xD807AA98,
        0x12835B01,
        0x243185BE,
        0x550C7DC3,
        0x72BE5D74,
        0x80DEB1FE,
        0x9BDC06A7,
        0xC19BF174,
        0xE49B69C1,
        0xEFBE4786,
        0x0FC19DC6,
        0x240CA1CC,
        0x2DE92C6F,
        0x4A7484AA,
        0x5CB0A9DC,
        0x76F988DA,
        0x983E5152,
        0xA831C66D,
        0xB00327C8,
        0xBF597FC7,
        0xC6E00BF3,
        0xD5A79147,
        0x06CA6351,
        0x14292967,
        0x27B70A85,
        0x2E1B2138,
        0x4D2C6DFC,
        0x53380D13,
        0x650A7354,
        0x766A0ABB,
        0x81C2C92E,
        0x92722C85,
        0xA2BFE8A1,
        0xA81A664B,
        0xC24B8B70,
        0xC76C51A3,
        0xD192E819,
        0xD6990624,
        0xF40E3585,
        0x106AA070,
        0x19A4C116,
        0x1E376C08,
        0x2748774C,
        0x34B0BCB5,
        0x391C0CB3,
        0x4ED8AA4A,
        0x5B9CCA4F,
        0x682E6FF3,
        0x748F82EE,
        0x78A5636F,
        0x84C87814,
        0x8CC70208,
        0x90BEFFFA,
        0xA4506CEB,
        0xBEF9A3F7,
        0xC67178F2,
    ]
    for start in range(0, len(data), 64):
        var w = List[UInt32]()
        for i in range(16):
            var offset = start + i * 4
            w.append(
                (UInt32(data[offset]) << 24)
                | (UInt32(data[offset + 1]) << 16)
                | (UInt32(data[offset + 2]) << 8)
                | UInt32(data[offset + 3])
            )
        for i in range(16, 64):
            var a = w[i - 15]
            var b = w[i - 2]
            w.append(
                w[i - 16]
                + (_rotr(a, 7) ^ _rotr(a, 18) ^ (a >> 3))
                + w[i - 7]
                + (_rotr(b, 17) ^ _rotr(b, 19) ^ (b >> 10))
            )
        var a = h[0]
        var b = h[1]
        var c = h[2]
        var d = h[3]
        var e = h[4]
        var f = h[5]
        var g = h[6]
        var v = h[7]
        for i in range(64):
            var t1 = (
                v
                + (_rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25))
                + ((e & f) ^ ((~e) & g))
                + k[i]
                + w[i]
            )
            var t2 = (_rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))
            v = g
            g = f
            f = e
            e = d + t1
            d = c
            c = b
            b = a
            a = t1 + t2
        h[0] += a
        h[1] += b
        h[2] += c
        h[3] += d
        h[4] += e
        h[5] += f
        h[6] += g
        h[7] += v
    var result = String()
    comptime hex_digits = "0123456789abcdef"
    for i in range(2):
        for j in range(8):
            result += String(hex_digits[byte=Int((h[i] >> UInt32(28 - j * 4)) & 15)])
    return result^
