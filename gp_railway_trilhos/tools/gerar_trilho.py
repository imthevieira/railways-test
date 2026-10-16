#!/usr/bin/env python3
"""
Gera os arquivos de trilho (.dat + traintracks.xml) do RDR2 a partir das
posições das peças de trilho do mapa G.P. Railway.

Uso (a partir da pasta do resource):

    python -I tools/gerar_trilho.py <gprailway.xml do objectloader> data

O que faz:
  1. lê os objetos `p_cs_railroadtrack01x` / `p_railroadtrack_single01x`;
  2. funde peças sobrepostas (duplicatas e trilhos simples em par) e liga cada
     peça às vizinhas (~5 m), formando uma linha de ponta a ponta;
  3. reamostra a linha central em nós a cada `--step` peças, calcula as
     alças de Bézier e as distâncias, e grava os `.dat`.

Formato do .dat (RDR2):
    <total_pontos> <pontos_com_curva> <open|close>
    c x y z  hax hay haz  hbx hby hbz  dist flag [nome]
    x y z  dist flag [nome]
"""
import argparse
import collections
import math
import os
import sys
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def joaat(text):
    h = 0
    for c in text.lower().encode('ascii'):
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


def signed(h):
    return h - (1 << 32) if h >= (1 << 31) else h


TRACK_HASHES = {signed(joaat('p_cs_railroadtrack01x')), signed(joaat('p_railroadtrack_single01x'))}


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def norm(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def unit(a):
    n = norm(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-9 else (0.0, 0.0, 0.0)


def load_pieces(path, merge_dist=2.5):
    """Lê as peças e funde as que estão a menos de `merge_dist` m (duplicatas e
    pares de trilhos simples lado a lado) no centróide do grupo."""
    root = ET.parse(path).getroot()
    pts = []
    for o in root.iter('Object'):
        if int(o.get('Hash')) in TRACK_HASHES:
            pts.append((float(o.get('Position_x')), float(o.get('Position_y')), float(o.get('Position_z'))))
    parent = list(range(len(pts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if norm(sub(pts[i], pts[j])) < merge_dist:
                parent[find(i)] = find(j)
    groups = collections.defaultdict(list)
    for i, p in enumerate(pts):
        groups[find(i)].append(p)
    merged = []
    for g in groups.values():
        n = len(g)
        merged.append((sum(p[0] for p in g) / n, sum(p[1] for p in g) / n, sum(p[2] for p in g) / n))
    return len(pts), merged

def build_graph(pts, link=6.5):
    adj = collections.defaultdict(set)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if norm(sub(pts[i], pts[j])) <= link:
                adj[i].add(j)
                adj[j].add(i)
    return adj


def smooth(points, closed):
    n = len(points)
    out = []
    for i in range(n):
        if not closed and (i == 0 or i == n - 1):
            out.append(points[i])
            continue
        a, b, c = points[(i - 1) % n], points[i], points[(i + 1) % n]
        out.append(((a[0] + 2 * b[0] + c[0]) / 4, (a[1] + 2 * b[1] + c[1]) / 4, (a[2] + 2 * b[2] + c[2]) / 4))
    return out


def resample(points, step, closed, keep_last=True):
    n = len(points)
    if closed:
        count = max(3, round(n / step))
        idx = sorted({int(k * n / count) for k in range(count)})
    else:
        count = max(1, round((n - 1) / step))
        idx = sorted({int(round(k * (n - 1) / count)) for k in range(count + 1)})
        if keep_last and idx[-1] != n - 1:
            idx.append(n - 1)
    return [points[i] for i in idx]


def _mod2pi(a):
    return a - 2 * math.pi * math.floor(a / (2 * math.pi))


def connector(p_from, t_from, p_to, t_to, radius, spacing):
    """Nós intermediários de um caminho de Dubins (arco, reta, arco) com raio
    mínimo `radius`, que sai de `p_from` na direção `t_from` e chega em `p_to`
    na direção `t_to`. Extremos excluídos. O Z varia linearmente."""
    x0, y0 = p_from[0], p_from[1]
    th0 = math.atan2(t_from[1], t_from[0])
    th1 = math.atan2(t_to[1], t_to[0])
    dx, dy = (p_to[0] - x0) / radius, (p_to[1] - y0) / radius
    d = math.hypot(dx, dy)
    theta = math.atan2(dy, dx)
    al, be = _mod2pi(th0 - theta), _mod2pi(th1 - theta)
    sa, ca, sb, cb = math.sin(al), math.cos(al), math.sin(be), math.cos(be)
    c_ab = math.cos(al - be)
    options = []

    p_sq = 2 + d * d - 2 * c_ab + 2 * d * (sa - sb)
    if p_sq >= 0:
        tmp = math.atan2(cb - ca, d + sa - sb)
        options.append(('LSL', _mod2pi(-al + tmp), math.sqrt(p_sq), _mod2pi(be - tmp)))
    p_sq = 2 + d * d - 2 * c_ab + 2 * d * (sb - sa)
    if p_sq >= 0:
        tmp = math.atan2(ca - cb, d - sa + sb)
        options.append(('RSR', _mod2pi(al - tmp), math.sqrt(p_sq), _mod2pi(-be + tmp)))
    p_sq = -2 + d * d + 2 * c_ab + 2 * d * (sa + sb)
    if p_sq >= 0:
        p = math.sqrt(p_sq)
        tmp = math.atan2(-ca - cb, d + sa + sb) - math.atan2(-2.0, p)
        options.append(('LSR', _mod2pi(-al + tmp), p, _mod2pi(-_mod2pi(be) + tmp)))
    p_sq = -2 + d * d + 2 * c_ab - 2 * d * (sa + sb)
    if p_sq >= 0:
        p = math.sqrt(p_sq)
        tmp = math.atan2(ca + cb, d - sa - sb) - math.atan2(2.0, p)
        options.append(('RSL', _mod2pi(al - tmp), p, _mod2pi(be - tmp)))
    if not options:
        sys.exit('não há conector possível com esse raio; reduza --radius')

    word, t, p, q = min(options, key=lambda o: o[1] + o[2] + o[3])
    total = (t + p + q) * radius
    segs = list(zip(word, (t, p, q)))

    # percorre o caminho em passos curtos (coordenadas normalizadas pelo raio)
    pts = [(0.0, 0.0, th0)]
    x = y = 0.0
    th = th0
    step_n = 0.01
    for kind, length in segs:
        done = 0.0
        while done < length - 1e-12:
            u = min(step_n, length - done)
            if kind == 'L':
                x += math.sin(th + u) - math.sin(th)
                y += -math.cos(th + u) + math.cos(th)
                th += u
            elif kind == 'R':
                x += -math.sin(th - u) + math.sin(th)
                y += math.cos(th - u) - math.cos(th)
                th -= u
            else:
                x += math.cos(th) * u
                y += math.sin(th) * u
            done += u
            pts.append((x, y, th))
    end_err = math.hypot(x0 + x * radius - p_to[0], y0 + y * radius - p_to[1])
    head_err = abs(math.degrees(math.atan2(math.sin(th - th1), math.cos(th - th1))))
    print(f'conector Dubins {word}: {total:.0f} m, raio {radius:.0f} m | erro de chegada {end_err:.2f} m, {head_err:.2f}°')

    count = max(2, round(total / spacing))
    out = []
    n = len(pts)
    for k in range(1, count):
        frac = k / count
        i = min(n - 1, int(round(frac * (n - 1))))
        z = p_from[2] + (p_to[2] - p_from[2]) * frac
        out.append((x0 + pts[i][0] * radius, y0 + pts[i][1] * radius, z))
    return out

def bezier_len(p0, h0, h1, p1, samples=24):
    total, prev = 0.0, p0
    for k in range(1, samples + 1):
        t = k / samples
        u = 1 - t
        cur = tuple(u * u * u * p0[i] + 3 * u * u * t * h0[i] + 3 * u * t * t * h1[i] + t * t * t * p1[i] for i in range(3))
        total += norm(sub(cur, prev))
        prev = cur
    return total


def build_nodes(pts, closed):
    n = len(pts)
    seg = []
    for i in range(n if closed else n - 1):
        seg.append(norm(sub(pts[(i + 1) % n], pts[i])))
    nodes = []
    for i in range(n):
        p = pts[i]
        if closed:
            prv, nxt = pts[(i - 1) % n], pts[(i + 1) % n]
            dprev, dnext = seg[(i - 1) % n], seg[i]
        else:
            prv = pts[i - 1] if i > 0 else None
            nxt = pts[i + 1] if i < n - 1 else None
            dprev = seg[i - 1] if i > 0 else None
            dnext = seg[i] if i < n - 1 else None
        if prv is None:
            t = unit(sub(nxt, p))
            ha, hb = p, add(p, mul(t, dnext / 3))
        elif nxt is None:
            t = unit(sub(p, prv))
            ha, hb = sub(p, mul(t, dprev / 3)), p
        else:
            t = unit(sub(nxt, prv))
            hl = (dprev + dnext) / 2 / 3
            ha, hb = sub(p, mul(t, hl)), add(p, mul(t, hl))
        nodes.append(dict(p=p, ha=ha, hb=hb))
    for i in range(n):
        if closed or i < n - 1:
            j = (i + 1) % n
            nodes[i]['dist'] = bezier_len(nodes[i]['p'], nodes[i]['hb'], nodes[j]['ha'], nodes[j]['p'])
        else:
            nodes[i]['dist'] = 0.0
    return nodes


def fmt(v):
    s = '{:.6g}'.format(v)
    return '0' if s in ('-0', '-0.0') else s


def write_dat(path, nodes, closed, flags=None):
    flags = flags or {}
    n = len(nodes)
    lines = []
    curve_points = 0
    for i, nd in enumerate(nodes):
        flag, name = flags.get(i, (0, None))
        tail = f' {flag}' + (f' {name}' if name else '')
        plain = (not closed) and i == n - 1
        if plain:
            lines.append(f'{fmt(nd["p"][0])} {fmt(nd["p"][1])} {fmt(nd["p"][2])} {fmt(nd["dist"])}{tail}')
        else:
            curve_points += 1
            vals = nd['p'] + nd['ha'] + nd['hb']
            lines.append('c ' + ' '.join(fmt(v) for v in vals) + f' {fmt(nd["dist"])}{tail}')
    header = f'{n} {curve_points} {"close" if closed else "open"}'
    with open(path, 'w', encoding='ascii', newline='\n') as f:
        f.write(header + '\n' + '\n'.join(lines) + '\n')
    return header


def max_deviation(originals, nodes, closed):
    """Maior distância de uma peça original até a curva gerada."""
    curve = []
    n = len(nodes)
    for i in range(n if closed else n - 1):
        a, b = nodes[i], nodes[(i + 1) % n]
        for k in range(0, 41):
            t = k / 40
            u = 1 - t
            curve.append(tuple(u ** 3 * a['p'][c] + 3 * u * u * t * a['hb'][c] + 3 * u * t * t * b['ha'][c] + t ** 3 * b['p'][c] for c in range(3)))
    worst = 0.0
    for o in originals:
        worst = max(worst, min(norm(sub(o, c)) for c in curve))
    return worst


def turn_stats(nodes, closed):
    n = len(nodes)
    worst, radius = 0.0, 1e9
    for i in range(n if closed else n - 2):
        a, b, c = nodes[i]['p'], nodes[(i + 1) % n]['p'], nodes[(i + 2) % n]['p']
        v1, v2 = unit(sub(b, a)), unit(sub(c, b))
        ang = math.acos(max(-1, min(1, sum(v1[k] * v2[k] for k in range(3)))))
        worst = max(worst, math.degrees(ang))
        chord = norm(sub(c, a))
        if ang > 1e-3:
            radius = min(radius, chord / (2 * math.sin(ang)))
    return worst, radius


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xml')
    ap.add_argument('out')
    ap.add_argument('--step', type=int, default=2, help='peças por nó (padrão: 2 = ~10 m)')
    ap.add_argument('--res', default='gp_railway_trilhos', help='nome do resource (sem hífens)')
    ap.add_argument('--name', default='gp_railway', help='nome da via (trainConfigName e arquivo .dat)')
    ap.add_argument('--z-offset', type=float, default=0.0, help='soma ao Z de todos os nós (metros)')
    ap.add_argument('--close', action='store_true',
                    help='fecha a via em laço com um conector suave entre as duas pontas (trecho SEM trilho visível)')
    ap.add_argument('--radius', type=float, default=60.0, help='raio mínimo (m) das curvas do conector')
    a = ap.parse_args()

    total, pts = load_pieces(a.xml)
    print(f'peças de trilho: {total} (pontos após fusão: {len(pts)})')
    adj = build_graph(pts)
    deg = collections.Counter(len(adj[i]) for i in range(len(pts)))
    print('graus do grafo:', dict(deg))
    ends = [i for i in range(len(pts)) if len(adj[i]) == 1]
    if len(ends) != 2 or set(deg) - {1, 2}:
        sys.exit('topologia inesperada: o gerador espera uma linha simples com 2 pontas')

    order = [ends[0]]
    last, cur = None, ends[0]
    while True:
        nxt = [n for n in adj[cur] if n != last]
        if not nxt:
            break
        last, cur = cur, nxt[0]
        order.append(cur)
    if len(order) != len(pts):
        sys.exit(f'a linha não cobre todas as peças ({len(order)} de {len(pts)})')
    print('pontas: ({:.1f}, {:.1f}, {:.1f}) e ({:.1f}, {:.1f}, {:.1f})'.format(*pts[order[0]], *pts[order[-1]]))

    os.makedirs(a.out, exist_ok=True)
    closed = a.close
    raw = [(pts[i][0], pts[i][1], pts[i][2] + a.z_offset) for i in order]
    sm = smooth(raw, False)
    samp = resample(sm, a.step, False)
    if closed:
        # tangentes de saída (na ponta B) e de chegada (na ponta A), na direção de marcha
        t_b = unit(sub(sm[-1], sm[-5]))
        t_a = unit(sub(sm[4], sm[0]))
        bridge = connector(sm[-1], t_b, sm[0], t_a, a.radius, a.step * 5.0)
        print(f'conector: {len(bridge)} nós (pontas a {norm(sub(sm[-1], sm[0])):.0f} m em linha reta)')
        samp = samp + bridge
    nodes = build_nodes(samp, closed)
    header = write_dat(os.path.join(a.out, a.name + '.dat'), nodes, closed)
    dev = max_deviation(raw, nodes, closed)
    turn, rad = turn_stats(nodes, closed)
    length = sum(nd['dist'] for nd in nodes)
    zs = [nd['p'][2] for nd in nodes]
    print(f'{a.name}.dat: cabeçalho "{header}" | comprimento {length:.0f} m | desvio máx. das peças {dev:.2f} m | '
          f'curva máx. por nó {turn:.1f}° | raio mín. ~{rad:.0f} m | Z {min(zs):.1f}..{max(zs):.1f}')

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<train_tracks>',
           f'\t<train_track filename="resources:/{a.res}/data/{a.name}.dat" trainConfigName="{a.name}" '
           f'stopsAtStations="false" brakingDist="10" />',
           '</train_tracks>']
    with open(os.path.join(a.out, 'traintracks.xml'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(xml) + '\n')
    print('traintracks.xml gravado')


if __name__ == '__main__':
    main()