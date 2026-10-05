from setuptools import setup, find_packages

setup(
    name="fpl_agent",
    version="1.0.0",
    author="FPL Agent",
    description="An AI-powered Fantasy Premier League team manager using LLM insights",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "numpy>=1.24.0",
        "scikit-learn>=1.3.0",
        "requests>=2.31.0",
        "google-genai>=1.28.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "torch>=2.2.0",
        "sentence-transformers>=2.2.0",
        "transformers>=4.29.0",
    ],
    entry_points={
        "console_scripts": ["fpl-agent=fpl_agent.main:main"],
    }
)