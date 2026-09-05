#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright © 2026 Xi Shi Du Liu Studio LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# 与 wyg-sikuquanshu-decoder 的 tools/pdf_bookmarks.py 同源；该目录留一份副本，
# 是为了本目录能独立排出带书签的 PDF，不必取得那个（私有的）解码工具链。
"""给排好的 PDF 加书签（PDF 大纲）。

输入是 to_tex.py 生成的 .tex 排版时写出的 <jobname>-bookmarks.txt ——
每葉一行「绝对页码 | 卷名」，由 shipout 钩子逐葉记下。本工具取每个卷名
第一次出现的页作为该卷起始页，按出现顺序建一层大纲。

  python3 tools/pdf_bookmarks.py 某书.pdf 某书-bookmarks.txt -o 某书-bm.pdf

不给 -o 就原地改写。页面内容一字不动，只往 catalog 里写 /Outlines，
所以页数、字体、版面与原 PDF 完全一致。

为什么不用 hyperref：\pdfbookmark 的锚点会被 luatex-cn 的网格引擎当成内容，
实测《欽定儀象考成》整本从 875 葉变成 876 葉。书签不该改变版面，故后处理。

书签标题统一成「<书名><篇名>」，书名取各卷共有的那个：

  欽定儀象考成御製序   ← 原卷名是「御製儀象考成序」
  欽定儀象考成奏議
  欽定儀象考成卷一

即先剥掉各卷名自带的书名，再一律冠上共有的书名。序的书名作「御製…」而非
「欽定…」，剥掉后把「御製」二字留给篇名，于是成为「御製序」——「序」单独
一个字在书签栏里认不出是什么，冠上「御製」才对得上原书。

--short 只留篇名（序、奏議、卷一），--full-title 保留原卷名不动。

需要 pikepdf（pip install pikepdf）。
"""
import argparse, io, os, re, sys


def read_map(path):
    """<jobname>-bookmarks.txt → [(卷名, 起始页 1-based)]，按首次出现排序。"""
    first, order = {}, []
    for lineno, ln in enumerate(io.open(path, encoding='utf-8'), 1):
        ln = ln.strip()
        if not ln:
            continue
        page, sep, title = ln.partition('|')
        if not sep:
            raise SystemExit('%s:%d 不是「页码 | 卷名」：%r' % (path, lineno, ln))
        title = title.strip()
        if not title:                      # 卷名为空的葉（书前无 \chapter 的部分）
            continue
        page = int(page.strip())
        if title not in first:
            first[title] = page
            order.append(title)
    return [(t, first[t]) for t in order]


def strip_prefix(title, prefixes):
    """→ (剥掉的书名, 剩下的篇名)。没有匹配的前缀就原样返回。"""
    for p in prefixes:
        if title.startswith(p) and len(title) > len(p):
            return p, title[len(p):]
    return '', title


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf')
    ap.add_argument('bookmarks', help='<jobname>-bookmarks.txt')
    ap.add_argument('-o', '--out', default=None, help='默认原地改写')
    ap.add_argument('--full-title', action='store_true', help='书签保留原卷名不动')
    ap.add_argument('--short', action='store_true',
                    help='只留篇名（序、奏議、卷一），不冠书名')
    ap.add_argument('--strip', default='欽定,御製,钦定,御制',
                    help='要剥掉的书名前缀首字，逗号分隔；实际剥的是「<首字>…」整个书名')
    a = ap.parse_args()

    try:
        import pikepdf
    except ImportError:
        raise SystemExit('需要 pikepdf：pip install pikepdf')

    entries = read_map(a.bookmarks)
    if not entries:
        raise SystemExit('%s 里没有可用的卷名' % a.bookmarks)

    pdf = pikepdf.open(a.pdf, allow_overwriting_input=True)
    n = len(pdf.pages)
    bad = [(t, p) for t, p in entries if not 1 <= p <= n]
    if bad:
        raise SystemExit('页码越界（PDF 共 %d 葉）：%s' % (n, bad))

    # 书名前缀：多数卷名共有「欽定儀象考成」，但序作「御製儀象考成序」，
    # 全体的公共前缀会是空串。所以除了全体的公共前缀，再取「除首条外」的
    # 公共前缀当书名主体，把 --strip 里的各种首二字配上同一主体一并剥掉。
    heads = tuple(x for x in a.strip.split(',') if x)
    titles = [t for t, _ in entries]
    cands = set()
    if not a.full_title and len(titles) > 1:
        for cp in (os.path.commonprefix(titles), os.path.commonprefix(titles[1:])):
            if len(cp) >= 2 and cp.startswith(heads):
                cands.add(cp)
                if cp[2:]:
                    cands.update(h + cp[2:] for h in heads)
    prefixes = sorted(cands, key=len, reverse=True)

    # 共有的书名：取各卷剥下来的前缀里最常见的那个（序作「御製…」是少数）
    from collections import Counter
    stripped = [strip_prefix(t, prefixes) for t in titles]
    canon = ''
    if not a.full_title and not a.short:
        got = Counter(p for p, _ in stripped if p)
        if got:
            canon = got.most_common(1)[0][0]

    labels = []
    for (pre, rest), title in zip(stripped, titles):
        if a.full_title:
            labels.append(title)
            continue
        # 书名首二字与共有书名不同（「御製」vs「欽定」）时，把它留给篇名，
        # 否则「序」单独一个字在书签栏里认不出是什么
        if canon and pre and not canon.startswith(pre[:2]):
            rest = pre[:2] + rest
        labels.append(canon + rest)

    with pdf.open_outline() as ol:
        ol.root.clear()
        for label, (_, page) in zip(labels, entries):
            ol.root.append(pikepdf.OutlineItem(label, page - 1))

    out = a.out or a.pdf
    pdf.save(out)
    print('%s：%d 葉，写入 %d 条书签' % (out, n, len(entries)), file=sys.stderr)
    for label, (_, page) in zip(labels, entries):
        print('  p.%-5d %s' % (page, label), file=sys.stderr)


if __name__ == '__main__':
    main()
