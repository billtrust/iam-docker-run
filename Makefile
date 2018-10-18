publish-test:
	rm -r dist/*
	python setup.py sdist
	twine upload -r pypitest dist/*

publish:
	rm -r dist/*
	python setup.py sdist
	twine upload dist/*
