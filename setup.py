# setup.py
import setuptools
import os

# 从 README.md 读取长描述
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# 从 requirements.txt 读取依赖
with open("requirements.txt", "r", encoding="utf-8") as fh:
    install_requires = fh.read().splitlines()

# 自动查找 xiaoyao 包的版本号


def get_version():
    """从 src/xiaoyao/version.py 中获取版本号"""
    version_path = os.path.join(os.path.dirname(
        __file__), 'src', 'xiaoyao', 'version.py')
    with open(version_path, 'r') as f:
        for line in f:
            if line.startswith('__version__'):
                # 从 '__version__ = "1.0.1"' 中提取版本号
                return line.split('=')[1].strip().strip('"')
    raise RuntimeError("在 version.py 中找不到版本号")


setuptools.setup(
    name="xiaoyao",  # pip install xiaoyao-sdk 时使用的包名
    version=get_version(),  # 从 version.py 自动获取版本号
    author="深圳果力智能科技有限公司",  # 您的名字或公司名
    author_email="contact@guoli-intelligent.com",  # 您的联系邮箱
    description="枭尧灵巧手 (Xiaoyao Hand) 官方 Python SDK",  # 包的简短描述
    long_description=long_description,  # 从 README.md 读取的长描述
    long_description_content_type="text/markdown",  # 长描述的格式
    url="https://github.com/YourGitHubOrg/Xiaoyao-SDK",  # 您的项目主页，例如 GitHub 仓库地址

    # 告诉 setuptools 在哪里查找源代码
    package_dir={"": "src"},

    # 自动查找 src 目录下的所有包
    packages=setuptools.find_packages(where="src"),

    # 分类信息，帮助 pip 和 PyPI 对包进行分类
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",  # 假设您使用 MIT 许可证
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries",
        "Topic :: System :: Hardware :: Hardware Drivers",
    ],

    # 指定 Python 版本要求
    python_requires='>=3.8',

    # 指定项目依赖
    install_requires=install_requires,
)
