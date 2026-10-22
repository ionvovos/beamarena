from setuptools import setup, find_packages

setup(
    name="beam-swe",
    version="1.0.0",
    description="Autonomous Software Engineering Agent and 1M-Context Evaluator powered by Beam-1.0-501B-A23B",
    author="Ion Vovos",
    packages=find_packages(),
    py_modules=["cli", "app"],
    install_requires=[
        "huggingface_hub",
        "gradio>=6.0.0",
        "pytest",
    ],
    entry_points={
        "console_scripts": [
            "beam-swe=cli:main",
            "beam-arena=cli:main",
        ],
    },
    python_requires=">=3.10",
)
