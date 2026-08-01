"""d3-style circle packing: front-chain sibling placement + iterative enclosure."""
import math


class C:
    __slots__ = ("x", "y", "r", "payload")

    def __init__(self, r, payload=None):
        self.x = self.y = 0.0
        self.r = r
        self.payload = payload


class _Node:
    __slots__ = ("c", "next", "previous")

    def __init__(self, c):
        self.c = c
        self.next = self.previous = None


def _place(a, b, c):
    dx, dy = b.x - a.x, b.y - a.y
    d2 = dx * dx + dy * dy
    if d2:
        a2 = (a.r + c.r) ** 2
        b2 = (b.r + c.r) ** 2
        if a2 > b2:
            x = (d2 + b2 - a2) / (2 * d2)
            y = math.sqrt(max(0.0, b2 / d2 - x * x))
            c.x = b.x - x * dx - y * dy
            c.y = b.y - x * dy + y * dx
        else:
            x = (d2 + a2 - b2) / (2 * d2)
            y = math.sqrt(max(0.0, a2 / d2 - x * x))
            c.x = a.x + x * dx - y * dy
            c.y = a.y + x * dy + y * dx
    else:
        c.x = a.x + a.r + c.r
        c.y = a.y


def _intersects(a, b):
    dr = a.r + b.r - 1e-6
    if dr <= 0:
        return False
    dx, dy = b.x - a.x, b.y - a.y
    return dr * dr > dx * dx + dy * dy


def pack_siblings(circles):
    """Position circles (in given order) mutually tangent without overlap."""
    n = len(circles)
    if n == 0:
        return
    a = circles[0]
    a.x = a.y = 0.0
    if n == 1:
        return
    b = circles[1]
    a.x = -b.r
    b.x = a.r
    b.y = 0.0
    if n == 2:
        return
    c = circles[2]
    _place(b, a, c)
    na, nb, nc = _Node(a), _Node(b), _Node(c)
    na.next = nc.previous = nb
    nb.next = na.previous = nc
    nc.next = nb.previous = na
    a, b = na, nb
    i = 3
    while i < n:
        cc = circles[i]
        _place(a.c, b.c, cc)
        nc = _Node(cc)
        j, k = b.next, a.previous
        sj, sk = b.c.r, a.c.r
        retry = False
        while True:
            if sj <= sk:
                if _intersects(j.c, cc):
                    b = j
                    a.next = b
                    b.previous = a
                    retry = True
                    break
                sj += j.c.r
                j = j.next
            else:
                if _intersects(k.c, cc):
                    a = k
                    a.next = b
                    b.previous = a
                    retry = True
                    break
                sk += k.c.r
                k = k.previous
            if j is k.next:
                break
        if retry:
            continue
        nc.previous = a
        nc.next = b
        a.next = b.previous = nc
        b = nc

        def score(nd):
            mx = (nd.c.x + nd.next.c.x) / 2
            my = (nd.c.y + nd.next.c.y) / 2
            return mx * mx + my * my

        best, best_s = a, score(a)
        cur = a.next
        while cur is not b:
            s = score(cur)
            if s < best_s:
                best, best_s = cur, s
            cur = cur.next
        a = best
        b = a.next
        i += 1


def enclose(circles):
    """Approximate smallest enclosing circle of circles: (cx, cy, R)."""
    if not circles:
        return 0.0, 0.0, 0.0
    if len(circles) == 1:
        c = circles[0]
        return c.x, c.y, c.r
    tw = sum(c.r for c in circles)
    cx = sum(c.x * c.r for c in circles) / tw
    cy = sum(c.y * c.r for c in circles) / tw
    for it in range(1, 160):
        far = max(circles, key=lambda c: math.hypot(c.x - cx, c.y - cy) + c.r)
        k = 0.5 / it
        cx += (far.x - cx) * k
        cy += (far.y - cy) * k
    R = max(math.hypot(c.x - cx, c.y - cy) + c.r for c in circles)
    return cx, cy, R


def max_overlap(circles):
    worst = 0.0
    for i, a in enumerate(circles):
        for b in circles[i + 1:]:
            pen = a.r + b.r - math.hypot(a.x - b.x, a.y - b.y)
            if pen > worst:
                worst = pen
    return worst
