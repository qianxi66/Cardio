from setuptools import find_packages, setup

setup(
    name="Recover",
    version="0.1.0",
    packages=find_packages(include=["backend", "backend.*"]),
    package_dir={"recover": "backend"},
)
