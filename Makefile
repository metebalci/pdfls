
test: pdfls.py
	pylint pdfls.py
	pdfls -p knuth65.pdf

upload: pdfls.py setup.py
	rm -rf dist
	python setup.py sdist
	twine upload dist/*
