import sys
from codecs import getwriter
sys.stdout = getwriter("utf-8")(sys.stdout.detach())

import logging
import os
import os.path
import platform
import time
from concurrent import futures
from threading import Semaphore
from zipfile import ZipFile

import requests
import requests.cookies
from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, \
    SessionNotCreatedException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.service import Service as firefox_service
from webdriver_manager.firefox import GeckoDriverManager
from tqdm import tqdm


class PanoptoDownloader:

    def __init__(self, username, password, update=False):
        self.username = username
        self.password = password
        self.update = update
        self.cwd = os.path.realpath(os.path.join(os.getcwd(),
                                                 os.path.dirname(__file__)))

        self.logger = logging.getLogger('CUPanoptoDownloader')
        self.driver = None
        self.session = requests.Session()
        self.session_lock = Semaphore(6)

        if not update:
            self.logger.info("Ignoring updates")

        self.logger.info('Checking for dependencies')
        self.check_dependencies()

    @staticmethod
    def get_version():
        return "{}_{}".format(platform.system(), platform.machine()[-2]).lower()

    def quit(self):
        """Quits the driver and close every associated window."""
        try:
            self.driver.close()
        except InvalidSessionIdException:
            pass
        self.session.close()

    def check_dependencies(self):

        # Set the paths
        bin_gecko = os.path.join(self.cwd, 'geckodriver')

        # Update names for windows
        if 'windows' in self.get_version():
            bin_gecko += '.exe'

        # Firefox is missing
        if not os.path.isfile(bin_gecko):
            self.get_firefox()
        else:
            if self.update:
                self.get_firefox()

    def get_firefox(self):
        self.logger.info("Getting url for latest version of geckodriver")

        api_url = 'https://api.github.com/repos/mozilla/geckodriver/releases' \
                  '/latest'
        resp = requests.get(api_url).json()
        for asset in resp['assets']:
            if self.get_version() in asset['name']:
                break

        file_f = asset['browser_download_url']

        '''# Making sure the directory actually exists
        dir_name = os.path.join(self.cwd, "include")
        if not os.path.isdir(dir_name):
            os.makedirs(dir_name)'''

        dir_name = self.cwd
        local_filename = file_f.split('/')[-1]
        write_loc = os.path.join(dir_name, local_filename)

        self.logger.info("Starting download")
        with requests.get(file_f, stream=True) as r:
            r.raise_for_status()
            with open(write_loc, 'wb') as f:
                for chunk in r.iter_content(chunk_size=16 * 1024):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
        self.logger.info("Download complete")

        self.logger.info("Extracting Zip")
        with ZipFile(write_loc, 'r') as zipObject:
            zipObject.extractall()
        self.logger.info('Cleaning up leftover zip')
        os.remove(write_loc)

        self.logger.info("Finished getting latest version of geckodriver")

    def launch_driver(self):
        self.logger.info("Launching geckodriver")

        cd_path = os.path.join(self.cwd, 'geckodriver')
        if 'windows' in self.get_version():
            cd_path += '.exe'

        options = webdriver.FirefoxOptions()
        options.add_argument('--mute-audio')  # Mute audio

        self.driver = webdriver.Firefox(service=firefox_service(cd_path),
                                        options=options)

        # Minimize the driver
        self.driver.minimize_window()

    def wait_for_page_load(self):
        while True:
            page_state = self.driver.execute_script('return '
                                                    'document.readyState;')
            if page_state != 'complete':
                time.sleep(0.5)
            else:
                return

    def clear_credentials(self):
        self.logger.info("Clearing credentials")
        self.username = None
        self.password = None

    def login(self):
        self.logger.info("Attempting to login")
        home_url = 'https://cardiff.cloud.panopto.eu/Panopto/Pages/Home.aspx'
        self.driver.get(home_url)

        # waiting for the redirect
        login_base = 'https://login.cardiff.ac.uk/nidp/idff/sso'
        while login_base not in self.driver.current_url:
            time.sleep(0.5)

        # Wait for the elements to load
        username = WebDriverWait(self.driver, 3).until(
            EC.presence_of_element_located((By.ID, 'username')))
        username.send_keys(self.username)
        password = self.driver.find_element("xpath", '//*[@id="Ecom_Password"]')
        password.send_keys(self.password)
        login_btn = self.driver.find_element("xpath", '//*[@name="Log in"]')
        login_btn.click()

        # Wait for the redirect
        while home_url not in self.driver.current_url:
            time.sleep(0.1)

        self.wait_for_page_load()

        self.logger.info("Login successful")

    def convert_selenium_cookies_to_requests(self):

        self.logger.info("Transferring cookies from selenium to requests")

        self.driver.refresh()
        # convert the cookies to requests form
        cookies = self.driver.get_cookies()
        for cookie in cookies:
            required_args = {
                'name':  cookie['name'],
                'value': cookie['value']
            }
            optional_args = {
                'domain': cookie['domain'],
                'path':   cookie['path'],
                'secure': cookie['secure']
            }

            new_cookie = requests.cookies.create_cookie(**required_args,
                                                        **optional_args)
            self.session.cookies.set_cookie(new_cookie)

    def get_video_list(self, folder_id):

        self.logger.debug("Obtaining video list for the module")

        url = "https://cardiff.cloud.panopto.eu/Panopto/Services/Data.svc/" \
              "GetSessions"

        payload = {"queryParameters":
                       {"query":            None,
                        "sortColumn":       1,
                        "sortAscending":    False,
                        "maxResults":       2500,
                        "page":             0,
                        "startDate":        None,
                        "endDate":          None,
                        "folderID":         folder_id,
                        "bookmarked":       False,
                        "getFolderData":    True,
                        "isSharedWithMe":   False,
                        "includePlaylists": True
                        }
                   }

        resp = self.session.post(url, json=payload)

        resp_json = resp.json()

        results = {}

        for item in resp_json['d']['Results']:
            results[item['SessionName']] = item['IosVideoUrl']

        # fix the m3u8 playlist issue
        for i in results:
            this_link = results[i]
            if this_link[-4:].lower() == "m3u8":
                results[i] = this_link[:-15] + "mp4"

        return results

    def get_folders(self):
        # Switch over to using requests
        self.convert_selenium_cookies_to_requests()

        self.driver.close()

        self.logger.info("Attempting to obtain modules")

        url = "https://cardiff.cloud.panopto.eu/Panopto/Api/Folders?" \
              "parentId=null&folderSet=1&includeMyFolder=false&" \
              "includePersonalFolders=true&page=0&" \
              "sort=Depth&names[0]=SessionCount"
        resp = self.session.get(url)

        resp_json = resp.json()

        folders = {}

        for item in resp_json:
            # Filter out the panopto generic video:
            filters = ['Featured Videos - Panopto Homepage (Not open ''links)',
                       'Getting Started with Panopto']
            if item['Name'] in filters:
                continue

            self.logger.info("Found module: %s", item['Name'])

            if item['SessionCount'] > 0:
                try:
                    result = {'key':    item['Id'],
                            'videos': self.get_video_list(item['Id'])}
                    folders[item['Name']] = result
                except:
                    self.logger.debug(f"Error: \n{item}")
            else:
                self.logger.debug("Module contains no videos, skipping...")

        return folders

    def download_video(self, link, f_name):
        self.session_lock.acquire()

        with self.session.get(link, stream=True) as r:
            desc_name = os.path.sep.join(f_name.split(os.path.sep)[-2:])
            with tqdm.wrapattr(open(f_name, "wb"), "write",
                               miniters=1, desc=desc_name,
                               total=int(r.headers.get('content-length'))) \
                    as f_out:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:  # filter out keep-alive new chunks
                        f_out.write(chunk)

        self.session_lock.release()

    def collect(self):
        self.launch_driver()
        self.login()
        self.clear_credentials()
        folders = self.get_folders()

        # Make the videos folder if it doesnt already exist
        vid_dir = os.path.join(self.cwd, "videos")
        if not os.path.isdir(vid_dir):
            os.makedirs(vid_dir)

        self.logger.info("Commencing downloads")

        ## add a simple menu thingy
        user_choice = ""
        download_all = True

        # download all?
        while user_choice == "":
            user_choice = input("Download all [y/n]: ").lower()
            if user_choice == "y":
                break
            elif user_choice == "n":
                download_all = False
                break
            else:
                user_choice = ""
        
        # simple menu
        if not download_all:
            unwanted_folders = []
            single_downloads = []

            for folder, videos in folders.items():
                print("\nFolder <%s>:\n- l: list videos\n- y: download\n- n: don\'t download\n- s: download single video" %(folder))
                user_choice = ""
                while user_choice == "":
                    user_choice = input("(y/n/l/s) >> ").lower()
                    if user_choice == "y":
                        break
                    elif user_choice == "n" or len(user_choice) == 0:
                        unwanted_folders.append(folder)
                        break
                    elif user_choice == "l":
                        for video_title in videos["videos"]:
                            print("  - %s" %(video_title))
                        user_choice = ""
                    elif user_choice == "s":
                        for video_title in videos["videos"]:
                            confirm = input("  - Download %s? (y/skip): " %(video_title))
                            if confirm.lower() == "y":
                                single_downloads.append((video_title, videos["videos"][video_title], folder))
                                pass
                        unwanted_folders.append(folder)
                        break
                    else:
                        user_choice = ""
            
            # remove unwanted folders
            for folder in unwanted_folders:
                folders.pop(folder)

        with futures.ThreadPoolExecutor() as executor:
            future_threads = []
            
            keep_chars = (' ', '.', '_', '-')
                
            for folder, videos in folders.items():

                # Cardiff specific dumb file naming
                fo_name = " ".join(folder.split(" ")[1:])
                fo_name = "".join(c for c in fo_name if c.isalnum() or c in
                                  keep_chars).rstrip()

                folder_dir = os.path.join(self.cwd, "videos", fo_name)

                if not os.path.isdir(folder_dir):
                    os.makedirs(folder_dir)

                for name, link in videos['videos'].items():
                    # Fix the name
                    f_name = name.replace("/", "-")
                    f_name = "".join(c for c in f_name if c.isalnum() or c in
                                     keep_chars).rstrip()

                    f_name = os.path.join(folder_dir, f_name)
                    f_name = "{}.mp4".format(f_name)

                    future = executor.submit(self.download_video,
                                             link, f_name)
                    future_threads.append(future)
                    
            if len(single_downloads) > 0:
                individual_folder_dir = os.path.join(self.cwd, "videos", "individual")
                if not os.path.isdir(individual_folder_dir):
                    os.makedirs(individual_folder_dir)
                for name, link, folder in single_downloads:
                    # Fix the name
                    folder = folder.replace("/", "-")
                    folder = "".join(c for c in folder if c.isalnum() or c in
                                     keep_chars).rstrip()
                    f_name = name.replace("/", "-")
                    f_name = folder + "-" + "".join(c for c in f_name if c.isalnum() or c in
                                     keep_chars).rstrip()

                    f_name = os.path.join(individual_folder_dir, f_name)
                    f_name = "{}.mp4".format(f_name)

                    future = executor.submit(self.download_video,
                                             link, f_name)
                    future_threads.append(future)

            for future in futures.as_completed(future_threads):
                try:
                    future.result()

                except Exception:
                    self.logger.exception("Failed downloading video")

        self.logger.info("Collection complete")
        self.logger.info("%d videos downloaded", len(future_threads))


def main(creds = "creds.txt"):
    # Set up the logger
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("Script")
    logger.info("Starting script")
    
    with open(creds, encoding="utf-8") as f_reader:
        username = f_reader.readline().strip('\n')
        password = f_reader.readline().strip('\n')

    client = None

    try:
        client = PanoptoDownloader(username, password, update=False)
        client.collect()
        logger.info("Finished downloading all videos")
    except SessionNotCreatedException:
        logging.exception("Go install firefox")
    except Exception:
        logger.exception("Unknown failure")
    finally:
        print("\n\nDOWNLOADS COMPLETE\nDo you want to remove your login information stored?")
        user_choice = ""
        while user_choice == "":
            user_choice = input("(y/n) >> ").lower()
            if user_choice == "y":
                try:
                    os.remove("creds.txt")
                except:
                    pass
                break
            elif user_choice == "n" or len(user_choice) < 1:
                break
            else:
                user_choice = ""
        client.quit()


if __name__ == '__main__':
    try:
        file = open("creds.txt", encoding="utf-8")
        file.close()
    except:
        not_confirmed = True
        while not_confirmed:
            user_name = input("username: ")
            user_pass = input("password: ")
            if input("Confirm [enter y]: ").lower() == 'y':
                not_confirmed = False
        file = open("creds.txt", 'w', encoding="utf-8")
        file.write(user_name + "\n" + user_pass)
        file.close()
    main()
