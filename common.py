
import logging
from requests import Response
from tqdm import tqdm

class Download(object):
    """Download file or video"""
    
    currentsize = 0

    def __init__(self):
        pass

    @classmethod
    def files(cls,filepath:str,response,encode = None):
        """Download file"""
        if encode is None:
            encode = "UTF-8"
        with open(filepath,"w",encoding=encode) as file:
            if isinstance(response,str):
                file.write(response)
            elif isinstance(response,Response):
                file.write(response.text)
            else:
                print ("Download Files must be 'str' or requests.Response's instance!")

    @classmethod
    def streamvideos(cls,videopath:str,response:Response):
        """Download video"""
        chunk_size = 10240
        with open(videopath,"wb") as file:
            with tqdm(total = int(response.headers["Content-Length"])) as pbar:
                for data in tqdm(response.iter_content(chunk_size = chunk_size),total = 1024):
                    file.write(data)    
                    pbar.update(chunk_size)
            pbar.close()    

class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)  

class RunCmdException(Exception):
    def __init__(self,error):
        super().__init__(error)
        self.error = error

