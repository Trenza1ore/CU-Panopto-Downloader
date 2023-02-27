# CU-Panopto-Downloader (Changed a bit)
Downloads Cardiff university lectures from panopto

**Forked from https://github.com/TThomasV/CU-Panopto-Downloader, go check the original version out, I just added some minor changes.**

*I added some ease-of-use improvements, one bug fix and an exe version for non CS students which only requires Firefox to be installed.*

- Need a Cardiff university account.
- Only works on windows right now (will probably remain that way).
- ~~Works on Python 3.4 to 3.6, **WILL NOT WORK WITH HIGHER (from my testing)**~~
- Current version's tested with Python 3.9.13 + Selenium 4.8.2
- Requires you have FireFox installed, you can easily change this to chrome.

**Building it for Windows machines yourself?**
- Create a new Python 3.6 virtual environment, you can use Anaconda if you hate troubles
- Activate your virtual environment -> conda activate MY_VIRTUAL_ENVIRONMENT //if you are using Anaconda
- Install cx_Freeze to your Python environment -> pip install cx_freeze
- Install other requirements in requirements.txt -> pip install -r requirements.txt
- Open your command line, move to the current folder -> cd C:\Users\YOURUSERNAME\Desktop\CU-Panopto-Downloader-master
- Run the building command -> python setup.py build
- Splendid, but you still need a FireFox Browser installed, remember it -> https://www.mozilla.org/en-GB/firefox/new/

**Use my pre-built windows version (run_downloader.exe) for your 64-bit machine:**
- Download the repo as a zip or git clone it or download release **v2.1**
- Unzip if needed, then open the **panopto_downloader_packed** folder
- Double click **run_downloader.exe**
- What, are you expecting more steps?

**How to run the source code:**
- Install requirements from requirements.txt -> pip install -r requirements.txt
- Run: python ./CU-Panopto-Downloader.py
- Videos can be found in the videos directory
