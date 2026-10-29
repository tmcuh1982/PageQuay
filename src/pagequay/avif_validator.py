"""Enveloppe ISO-BMFF d’un AVIF statique ; aucun décodage ni accès réseau."""


def avif_signature(data: bytes) -> bool:
    offset = 0
    boxes = 0
    kinds = set()
    while offset < len(data):
        boxes += 1
        if boxes > 10000 or len(data) - offset < 8:
            return False
        size = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        header = 8
        if size == 1:
            if len(data) - offset < 16:
                return False
            size = int.from_bytes(data[offset + 8 : offset + 16], "big")
            header = 16
        elif size == 0:
            size = len(data) - offset
        if size < header or size > len(data) - offset:
            return False
        if offset == 0:
            payload = data[header:size]
            if kind != b"ftyp" or len(payload) < 8 or len(payload) % 4:
                return False
            brands = {payload[:4], *(payload[i : i + 4] for i in range(8, len(payload), 4))}
            if b"avif" not in brands or b"avis" in brands:
                return False
        kinds.add(kind)
        offset += size
    return {b"ftyp", b"meta", b"mdat"} <= kinds
