Environment Setup
=================

Check Python Version
--------------------
GHand SDK supports Python 3.10 to 3.13.

.. code-block:: bash

   # Check Python version
   python --version

   # If the version does not match, install the correct Python version

Install Npcap Library
---------------------
Download and install the Npcap installer from the official website: https://npcap.com/

Check C/C++ Compilation Tools
-----------------------------
Before installing dependencies, ensure your system or environment includes C/C++ compilation tools.

On Windows, you can install Microsoft C++ Build Tools and select "Desktop development with C++" to install the C/C++ compilation tools.

Microsoft C++ Build Tools official website: https://visualstudio.microsoft.com/visual-cpp-build-tools/

Install Dependencies
--------------------
Use pip to install the required dependencies:

.. code-block:: bash

   pip install -r requirements.txt

Configure Development Environment
---------------------------------
VS Code is recommended as the development environment with the Python extension installed.
