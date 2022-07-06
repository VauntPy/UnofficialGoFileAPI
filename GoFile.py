from urllib import response
from requests_toolbelt import MultipartEncoder
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
import requests
import hashlib
import time
# import shutil

class GoFile:
    backoff_factor = 1
    defaultWebsiteToken = '12345'
    chunk_size = 8388608 # IN BYTES
    timeout = 15
    retries = 30 # retries = connect + read
    connect = 15
    read = 15

    def __init__(self) -> None:
        self.http = requests.Session()
        self.setRetry()
        
    def setData(self):
        values = self.parseData(True)
        self.urlCode = next(values).split('/')[-1]
        password = next(values)
        if password != '':
            self.password = hashlib.sha256(password.encode()).hexdigest()
        else:
            self.password = None
        self.localdlFolderName = next(values)

        print(f"UrlCode: {self.urlCode} , Password: {password}, Local Folder: {self.localdlFolderName}")

    # RETRIES IF FAILED CONNECTION        
    def setRetry(self):
        retry = Retry(
            total = self.retries,
            status_forcelist = [404, 429, 500, 502, 503, 504], #Agregar 404?????????????
            allowed_methods = ["HEAD", "GET", "OPTIONS", "PUT", "DELETE", "POST"],
            backoff_factor= self.backoff_factor,
            connect= self.connect,
            read= self.read
        )
        adapter = HTTPAdapter(max_retries= retry)
        self.http.mount('https://', adapter); self.http.mount('http://', adapter)   

    # ARGUMENTS
    def setArg(self):
        if self.password is None:
            self.payload = {
                'contentId': self.urlCode, 
                'token': self.token, 
                'websiteToken': self.defaultWebsiteToken
            }
        else:
            self.payload = {
                'contentId': self.urlCode, 
                'token': self.token, 
                'websiteToken': self.defaultWebsiteToken, 
                'password': self.password, 
                'cache': 'true'}

        self.cookies = {'accountToken': self.token}
        print(self.payload)
    # GET FILE LINKS TO BE DOWNLOADED
    def getLinks(self):
        try:
            response = self.http.get(
                url = "https://api.gofile.io/getContent", 
                params= self.payload, 
                cookies= self.cookies, 
                verify= True
                ).json()['data']['contents']
            if response == {}:
                return None
            else:
                p = Path(f"{self.localdlFolderName}")
                if p.exists() and p.is_dir():
                    return response
                else:
                    print(f"Creating Folder {self.localdlFolderName} ...")
                    p.mkdir()
                    return response
        except requests.exceptions.RequestException as err:
            print(err)

    def downloadFiles(self):
        self.newTempAccount()
        self.setData()
        self.setArg()

        _bool = True
        links = self.getLinks()
        if links is None:
            print('No content available to download')
        else:
            for key in links:
                while _bool:
                    overload = self.getLinks()[key]
                    if 'overloaded' not in overload:
                        _bool = False
                    else:
                        print('Waiting for server to be available ...')
                _bool = True
                url = links[key]['link']
                filename = links[key]['name']
                print(f"Downloading {filename} ...")
                try:
                    response = self.http.get(
                        url = url,
                        params= self.payload,
                        cookies= self.cookies,
                        stream= True,
                        verify= True,
                        allow_redirects= True,
                        timeout= self.timeout
                    )
                    if response.status_code == 200:
                        with open(f"{self.localdlFolderName}/{filename}", "wb") as f:
                            # shutil.copyfileobj(_r.raw, _f)
                            for chunk in response.iter_content(chunk_size= self.chunk_size):
                                # if chunk:
                                f.write(chunk)
                    else:
                        print(f"Couldn't download file {filename}, error {response.status_code}")

                except requests.exceptions.RequestException as err:
                    print(err)

    # NEW ACCOUNT
    def newTempAccount(self, public= 'true', password = ''):
        try:
            response = requests.get(url = "https://api.gofile.io/createAccount").json()
            self.token = response['data']['token']
            response = requests.get(url = "https://api.gofile.io/getAccountDetails", params = {'token': self.token}).json()
            self.rootFolderId = response['data']['rootFolder']
            response = requests.put(
                url = "https://api.gofile.io/setFolderOption", 
                data = {
                    'token': self.token,
                    'folderId': self.rootFolderId,
                    'option': 'public',
                    'value': public
                })       
            time.sleep(15)
        except requests.exceptions.RequestException as err:
            print(err)


    #QUICK UPLOAD WITH NO ACCOUNT
    def quickUpload(self):
        self.newTempAccount()
        localupFolderName = next(self.parseData(False))
        p = Path(f"{localupFolderName}")
        if any(p.iterdir()):
            def innerIter(p):
                for child in p.iterdir():
                    if child.is_file():
                        server = self.optimalServer()
                        print(f"Uploading {child.name} ...")
                        try:
                            m = MultipartEncoder(
                                fields={
                                    'token': self.token, 
                                    'folderId': self.rootFolderId, 
                                    'file': (f'{child.name}', 
                                    open(child.resolve(), 'rb'))
                                }
                            )
                            response = self.http.post(
                                url = f"https://{server}.gofile.io/uploadFile",
                                data= m,
                                headers= {'Content-Type': m.content_type}                            
                            )
                            print(f"File {child.name} uploaded at {response.json()['data']['downloadPage']}")
                        except requests.exceptions.RequestException as err:
                            print(err)
                    else:
                        innerIter(child)
            innerIter(p)
        else:
            print("Folder Empty")

    # BEST SERVER TO UPLOAD FILES
    @staticmethod
    def optimalServer():
        try:
            response = requests.get(
                url = "https://api.gofile.io/getServer").json()
            return response['data']['server']
        except requests.exceptions.RequestException as err:
            print(err)
            
    # GET DATA FROM TEXT FILE        
    @staticmethod
    def parseData(nMode): # True = DOWNLOAD MODE, False = UPLOAD MODE
        if nMode is True:
            with open('GoFileDLData.txt', 'r') as f:
                for line in f.readlines():
                    yield line.strip('\n').split('=')[-1]
        else:
            with open('GoFileUPData.txt', 'r') as f:
                for line in f.readlines():
                    yield line.strip('\n').split('=')[-1]
        


gf = GoFile()
# gf.quickUpload()
gf.downloadFiles()

