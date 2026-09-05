#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright © 2026 Xi Shi Du Liu Studio LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""由黑白版 .tex 派生彩色版：朱欄墨字，四庫全書原本的樣子。

  python3 tools/make_colored.py 欽定儀象考成.tex -o 欽定儀象考成-彩色.tex

改兩處：文檔類選項換成 `四庫全書彩色`（luatex-cn 內建模板，框線
RGB(180,95,75)、文字 RGB(35,25,20)、底色 RGB(244,241,225)），再用
`\\pageSetup` 把底色改回白。

底色為什麼要改回白：本書 701/875 葉帶原書的掃描圖版，那些是白底黑線的
點陣圖，不隨模板著色。留著模板的米色底，圖版就成了一塊白斑貼在米色紙上，
邊緣有明顯接縫；改回白底則接得上。代價是失去紙色 —— 純排版的那 174 葉，
米色底其實更像原書。要那個效果就加 --paper-tint。

還剩一處無解：685 葉的嵌圖星表，紅色只到最外一圈 —— 引擎只畫最外圈版框
（變紅），框內所有欄線與文字都來自掃描圖版，一律是黑的。原書那些星表的
欄線本該同樣是朱欄，掃描件卻把欄線和字都印成了黑的；要還原得從掃描件裡
把欄線從筆畫中切出來單獨改色，那是圖像處理的活，不在排版層面。

（`\\pageSetup` 在導言區呼叫需要 luatex-cn ≥ open-guji/luatex-cn#166；在那
之前它會重開分頁，把 875 葉排成 1734 葉。）
"""
import argparse, io, re, sys

CLASS_RE = re.compile(r'(\\documentclass\[)(四库全书|四庫全書)(\]\{ltc-guji\})')
ANCHOR_RE = re.compile(r'^(\\夹注设置\{[^}]*\})$', re.M)
WHITE = r'\pageSetup{ background-color = {255, 255, 255} }'


def convert(src, paper_tint=False):
    out, n = CLASS_RE.subn(lambda m: m.group(1) + '四庫全書彩色' + m.group(3), src, count=1)
    if not n:
        raise SystemExit('找不到 \\documentclass[四库全书]{ltc-guji}')
    if paper_tint:
        return out
    out, n = ANCHOR_RE.subn(lambda m: m.group(1) + '\n' + WHITE, out, count=1)
    if not n:
        raise SystemExit('找不到插入 \\pageSetup 的錨點（\\夹注设置{...} 那一行）')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('tex')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--paper-tint', action='store_true',
                    help='保留模板的米色紙底（純排版葉更像原書，圖版葉會露白斑）')
    a = ap.parse_args()
    io.open(a.out, 'w', encoding='utf-8').write(
        convert(io.open(a.tex, encoding='utf-8').read(), a.paper_tint))
    print('%s → %s%s' % (a.tex, a.out, '（米色紙底）' if a.paper_tint else '（白底）'),
          file=sys.stderr)


if __name__ == '__main__':
    main()
