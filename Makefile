.PHONY: release clean

clean:
	rm -rf build/ dist/ asgiref.egg-info/

release: clean
	python3 -m build
	python3 -m twine upload dist/*
