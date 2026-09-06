MAIN := proposal

.PHONY: all clean view

all:
	latexmk -pdf -interaction=nonstopmode -halt-on-error $(MAIN).tex

clean:
	latexmk -C $(MAIN).tex
	rm -f $(MAIN).bbl $(MAIN).run.xml $(MAIN).synctex.gz

view: all
	xdg-open $(MAIN).pdf >/dev/null 2>&1 &
