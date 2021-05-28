from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need
# fine tuning.
build_options = {'packages': [], 'excludes': []}

base = 'Console'

executables = [
    Executable('CU-Panopto-Downloader.py', base=base, target_name = 'run_downloader')
]

setup(name='panopto_downloader',
      version = '2.1',
      description = "Code from https://github.com/TThomasV/CU-Panopto-Downloader, I just improved the ease of use aspect (fixed a bug with downloading playlists instead of videos) and packed it.",
      options = {'build_exe': build_options},
      executables = executables)
