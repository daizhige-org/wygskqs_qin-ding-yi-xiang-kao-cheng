#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright © 2026 Xi Shi Du Liu Studio LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""把掃描圖版的欄線與文字分開，各上各的色 —— 朱欄墨書。

  python3 tools/colorize_plates.py colorize img      # 就地上色（一次性，結果入庫）
  python3 tools/colorize_plates.py restore  img      # 還原成原本的黑白

原書是朱欄墨書，但電子版的掃描件把欄線和字都印成了黑的。不處理的話，彩色
模板只管得到引擎畫的最外圈版框，框內整片黑 —— 純排版葉是滿版朱欄，圖版葉
只有外緣一圈紅邊，兩者對不上。

## 怎麼分的

原掃描件是純 1-bit（只有 0 和 255，無反鋸齒），所以形態學處理乾淨：

  欄線 = 以長條結構元素對墨跡做開運算（橫、豎各一次）。結構元素長取邊長
         的 1/25（約 67px），而單字筆畫最長約 40px，「一」「三」這類橫畫
         夠不到門檻，不會被誤判
  接線 = 再沿各自方向做閉運算，把被字壓斷的線接回來，並與原墨跡取交集，
         保證不憑空生出墨
  文字 = 墨跡減去欄線

品質自檢：對「判為文字」那層再跑一次分離，殘留長直線應為 0 px。

## 可逆

輸出是 3 色調色盤 PNG（紙 244,241,225／朱 180,95,75／墨 35,25,20）。
`restore` 把朱與墨映回黑、紙映回白，即得與原掃描件逐像素相同的 1-bit 圖 ——
分類只是把資訊分了層，沒有丟掉任何東西。

## 為什麼不用「白轉透明」

PDF 沒有調色盤透明，LuaTeX 得為每張圖生成 SMask 軟遮罩，實測全書編譯
23 秒變 11 分鐘、PDF 38 MB 漲到 110 MB，而且只解決底色、解決不了欄線。
三色圖把紙色直接畫進圖裡，代價只有編譯 23→151 秒、PDF 38→44 MB。

已知瑕疵：版心的魚尾是實心塊不是線，開運算取不到，仍歸為文字（黑）。
"""
import argparse, os, sys, glob
import multiprocessing as mp

PAPER = (244, 241, 225)
RULE  = (180,  95,  75)
INK   = ( 35,  25,  20)
BW    = [255, 255, 255, 0, 0, 0, 0, 0, 0]          # 紙白、欄線黑、文字黑
COLOR = list(PAPER) + list(RULE) + list(INK)


def separate(ink, long_frac=25, mend=15):
    """墨跡布林陣列 → (欄線, 文字)。"""
    import numpy as np
    from scipy import ndimage as ndi
    H, W = ink.shape
    h = ndi.binary_opening(ink, structure=np.ones((1, max(30, W // long_frac))))
    v = ndi.binary_opening(ink, structure=np.ones((max(30, H // long_frac), 1)))
    rules = h | v
    rules = ndi.binary_closing(rules, structure=np.ones((1, mend)))
    rules = ndi.binary_closing(rules, structure=np.ones((mend, 1)))
    rules &= ink                      # 只在原本有墨處成立
    return rules, ink & ~rules


def _colorize(job):
    src, long_frac, mend = job
    import numpy as np
    from PIL import Image
    im = Image.open(src)
    if im.mode == 'P' and (im.getpalette() or [])[:9] == COLOR:
        return src, 'already'
    if im.mode != '1':
        return src, 'skip:mode=%s' % im.mode
    ink = ~np.array(im)
    rules, text = separate(ink, long_frac, mend)
    idx = np.zeros(ink.shape, dtype='uint8')
    idx[rules] = 1
    idx[text] = 2
    out = Image.fromarray(idx, mode='P')
    out.putpalette(COLOR)
    out.save(src, bits=2, optimize=True)
    return src, '%.1f%%' % (100 * rules.sum() / ink.sum() if ink.any() else 0)


def _restore(job):
    """三色圖 → 原本的 1-bit 黑白，逐像素相同。"""
    src, = job
    import numpy as np
    from PIL import Image
    im = Image.open(src)
    if im.mode == '1':
        return src, 'already'
    if im.mode != 'P' or (im.getpalette() or [])[:9] != COLOR:
        return src, 'skip:非本工具產生的三色圖'
    idx = np.array(im)
    Image.fromarray(idx == 0).save(src, optimize=True)   # 紙=白，朱與墨都=黑
    return src, 'ok'


def run(fn, jobs, jn):
    ok = bad = 0
    with mp.Pool(jn) as p:
        for src, info in p.imap_unordered(fn, jobs, chunksize=4):
            if info.startswith('skip'):
                bad += 1
                print('跳過 %s（%s）' % (src, info), file=sys.stderr)
            else:
                ok += 1
    return ok, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    c = sub.add_parser('colorize', help='就地把圖版分成朱欄與墨字（結果入庫）')
    c.add_argument('src_dir')
    c.add_argument('--long-frac', type=int, default=25,
                   help='結構元素長 = 邊長 / 此值（越小越嚴，越不容易誤判筆畫）')
    c.add_argument('--mend', type=int, default=15, help='接回斷線的閉運算長度（px）')

    r = sub.add_parser('restore', help='還原成原本的黑白 1-bit 圖')
    r.add_argument('src_dir')

    for p in (c, r):
        p.add_argument('-j', '--jobs', type=int, default=os.cpu_count())
        p.add_argument('--only', nargs='*', help='只處理這些檔名（除錯用）')
    a = ap.parse_args()

    srcs = sorted(glob.glob(os.path.join(a.src_dir, '*.png')))
    if a.only:
        keep = set(a.only)
        srcs = [s for s in srcs if os.path.basename(s) in keep]
    if not srcs:
        raise SystemExit('%s 裡沒有 PNG' % a.src_dir)

    before = sum(os.path.getsize(s) for s in srcs)
    if a.cmd == 'colorize':
        ok, bad = run(_colorize, [(s, a.long_frac, a.mend) for s in srcs], a.jobs)
        verb = '上色'
    else:
        ok, bad = run(_restore, [(s,) for s in srcs], a.jobs)
        verb = '還原'
    after = sum(os.path.getsize(s) for s in srcs)
    print('%s %d 張，跳過 %d；%.1f MB → %.1f MB'
          % (verb, ok, bad, before / 1e6, after / 1e6), file=sys.stderr)


if __name__ == '__main__':
    main()
