init:
	python setup.py --command-packages=stdeb.command bdist_deb
	rm -rf build dist .egg dvbbox.egg-info dvbbox*.tar.gz
	mv deb_dist/python-dvbbox_*.deb .
	mv python-dvbbox_*.deb deb_dist/python-dvbbox.deb
install:
	dpkg -i deb_dist/python-dvbbox.deb
