# 排版。整本：make；分冊（一冊一個 PDF，可 -j 並行）：make parts；
# 單獨一冊：make 欽定儀象考成-03.pdf。都順手加上書籤（需 pikepdf）。
BOOK     := 欽定儀象考成
LUALATEX := lualatex -interaction=nonstopmode -halt-on-error
PYTHON   ?= python3
NUMS     := $(patsubst parts/part%.tex,%,$(sort $(wildcard parts/part*.tex)))
PARTPDFS := $(foreach n,$(NUMS),$(BOOK)-$(n).pdf)
DEPS     := $(BOOK).tex $(wildcard img/*.png) tools/pdf_bookmarks.py

.PHONY: all parts clean
.DELETE_ON_ERROR:
all: $(BOOK).pdf
parts: $(PARTPDFS)

$(BOOK).pdf: $(wildcard parts/part*.tex) $(DEPS)
	$(LUALATEX) $(BOOK).tex
	$(PYTHON) tools/pdf_bookmarks.py $@ $(BOOK)-bookmarks.txt

# 單冊走同一個主檔：命令列先定義 \ltcPart，主檔便只 \input 那一冊
$(BOOK)-%.pdf: parts/part%.tex $(DEPS)
	$(LUALATEX) -jobname=$(BOOK)-$* '\def\ltcPart{$*}\input{$(BOOK)}'
	$(PYTHON) tools/pdf_bookmarks.py $@ $(BOOK)-$*-bookmarks.txt

clean:
	rm -f $(BOOK)*.pdf $(BOOK)*.log $(BOOK)*.aux $(BOOK)*-bookmarks.txt $(BOOK)*-layout.json
