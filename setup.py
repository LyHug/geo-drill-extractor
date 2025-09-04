"""
KG钻孔实体提取系统安装配置
"""

from setuptools import setup, find_packages
from pathlib import Path

# 读取README文件
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8') if (this_directory / "README.md").exists() else ""

# 读取requirements.txt
requirements = []
requirements_file = this_directory / "requirements.txt"
if requirements_file.exists():
    with open(requirements_file, encoding='utf-8') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="kg-drill-extraction",
    version="0.1.0",
    author="KG Team",
    author_email="kg@example.com",
    description="地质钻孔实体提取与坐标推理系统",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kg-team/kg-drill-extraction",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "isort>=5.12.0",
        ],
        "docs": [
            "sphinx>=6.0.0",
            "sphinx-rtd-theme>=1.2.0",
            "sphinx-autodoc-typehints>=1.23.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "kg-extract=kg_drill_extraction.cli:main",
            "kg-experiment=kg_drill_extraction.experiment.runner:main",
        ],
    },
    include_package_data=True,
    package_data={
        "kg_drill_extraction": [
            "configs/*.yaml",
            "data/*.csv",
        ],
    },
    zip_safe=False,
)